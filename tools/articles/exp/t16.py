import sys, os, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import pymysql
tee('t16'); reset()
A = MySQL('t16_ord'); B = MySQL('t16_pay'); ths = [threading.Thread(target=n.start) for n in (A, B)]; [t.start() for t in ths]; [t.join() for t in ths]
for n in (A, B): n.q('create database shop')
A.q('create table orders(id bigint primary key, amount int, status varchar(10), updated_at datetime, key idx_upd (updated_at))', db='shop')
B.q('create table payments(id bigint auto_increment primary key, order_id bigint, amount int, status varchar(10) default "PAID", updated_at datetime, key idx_oid (order_id), key idx_upd (updated_at))', db='shop')
print(f'两个独立的 MySQL {A.q("select version()")[0][0]}:订单库(orders)和支付库(payments);规则:订单状态是 PAID 的,支付库里必须有且只有一条金额相同的 payments;订单是 CANCELLED 的,支付库里不该有这个订单的 payments')
NOW = datetime.datetime.now().replace(microsecond=0)
def build(n, seed=16, inject=True):
    """造 n 个订单、对应的支付;按固定比例注入四类分歧,返回 {类型: [order_id...]}。"""
    for t, node in (('orders', A), ('payments', B)): node.q(f'truncate table {t}', db='shop')
    rng = random.Random(seed); orders = []; pays = []
    for i in range(1, n + 1):
        st = 'PAID' if rng.random() < 0.9 else 'CANCELLED'; upd = NOW - datetime.timedelta(seconds=rng.randrange(86400)); orders.append((i, 100 + i % 50, st, upd))
        if st == 'PAID': pays.append((i, 100 + i % 50, upd + datetime.timedelta(seconds=rng.randrange(1, 4))))
    inj = {'丢失(订单已付,没有支付)': [], '重复(同一订单两条支付)': [], '金额不一致': [], '孤儿(有支付、订单不存在)': []}
    if inject:
        paid = [o[0] for o in orders if o[2] == 'PAID']; rng.shuffle(paid); k = lambda r: int(len(paid) * r)
        lost, dup, mism = set(paid[:k(0.01)]), set(paid[k(0.01):k(0.015)]), set(paid[k(0.015):k(0.02)])
        pays2 = []
        for (oid, amt, upd) in pays:
            if oid in lost: continue
            if oid in mism: amt += 1
            pays2.append((oid, amt, upd))
            if oid in dup: pays2.append((oid, amt, upd + datetime.timedelta(seconds=2)))
        orphans = [n + 1 + j for j in range(int(len(paid) * 0.003))]
        for oid in orphans: pays2.append((oid, 100, NOW - datetime.timedelta(seconds=rng.randrange(86400))))
        pays = pays2; inj['丢失(订单已付,没有支付)'] = sorted(lost); inj['重复(同一订单两条支付)'] = sorted(dup); inj['金额不一致'] = sorted(mism); inj['孤儿(有支付、订单不存在)'] = orphans
    for node, tbl, rows, sql in ((A, 'orders', orders, 'insert into orders values (%s, %s, %s, %s)'), (B, 'payments', pays, 'insert into payments(order_id, amount, updated_at) values (%s, %s, %s)')):
        c = node.conn('shop', autocommit=False); cur = c.cursor()
        for i in range(0, len(rows), 10000): cur.executemany(sql, rows[i:i + 10000]); c.commit()
        c.close()
    return inj
def full_reconcile():
    """全量对账:两边各按订单号排序流式读出(服务端游标),做归并比较。返回 {类型: set(order_id)}。"""
    ca = A.conn('shop', cursorclass=pymysql.cursors.SSCursor); cb = B.conn('shop', cursorclass=pymysql.cursors.SSCursor)
    oa = ca.cursor(); ob = cb.cursor()
    oa.execute("select id, amount from orders where status = 'PAID' order by id"); ob.execute('select order_id, count(*), min(amount), max(amount) from payments group by order_id order by order_id')
    out = {'丢失(订单已付,没有支付)': set(), '重复(同一订单两条支付)': set(), '金额不一致': set(), '孤儿(有支付、订单不存在)': set()}
    a = oa.fetchone(); b = ob.fetchone(); scanned = 0
    while a is not None or b is not None:
        scanned += 1
        if b is None or (a is not None and a[0] < b[0]): out['丢失(订单已付,没有支付)'].add(a[0]); a = oa.fetchone()
        elif a is None or b[0] < a[0]:                                                       # 支付有、订单(PAID)没有:可能订单不存在,也可能订单是 CANCELLED
            out['孤儿(有支付、订单不存在)'].add(b[0]); b = ob.fetchone()
        else:
            if b[1] > 1: out['重复(同一订单两条支付)'].add(a[0])
            elif b[2] != a[1]: out['金额不一致'].add(a[0])
            a = oa.fetchone(); b = ob.fetchone()
    ca.close(); cb.close(); return out, scanned
def show_cmp(inj, found):
    rows = []
    for k in inj:
        i = set(inj[k]); f = found[k]; rows.append((k, len(i), len(f), len(i & f), len(f - i), len(i - f)))
    table(rows, ['分歧类型', '注入的', '对账报出的', '其中命中', '误报(多报)', '漏报'])

print('== 一:全量对账:10 万个订单,按固定比例注入四类分歧(丢失 1%、重复 0.5%、金额不一致 0.5%、孤儿约 0.27%),两边各按订单号排序流式读出再归并比较')
inj = build(100000); t0 = time.perf_counter(); found, scanned = full_reconcile(); dt = time.perf_counter() - t0
print(f'  订单库 {A.q("select count(*) from orders", db="shop")[0][0]} 行(PAID {A.q("select count(*) from orders where status = \'PAID\'", db="shop")[0][0]}),支付库 {B.q("select count(*) from payments", db="shop")[0][0]} 行;归并比较了 {scanned} 个订单号,用时 {dt:.2f} s')
show_cmp(inj, found)
print('  (孤儿的判定里会混进“订单是 CANCELLED 但支付库里还有支付”的订单——本数据里没有这种,所以误报为 0)')

print('== 二:增量对账(只比 updated_at 落在最近一个窗口里的行):窗口之外的分歧发现不了,窗口边缘还会出误报;支付服务的时钟比订单服务慢 5 分钟时更糟')
def window_reconcile(hours, skew_min=0):
    cut = NOW - datetime.timedelta(hours=hours)
    o = {r[0]: r[1] for r in A.q("select id, amount from orders where status = 'PAID' and updated_at >= %s", (cut,), db='shop')}
    p = {}
    # 支付库时钟慢 skew_min 分钟 = 支付行上盖的时间比真实时间早 skew_min 分钟;两边用同一个时间点做窗口
    for r in B.q('select order_id, count(*), min(amount), max(amount) from payments where updated_at - interval %s minute >= %s group by order_id', (skew_min, cut), db='shop'): p[r[0]] = r
    out = {k: set() for k in inj}
    for oid, amt in o.items():
        if oid not in p: out['丢失(订单已付,没有支付)'].add(oid)
        elif p[oid][1] > 1: out['重复(同一订单两条支付)'].add(oid)
        elif p[oid][2] != amt: out['金额不一致'].add(oid)
    for oid in p:
        if oid not in o: out['孤儿(有支付、订单不存在)'].add(oid)
    return out
rows = []
alln = sum(len(v) for v in inj.values())
for hours, skew in ((1, 0), (6, 0), (24, 0), (6, 5)):
    f = window_reconcile(hours, skew); tot_found = sum(len(f[k] & set(inj[k])) for k in inj); fp = sum(len(f[k] - set(inj[k])) for k in inj)
    rows.append((f'最近 {hours} 小时' + (f'(支付库时钟慢 {skew} 分钟,支付行盖的时间比真实时间早 {skew} 分钟)' if skew else ''), f'{tot_found} / {alln}', f'{tot_found / alln * 100:.0f}%', fp))
table(rows, ['对账窗口', '发现的真分歧', '召回率', '误报(多报)'])
print('  窗口外的分歧永远发现不了;窗口边缘上订单在窗口里、而支付的时间戳(晚了几秒,或者因为时钟慢了几分钟)落在窗口外,会被报成“丢失”;所以增量对账要有重叠窗口,并定期做全量')

print('== 三:业务还在写入时对账:订单提交之后 80 ms 支付才提交(正常的延迟),此时对账会把“正在途中”的订单报成丢失;只对“已经足够老”的行下结论(宽限期)可以消除这类误报')
build(20000, seed=17, inject=False)
stop = threading.Event(); made = [0]
def writer():
    ca = A.conn('shop'); cb = B.conn('shop'); i = 20001; rng = random.Random(1)
    while not stop.is_set():
        now = datetime.datetime.now().replace(microsecond=0); ca.cursor().execute("insert into orders values (%s, 100, 'PAID', %s)", (i, now)); time.sleep(0.08)
        cb.cursor().execute('insert into payments(order_id, amount, updated_at) values (%s, 100, now())', (i,)); i += 1; made[0] += 1; time.sleep(0.01)
    ca.close(); cb.close()
th = threading.Thread(target=writer); th.start(); time.sleep(4.0)             # 先让写入线程跑一会儿,积累一些新订单
def recon_new(grace):
    ca = A.conn('shop'); cb = B.conn('shop'); cur = ca.cursor(); cur.execute('select now(3)'); now = cur.fetchone()[0]
    lim = now - datetime.timedelta(seconds=grace)
    cur.execute("select id from orders where status = 'PAID' and id > 20000 and updated_at <= %s", (lim,)); ids = [r[0] for r in cur.fetchall()]
    cb2 = cb.cursor(); miss = 0
    for i in ids:
        cb2.execute('select 1 from payments where order_id = %s', (i,))
        if cb2.fetchone() is None: miss += 1
    ca.close(); cb.close(); return len(ids), miss
rows = []
for grace in (0, 1, 3):
    rs = []
    for _ in range(8): rs.append(recon_new(grace)); time.sleep(0.4)
    rows.append((f'宽限期 {grace} 秒', f'{statistics.mean(r[0] for r in rs):.0f}', f'{statistics.mean(r[1] for r in rs):.1f}', max(r[1] for r in rs)))
stop.set(); th.join()
table(rows, ['对账策略', '每次检查的新订单数(平均)', '每次误报“丢失”(平均)', '最多一次误报'])
print(f'  写入线程这段时间一共产生了 {made[0]} 个订单,所有订单的支付最终都落地了(没有真实分歧),所以这里的“丢失”全是误报;宽限期换来 0 误报,代价是真正的分歧要等宽限期之后才能发现')

print('== 四:修复:以订单库为准,写成幂等的修复动作:丢失 → 补一条支付;重复 → 把多余的标成 REFUNDED;金额不一致 → 按订单金额更正;孤儿 → 标成 REFUNDED。修完再对一次账;再跑一遍修复看会不会重复动手')
inj = build(100000); found, _ = full_reconcile()
def repair(found):
    ca = A.conn('shop'); cb = B.conn('shop', autocommit=False); cur = cb.cursor(); acts = {k: 0 for k in found}
    amt = {r[0]: r[1] for r in ca.cursor().__class__ and []}
    ca2 = ca.cursor()
    for k in found:
        ids = sorted(found[k])
        for j in range(0, len(ids), 1000):
            chunk = ids[j:j + 1000]; ph = ','.join(['%s'] * len(chunk))
            if k.startswith('丢失'):
                ca2.execute(f'select id, amount from orders where id in ({ph})', chunk)
                for oid, a in ca2.fetchall():
                    cur.execute('insert into payments(order_id, amount, updated_at) select %s, %s, now() from dual where not exists (select 1 from payments where order_id = %s)', (oid, a, oid)); acts[k] += cur.rowcount
            elif k.startswith('重复'):
                for oid in chunk:
                    cur.execute("update payments set status = 'REFUNDED' where order_id = %s and status = 'PAID' and id <> (select m from (select min(id) m from payments where order_id = %s and status = 'PAID') t)", (oid, oid)); acts[k] += cur.rowcount
            elif k.startswith('金额'):
                ca2.execute(f'select id, amount from orders where id in ({ph})', chunk)
                for oid, a in ca2.fetchall():
                    cur.execute("update payments set amount = %s where order_id = %s and status = 'PAID' and amount <> %s", (a, oid, a)); acts[k] += cur.rowcount
            else:
                cur.execute(f"update payments set status = 'REFUNDED' where order_id in ({ph}) and status = 'PAID'", chunk); acts[k] += cur.rowcount
        cb.commit()
    ca.close(); cb.close(); return acts
t0 = time.perf_counter(); acts = repair(found); dt = time.perf_counter() - t0
print(f'  第一次修复(用时 {dt:.2f} s)各类动作数:{acts}')
# 对账要把 REFUNDED 的支付当作“不存在”:重新对账时只看 PAID 的支付
def full_reconcile_paid():
    ca = A.conn('shop', cursorclass=pymysql.cursors.SSCursor); cb = B.conn('shop', cursorclass=pymysql.cursors.SSCursor); oa = ca.cursor(); ob = cb.cursor()
    oa.execute("select id, amount from orders where status = 'PAID' order by id"); ob.execute("select order_id, count(*), min(amount), max(amount) from payments where status = 'PAID' group by order_id order by order_id")
    out = {k: set() for k in inj}; a = oa.fetchone(); b = ob.fetchone()
    while a is not None or b is not None:
        if b is None or (a is not None and a[0] < b[0]): out['丢失(订单已付,没有支付)'].add(a[0]); a = oa.fetchone()
        elif a is None or b[0] < a[0]: out['孤儿(有支付、订单不存在)'].add(b[0]); b = ob.fetchone()
        else:
            if b[1] > 1: out['重复(同一订单两条支付)'].add(a[0])
            elif b[2] != a[1]: out['金额不一致'].add(a[0])
            a = oa.fetchone(); b = ob.fetchone()
    ca.close(); cb.close(); return out
after = full_reconcile_paid(); print(f'  修复之后重新对账(只看状态为 PAID 的支付):{ {k: len(v) for k, v in after.items()} }')
acts2 = repair(after); print(f'  再跑一遍修复(基于重新对账的结果):各类动作数 {acts2} —— 修复是幂等的,没有更多可做的')

print('== 五:全量对账的成本随规模的变化(每种规模各对一次,两边都是同样的分歧比例)')
rows = []
for n in (20000, 100000, 300000):
    build(n, seed=18); t0 = time.perf_counter(); f, sc = full_reconcile(); dt = time.perf_counter() - t0
    rows.append((n, sc, f'{dt:.2f} s', f'{n / dt:.0f}', sum(len(v) for v in f.values())))
table(rows, ['订单数', '归并比较的订单号数', '用时', '订单/秒', '发现的分歧总数'])
print('  用时随订单数大致线性增长;只比较了金额与笔数,没有比较其它字段')
reset()
for n in ('my_t16_ord', 'my_t16_pay'): shutil.rmtree(TT / n, ignore_errors=True)
