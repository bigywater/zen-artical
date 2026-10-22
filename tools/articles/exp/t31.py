import sys, os, zlib, hashlib, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t31'); reset()
A = MySQL('t31_a'); B = MySQL('t31_b', opts=['--innodb-buffer-pool-size=256M']); ths = [threading.Thread(target=n.start) for n in (A, B)]; [t.start() for t in ths]; [t.join() for t in ths]
for n in (A, B): n.q('create database shop'); n.q('create table orders(id bigint primary key, amount int, status varchar(10), updated_at datetime(3) default current_timestamp(3), key idx_upd (updated_at))', db='shop')
NROWS = 1_000_000
print(f'两个独立的 MySQL {A.q("select version()")[0][0]}(订单服务的库 A、对账用的副本库 B,表结构一样:orders(id, amount, status, updated_at));各 {NROWS} 行;校验的目标是找出两边不一样的行')
def load(n, rows_fn):
    c = n.conn('shop', autocommit=False); cur = c.cursor(); cur.execute('truncate table orders')
    for i in range(0, NROWS, 20000): cur.executemany('insert into orders(id, amount, status) values (%s, %s, %s)', rows_fn(i, min(i + 20000, NROWS))); c.commit()
    c.close()
base = lambda a, b: [(i, 100 + i % 977, 'PAID' if i % 10 else 'CANCELLED') for i in range(a, b)]
t0 = time.perf_counter(); ths = [threading.Thread(target=load, args=(n, base)) for n in (A, B)]; [t.start() for t in ths]; [t.join() for t in ths]
print(f'  两个库各装入 {NROWS} 行,用时 {time.perf_counter() - t0:.0f} s;一致性检查:两边 count 都是 {A.q("select count(*) from orders", db="shop")[0][0]}')

def scalar(n, sql): return n.q(sql, db='shop')[0]
print('== 一:汇总校验(count、sum)的盲区:在 B 里改 2 行——一行金额 +7、另一行金额 -7(互相抵消),再看 count / sum / 逐行哈希各发现了没有')
B.q('update orders set amount = amount + 7 where id = 123456', db='shop'); B.q('update orders set amount = amount - 7 where id = 654321', db='shop')
ca, cb = scalar(A, 'select count(*), sum(amount) from orders'), scalar(B, 'select count(*), sum(amount) from orders')
ha = scalar(A, 'select bit_xor(crc32(concat_ws("|", id, amount, status))) from orders')[0]; hb = scalar(B, 'select bit_xor(crc32(concat_ws("|", id, amount, status))) from orders')[0]
print(f'  A:count = {ca[0]}, sum(amount) = {ca[1]};B:count = {cb[0]}, sum(amount) = {cb[1]} —— count 和 sum 都一样,汇总校验认为“一致”')
print(f'  逐行哈希再异或(bit_xor(crc32(id|amount|status))):A = {ha},B = {hb} —— {"不同,发现了" if ha != hb else "相同,没发现"}')
B.q('update orders set amount = amount - 7 where id = 123456', db='shop'); B.q('update orders set amount = amount + 7 where id = 654321', db='shop')

# 注入 50 个差异(落在不同的位置):金额不同 20 个、B 少一行 15 个、B 多一行(A 没有的 id)15 个
rng = random.Random(31)
ids = rng.sample(range(1, NROWS + 1), 50); amt_ids, miss_ids, extra_n = ids[:20], ids[20:35], 15
for i in amt_ids: B.q('update orders set amount = amount + 1 where id = %s', (i,), db='shop')
for i in miss_ids: B.q('delete from orders where id = %s', (i,), db='shop')
extra_ids = [NROWS + 1 + k for k in range(extra_n)]
for i in extra_ids: B.q("insert into orders(id, amount, status) values (%s, 1, 'PAID')", (i,), db='shop')
TRUTH = set(amt_ids) | set(miss_ids) | set(extra_ids)

print('== 二:分桶校验和 vs 全量比较:A、B 各有 100 万行,里面有 50 处差异(20 行金额不同、15 行 B 缺失、15 行 B 多出)。全量比较:两边的所有行都拉出来比;分桶校验:每个库在库内按 1000 行一个桶算 (count, bit_xor 的行哈希),只把每个桶的校验和拿出来比,有差异的桶再拉出行')
def bytes_of(rows): return sum(len(','.join(map(str, r))) + 1 for r in rows)
t0 = time.perf_counter(); ra = A.q('select id, amount, status from orders order by id', db='shop'); rb = B.q('select id, amount, status from orders order by id', db='shop'); fetch_t = time.perf_counter() - t0
da = {r[0]: r for r in ra}; db_ = {r[0]: r for r in rb}; found_full = {i for i in set(da) | set(db_) if da.get(i) != db_.get(i)}; full_t = time.perf_counter() - t0; full_bytes = bytes_of(ra) + bytes_of(rb)
BS = 1000
SQLB = f'select floor((id - 1) / {BS}) b, count(*), bit_xor(crc32(concat_ws("|", id, amount, status))) from orders group by b'
t0 = time.perf_counter(); ba = {r[0]: (r[1], r[2]) for r in A.q(SQLB, db='shop')}; bb = {r[0]: (r[1], r[2]) for r in B.q(SQLB, db='shop')}; sum_t = time.perf_counter() - t0
bad_b = sorted(b for b in set(ba) | set(bb) if ba.get(b) != bb.get(b)); sum_bytes = bytes_of([(b, *v) for b, v in ba.items()]) + bytes_of([(b, *v) for b, v in bb.items()])
t1 = time.perf_counter(); found_b = set(); drill_bytes = 0
for b in bad_b:
    lo, hi = b * BS + 1, (b + 1) * BS
    xa = A.q('select id, amount, status from orders where id between %s and %s order by id', (lo, hi), db='shop'); xb = B.q('select id, amount, status from orders where id between %s and %s order by id', (lo, hi), db='shop'); drill_bytes += bytes_of(xa) + bytes_of(xb)
    ma = {r[0]: r for r in xa}; mb = {r[0]: r for r in xb}; found_b |= {i for i in set(ma) | set(mb) if ma.get(i) != mb.get(i)}
drill_t = time.perf_counter() - t1
table([('全量比较(两边所有行拉出来)', f'{full_t:.1f} s', f'{full_bytes / 1024 / 1024:.1f} MiB', len(found_full), len(found_full & TRUTH), len(TRUTH - found_full)),
       (f'分桶校验和(每 {BS} 行一个桶)+ 只拉有差异的桶', f'{sum_t + drill_t:.2f} s(校验和 {sum_t:.2f} s + 下钻 {drill_t:.2f} s)', f'{(sum_bytes + drill_bytes) / 1024:.0f} KiB(校验和 {sum_bytes / 1024:.0f} KiB + 下钻 {drill_bytes / 1024:.0f} KiB)', len(found_b), len(found_b & TRUTH), len(TRUTH - found_b))],
      ['做法', '用时', '传输的数据量', '报出的差异行', '其中真差异', '漏报'])
print(f'  有差异的桶 {len(bad_b)} 个(共 {len(set(ba) | set(bb))} 个桶);注入的差异 {len(TRUTH)} 处。校验和在数据库内部算,只有每个桶的 (桶号, count, 哈希) 离开数据库')

print('== 三:不同的汇总方式能发现哪几类差异:每种方式对同一种差异单独测一次(每类差异 60 次,每次随机选行,先取 B 这一段 id 1~20000 的各种校验值,在 B 里造出一种差异,再取一次,看这种校验的值有没有变,然后还原)')
def checks(n):
    c = n.conn('shop'); cur = c.cursor(); cur.execute('set session group_concat_max_len = 100000000')
    cur.execute('select count(*), sum(amount), bit_xor(crc32(concat_ws("|", id, amount, status))), sum(crc32(concat_ws("|", id, amount, status))), sha2(group_concat(sha2(concat_ws("|", id, amount, status), 256) order by id separator ""), 256) from orders where id between 1 and 20000')
    r = cur.fetchone(); c.close()
    return dict(count=r[0], sum_amount=r[1], xor=r[2], sum_crc=r[3], sha2chain=r[4])
def inject(kind, i, j):
    if kind == '金额 +1':     B.q('update orders set amount = amount + 1 where id = %s', (i,), db='shop'); return lambda: B.q('update orders set amount = amount - 1 where id = %s', (i,), db='shop')
    if kind == '少一行':       row = B.q('select id, amount, status from orders where id = %s', (i,), db='shop')[0]; B.q('delete from orders where id = %s', (i,), db='shop'); return lambda: B.q('insert into orders(id, amount, status) values (%s, %s, %s)', tuple(row), db='shop')
    if kind == '一加一减(抵消)': B.q('update orders set amount = amount + 5 where id = %s', (i,), db='shop'); B.q('update orders set amount = amount - 5 where id = %s', (j,), db='shop'); return lambda: (B.q('update orders set amount = amount - 5 where id = %s', (i,), db='shop'), B.q('update orders set amount = amount + 5 where id = %s', (j,), db='shop'))
    if kind == '状态被改(金额不变)': orig_s = B.q('select status from orders where id = %s', (i,), db='shop')[0][0]; B.q("update orders set status = 'REFUNDED' where id = %s", (i,), db='shop'); return lambda: B.q('update orders set status = %s where id = %s', (orig_s, i), db='shop')
kinds = ['金额 +1', '少一行', '一加一减(抵消)', '状态被改(金额不变)']; names = ['count', 'sum_amount', 'xor', 'sum_crc', 'sha2chain']; hit = {k: {n: 0 for n in names} for k in kinds}; T = 60
for kind in kinds:
    for _ in range(T):
        i, j = rng.sample(range(1, 20001), 2); before = checks(B); undo = inject(kind, i, j); cb_ = checks(B)
        for n in names: hit[kind][n] += (cb_[n] != before[n])
        undo()
table([(k, *[f'{hit[k][n]} / {T}' for n in names]) for k in kinds], ['差异类型(在 id 1~20000 的范围内)', 'count', 'sum(amount)', '行哈希 bit_xor', '行哈希 sum', '按 id 排序的行哈希串再 SHA-256'])
print(f'  count 只能发现行数变化;sum(amount) 发现不了“一加一减”和“只改状态”;行哈希 bit_xor 在“一加一减”上漏了 {T - hit["一加一减(抵消)"]["xor"]} / {T} 次(异或把两行的哈希变化互相抵消了;我的解释是 CRC32 是线性的,两处改动的比特差异模式相同时哈希差相同,这个解释没有单独验证);行哈希 sum 和按 id 排序的 SHA-256 链在这四类上都没有漏,代价是 SHA-256 链要排序、拼接,算起来最重')

print('== 四:增量校验的提交顺序陷阱:检查器每 100 ms 跑一次,只看 updated_at 落在“上次检查开始之后”的行。updated_at 是语句执行时的时刻、不是提交时刻,事务提交得晚,它的行可能在被查到之前就“滑出”了窗口。300 个事务在 3 秒里随机开始,每个事务改一行后持有一段时间才提交(70% 持有 0 到 20 ms,25% 持有 20 到 250 ms,5% 持有 250 到 900 ms)')
def incremental(overlap_ms, seed):
    rng = random.Random(seed); ids = rng.sample(range(1, NROWS + 1), 300); plan = [(rng.random() * 3.0, i, (rng.random() * 0.02 if (x := rng.random()) < 0.70 else (0.02 + rng.random() * 0.23 if x < 0.95 else 0.25 + rng.random() * 0.65))) for i in ids]
    seen = set(); stop = threading.Event(); done = threading.Event(); lk = threading.Lock(); committed = set()
    def checker():
        c = A.conn('shop'); cur = c.cursor(); cur.execute('select now(3)'); w = cur.fetchone()[0]
        while True:
            time.sleep(0.1); fin = done.is_set()
            cur.execute('select now(3)'); w_new = cur.fetchone()[0]
            cur.execute('select id from orders where updated_at >= %s and updated_at < %s', (w - datetime.timedelta(milliseconds=overlap_ms), w_new)); seen.update(r[0] for r in cur.fetchall()); w = w_new
            if fin: break
        c.close()
    def writer(chunk):
        c = A.conn('shop', autocommit=False); cur = c.cursor(); t0 = T0
        for start, rid, hold in sorted(chunk):
            time.sleep(max(0, t0 + start - time.perf_counter())); cur.execute('update orders set amount = amount + 1, updated_at = now(3) where id = %s', (rid,)); time.sleep(hold); c.commit()
            with lk: committed.add(rid)
        c.close()
    T0 = time.perf_counter() + 0.2; ck = threading.Thread(target=checker); ck.start(); chunks = [plan[k::30] for k in range(30)]; ws = [threading.Thread(target=writer, args=(c,)) for c in chunks]; [w.start() for w in ws]; [w.join() for w in ws]
    time.sleep(0.25); done.set(); ck.join()
    for rid in ids: A.q('update orders set amount = amount - 1 where id = %s', (rid,), db='shop')
    return len(committed), len(committed - seen)
rows = []
for ov in (0, 100, 300, 1000):
    tot, miss = incremental(ov, 4); rows.append((f'窗口往前重叠 {ov} ms' if ov else '不重叠(只看上次检查开始之后)', tot, miss, f'{miss / tot * 100:.1f}%'))
table(rows, ['增量窗口', '提交的改动', '一直没被检查到的改动', '漏报率'])
print('  不重叠时,提交得比较晚的事务(持有超过一个检查周期的)会在检查器两次窗口之间漏掉;窗口往前重叠一段(要大于最长事务的持有时间)可以补上。更稳的做法是用提交顺序单调的位点(binlog 位点 / LSN / 自增版本号),而不是 updated_at')

print('== 五:抽样校验:从 100 万行里按 A 的 id 随机抽 n 行比对。第二节注入的 50 处差异里,B 里多出来的 15 行在 A 里没有对应的 id,按 A 的 id 抽不到,所以只统计另外 35 处;抽到至少一处的概率(各 300 次试验;理论值 1 - (1 - n/N)^35)')
rows = []
sample_ids = list(range(1, NROWS + 1))
for n in (1000, 10000, 100000, 500000):
    hits = 0
    for _ in range(300):
        s = set(random.sample(sample_ids, n)) if n <= 100000 else None
        if s is None: s = set(random.sample(sample_ids, n))
        hits += bool(s & (set(amt_ids) | set(miss_ids)))                     # B 多出来的 id 不在 1..N 里,抽样检查“按 A 的 id 去查 B”时看不到它们,所以只统计 35 处在 A 里有的差异
    theory = 1 - (1 - n / NROWS) ** 35
    rows.append((n, f'{n / NROWS * 100:.1f}%', f'{hits} / 300', f'{hits / 300 * 100:.0f}%', f'{theory * 100:.0f}%'))
table(rows, ['抽样行数', '占总行数', '抽到至少一处差异的试验数', '实测发现概率', '理论值(35 处差异)'])
print('  差异只有总量的 0.0035% ~ 0.005% 时,抽样要抽到相当大的比例才有把握;而且按 A 的 id 抽样根本看不到 B 里“多出来”的行(那 15 处)。罕见的错误靠抽样找不出来')
for n in (A, B): n.stop()
reset(); [shutil.rmtree(TT / x, ignore_errors=True) for x in ('my_t31_a', 'my_t31_b')]
