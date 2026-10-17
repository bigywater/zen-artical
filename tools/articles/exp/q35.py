import sys, os, sqlite3, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q35'); reset()
n = Node('q35'); n.start()
c = n.conn(); ch = c.channel(); ch.queue_declare('events', durable=True); ch.confirm_delivery()
D = qdir('q35db'); 
def newdb(name):
    db = sqlite3.connect(str(D / f'{name}.db'), isolation_level=None, check_same_thread=False); db.execute('pragma journal_mode=wal')
    db.execute('create table orders(id integer primary key, amount int)')
    db.execute('create table outbox(id integer primary key autoincrement, order_id int, payload text, sent int default 0)')
    return db
def qcount(q): 
    r = 0
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=True)
        if mt is None: return r
        r += 1
def drain_ids(q):
    ids = []
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=True)
        if mt is None: return ids
        ids.append(b.decode())

print('== 一:双写问题:先写数据库、再发消息,中间进程崩溃(这里用随机失败模拟,5% 的订单在提交之后、发消息之前“崩溃”)。1000 个订单,数据库里订单数和队列里的消息数对得上吗?')
random.seed(7)
db = newdb('naive'); ch.queue_purge('events'); lost = 0
for i in range(1000):
    db.execute('begin'); db.execute('insert into orders values (?, ?)', (i, 100)); db.execute('commit')
    if random.random() < 0.05: lost += 1; continue      # 崩溃:订单已提交,消息没发出去
    ch.basic_publish('', 'events', f'order-{i}'.encode(), pika.BasicProperties(delivery_mode=2))
orders = db.execute('select count(*) from orders').fetchone()[0]; msgs = qcount('events')
print(f'  数据库里订单 {orders} 条,队列里消息 {msgs} 条,丢了 {orders - msgs} 条消息(= 崩溃 {lost} 次)——下游永远不知道这些订单')
print('  反过来(先发消息、再写库,中间崩溃)会得到“有消息、没订单”的幽灵事件;两种顺序都不对')

print('== 二:Outbox 模式:订单和“待发送事件”在同一个数据库事务里写入;另一个 relay 进程轮询 outbox 表、发消息、确认后标记已发送。同样的 1000 个订单,relay 在 5% 的发送后“崩溃”(消息发出、标记之前)')
random.seed(7)
db = newdb('outbox'); ch.queue_purge('events')
for i in range(1000):
    db.execute('begin'); db.execute('insert into orders values (?, ?)', (i, 100)); db.execute('insert into outbox(order_id, payload) values (?, ?)', (i, f'order-{i}')); db.execute('commit')
crashes = 0
def relay_once(batch=100, crash_p=0.05):
    global crashes
    rows = db.execute('select id, order_id, payload from outbox where sent = 0 order by id limit ?', (batch,)).fetchall()
    for oid, order_id, payload in rows:
        ch.basic_publish('', 'events', payload.encode(), pika.BasicProperties(delivery_mode=2, message_id=f'outbox-{oid}'))      # 带 confirm,发布失败会抛异常
        if random.random() < crash_p: crashes += 1; return -1          # 崩溃:消息已确认发出,但还没标记 sent
        db.execute('update outbox set sent = 1 where id = ?', (oid,))
    return len(rows)
rounds = 0
while True:
    r = relay_once(); rounds += 1
    if r == 0: break
    # relay 重启后继续(未标记的行会被重新发送)
ids = drain_ids('events')
print(f'  relay 一共崩溃 {crashes} 次、跑了 {rounds} 轮;订单 1000 条;队列里消息 {len(ids)} 条')
uniq = len(set(ids))
print(f'  不同的 message_id {uniq} 个(= 订单数,没有丢);重复 {len(ids) - uniq} 条(崩溃那一刻已发出、还没标记的消息,重启后又发了一次)')
print('  所以 outbox 把“可能丢”换成了“可能重复”——至少一次;下游要用 message_id 去重(见第 25 篇)')

print('== 三:下游用 message_id 去重后的效果:同样的消息流,消费者记录已处理的 message_id,最终业务只执行 1000 次')
ch.queue_purge('events'); random.seed(7)
db = newdb('outbox2')
for i in range(1000):
    db.execute('begin'); db.execute('insert into orders values (?, ?)', (i, 100)); db.execute('insert into outbox(order_id, payload) values (?, ?)', (i, f'order-{i}')); db.execute('commit')
crashes = 0
while relay_once() != 0: pass
seen = set(); effects = 0
for mid in [x for x in drain_ids('events')]: 
    effects += 1 if mid not in seen else 0; seen.add(mid)
print(f'  收到的消息(按内容 order-N 记)里不同的有 {len(seen)} 个,业务效果执行 {effects} 次,订单 1000 个——一一对应')

print('== 四:relay 的延迟:从订单提交到消息出现在队列里。relay 每隔 poll 间隔轮询一次。100 个订单、每 20 ms 提交一个,poll 间隔 10 ms / 100 ms / 500 ms,看提交到发布完成的延迟 p50 / p99')
def relay_latency(poll, K=100):
    dbl = newdb(f'lat{poll}'); stop = threading.Event(); lat = []; commits = {}
    def relay():
        cc = n.conn(); cch = cc.channel(); cch.confirm_delivery()
        while not stop.is_set():
            rows = dbl.execute('select id, order_id from outbox where sent = 0 order by id limit 100').fetchall()
            for oid, order_id in rows:
                cch.basic_publish('', 'events', f'order-{order_id}'.encode(), pika.BasicProperties(delivery_mode=2))
                lat.append((time.perf_counter() - commits[order_id]) * 1000); dbl.execute('update outbox set sent = 1 where id = ?', (oid,))
            time.sleep(poll / 1000)
        cc.close()
    th = threading.Thread(target=relay, daemon=True); th.start()
    for i in range(K):
        dbl.execute('begin'); dbl.execute('insert into orders values (?, ?)', (i, 100)); dbl.execute('insert into outbox(order_id, payload) values (?, ?)', (i, f'order-{i}')); dbl.execute('commit'); commits[i] = time.perf_counter()
        time.sleep(0.02)
    time.sleep(poll / 1000 * 2 + 0.5); stop.set(); th.join(3); lat.sort(); return lat[len(lat) // 2], lat[int(len(lat) * 0.99)]
ch.queue_purge('events')
for poll in (10, 100, 500):
    a, b = relay_latency(poll); print(f'  poll {poll:>3} ms: p50 {a:.0f} ms,p99 {b:.0f} ms')
    ch.queue_purge('events')

print('== 五:relay 的吞吐:单线程 relay 逐条带 confirm 发布,区别只在“每批多少行提交一次 sent 标记”(数据库提交次数):10000 行 outbox,每批 1 / 100 / 1000')
def relay_tp(batch, K=10000):
    dbl = newdb(f'tp{batch}'); ch.queue_purge('events')
    dbl.execute('begin'); 
    for i in range(K): dbl.execute('insert into outbox(order_id, payload) values (?, ?)', (i, f'order-{i}'))
    dbl.execute('commit')
    t0 = time.perf_counter()
    while True:
        rows = dbl.execute('select id, payload from outbox where sent = 0 order by id limit ?', (batch,)).fetchall()
        if not rows: break
        for oid, payload in rows: ch.basic_publish('', 'events', payload.encode(), pika.BasicProperties(delivery_mode=2))
        dbl.execute('begin'); dbl.executemany('update outbox set sent = 1 where id = ?', [(r[0],) for r in rows]); dbl.execute('commit')
    return ms(t0)
for batch in (1, 100, 1000):
    e = relay_tp(batch)
    print(f'  每批 {batch:>4}: 搬 10000 行用了 {e:.0f} ms,{10000 / e * 1000:.0f} 行/秒')
ch.queue_purge('events'); c.close(); n.stop()
