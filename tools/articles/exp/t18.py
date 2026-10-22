import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t18'); reset()
M = MySQL('t18').start(); M.q('create database shop')
M.q('create table acct(id int primary key, balance int, version int default 0)', db='shop')
M.q("create table ord(id int primary key, status varchar(10), pay_id int, version int default 0, shipped_pay_id int)", db='shop')
print(f'MySQL {M.q("select version()")[0][0]}(默认隔离级别 {M.q("select @@transaction_isolation")[0][0]}),acct(id, balance, version);客户端 PyMySQL,每个线程自己一个连接;“乐观锁”= 不加锁地读出版本号,更新时带上 WHERE version = ?,更新行数为 0 就是冲突、重读重试')
def reset_acct(n=1, bal=0): M.q('delete from acct', db='shop'); [M.q('insert into acct values (%s, %s, 0)', (i, bal), db='shop') for i in range(1, n + 1)]
def total(): return M.q('select sum(balance) from acct', db='shop')[0][0]
def pct(l, p): return sorted(l)[max(int(len(l) * p) - 1, 0)]

def op_nolock(cur, c, rid):
    cur.execute('select balance from acct where id = %s', (rid,)); b = cur.fetchone()[0]; time.sleep(0.0003); cur.execute('update acct set balance = %s where id = %s', (b + 1, rid)); c.commit(); return 1
def op_optimistic(cur, c, rid, backoff=None):
    attempts = 0
    while True:
        attempts += 1
        cur.execute('select balance, version from acct where id = %s', (rid,)); b, v = cur.fetchone(); c.commit()
        cur.execute('update acct set balance = %s, version = version + 1 where id = %s and version = %s', (b + 1, rid, v)); n = cur.rowcount; c.commit()
        if n == 1: return attempts
        if backoff: time.sleep(random.random() * backoff * min(2 ** min(attempts, 6), 64))
def op_forupdate(cur, c, rid):
    cur.execute('select balance from acct where id = %s for update', (rid,)); b = cur.fetchone()[0]; cur.execute('update acct set balance = %s where id = %s', (b + 1, rid)); c.commit(); return 1
def op_atomic(cur, c, rid): cur.execute('update acct set balance = balance + 1 where id = %s', (rid,)); c.commit(); return 1
def run(op, threads, per, rows=1, **kw):
    reset_acct(rows); res = []; lk = threading.Lock()
    def w(k):
        c = M.conn('shop', autocommit=False); cur = c.cursor(); att = []; lat = []
        for _ in range(per):
            t0 = time.perf_counter(); att.append(op(cur, c, 1 + (k % rows), **kw)); lat.append(time.perf_counter() - t0)
        c.close()
        with lk: res.append((att, lat))
    t0 = time.perf_counter(); ts = [threading.Thread(target=w, args=(k,)) for k in range(threads)]; [t.start() for t in ts]; [t.join() for t in ts]; dt = time.perf_counter() - t0
    att = [a for r in res for a in r[0]]; lat = [x for r in res for x in r[1]]
    return dict(dt=dt, tps=threads * per / dt, att=att, lat=lat, total=total(), expect=threads * per)

print('== 一:基线:不加任何保护的读-改-写,8 个线程各加 100 次(应得 800),丢更新')
r = run(op_nolock, 8, 100); print(f'  最终余额 {r["total"]},丢了 {r["expect"] - r["total"]} 次更新({(r["expect"] - r["total"]) / r["expect"] * 100:.0f}%)')

print('== 二:乐观锁(version 做 CAS):8 个线程各加 100 次,同一行;冲突的重读重试,看有没有丢、每次成功平均试几次')
r = run(op_optimistic, 8, 100); att = r['att']
print(f'  最终余额 {r["total"]}(应为 {r["expect"]},丢 {r["expect"] - r["total"]} 次);一共 {sum(att)} 次尝试成功 {len(att)} 次,平均每次成功试 {statistics.mean(att):.2f} 次,p99 {pct(att, 0.99)} 次,最多 {max(att)} 次;{sum(att) - len(att)} 次尝试因 version 变了而更新 0 行(白做)')
print(f'  用时 {r["dt"]:.2f} s({r["tps"]:.0f} 成功/秒),延迟中位数 {statistics.median(r["lat"]) * 1000:.2f} ms,p99 {pct(r["lat"], 0.99) * 1000:.2f} ms')

print('== 三:冲突程度的影响:同一行上并发线程数 1 → 32,每个线程 200 次;乐观锁 vs SELECT ... FOR UPDATE vs 原子 UPDATE(各 2 轮取中位数)')
rows = []
for th in (1, 2, 4, 8, 16, 32):
    o = [run(op_optimistic, th, 200) for _ in range(2)]; f = [run(op_forupdate, th, 200) for _ in range(2)]; a = [run(op_atomic, th, 200) for _ in range(2)]
    assert all(x['total'] == x['expect'] for x in o + f + a)
    att = statistics.mean(statistics.mean(x['att']) for x in o)
    rows.append((th, f'{statistics.median(x["tps"] for x in o):.0f}', f'{att:.2f}', f'{statistics.median(x["tps"] for x in f):.0f}', f'{statistics.median(x["tps"] for x in a):.0f}'))
table(rows, ['并发线程数', '乐观锁 成功/秒', '乐观锁 平均每次成功试几次', 'FOR UPDATE 操作/秒', '原子 UPDATE 操作/秒'])
print('  线程越多,同一行上乐观锁的白做越多(每次成功要试的次数涨),吞吐不再增长甚至下降;悲观加锁让冲突的请求排队而不是重做')

print('== 四:低冲突:32 个线程各用自己的一行(没有冲突)')
o = run(op_optimistic, 32, 200, rows=32); f = run(op_forupdate, 32, 200, rows=32)
table([('乐观锁', f'{o["tps"]:.0f}', f'{statistics.mean(o["att"]):.2f}'), ('FOR UPDATE', f'{f["tps"]:.0f}', '1.00')], ['写法', '操作/秒', '平均每次成功试几次'])
print('  没有冲突时乐观锁一次就成功,不需要任何等待;它的价值就在“冲突少”的场景')

print('== 五:ABA:订单状态 PAID → REFUNDED → PAID(新的支付单),发货方在读到 PAID 之后、更新之前,这两步都发生了。按“状态值”做 CAS 与按“version”做 CAS')
def aba_trial(mode, rng):
    M.q('delete from ord', db='shop'); M.q("insert into ord values (1, 'PAID', 1, 0, null)", db='shop')
    ca = M.conn('shop', autocommit=False); cb = M.conn('shop'); cur = ca.cursor()
    def b():
        time.sleep(rng.random() * 0.004); cb.cursor().execute("update ord set status = 'REFUNDED', version = version + 1 where id = 1"); time.sleep(rng.random() * 0.002); cb.cursor().execute("update ord set status = 'PAID', pay_id = 2, version = version + 1 where id = 1")
    th = threading.Thread(target=b); started = [False]
    while True:
        cur.execute('select status, pay_id, version from ord where id = 1'); st, pid, ver = cur.fetchone(); ca.commit()
        if st != 'PAID': time.sleep(0.001); continue
        if not started[0]: started[0] = True; th.start()      # 读到 PAID 之后,另一个线程才开始退款 + 重新支付
        time.sleep(rng.random() * 0.01)                      # 发货方做决定、调物流接口的时间
        if mode == 'value': cur.execute("update ord set shipped_pay_id = pay_id, status = 'SHIPPED' where id = 1 and status = 'PAID'")          # 同一条语句里记下发货那一刻订单上的支付单号
        else: cur.execute("update ord set shipped_pay_id = pay_id, status = 'SHIPPED', version = version + 1 where id = 1 and version = %s", (ver,))
        n = cur.rowcount; ca.commit()
        if n == 1: break
        # 冲突:重读重试
    th.join(); cur.execute('select shipped_pay_id from ord where id = 1'); sp = cur.fetchone()[0]; ca.commit(); ca.close(); cb.close()
    return pid, sp
res = {}
for mode in ('value', 'version'):
    rng = random.Random(18); stale = 0; n = 300
    for _ in range(n):
        pid, sp = aba_trial(mode, rng)
        stale += (sp != pid)                                 # 发货方决定发货时看到的是 pid 号支付单,发货那一刻订单上的支付单已经换成了别的(原来那张已经退款)
    res[mode] = stale
table([('按状态值 CAS(WHERE status = \'PAID\')', n, res['value']), ('按 version CAS(WHERE version = ?)', n, res['version'])], ['写法', '试验次数', '发货时订单上的支付单已不是发货方看到的那张(原单已退款)的次数'])
print('  ABA:状态值回到了“PAID”,CAS 看不出中间发生过退款和重新支付,于是按旧的支付单发了货;version 每次改动都会增加,不会“变回去”')

print('== 六:高冲突下的重试风暴:32 个线程抢同一行(各 200 次)。无退避 vs 随机指数退避(退避基数 0.2 ms)')
rows = []
for name, bo in (('无退避(失败立刻重试)', None), ('随机指数退避', 0.0002)):
    rs = [run(op_optimistic, 32, 200, backoff=bo) for _ in range(2)]
    rows.append((name, f'{statistics.median(r["tps"] for r in rs):.0f}', f'{statistics.mean(statistics.mean(r["att"]) for r in rs):.2f}', f'{statistics.median(pct(r["lat"], 0.99) for r in rs) * 1000:.1f} ms', f'{sum(sum(r["att"]) - len(r["att"]) for r in rs) // 2}'))
table(rows, ['重试策略', '成功/秒', '平均每次成功试几次', '延迟 p99', '白做的尝试(每轮)'])
reset(); shutil.rmtree(TT / 'my_t18', ignore_errors=True)
