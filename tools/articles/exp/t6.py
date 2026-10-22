import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from tcc import *
tee('t6'); reset()
MA = MySQL('t6_acct'); MS = MySQL('t6_stock')
ths = [threading.Thread(target=n.start) for n in (MA, MS)]; [t.start() for t in ths]; [t.join() for t in ths]
for n in (MA, MS): n.q('create database shop')
MA.q('create table account(user_id int primary key, balance int, frozen int, spent int, constraint c1 check (balance >= 0 and frozen >= 0))', db='shop')
MS.q('create table stock(sku varchar(10) primary key, avail int, locked int, sold int, constraint c2 check (avail >= 0 and locked >= 0))', db='shop')
ACC, STK = AccountSvc(MA), StockSvc(MS)
INIT_BAL, INIT_STK = 100000, 100
def reset_data(bal=INIT_BAL, stk=INIT_STK, users=(1,), skus=('sku-1',)):
    MA.q('delete from account', db='shop'); MS.q('delete from stock', db='shop')
    for u in users: MA.q('insert into account values(%s, %s, 0, 0)', (u, bal), db='shop')
    for s in skus: MS.q('insert into stock values(%s, %s, 0, 0)', (s, stk), db='shop')
print(f'账户服务和库存服务各占一个 MySQL 实例(端口 {MA.port}、{MS.port},{MA.q("select version()")[0][0]});TCC 的三个动作是自己写的 Python(tools/articles/tcc.py):账户 Try = 把钱从 balance 挪到 frozen,Confirm = 从 frozen 挪到 spent,Cancel = 从 frozen 挪回 balance;库存同理(avail → locked → sold)。这个版本故意不带 xid 记录和防重复,下一篇再补')
def snap(): return f'账户 (balance, frozen, spent) = {tuple(ACC.row(1))},库存 (avail, locked, sold) = {tuple(STK.row("sku-1"))}'

print('== 一:一次 TCC 事务的三个动作各改了什么:成功路径(Try → Confirm)、取消路径(Try → Cancel)、Try 失败路径(余额不够)')
reset_data(bal=1000, stk=10)
print('  初始:', snap())
r = tcc_order(ACC, STK, 1, 'sku-1', 1, 80, decide='confirm', hold=0, log=lambda m: print('   ', m)); print(f'  → {r}。', snap())
r = tcc_order(ACC, STK, 1, 'sku-1', 1, 80, decide='cancel', log=lambda m: print('   ', m)); print(f'  → {r}。', snap())
MA.q('update account set balance = 50 where user_id = 1', db='shop')
r = tcc_order(ACC, STK, 1, 'sku-1', 1, 80, decide='confirm', log=lambda m: print('   ', m)); print(f'  → {r}(余额 50 买不起 80 的商品)。', snap())

print('== 二:Try 到 Confirm 之间,资源被“业务层预留”而不是被数据库锁住:订单 A 在 Try 之后停 500 ms 再 Confirm,订单 B 同时去买同一个商品、扣同一个账户,看 B 要等多久;同样的场景用 MySQL XA 做对照')
reset_data(bal=10 ** 9, stk=10 ** 6)
def tcc_gap(hold=0.5):
    res = {}
    def a(): tcc_order(ACC, STK, 1, 'sku-1', 1, 80, hold=hold)
    ta = threading.Thread(target=a); ta.start(); time.sleep(hold / 5)
    t0 = time.perf_counter(); r = tcc_order(ACC, STK, 1, 'sku-1', 1, 80); res['b'] = time.perf_counter() - t0; ta.join()
    return res['b'], r
class XAO:
    """同样的订单用 XA 做:两个实例各 XA START/UPDATE/END/PREPARE,hold 之后各 XA COMMIT。"""
    def __init__(self): self.ca, self.cs = ACC.c(), STK.c()
def xa_order(i, hold=0.0, timeout=5):
    ca, cs = ACC.c(), STK.c(); x = f"'xa{i}-{random.random()}'"
    a, s = ca.cursor(), cs.cursor()
    a.execute(f'XA START {x}'); a.execute('update account set balance = balance - 80, spent = spent + 80 where user_id = 1'); a.execute(f'XA END {x}')
    s.execute(f'XA START {x}'); s.execute("update stock set avail = avail - 1, sold = sold + 1 where sku = 'sku-1'"); s.execute(f'XA END {x}')
    a.execute(f'XA PREPARE {x}'); s.execute(f'XA PREPARE {x}')
    if hold: time.sleep(hold)
    a.execute(f'XA COMMIT {x}'); s.execute(f'XA COMMIT {x}')
def xa_gap(hold=0.5):
    ta = threading.Thread(target=lambda: xa_order(1, hold)); ta.start(); time.sleep(hold / 5)
    t0 = time.perf_counter(); xa_order(2); d = time.perf_counter() - t0; ta.join(); return d
rows = []
for hold in (0.0, 0.2, 0.5):
    if hold == 0:
        lat = []
        for _ in range(50): t0 = time.perf_counter(); tcc_order(ACC, STK, 1, 'sku-1', 1, 80); lat.append(time.perf_counter() - t0)
        tb = statistics.median(lat); lat = []
        for i in range(50): t0 = time.perf_counter(); xa_order(i); lat.append(time.perf_counter() - t0)
        xb = statistics.median(lat)
    else:
        tb, _ = tcc_gap(hold); xb = xa_gap(hold)
    rows.append((f'{int(hold * 1000)} ms', ms(tb), ms(xb)))
table(rows, ['订单 A 在中间停多久', '订单 B(TCC)耗时', '订单 B(XA)耗时'])
print('  hold=0 一行是 50 次的中位数,其余是单次测量。TCC 里订单 A 的 Try 在各自的本地事务里已经提交,行锁早就放了;XA 里订单 A 的行锁从 PREPARE 一直握到 COMMIT')

print('== 三:Try 必须在一条语句里“检查并预留”:库存 100,150 个订单用 16 个线程并发抢;对照一个“先 SELECT 看够不够、再 UPDATE 扣”的写法')
def storm(try_fn, n=150, threads=16):
    reset_data(bal=10 ** 9, stk=100); ok = [0]; rej = [0]; lock = threading.Lock(); q = list(range(n))
    def w():
        while True:
            with lock:
                if not q: return
                q.pop()
            try: try_fn(); 
            except Insufficient:
                with lock: rej[0] += 1
            else:
                with lock: ok[0] += 1
    ts = [threading.Thread(target=w) for _ in range(threads)]; [t.start() for t in ts]; [t.join() for t in ts]
    return ok[0], rej[0]
ok, rej = storm(lambda: STK.try_('sku-1', 1))
a, l, s = STK.row('sku-1'); print(f'  条件 UPDATE(avail >= n 写在 WHERE 里,正确的 Try):成功 {ok}、被拒 {rej};库存 avail={a} locked={l} sold={s},avail + locked + sold = {a + l + s}')
def naive_try():
    avail = STK.one("select avail from stock where sku = 'sku-1'")[0]
    if avail < 1: raise Insufficient('x')
    time.sleep(0.001); STK.run("update stock set avail = avail - 1, locked = locked + 1 where sku = 'sku-1'")
MS.q('alter table stock drop check c2', db='shop')
ok, rej = storm(naive_try)
a, l, s = STK.row('sku-1'); print(f'  先 SELECT 再 UPDATE(检查和扣减是两条语句):成功 {ok}、被拒 {rej};库存 avail={a} locked={l} sold={s} —— 多卖了 {ok - 100} 件,avail 变成 {a}')

print('== 四:并发压力下的不变量:4 个线程共 2000 个订单,结局随机(60% Confirm、30% Cancel、10% 管理器在 Try 之后崩溃);另一个线程每 5 ms 采样一次,检查 balance + frozen + spent 和 avail + locked + sold 是否始终等于初始值')
MS.q('delete from stock', db='shop'); MS.q('alter table stock add constraint c2 check (avail >= 0 and locked >= 0)', db='shop')
reset_data(bal=10 ** 7, stk=5000)
stop = threading.Event(); samples = [0]; viol = []
def sampler():
    while not stop.is_set():
        b, f, sp = ACC.row(1); a, l, so = STK.row('sku-1'); samples[0] += 1
        if b + f + sp != 10 ** 7 or a + l + so != 5000: viol.append((b, f, sp, a, l, so))
        time.sleep(0.005)
st = threading.Thread(target=sampler); st.start()
rng = random.Random(4); outcome = {'CONFIRMED': 0, 'CANCELLED': 0, 'ABANDONED': 0, 'REJECTED': 0}; lk = threading.Lock(); decs = [rng.choices(['confirm', 'cancel', 'abandon'], [60, 30, 10])[0] for _ in range(2000)]
def worker(k):
    for i in range(k, 2000, 4):
        r = tcc_order(ACC, STK, 1, 'sku-1', 1, 80, decide=decs[i], hold=rng.random() * 0.003)
        with lk: outcome[r] += 1
ws = [threading.Thread(target=worker, args=(k,)) for k in range(4)]; [w.start() for w in ws]; [w.join() for w in ws]; stop.set(); st.join()
b, f, sp = ACC.row(1); a, l, so = STK.row('sku-1')
print(f'  结局:{outcome};采样 {samples[0]} 次,违反不变量 {len(viol)} 次')
print(f'  最终:账户 balance={b} frozen={f} spent={sp}(frozen = {outcome["ABANDONED"]} 笔崩溃订单 × 80 = {outcome["ABANDONED"] * 80});库存 avail={a} locked={l} sold={so}')

print('== 五:管理器崩溃留下的预留会一直占着库存:库存 100,130 个订单,其中 15% 在 Try 之后崩溃,其余 Confirm;看最后卖出多少、有多少被冻死、有多少人被拒')
reset_data(bal=10 ** 9, stk=100)
rng = random.Random(5); res = {'CONFIRMED': 0, 'ABANDONED': 0, 'REJECTED': 0}
for i in range(130): res[tcc_order(ACC, STK, 1, 'sku-1', 1, 80, decide='abandon' if rng.random() < 0.15 else 'confirm')] += 1
a, l, so = STK.row('sku-1')
print(f'  结局:{res};库存 avail={a} locked={l} sold={so}')
print(f'  {res["REJECTED"]} 个订单因“库存不足”被拒,但库里其实只卖出了 {so} 件,有 {l} 件被崩溃订单的预留占着(没有人会再来 Confirm 或 Cancel)')
print('  朴素版本里 stock 表只有一个总数 locked,没有“这 {} 件是哪个订单的”:想释放只能整体清零。试一下:'.format(l))
def cleanup_demo(drop_check):
    reset_data(bal=10 ** 9, stk=10)
    if drop_check: MS.q('alter table stock drop check c2', db='shop')
    STK.try_('sku-1', 1); ACC.try_(1, 80)                  # 订单 X:Try 完了,Confirm 还在路上
    MS.q("update stock set avail = avail + locked, locked = 0 where sku = 'sku-1'", db='shop')   # “清理程序”把所有 locked 释放掉
    print('  清理程序把 locked 整体释放:', snap().split(',库存')[1].strip(), '(此时订单 X 的预留也被释放了)')
    try: STK.confirm('sku-1', 1)                           # 订单 X 的 Confirm 现在才到
    except Exception as e: print(f'  订单 X 的 Confirm 随后到达:{type(e).__name__} {e.args[0]} {e.args[1][:60]}')
    else: print('  订单 X 的 Confirm 随后到达,执行成功:', snap().split(',库存')[1].strip())
    if drop_check: MS.q('alter table stock add constraint c2 check (avail >= 0 and locked >= 0)', db='shop') if False else None
print('  (a) 表上有 CHECK(locked >= 0) 兜底:')
cleanup_demo(False)
print('  (b) 表上没有这个 CHECK:')
cleanup_demo(True)
MS.q('delete from stock', db='shop'); MS.q('alter table stock add constraint c2 check (avail >= 0 and locked >= 0)', db='shop')

print('== 六:代价:同样的“扣账户 + 扣库存”,单个实例里的本地事务 vs TCC(两个服务,Try + Confirm 共 4 次调用)vs XA(两个实例);各 300 次')
reset_data(bal=10 ** 9, stk=10 ** 6)
SG = MySQL('t6_single').start(); SG.q('create database shop'); SG.q('create table account(user_id int primary key, balance int)', db='shop'); SG.q('create table stock(sku varchar(10) primary key, avail int)', db='shop')
SG.q('insert into account values(1, 1000000000)', db='shop'); SG.q("insert into stock values('sku-1', 1000000)", db='shop')
cg = SG.conn('shop', autocommit=False)
def local_order(i):
    cur = cg.cursor(); cur.execute('update account set balance = balance - 80 where user_id = 1'); cur.execute("update stock set avail = avail - 1 where sku = 'sku-1'"); cg.commit()
cnt = {'tcc': 0}
def tcc_one(i): tcc_order(ACC, STK, 1, 'sku-1', 1, 80)
def xa_one(i): xa_order(i)
cases = (('本地事务(一个实例)', local_order, '1 次提交'), ('TCC(两个服务)', tcc_one, '4 次服务调用,4 次提交'), ('XA(两个实例)', xa_one, '2 次 PREPARE + 2 次 COMMIT'))
acc_l = {n: [] for n, _, _ in cases}
for rnd in range(3):
    for n, fn, _ in cases:
        for i in range(100):
            t0 = time.perf_counter(); fn(rnd * 100 + i + 1000); acc_l[n].append(time.perf_counter() - t0)
rows = []; base = None
for n, fn, note in cases:
    l = acc_l[n]; med = statistics.median(l); base = base or med
    rows.append((n, note, ms(med), ms(sorted(l)[int(len(l) * 0.99) - 1]), f'{med / base:.1f}x'))
table(rows, ['写法', '提交动作', '中位数', 'p99', '相对本地事务'])
print('  TCC 没有协调者写决定日志、没有 prepare 状态,每个动作都是普通的单语句提交,所以比 XA 便宜;代价是业务代码要为每个服务写 Try / Confirm / Cancel 三套逻辑,并且自己负责防重复、防悬挂(下一篇)')
cg.close(); reset()
for n in ('my_t6_acct', 'my_t6_stock', 'my_t6_single'): shutil.rmtree(TT / n, ignore_errors=True)
