import sys, os, zlib, inspect; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import pymysql
tee('t32'); reset()
INST = {n: MySQL(f't32_{n}') for n in ('S', 'O', 'K', 'W')}
ths = [threading.Thread(target=m.start) for m in INST.values()]; [t.start() for t in ths]; [t.join() for t in ths]
S, O, K, W = INST['S'], INST['O'], INST['K'], INST['W']
def schema(m, tables):
    m.q('create database if not exists shop')
    for t in tables: m.q(t, db='shop')
T_ORD = 'create table orders(id varchar(40) primary key, status varchar(12))'
T_STK = ['create table stock(sku varchar(10) primary key, qty int)', 'create table reservations(order_id varchar(40) primary key)']
T_WAL = ['create table wallet(user_id int primary key, balance bigint)', 'create table payments(order_id varchar(40) primary key)']
schema(S, [T_ORD, *T_STK, *T_WAL]); schema(O, [T_ORD, 'create table saga_log(id varchar(40) primary key, status varchar(14), step varchar(10))']); schema(K, T_STK); schema(W, T_WAL)
# 订单 + 库存合并的变体需要 O 里也有库存表
for t in T_STK: O.q(t, db='shop')
TL = threading.local()
def c(m):
    d = getattr(TL, 'd', None)
    if d is None: d = TL.d = {}
    if m.name not in d: d[m.name] = m.conn('shop', autocommit=False)
    return d[m.name]
for m in INST.values(): m.name = m.d.name
class Transient(Exception): pass
class Rejected(Exception): pass
def idx(oid): return oid.rsplit('-', 1)[-1]                      # 失败只由订单序号决定,五种实现里同一个序号的订单遇到的失败完全一样
def tf(oid, step, attempt): return zlib.crc32(f'{idx(oid)}|{step}|{attempt}'.encode()) % 1000 < 30       # 每次“远程调用”有 3% 的概率临时失败(调用发出之前就失败了,没有执行)
POOR_ON = [False]
def is_poor(oid): return POOR_ON[0] and zlib.crc32(f'poor|{idx(oid)}'.encode()) % 1000 < 20                           # 2% 的订单金额超过余额(业务失败)
def amount(oid): return 10 ** 10 if is_poor(oid) else 80
COMMITS = [0]; clk = threading.Lock()
def commit(conn):
    conn.commit()
    with clk: COMMITS[0] += 1
def reset_data(clean=True):
    for m in (S, O, K, W):
        for t in ('orders', 'reservations', 'payments', 'saga_log'):
            try: m.q(f'delete from {t}', db='shop')
            except Exception: pass
    for m in (S, K, O): m.q('delete from stock', db='shop'); m.q("insert into stock values ('sku', 10000000)", db='shop')
    for m in (S, W): m.q('delete from wallet', db='shop'); m.q('insert into wallet values (1, 1000000000)', db='shop')

# ---------- 四种(加一种)实现:同一个业务“下单 = 建订单 + 扣库存 + 扣余额”----------
def place_mono(oid, fail=True):
    for attempt in range(3):
        cn = c(S); cur = cn.cursor()
        try:
            cur.execute("insert into orders values (%s, 'CONFIRMED')", (oid,))
            if fail and tf(oid, 'stock', attempt): raise Transient()
            cur.execute('insert into reservations values (%s)', (oid,)); cur.execute("update stock set qty = qty - 1 where sku = 'sku' and qty >= 1")
            if fail and tf(oid, 'wallet', attempt): raise Transient()
            cur.execute('insert into payments values (%s)', (oid,)); cur.execute('update wallet set balance = balance - %s where user_id = 1 and balance >= %s', (amount(oid), amount(oid)))
            if cur.rowcount == 0: raise Rejected()
            commit(cn); return 'OK'
        except Transient: cn.rollback()
        except Rejected: cn.rollback(); return 'REJECTED'
    return 'ERROR'
def place_naive(oid, fail=True):
    try:
        co = c(O); co.cursor().execute("insert into orders values (%s, 'CONFIRMED')", (oid,)); commit(co)
        if fail and tf(oid, 'stock', 0): raise Transient()
        ck = c(K); cur = ck.cursor(); cur.execute('insert into reservations values (%s)', (oid,)); cur.execute("update stock set qty = qty - 1 where sku = 'sku' and qty >= 1"); commit(ck)
        if fail and tf(oid, 'wallet', 0): raise Transient()
        cw = c(W); cur = cw.cursor(); cur.execute('insert into payments values (%s)', (oid,)); cur.execute('update wallet set balance = balance - %s where user_id = 1 and balance >= %s', (amount(oid), amount(oid)))
        if cur.rowcount == 0: cw.rollback(); return 'REJECTED'
        commit(cw); return 'OK'
    except Transient: return 'ERROR'
XID = [0]
def place_xa(oid, fail=True):
    for attempt in range(3):
        XID[0] += 1; x = f"'x{threading.get_ident()}-{XID[0]}'"; started = []; prepared = []
        try:
            for name, m in (('O', O), ('K', K), ('W', W)):
                cur = c(m).cursor(); cur.execute(f'XA START {x}'); started.append((m, cur))
                if name == 'O': cur.execute("insert into orders values (%s, 'CONFIRMED')", (oid,))
                if name == 'K':
                    if fail and tf(oid, 'stock', attempt): raise Transient()
                    cur.execute('insert into reservations values (%s)', (oid,)); cur.execute("update stock set qty = qty - 1 where sku = 'sku' and qty >= 1")
                if name == 'W':
                    if fail and tf(oid, 'wallet', attempt): raise Transient()
                    cur.execute('insert into payments values (%s)', (oid,)); cur.execute('update wallet set balance = balance - %s where user_id = 1 and balance >= %s', (amount(oid), amount(oid)))
                    if cur.rowcount == 0: raise Rejected()
            for m, cur in started: cur.execute(f'XA END {x}')
            for m, cur in started: cur.execute(f'XA PREPARE {x}'); prepared.append((m, cur))
            for m, cur in started: cur.execute(f'XA COMMIT {x}')
            with clk: COMMITS[0] += 3
            return 'OK'
        except (Transient, Rejected) as e:
            for m, cur in started:
                try:
                    if (m, cur) in prepared: cur.execute(f'XA ROLLBACK {x}')
                    else: cur.execute(f'XA END {x}'); cur.execute(f'XA ROLLBACK {x}')
                except Exception:
                    try: cur.execute(f'XA ROLLBACK {x}')
                    except Exception: pass
            if isinstance(e, Rejected): return 'REJECTED'
    return 'ERROR'
def retry(oid, step, fn, tries=4, base=0.002):
    for a in range(tries):
        if tf(oid, step, a): time.sleep(base * 2 ** a); continue
        return fn()
    raise Transient()
STUCK = []
def place_saga(oid, fail=True):
    co = c(O); cur = co.cursor(); cur.execute("insert into orders values (%s, 'PENDING')", (oid,)); cur.execute("insert into saga_log values (%s, 'RUNNING', 'reserve')", (oid,)); commit(co)
    def reserve():
        ck = c(K); cu = ck.cursor(); cu.execute('insert ignore into reservations values (%s)', (oid,))
        if cu.rowcount: cu.execute("update stock set qty = qty - 1 where sku = 'sku' and qty >= 1")
        commit(ck)
    def release():
        ck = c(K); cu = ck.cursor(); cu.execute('delete from reservations where order_id = %s', (oid,))
        if cu.rowcount: cu.execute("update stock set qty = qty + 1 where sku = 'sku'")
        commit(ck)
    def charge():
        cw = c(W); cu = cw.cursor(); cu.execute('insert ignore into payments values (%s)', (oid,))
        if cu.rowcount:
            cu.execute('update wallet set balance = balance - %s where user_id = 1 and balance >= %s', (amount(oid), amount(oid)))
            if cu.rowcount == 0: cw.rollback(); raise Rejected()
        commit(cw)
    def finish(st):
        co = c(O); cu = co.cursor(); cu.execute('update orders set status = %s where id = %s', (st, oid)); cu.execute("update saga_log set status = %s, step = 'done' where id = %s", (st, oid)); commit(co)
    try:
        if fail: retry(oid, 'stock', reserve)
        else: reserve()
        try:
            if fail: retry(oid, 'wallet', charge)
            else: charge()
        except Rejected:
            for t in range(8):
                try: retry(oid, 'release', release, tries=2); break
                except Transient: continue
            else: STUCK.append(oid); return 'STUCK'
            finish('CANCELLED'); return 'REJECTED'
        except Transient:
            for t in range(8):
                try: retry(oid, 'release', release, tries=2); break
                except Transient: continue
            else: STUCK.append(oid); return 'STUCK'
            finish('CANCELLED'); return 'ERROR'
        finish('CONFIRMED'); return 'OK'
    except Transient:
        finish('CANCELLED'); return 'ERROR'
def place_merged(oid, fail=True):
    """订单和库存在同一个服务的库里(O),只有支付在另一个库(W):下单 + 预留库存是一个本地事务,支付是 Saga 里仅剩的一个远程步骤。"""
    co = c(O); cu = co.cursor(); cu.execute("insert into orders values (%s, 'PENDING')", (oid,)); cu.execute('insert into reservations values (%s)', (oid,)); cu.execute("update stock set qty = qty - 1 where sku = 'sku' and qty >= 1"); commit(co)
    def charge():
        cw = c(W); cu = cw.cursor(); cu.execute('insert ignore into payments values (%s)', (oid,))
        if cu.rowcount:
            cu.execute('update wallet set balance = balance - %s where user_id = 1 and balance >= %s', (amount(oid), amount(oid)))
            if cu.rowcount == 0: cw.rollback(); raise Rejected()
        commit(cw)
    def fin(st, release):
        co = c(O); cu = co.cursor(); cu.execute('update orders set status = %s where id = %s', (st, oid))
        if release: cu.execute('delete from reservations where order_id = %s', (oid,)); cu.execute("update stock set qty = qty + 1 where sku = 'sku'")
        commit(co)
    try:
        if fail: retry(oid, 'wallet', charge)
        else: charge()
        fin('CONFIRMED', False); return 'OK'
    except Rejected: fin('CANCELLED', True); return 'REJECTED'
    except Transient: fin('CANCELLED', True); return 'ERROR'

VARIANTS = [('mono', '单体:一个库、一个本地事务', place_mono, 'S'), ('naive', '拆成三个库,各自提交,没有保护', place_naive, 'ONKW'), ('xa', '拆成三个库 + XA(两阶段提交)', place_xa, 'ONKW'), ('saga', '拆成三个库 + Saga(状态表 + 补偿 + 重试)', place_saga, 'ONKW'), ('merged', '订单与库存合并成一个库,只有支付在另一个库(Saga 只剩支付一步)', place_merged, 'ONW')]
print(f'同一个业务“下单 = 建订单 + 扣库存 + 扣余额”,五种实现,跑在 4 个独立的 MySQL {S.q("select version()")[0][0]} 实例上(S = 单体;O / K / W = 订单库 / 库存库 / 钱包库);失败按订单号确定地注入(每次远程调用 3% 临时失败——调用发出之前就失败,没有执行;2% 的订单金额超过余额,业务上必败),五种实现面对完全相同的失败;客户端是 PyMySQL,每个线程每个库一个连接')

print('== 一:没有任何失败时的代价(没有临时失败,也没有“余额不足”的订单):400 个订单单线程顺序下单的延迟,以及每个订单用了几次提交(COMMIT / XA COMMIT 的次数,XA 的一次全局提交算 3 次分支提交)')
rows = []
for key, name, fn, _ in VARIANTS:
    reset_data(); COMMITS[0] = 0; lat = []
    for i in range(400): t0 = time.perf_counter(); fn(f'c-{key}-{i}', fail=False); lat.append(time.perf_counter() - t0)
    rows.append((name, f'{statistics.median(lat) * 1000:.2f} ms', f'{sorted(lat)[int(len(lat) * 0.99) - 1] * 1000:.2f} ms', f'{COMMITS[0] / 400:.1f}'))
table(rows, ['实现', '延迟中位数', 'p99', '每个订单的提交次数'])

print('== 二:8 个线程并发下单(每个线程 100 单,没有失败):订单/秒(3 轮中位数)')
rows = []; base = None
def conc(fn, key):
    reset_data(); lk = threading.Lock()
    def w(k):
        for i in range(100): fn(f'p-{key}-{k}-{i}', fail=False)
    t0 = time.perf_counter(); ts = [threading.Thread(target=w, args=(k,)) for k in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]; return 800 / (time.perf_counter() - t0)
res = {k: [] for k, *_ in VARIANTS}
for rnd in range(3):
    for key, name, fn, _ in VARIANTS: res[key].append(conc(fn, key))
for key, name, fn, _ in VARIANTS:
    v = sorted(res[key]); base = base or statistics.median(v); rows.append((name, f'{statistics.median(v):.0f}', f'{v[0]:.0f} ~ {v[-1]:.0f}', f'{statistics.median(v) / base:.2f}x'))
table(rows, ['实现', '订单/秒(3 轮中位数)', '3 轮范围', '相对单体'])

print('== 三:有失败时的结果(2000 个订单、单线程):每个订单的结局,以及全部做完之后跨库对账的结果。对账的口径:订单状态是 CONFIRMED 的,库存预留和扣款都必须存在;预留或扣款存在而订单不是 CONFIRMED 的,是泄漏')
def audit(key):
    if key == 'mono': o, k, w = S, S, S
    elif key == 'merged': o, k, w = O, O, W
    else: o, k, w = O, K, W
    orders = {r[0]: r[1] for r in o.q('select id, status from orders', db='shop')}; res = {r[0] for r in k.q('select order_id from reservations', db='shop')}; pay = {r[0] for r in w.q('select order_id from payments', db='shop')}
    conf = {i for i, s in orders.items() if s == 'CONFIRMED'}
    bad_conf = len([i for i in conf if i not in res or i not in pay]); leak_res = len([i for i in res if i not in conf]); leak_pay = len([i for i in pay if i not in conf]); pending = len([1 for s in orders.values() if s == 'PENDING'])
    return len(orders), len(conf), bad_conf, leak_res, leak_pay, pending
rows = []; info = {}; POOR_ON[0] = True
for key, name, fn, _ in VARIANTS:
    reset_data(); STUCK.clear(); out = {}
    for i in range(2000): r = fn(f'f-{key}-{i}', fail=True); out[r] = out.get(r, 0) + 1
    n, conf, bad, lr, lp, pend = audit(key); info[key] = (out, n, conf, bad, lr, lp, pend)
    rows.append((name, out.get('OK', 0), out.get('REJECTED', 0), out.get('ERROR', 0) + out.get('STUCK', 0), n, bad, lr + lp, pend))
table(rows, ['实现', '下单成功', '业务拒绝(余额不足)', '失败 / 卡住', '库里有记录的订单', '订单已确认却缺预留或扣款', '预留或扣款泄漏(订单不是 CONFIRMED)', '停在 PENDING 的订单'])
print(f'  Saga 里补偿重试用完仍没释放库存、停在“卡住”的:{len(STUCK)} 个(要靠恢复 / 人工;没有失败注入的恢复扫描能把它们收尾,见第 30 篇)')
print('  单体和 XA 失败时整体回滚,什么都不留;朴素拆分在中间步骤失败(临时失败、余额不足)时,前面已经提交的步骤没有人撤销;Saga 靠补偿把它们撤回,代价是中间状态对外可见一小段时间')

print('== 四:代码量与组件:这五个实现函数(含各自的辅助步骤)的有效代码行数,以及它们额外依赖的东西')
def loc(*fns): return sum(1 for f in fns for l in inspect.getsource(f).splitlines() if l.strip() and not l.strip().startswith('#'))
rows = [('单体', loc(place_mono), '0 个额外的表,1 个库'), ('朴素拆分', loc(place_naive), '3 个库,没有额外的表'), ('XA', loc(place_xa), '3 个库 + 数据库对 XA 的支持(prepared 事务要有人收尾,见第 3、5 篇)'), ('Saga', loc(place_saga, retry), '3 个库 + saga_log 表 + 重试 / 补偿逻辑;生产里还需要恢复守护进程和对账(第 30、16 篇)'), ('订单 + 库存合并', loc(place_merged, retry), '2 个库 + 只剩支付一步需要重试 / 补偿')]
table(rows, ['实现', '有效代码行数(Python,本实验里的版本)', '额外依赖'])
print('  行数只是这几个函数在本实验里的写法,不是任何框架的真实工作量;但相对大小能说明:每多拆一个库,就要多写一段“这一步失败怎么办”')
for m in INST.values(): m.stop()
reset(); [shutil.rmtree(TT / f'my_t32_{n}', ignore_errors=True) for n in ('S', 'O', 'K', 'W')]
