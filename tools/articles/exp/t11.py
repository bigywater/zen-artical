import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import ql
from outbox import *
tee('t11'); reset(); ql.reset()
M = MySQL('t11').start(); create_schema(M)
KN = ql.KafkaNode('t11k', port=9580).start()
print(f'MySQL {M.q("select version()")[0][0]}(orders、outbox 两张表)+ Kafka {KN.port}(单节点 KRaft,topic 单分区);事件按订单号做 key;“发布失败 / 提交失败”有的是 kill -9 一个子进程,有的是在代码里按概率抛错(会写明)')
def topic(name): KN.topics('--create', '--topic', name, '--partitions', '1', '--replication-factor', '1'); return name
CHILD = r'''
import sys, time, json, pymysql
from confluent_kafka import Producer
mode, crash, sock, kport, oid = sys.argv[1:6]
def db(): return pymysql.connect(unix_socket=sock, user='root', password='', database='shop', autocommit=False)
def publish(topic):
    p = Producer({'bootstrap.servers': f'127.0.0.1:{kport}', 'enable.idempotence': True, 'log_level': 3}); p.produce(topic, key=oid, value=json.dumps({'order_id': oid})); p.flush(10)
def wait(tag): print('WAIT', tag, flush=True); time.sleep(60)
if mode == 'A':                                   # 先写库,再发消息
    c = db(); c.cursor().execute('insert into orders values (%s, 100)', (oid,)); c.commit(); print('DB-COMMITTED', flush=True)
    if crash == 'mid': wait('mid')
    publish('ev-A'); print('PUBLISHED', flush=True)
elif mode == 'B':                                 # 先发消息,再写库
    publish('ev-B'); print('PUBLISHED', flush=True)
    if crash == 'mid': wait('mid')
    c = db(); c.cursor().execute('insert into orders values (%s, 100)', (oid,)); c.commit(); print('DB-COMMITTED', flush=True)
else:                                             # outbox:订单和事件在同一个本地事务里,应用自己不发消息
    c = db(); cur = c.cursor(); cur.execute('insert into orders values (%s, 100)', (oid,)); cur.execute("insert into outbox(aggregate_id, type, payload) values (%s, 'OrderCreated', %s)", (oid, json.dumps({'order_id': oid}))); c.commit(); print('DB-COMMITTED', flush=True)
    if crash == 'mid': wait('mid')
print('DONE', flush=True)
'''
(TT / 't11_child.py').write_text(CHILD)
def spawn(mode, crash, oid):
    p = subprocess.Popen([sys.executable, str(TT / 't11_child.py'), mode, crash, M.sock, str(KN.port), oid], stdout=subprocess.PIPE, text=True)
    while True:
        l = p.stdout.readline()
        if l.startswith('WAIT') or l.startswith('DONE') or l.startswith('PUBLISHED') and mode == 'A' or l == '': 
            if l.startswith('WAIT'): os.kill(p.pid, signal.SIGKILL)
            if not l.startswith('PUBLISHED') or mode == 'A': break
    p.wait()
for t in ('ev-A', 'ev-B', 'ev-O'): topic(t)

print('== 一:双写(先写库、再发消息)和反过来(先发消息、再写库),在两次操作之间被 kill -9:各留下什么')
M.q('delete from orders', db='shop'); M.q('delete from outbox', db='shop')
spawn('A', 'mid', 'A-1'); spawn('B', 'mid', 'B-1')
for name, tp, oid in (('A(先写库,再发消息),在两者之间被杀', 'ev-A', 'A-1'), ('B(先发消息,再写库),在两者之间被杀', 'ev-B', 'B-1')):
    orders = [r[0] for r in M.q('select id from orders where id = %s', (oid,), db='shop')]; evs = [k for k, v, t in read_all(KN.port, tp, idle=1.0) if k == oid]
    print(f'  {name}:订单库里 {"有" if orders else "没有"}订单 {oid},Kafka 里 {"有" if evs else "没有"}事件 → ' + ('订单已存在、事件丢了(下游永远不知道)' if orders and not evs else '事件发出去了、订单不存在(下游看到了一个不存在的订单)' if evs and not orders else '一致'))

print('== 二:Outbox:订单和事件在同一个本地事务里写,应用进程在提交之后被 kill -9,事件还在 outbox 表里,relay 起来之后补发')
spawn('O', 'mid', 'O-1')
print('  kill -9 之后:订单库', [r[0] for r in M.q('select id from orders where id = %s', ('O-1',), db='shop')], ',outbox 表', [tuple(r) for r in M.q('select id, aggregate_id, type, sent from outbox', db='shop')], ',Kafka ev-O', [k for k, v, t in read_all(KN.port, 'ev-O', idle=1.0)])
pr = mk_producer(KN.port); n, crashed = relay_once(M, pr, 'ev-O')
print(f'  relay 跑一轮:发出 {n} 条;Kafka ev-O', [k for k, v, t in read_all(KN.port, 'ev-O', idle=1.0)], ',outbox sent 标记', [r[0] for r in M.q('select sent from outbox', db='shop')])
print('  事务如果回滚,事件跟着回滚:')
c = M.conn('shop', autocommit=False); cur = c.cursor(); cur.execute("insert into orders values ('O-2', 100)"); cur.execute("insert into outbox(aggregate_id, type, payload) values ('O-2', 'OrderCreated', '{}')"); c.rollback(); c.close()
print('   回滚之后:订单库有 O-2 吗?', bool(M.q("select 1 from orders where id = 'O-2'", db='shop')), ',outbox 有 O-2 吗?', bool(M.q("select 1 from outbox where aggregate_id = 'O-2'", db='shop')))

print('== 三:放大到 1000 单,每一步有一定的失败概率,数一数丢了多少事件、多了多少“幽灵”事件、重复了多少')
N = 1000; P = 0.03
def run(variant, seed):
    M.q('delete from orders', db='shop'); M.q('delete from outbox', db='shop'); tp = topic(f'ev-{variant}-{seed}'); rng = random.Random(seed); pr = mk_producer(KN.port); c = M.conn('shop', autocommit=False); cur = c.cursor(); committed = []
    for i in range(N):
        oid = f'{variant}{i}'
        if variant == 'A':                                  # 先写库,再发:发布有 3% 概率失败(超时之后放弃)
            cur.execute('insert into orders values (%s, 100)', (oid,)); c.commit(); committed.append(oid)
            if rng.random() >= P: pr.produce(tp, key=oid, value='x'); pr.flush(10)
        elif variant == 'B':                                # 先发,再写库:提交有 3% 概率失败(比如死锁或约束冲突)
            pr.produce(tp, key=oid, value='x'); pr.flush(10)
            cur.execute('insert into orders values (%s, 100)', (oid,))
            if rng.random() < P: c.rollback()
            else: c.commit(); committed.append(oid)
        else:                                               # outbox:订单 + 事件在一个事务里,提交有 3% 概率失败
            cur.execute('insert into orders values (%s, 100)', (oid,)); cur.execute("insert into outbox(aggregate_id, type, payload) values (%s, 'OrderCreated', '{}')", (oid,))
            if rng.random() < P: c.rollback()
            else: c.commit(); committed.append(oid)
    c.close()
    if variant == 'O':                                      # relay:每 100 条一批;2% 的行在“已发出、未标记”处崩溃一次(下一轮重发)
        crashes = set(rng.sample(range(1, N), 20)); total = 0
        while True:
            n, crashed = relay_once(M, pr, tp, crash_after_publish=lambda id_: id_ in crashes and not crashes.discard(id_))
            total += n
            if not crashed and n == 0: break
    evs = [k for k, v, t in read_all(KN.port, tp, idle=1.0)]
    ev_set = set(evs); ord_set = set(committed)
    return len(committed), len(ev_set), len(ord_set - ev_set), len(ev_set - ord_set), len(evs) - len(ev_set)
rows = []
for variant, name, seed in (('A', 'A 先写库再发消息(发布失败率 3%)', 1), ('B', 'B 先发消息再写库(提交失败率 3%)', 2), ('O', 'Outbox(提交失败率 3%,relay 崩溃 20 次)', 3)):
    c_, e_, lost, ghost, dup = run(variant, seed); rows.append((name, c_, e_, lost, ghost, dup))
table(rows, ['写法', '提交成功的订单', 'Kafka 里不同的事件数', '丢失的事件', '幽灵事件(没有订单)', '重复投递的条数'])
print('  A 丢事件,B 出现幽灵事件;Outbox 既不丢也没有幽灵,代价是至少一次投递——relay 在“已发出、未标记”处崩溃就会重发,消费者必须能处理重复(第 14、15 篇)')

print('== 四:Outbox 的额外成本:同一个本地事务多写一行事件(每轮 500 次、3 轮交替,共 1500 次,取中位数),以及 outbox 行的体积')
def timeit(extra):
    lat = []; c = M.conn('shop', autocommit=False); cur = c.cursor()
    for i in range(500):
        oid = f'T{time.time_ns()}'; t0 = time.perf_counter(); cur.execute('insert into orders values (%s, 100)', (oid,))
        if extra: cur.execute("insert into outbox(aggregate_id, type, payload) values (%s, 'OrderCreated', %s)", (oid, json.dumps({'order_id': oid, 'amount': 100})))
        c.commit(); lat.append(time.perf_counter() - t0)
    c.close(); return lat
acc = {False: [], True: []}
for rnd in range(3):
    for extra in (False, True): acc[extra] += timeit(extra)
M.q('delete from outbox', db='shop'); M.q('analyze table outbox', db='shop')
c = M.conn('shop', autocommit=False); cur = c.cursor()
for k in range(20): cur.executemany("insert into outbox(aggregate_id, type, payload) values (%s, 'OrderCreated', %s)", [(f'S{k}-{i}', json.dumps({'order_id': f'S{k}-{i}', 'amount': 100})) for i in range(1000)]); c.commit()
c.close(); M.q('analyze table outbox', db='shop')
sz = M.q("select data_length + index_length from information_schema.tables where table_schema = 'shop' and table_name = 'outbox'")[0][0]
us = lambda t: f'{t * 1e6:.0f} µs'
print(f'  只写订单:中位数 {us(statistics.median(acc[False]))};订单 + outbox 一行:中位数 {us(statistics.median(acc[True]))}(多 {(statistics.median(acc[True]) / statistics.median(acc[False]) - 1) * 100:.0f}%)')
print(f'  outbox 表 2 万行(payload 约 40 字节的 JSON)占 {int(sz) / 1024 / 1024:.1f} MiB,平均每行约 {int(sz) / 20000:.0f} 字节(含 (sent, id) 索引);发出去的行不清理会一直涨')
KN.stop(); reset(); ql.reset(); (TT / 't11_child.py').unlink()
shutil.rmtree(TT / 'my_t11', ignore_errors=True); shutil.rmtree(HERE / 'qtmp' / 't11k', ignore_errors=True)
