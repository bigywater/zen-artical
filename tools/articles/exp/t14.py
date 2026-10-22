import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import pymysql
tee('t14'); reset()
M = MySQL('t14').start(); M.q('create database shop')
M.q('create table payments(id bigint auto_increment primary key, order_key varchar(64), amount int)', db='shop')
M.q('create table dedup(k varchar(64) primary key, created datetime default current_timestamp)', db='shop')
M.q("create table idem(k varchar(64) primary key, status varchar(12), result varchar(80), locked_until datetime(3), created datetime default current_timestamp)", db='shop')
print(f'MySQL {M.q("select version()")[0][0]},业务动作 = 往 payments 表插一行“扣款”(所以 payments 里某个 key 出现几行就是执行了几次);去重表 dedup(k 主键)、状态表 idem(k 主键、status、result、locked_until)')
def conn(): return M.conn('shop', autocommit=False)
def reset_tables():
    for t in ('payments', 'dedup', 'idem'): M.q(f'delete from {t}', db='shop')
def per_key():
    return {r[0]: r[1] for r in M.q('select order_key, count(*) from payments group by order_key', db='shop')}

print('== 一:先查后插 vs 先插唯一键:200 个 key,每个 key 同时到达 8 个重复请求(8 个线程过屏障后同时执行)')
def worker_check_then_insert(key, bar):
    c = conn(); cur = c.cursor(); bar.wait()
    cur.execute('select 1 from dedup where k = %s', (key,))
    if cur.fetchone() is None:
        cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,))
        try: cur.execute('insert into dedup(k) values (%s)', (key,)); c.commit()
        except pymysql.err.IntegrityError: c.commit()                 # 记录已经被别人插了:业务却已经执行了
    else: c.rollback()
    c.close()
def worker_insert_first(key, bar):
    c = conn(); cur = c.cursor(); bar.wait()
    try:
        cur.execute('insert into dedup(k) values (%s)', (key,)); cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,)); c.commit()
    except pymysql.err.IntegrityError: c.rollback()
    c.close()
rows = []
for name, fn in (('先 SELECT 看有没有,没有再做业务并插记录', worker_check_then_insert), ('先 INSERT 唯一键,成功才做业务(同一个事务)', worker_insert_first)):
    reset_tables(); t0 = time.perf_counter()
    for i in range(200):
        bar = threading.Barrier(8); ts = [threading.Thread(target=fn, args=(f'k{i}', bar)) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
    pk = per_key(); dup_keys = sum(1 for v in pk.values() if v > 1); total = sum(pk.values())
    rows.append((name, 200 * 8, total, dup_keys, total - len(pk), f'{time.perf_counter() - t0:.1f} s'))
table(rows, ['写法', '收到的请求', '业务实际执行次数', '被执行了多次的 key', '多执行的次数', '用时'])
print('  “先查后插”在两个请求都查到“没有”之后各自去做业务,唯一键只管得住记录,管不住业务;先插唯一键的那个请求才有资格执行业务')

print('== 二:去重记录和业务必须在同一个本地事务里:每个 key 的第二步有 20% 概率失败(代码里直接抛错),客户端失败后重试(最多 6 次),看每个 key 最后被执行了几次(1000 个 key)')
def attempt(mode, key, rng):
    c = conn(); cur = c.cursor()
    try:
        if mode == 'dedup-first':                       # 先单独提交去重记录,再做业务
            try: cur.execute('insert into dedup(k) values (%s)', (key,)); c.commit()
            except pymysql.err.IntegrityError: c.rollback(); return 'dup'
            if rng.random() < 0.2: raise RuntimeError('业务这一步失败')
            cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,)); c.commit(); return 'done'
        if mode == 'biz-first':                         # 先单独提交业务,再记去重
            cur.execute('select 1 from dedup where k = %s', (key,))
            if cur.fetchone(): c.rollback(); return 'dup'
            cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,)); c.commit()
            if rng.random() < 0.2: raise RuntimeError('记去重这一步失败')
            cur.execute('insert into dedup(k) values (%s)', (key,)); c.commit(); return 'done'
        try: cur.execute('insert into dedup(k) values (%s)', (key,))   # same-tx:同一个事务
        except pymysql.err.IntegrityError: c.rollback(); return 'dup'
        if rng.random() < 0.2: raise RuntimeError('业务这一步失败')
        cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,)); c.commit(); return 'done'
    except RuntimeError: c.rollback(); return 'fail'
    finally: c.close()
rows = []
for mode, name in (('dedup-first', '去重记录先单独提交,再做业务'), ('biz-first', '业务先单独提交,再记去重'), ('same-tx', '去重记录和业务在同一个事务里')):
    reset_tables(); rng = random.Random(14)
    for i in range(1000):
        for _ in range(6):
            if attempt(mode, f'k{i}', rng) in ('done', 'dup'): break
    pk = per_key(); ok1 = sum(1 for i in range(1000) if pk.get(f'k{i}', 0) == 1); lost = sum(1 for i in range(1000) if pk.get(f'k{i}', 0) == 0); dup = sum(1 for i in range(1000) if pk.get(f'k{i}', 0) > 1)
    rows.append((name, 1000, ok1, lost, dup))
table(rows, ['写法', 'key 数', '恰好执行 1 次', '一次都没执行(丢)', '执行了多次(重复)'])
print('  去重记录先提交:业务失败后重试会被当成重复拒绝,这笔业务永远丢了;业务先提交:记去重失败后重试会再执行一遍;同一个事务里两者一起成功或一起回滚')

print('== 三:状态型幂等键(PROCESSING → DONE,并保存结果):第一个请求还在处理(300 ms)时重复请求到达;处理完之后再来的重复请求直接拿保存的结果')
M.q('delete from idem', db='shop'); M.q('delete from payments', db='shop')
def handle(key, work_ms=300, wait=False, lease=2.0):
    c = conn(); cur = c.cursor(); t0 = time.perf_counter()
    try:
        cur.execute("insert into idem(k, status, locked_until) values (%s, 'PROCESSING', now(3) + interval %s second)", (key, lease)); c.commit()
    except pymysql.err.IntegrityError:
        c.rollback()
        while True:
            cur.execute('select status, result from idem where k = %s', (key,)); st, res = cur.fetchone(); c.commit()
            if st == 'DONE': c.close(); return ('返回已保存的结果', res, time.perf_counter() - t0)
            if not wait: c.close(); return ('409 正在处理中', None, time.perf_counter() - t0)
            time.sleep(0.01)
    time.sleep(work_ms / 1000); cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,)); cur.execute("update idem set status = 'DONE', result = %s where k = %s", (f'扣款成功#{key}', key)); c.commit(); c.close()
    return ('第一次执行', f'扣款成功#{key}', time.perf_counter() - t0)
def concurrent(key, waits):
    res = {}; ths = []
    def run(i, delay, w):
        time.sleep(delay); res[i] = handle(key, wait=w)
    for i, (delay, w) in enumerate(waits): ths.append(threading.Thread(target=run, args=(i, delay, w)))
    [t.start() for t in ths]; [t.join() for t in ths]; return res
r = concurrent('s1', [(0.0, False), (0.1, False), (0.5, False)])
for i, (a, v, d) in sorted(r.items()): print(f'  请求 {i + 1}(到达于 {[0, 100, 500][i]} ms,重复请求遇到“处理中”就返回 409):{a},结果 {v},耗时 {d * 1000:.0f} ms')
r = concurrent('s2', [(0.0, True), (0.1, True)])
for i, (a, v, d) in sorted(r.items()): print(f'  请求 {i + 1}(到达于 {[0, 100][i]} ms,重复请求等待处理完成再返回):{a},结果 {v},耗时 {d * 1000:.0f} ms')
print('  payments 里这两个 key 的执行次数:', per_key())
print('  如果第一个请求在 PROCESSING 时进程被 kill -9,这行 PROCESSING 会一直留着;租约(locked_until)过期之后才允许别的请求接管:')
M.q("insert into idem(k, status, locked_until) values ('s3', 'PROCESSING', now(3) + interval 1 second)", db='shop')
c = conn(); cur = c.cursor(); cur.execute("select status, locked_until > now(3) from idem where k = 's3'"); a = cur.fetchone(); c.commit()
print(f'   0 秒时 s3:status={a[0]},租约未过期={bool(a[1])} → 重复请求只能等')
time.sleep(1.2)
cur.execute("update idem set locked_until = now(3) + interval 1 second where k = 's3' and status = 'PROCESSING' and locked_until < now(3)"); took = cur.rowcount; c.commit(); c.close()
print(f'   1.2 秒后:租约过期,接管用 UPDATE ... WHERE locked_until < now() 抢到的行数 = {took}(抢到 1 才能重新执行;两个请求同时抢,只有一个能抢到)')

print('== 四:去重表的成本:插入开销、体积、过期清理对并发写入的影响,以及保留期太短会怎样')
def bench_insert(table, n=3000):
    c = conn(); cur = c.cursor(); lat = []
    for i in range(n):
        t0 = time.perf_counter()
        if table == 'dedup': cur.execute('insert into dedup(k) values (%s)', (f'b{time.time_ns()}',))
        else: cur.execute('insert into payments(order_key, amount) values (%s, 1)', (f'p{time.time_ns()}',))
        c.commit(); lat.append(time.perf_counter() - t0)
    c.close(); return statistics.median(lat)
reset_tables(); us = lambda t: f'{t * 1e6:.0f} µs'
print(f'  单行插入(各 3000 次的中位数):只插 payments {us(bench_insert("payments"))};只插 dedup {us(bench_insert("dedup"))}')
M.q('delete from dedup', db='shop'); c = conn(); cur = c.cursor()
for b in range(30): cur.executemany('insert into dedup(k, created) values (%s, now() - interval %s minute)', [(f'order-{b}-{i:06d}', 120 if b < 15 else 1) for i in range(10000)]); c.commit()
c.close(); M.q('analyze table dedup', db='shop')
sz = M.q("select data_length + index_length from information_schema.tables where table_schema = 'shop' and table_name = 'dedup'")[0][0]
print(f'  dedup 里 30 万个 key(形如 order-3-000123):{int(sz) / 1024 / 1024:.1f} MiB,平均每行约 {int(sz) / 300000:.0f} 字节(主键聚簇索引含 created 列);其中 15 万个是 120 分钟前的、15 万个是 1 分钟前的')
lat_base = []; lat_purge = []; stop = threading.Event()
def inserter(store):
    c = conn(); cur = c.cursor()
    while not stop.is_set():
        t0 = time.perf_counter(); cur.execute('insert into dedup(k) values (%s)', (f'w{time.time_ns()}',)); c.commit(); store.append(time.perf_counter() - t0); time.sleep(0.001)
    c.close()
th = threading.Thread(target=inserter, args=(lat_base,)); th.start(); time.sleep(2.0); stop.set(); th.join(); stop.clear()
th = threading.Thread(target=inserter, args=(lat_purge,)); th.start(); t0 = time.perf_counter(); total = 0
c = conn(); cur = c.cursor()
while True:
    cur.execute('delete from dedup where created < now() - interval 60 minute limit 5000'); n = cur.rowcount; c.commit(); total += n
    if n == 0: break
purge_t = time.perf_counter() - t0; stop.set(); th.join(); c.close()
print(f'  按保留期 60 分钟分批清理(每批 5000 行):删掉 {total} 行,用时 {purge_t:.2f} s;清理期间同时插入的 p99:{us(sorted(lat_purge)[int(len(lat_purge) * 0.99) - 1])}(没清理时 p99 {us(sorted(lat_base)[int(len(lat_base) * 0.99) - 1])},中位数 {us(statistics.median(lat_base))} → {us(statistics.median(lat_purge))})。单次测量、样本只有两三千次,同一个实验重跑时 p99 的高低方向会变,所以只能说“清理的 1 秒多里写入照常在进行”,不能据此断言清理对写入延迟有多大影响')
reset_tables(); M.q("insert into dedup(k, created) values ('late-1', now() - interval 120 minute)", db='shop')
M.q("delete from dedup where created < now() - interval 60 minute", db='shop')
c = conn(); cur = c.cursor()
try: cur.execute("insert into dedup(k) values ('late-1')"); c.commit(); print('  保留期(60 分钟)比客户端的最长重试窗口(假设 2 小时)短:2 小时前处理过的 late-1 被清掉了,它的重试到达时 INSERT 成功 —— 被当成新请求,业务会再执行一次')
except pymysql.err.IntegrityError: print('  仍被识别为重复')
c.close()

print('== 五:三种“先占位”的写法:INSERT IGNORE、INSERT ... ON DUPLICATE KEY UPDATE、捕获唯一键冲突异常;4 个线程,每个线程 5000 次请求,key 从 2500 个里随机选(约一半是重复)')
def run_variant(variant):
    reset_tables(); done = [0]; execd = [0]; lk = threading.Lock()
    def w(seed):
        rng = random.Random(seed); c = conn(); cur = c.cursor(); e = 0
        for _ in range(5000):
            key = f'v{rng.randrange(2500)}'
            if variant == 'ignore':
                cur.execute('insert ignore into dedup(k) values (%s)', (key,)); first = cur.rowcount == 1
            elif variant == 'odku':
                cur.execute('insert into dedup(k, created) values (%s, now()) on duplicate key update created = created', (key,)); first = cur.rowcount == 1
            else:
                try: cur.execute('insert into dedup(k) values (%s)', (key,)); first = True
                except pymysql.err.IntegrityError: first = False
            if first: cur.execute('insert into payments(order_key, amount) values (%s, 100)', (key,)); e += 1
            c.commit()
        with lk: execd[0] += e
        c.close()
    t0 = time.perf_counter(); ts = [threading.Thread(target=w, args=(s,)) for s in range(4)]; [t.start() for t in ts]; [t.join() for t in ts]
    dt = time.perf_counter() - t0; distinct = M.q('select count(*) from dedup', db='shop')[0][0]; pays = M.q('select count(*) from payments', db='shop')[0][0]
    return dt, execd[0], distinct, pays
rows = []; res5 = {v: [] for v in ('ignore', 'odku', 'except')}
for rnd in range(3):
    for v in ('ignore', 'odku', 'except'):
        dt, e, distinct, pays = run_variant(v); res5[v].append((20000 / dt, e, distinct, pays))
for v, name in (('ignore', 'INSERT IGNORE,看 rowcount'), ('odku', 'INSERT ... ON DUPLICATE KEY UPDATE,看 rowcount'), ('except', '直接 INSERT,捕获唯一键异常')):
    tps = sorted(r[0] for r in res5[v]); rows.append((name, f'{statistics.median(tps):.0f}', f'{tps[0]:.0f} ~ {tps[-1]:.0f}', res5[v][-1][1], res5[v][-1][2], res5[v][-1][3]))
table(rows, ['写法', '请求/秒(3 轮中位数)', '3 轮的范围', '业务执行次数', '去重表里不同的 key', 'payments 行数'])
print('  三种写法都是“只有抢到唯一键的那个请求才执行业务”,执行次数都等于不同 key 的个数;吞吐的差别落在各轮的波动范围附近,不是明确的高低')
reset(); shutil.rmtree(TT / 'my_t14', ignore_errors=True)
