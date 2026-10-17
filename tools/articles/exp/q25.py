import sys, os, sqlite3; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ql import *
tee('q25'); reset()
n = Node('q25'); n.start()
c = n.conn(); ch = c.channel()
ch.queue_declare('iq', durable=True)
def drain_q(q):
    r = []
    while True:
        mt, p, b = ch.basic_get(q, auto_ack=True)
        if mt is None: return r
        r.append((b.decode(), mt.redelivered, p.message_id))

print('== 一:重复的来源 1:消费者处理完、确认之前崩溃 → 消息被重新投递,第二个消费者又处理一遍(至少一次投递的代价)')
ch.queue_purge('iq'); ch.basic_publish('', 'iq', b'order-1001', pika.BasicProperties(message_id='msg-1', delivery_mode=2))
processed = []
c1 = n.conn(); ch1 = c1.channel()
mt, p, b = ch1.basic_get('iq', auto_ack=False)
processed.append(('消费者 A', b.decode(), mt.redelivered))       # 业务处理完了
c1.close()                                                       # ……但在 ack 之前崩溃
time.sleep(0.3)
c2 = n.conn(); ch2 = c2.channel()
mt, p, b = ch2.basic_get('iq', auto_ack=False)
processed.append(('消费者 B', b.decode(), mt.redelivered)); ch2.basic_ack(mt.delivery_tag); c2.close()
for who, body, red in processed: print(f'  {who} 处理了 {body},redelivered={red}')
print(f'  同一条订单被业务处理了 {len(processed)} 次')

print('== 二:重复的来源 2:发布端没等到 confirm 就重试。经过代理,把 broker → 客户端方向延迟 300 ms,发完消息 100 ms 后切断连接(消息已被 broker 收下,但 Ack 还在路上),重连后发布端以为失败,重发')
px = Proxy(n.amqp); px.dd = {'S→C': 0.3}
ch.queue_purge('iq')
pc = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', px.port)); pch = pc.channel(); pch.confirm_delivery()
res = {}
def pub():
    try: pch.basic_publish('', 'iq', b'order-1002', pika.BasicProperties(message_id='msg-2', delivery_mode=2)); res['r'] = '收到 Ack'
    except Exception as e: res['r'] = type(e).__name__
th = threading.Thread(target=pub, daemon=True); th.start()
time.sleep(0.1); px.cut(); th.join(5)
print(f'  第一次发布(msg-2)的结果: {res.get("r")}(发布端据此认为“没发成功”)')
time.sleep(0.3)
print(f'  这时队列里实际已经有: {n.qinfo("iq")[0]} 条')
pc2 = n.conn(); pch2 = pc2.channel(); pch2.confirm_delivery()
pch2.basic_publish('', 'iq', b'order-1002', pika.BasicProperties(message_id='msg-2', delivery_mode=2))
print(f'  发布端重连后重发同一条(同样的 message_id=msg-2)并收到 Ack;队列里现在有: {n.qinfo("iq")[0]} 条')
print(f'  取出来: {drain_q("iq")}  ——两份都是 redelivered=False:redelivered 标志抓不住发布端造成的重复')
px.close(); pc2.close()

print('== 三:broker 本身不去重:同一个 message_id 发 3 次,收到 3 条')
ch.queue_purge('iq')
for i in range(3): ch.basic_publish('', 'iq', b'same', pika.BasicProperties(message_id='msg-3'))
time.sleep(0.3)
print(f'  收到 {len(drain_q("iq"))} 条(message_id 只是一个普通属性,RabbitMQ 不会用它去重)')

print('== 四:消费端幂等:在同一个事务里“记下 message_id + 做业务”,重复的消息被唯一约束挡住。模拟:1000 条消息里 10% 被重复投递(共 1100 次投递),业务是“账户余额 +1”')
def run_consumer(idempotent):
    db = sqlite3.connect(':memory:'); db.execute('create table acct(id int primary key, bal int)'); db.execute('insert into acct values (1, 0)')
    db.execute('create table seen(mid text primary key)')
    q = 'iq4'; ch.queue_declare(q, durable=True); ch.queue_purge(q)
    msgs = [f'm{i}' for i in range(1000)]
    dups = msgs[:100]
    for m in msgs + dups: ch.basic_publish('', q, b'+1', pika.BasicProperties(message_id=m, delivery_mode=2))
    ch.queue_declare(q, passive=True)
    cc = n.conn(); cch = cc.channel(); cch.basic_qos(prefetch_count=200); cnt = [0]; applied = [0]
    def cb(chn, m, p, b):
        cnt[0] += 1
        if idempotent:
            try:
                with db: db.execute('insert into seen values (?)', (p.message_id,)); db.execute('update acct set bal = bal + 1 where id = 1'); applied[0] += 1
            except sqlite3.IntegrityError: pass
        else:
            with db: db.execute('update acct set bal = bal + 1 where id = 1'); applied[0] += 1
        chn.basic_ack(m.delivery_tag)
    cch.basic_consume(q, cb)
    t0 = time.perf_counter()
    while cnt[0] < 1100: cc.process_data_events(0.05)
    el = ms(t0); cc.close()
    return db.execute('select bal from acct').fetchone()[0], applied[0], el
bal_n, ap_n, el_n = run_consumer(False)
bal_i, ap_i, el_i = run_consumer(True)
print(f'  朴素消费者:收到 1100 次投递,业务执行 {ap_n} 次,余额 = {bal_n}(应为 1000)')
print(f'  幂等消费者(message_id 唯一约束):收到 1100 次投递,业务执行 {ap_i} 次,余额 = {bal_i}')
print(f'  耗时: 朴素 {el_n:.0f} ms,幂等 {el_i:.0f} ms(幂等版多一次 insert,sqlite 内存库,两者差别在噪声内)')

print('== 五:去重表不能无限长:message_id 要保留多久?按“重复可能出现的最长窗口”清理。这里只看一个事实——去重表里记 100 万个 message_id 要占多大')
db = sqlite3.connect(':memory:'); db.execute('create table seen(mid text primary key) without rowid')
t0 = time.perf_counter()
with db:
    db.executemany('insert into seen values (?)', ((f'8f3b2c1a-{i:012d}',) for i in range(1000000)))
el = ms(t0)
pc_ = db.execute('pragma page_count').fetchone()[0]; ps = db.execute('pragma page_size').fetchone()[0]
print(f'  100 万个 36 字符的 message_id:插入 {el:.0f} ms,库大小约 {pc_ * ps / 1048576:.1f} MiB(sqlite,without rowid)')
c.close(); n.stop()
