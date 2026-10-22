import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import redis as redislib, queue
from rl import Node as RNode
tee('t19'); reset()
M = MySQL('t19').start(); M.q('create database shop')
M.q('create table stock(sku varchar(20) primary key, qty int, version int default 0)', db='shop'); M.q('create table orders(id bigint auto_increment primary key, sku varchar(20))', db='shop')
RP = free_port(); RN = RNode(RP, 't19_redis').start(); R = redislib.Redis(port=RP, decode_responses=True)
S0, N, TH = 1000, 3000, 32
print(f'MySQL {M.q("select version()")[0][0]} + Redis {R.info()["redis_version"]};库存 {S0} 件、{N} 个买家(每人买 1 件)、{TH} 个线程并发抢同一个商品;超卖 = 成功的单数 - {S0}')
def reset_stock(shards=1, total=None):
    total = total or S0
    M.q('delete from stock', db='shop'); M.q('delete from orders', db='shop')
    if shards == 1: M.q("insert into stock values ('sku', %s, 0)", (total,), db='shop')
    else: [M.q("insert into stock values (%s, %s, 0)", (f'sku#{i}', total // shards), db='shop') for i in range(shards)]
def db_qty(): return M.q('select coalesce(sum(qty), 0) from stock', db='shop')[0][0]

def buy_naive(cur, c):
    cur.execute("select qty from stock where sku = 'sku'"); q = cur.fetchone()[0]
    if q < 1: return False
    cur.execute("update stock set qty = %s where sku = 'sku'", (q - 1,)); c.commit(); return True
def buy_forupdate(cur, c):
    cur.execute("select qty from stock where sku = 'sku' for update"); q = cur.fetchone()[0]
    if q < 1: c.rollback(); return False
    cur.execute("update stock set qty = qty - 1 where sku = 'sku'"); c.commit(); return True
def buy_conditional(cur, c):
    cur.execute("update stock set qty = qty - 1 where sku = 'sku' and qty >= 1"); ok = cur.rowcount == 1; c.commit(); return ok
def buy_optimistic(cur, c):
    for _ in range(50):
        cur.execute("select qty, version from stock where sku = 'sku'"); q, v = cur.fetchone(); c.commit()
        if q < 1: return False
        cur.execute("update stock set qty = qty - 1, version = version + 1 where sku = 'sku' and version = %s", (v,))
        n = cur.rowcount; c.commit()
        if n == 1: return True
        time.sleep(random.random() * 0.0005)
    return False
SH = 8
def buy_sharded(cur, c, rng=random.Random()):
    start = rng.randrange(SH)
    for k in range(SH):
        cur.execute("update stock set qty = qty - 1 where sku = %s and qty >= 1", (f'sku#{(start + k) % SH}',)); ok = cur.rowcount == 1; c.commit()
        if ok: return True
    return False
LUA = R.register_script("local q = tonumber(redis.call('get', KEYS[1])); if q and q >= 1 then redis.call('decr', KEYS[1]); return 1 else return 0 end")
def run(buy, label, shards=1, redis_mode=False, total=None):
    reset_stock(shards, total); cnt = queue.Queue(); ok = [0]; lat = []; lk = threading.Lock(); work = list(range(N)); wl = threading.Lock()
    if redis_mode: R.set('stock:sku', total or S0)
    pend = queue.Queue(); stop_w = threading.Event(); applied = [0]
    def writer():                                    # 把 Redis 里成功的扣减异步地批量落到 MySQL
        c = M.conn('shop', autocommit=False); cur = c.cursor()
        while True:
            batch = []
            try:
                batch.append(pend.get(timeout=0.05))
                while len(batch) < 500: batch.append(pend.get_nowait())
            except queue.Empty: pass
            if batch:
                cur.execute("update stock set qty = qty - %s where sku = 'sku'", (len(batch),)); cur.executemany("insert into orders(sku) values (%s)", [('sku',)] * len(batch)); c.commit(); applied[0] += len(batch)
            elif stop_w.is_set(): break
        c.close()
    def w():
        c = M.conn('shop', autocommit=False) if not redis_mode else None; cur = c.cursor() if c else None; mine = 0; ll = []
        while True:
            with wl:
                if not work: break
                work.pop()
            t0 = time.perf_counter()
            if redis_mode:
                good = LUA(keys=['stock:sku']) == 1
                if good: pend.put(1)
            else: good = buy(cur, c)
            ll.append(time.perf_counter() - t0); mine += good
        with lk: ok[0] += mine; lat.extend(ll)
        if c: c.close()
    wt = threading.Thread(target=writer) if redis_mode else None
    if wt: wt.start()
    t0 = time.perf_counter(); ts = [threading.Thread(target=w) for _ in range(TH)]; [t.start() for t in ts]; [t.join() for t in ts]; dt = time.perf_counter() - t0
    lag = None
    if wt:
        t1 = time.perf_counter(); stop_w.set(); wt.join(); lag = time.perf_counter() - t0
    return dict(label=label, ok=ok[0], over=ok[0] - (total or S0), final=db_qty(), tps=N / dt, p99=sorted(lat)[int(len(lat) * 0.99) - 1], orders=M.q('select count(*) from orders', db='shop')[0][0], lag=lag, dt=dt)

variants = [('naive', '先 SELECT 再 UPDATE(不加锁)', buy_naive, 1, False), ('forupdate', 'SELECT ... FOR UPDATE 再 UPDATE', buy_forupdate, 1, False), ('cond', '一条条件 UPDATE(qty >= 1)', buy_conditional, 1, False),
            ('opt', '乐观锁(version CAS,最多重试 50 次)', buy_optimistic, 1, False), ('shard', f'库存拆成 {SH} 行,随机选一行做条件 UPDATE', buy_sharded, SH, False), ('redis', 'Redis Lua 先扣减,再异步批量落库', None, 1, True)]
R1 = {}; TP = {k: [] for k, *_ in variants}
for rnd in range(3):
    for k, label, fn, sh, rm in variants:
        r = run(fn, label, sh, rm); TP[k].append(r['tps'])
        if rnd == 0: R1[k] = r
print('== 一:六种扣减方式(同样的 3000 个买家抢 1000 件):成功的单数、超卖、最后库里剩多少')
rows = []
for k, label, *_ in variants:
    r = R1[k]; rows.append((label, r['ok'], r['over'], r['final'], r['orders'] if k == 'redis' else '-'))
table(rows, ['做法', '成功的单数', '超卖(成功数 - 1000)', 'MySQL 里最终库存', '落库的订单行数(只有 Redis 方案是异步落库)'])
print('  先读后写的做法(第一行)成功的单数远多于库存;其余几种成功数正好是 1000')
print('== 二:吞吐与延迟(3 轮取中位数;延迟 p99 取第 1 轮)')
rows = []
for k, label, *_ in variants:
    tps = sorted(TP[k]); r = R1[k]; rows.append((label, f'{statistics.median(tps):.0f}', f'{tps[0]:.0f} ~ {tps[-1]:.0f}', f'{r["p99"] * 1000:.1f} ms'))
table(rows, ['做法', '请求/秒(3 轮中位数)', '3 轮范围', '延迟 p99(第 1 轮)'])
r = R1['redis']; print(f'  Redis 方案:3000 个请求在 {r["dt"]:.2f} s 内处理完(成功的 {r["ok"]} 个在 Redis 里已经确认),全部落到 MySQL 用了 {r["lag"]:.2f} s,即最后一个订单比用户看到成功晚 {r["lag"] - r["dt"]:.2f} s 才进库')

print('== 二(续):同样的 3000 个买家,但库存很大(100000 件,没有人会被拒绝):去掉“卖完之后的失败请求”的影响,只看热点行上的争用(3 轮中位数)')
BIG = {k: [] for k, *_ in variants}; BIGOK = {k: [] for k, *_ in variants}
for rnd in range(3):
    for k, label, fn, sh, rm in variants:
        if k == 'naive': continue
        r = run(fn, label, sh, rm, total=100000); BIG[k].append(r['tps']); BIGOK[k].append(r['ok'])
rows = []
for k, label, *_ in variants:
    if k == 'naive': continue
    tps = sorted(BIG[k]); rows.append((label, f'{statistics.median(tps):.0f}', f'{tps[0]:.0f} ~ {tps[-1]:.0f}', f'{min(BIGOK[k])} ~ {max(BIGOK[k])}'))
table(rows, ['做法', '请求/秒(库存充足,3 轮中位数)', '3 轮范围', '成功的单数(应为 3000)'])
print('  乐观锁在 32 个线程抢同一行时,有的买家重试 50 次仍然抢不到(库存明明充足),成功数少于 3000;分片后单行争用小了,库存充足时的吞吐上去了;上面库存卖完时分片更慢,是因为卖完之后每个失败请求要把 8 个分片挨个试一遍')

print('== 三:Redis 先扣减的代价:Redis 没开持久化,被 kill -9 后只能用 MySQL 里的库存重新初始化,而异步落库还没追上——这段差距就会被重复卖出去(落库每批间隔 300 ms,Redis 在确认第 600 个订单时被杀)')
reset_stock(1); R.set('stock:sku', S0); ack = [0]; lk = threading.Lock(); pend = queue.Queue(); stopw = threading.Event(); work = list(range(N + 2000)); wl = threading.Lock(); state = {'killed': False, 'ack_at_kill': None, 'applied_at_kill': None, 'rebuilt': None}
applied2 = [0]
def writer2():
    c = M.conn('shop', autocommit=False); cur = c.cursor()
    while not stopw.is_set() or not pend.empty():
        batch = []
        try:
            batch.append(pend.get(timeout=0.05))
            while len(batch) < 100: batch.append(pend.get_nowait())
        except queue.Empty: pass
        if batch: cur.execute("update stock set qty = qty - %s where sku = 'sku'", (len(batch),)); cur.executemany("insert into orders(sku) values (%s)", [('sku',)] * len(batch)); c.commit(); applied2[0] += len(batch); time.sleep(0.3)
    c.close()
def w2():
    r = redislib.Redis(port=RP, decode_responses=True, socket_timeout=2); s_ = r.register_script("local q = tonumber(redis.call('get', KEYS[1])); if q and q >= 1 then redis.call('decr', KEYS[1]); return 1 else return 0 end")
    while True:
        with wl:
            if not work: break
            item = work.pop()
        while True:
            try: good = s_(keys=['stock:sku']) == 1; break
            except Exception: time.sleep(0.05)
        if good:
            with lk:
                ack[0] += 1; n = ack[0]
            pend.put(1)
            if n == 600 and not state['killed']:
                state['killed'] = True; state['ack_at_kill'] = n; state['applied_at_kill'] = applied2[0]
                RN.kill9(); time.sleep(0.2); RN.start()                                     # 重启之后 Redis 是空的
                state['rebuilt'] = int(db_qty()); redislib.Redis(port=RP).set('stock:sku', state['rebuilt'])   # 用 MySQL 里当前的库存重新初始化
wt = threading.Thread(target=writer2); wt.start(); ts = [threading.Thread(target=w2) for _ in range(TH)]; [t.start() for t in ts]; [t.join() for t in ts]
stopw.set(); wt.join()
print(f'  Redis 被杀时:已经对用户确认成功的订单 {state["ack_at_kill"]} 个,其中已经落到 MySQL 的 {state["applied_at_kill"]} 个(落后 {state["ack_at_kill"] - state["applied_at_kill"]} 个);重启后按 MySQL 里的库存 {state["rebuilt"]} 重新初始化 Redis(此时 MySQL 库存应该是 {S0 - state["ack_at_kill"]})')
print(f'  之后的买家继续抢:最终对用户确认成功的订单一共 {ack[0]} 个,库存只有 {S0} 件 —— 超卖 {ack[0] - S0} 件;MySQL 里的库存最终是 {db_qty()}(负数 = 超卖)')
R.close(); reset(); shutil.rmtree(TT / 'my_t19', ignore_errors=True)
import rl; shutil.rmtree(rl.RDATA / 't19_redis', ignore_errors=True)
