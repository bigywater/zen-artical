import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from saga import *
tee('t9'); reset()
M = MySQL('t9').start(); shop = Shop(M)
M.q('create table notifications(id int auto_increment primary key, order_id varchar(40), text varchar(60))', db='order_db')
M.q('create database saga_db'); M.q("create table saga_log(id varchar(40) primary key, status varchar(20), attempts int default 0, last_error varchar(100))", db='saga_db')
M.q("create table manual_queue(id int auto_increment primary key, saga_id varchar(40), step varchar(20), error varchar(100), attempts int, created datetime default current_timestamp)", db='saga_db')
print(f'三个服务各读写自己的库(同一个 MySQL {M.q("select version()")[0][0]} 里的 order_db / stock_db / pay_db),另有编排器自己的 saga_db(saga_log、manual_queue);故障用 shop.inject() 在服务调用里按次数或概率注入;每个本地动作用 order_id 做主键,是幂等的')
def snap():
    s = shop.snapshot(); return f'订单 {s["orders"]},库存 {s["stock"]}(预留中 {s["reserved"]}),余额 {s["balance"]}(已扣款 {s["charged"]} 笔)'

print('== 一:补偿也会失败:支付失败后补偿“释放库存”,释放这一步恰好遇到临时错误;朴素编排器 try/except 之后继续往下走')
shop.reset(stock=100, balance=50)
def naive_saga(oid):
    shop.order_create(oid); shop.stock_reserve(oid, 'sku-1', 1)
    try: shop.pay_charge(oid, 1, 80)
    except StepFailed:
        try: shop.stock_release(oid)
        except Exception as e: print(f'  补偿 stock_release 失败:{type(e).__name__} {e},编排器记了一行日志就往下走')
        shop.order_set(oid, 'CANCELLED'); return 'CANCELLED'
shop.inject('stock_release', times=1)
print('  结果:', naive_saga('o-1'), snap())
leak = M.q("select r.order_id from stock_db.reservations r join order_db.orders o on o.id = r.order_id where r.status = 'RESERVED' and o.status = 'CANCELLED'")
print(f'  对账:订单已经 CANCELLED 但库存预留还是 RESERVED 的有 {len(leak)} 笔 {[r[0] for r in leak]} —— 这件商品被一个已取消的订单占着')
print('  放大到 400 单:20% 支付失败,每次释放库存有 10% 概率遇到临时错误:')
shop.reset(stock=10000, balance=10 ** 9); rng = random.Random(9); fail_pay = fail_rel = 0
for i in range(400):
    poor = rng.random() < 0.2; shop.faults.clear()
    if rng.random() < 0.1: shop.inject('stock_release', times=1)
    if poor: M.q('update wallet set balance = 50 where user_id = 1', db='pay_db')
    else: M.q('update wallet set balance = 10000000 where user_id = 1', db='pay_db')
    oid = f'n-{i}'; shop.order_create(oid); shop.stock_reserve(oid, 'sku-1', 1)
    try: shop.pay_charge(oid, 1, 80); shop.order_set(oid, 'CONFIRMED')
    except StepFailed:
        fail_pay += 1
        try: shop.stock_release(oid)
        except Exception: fail_rel += 1
        shop.order_set(oid, 'CANCELLED')
leak = M.q("select count(*) from stock_db.reservations r join order_db.orders o on o.id = r.order_id where r.status = 'RESERVED' and o.status = 'CANCELLED'")[0][0]
print(f'  400 单里支付失败 {fail_pay} 单,其中补偿失败 {fail_rel} 单;对账出来“已取消但仍占库存”的 {leak} 单(期望值约 {400 * 0.2 * 0.1:.0f})')

print('== 二:补偿要重试到成功、并且补偿本身必须幂等')
shop.reset(stock=100, balance=10 ** 6)
shop.order_create('o-r'); shop.stock_reserve('o-r', 'sku-1', 1); shop.inject('stock_release', times=3)
def comp_retry(fn, base=0.05, factor=2.0, cap=1.0, max_attempts=100, log=None):
    t0 = time.perf_counter(); d = base
    for k in range(1, max_attempts + 1):
        try: r = fn(); (log or print)(f'    第 {k} 次:成功({r}),距开始 {ms(time.perf_counter() - t0)}'); return k, time.perf_counter() - t0
        except Transient as e:
            (log or print)(f'    第 {k} 次:临时错误,{ms(d)} 后重试,距开始 {ms(time.perf_counter() - t0)}'); time.sleep(d); d = min(d * factor, cap)
    raise RuntimeError('放弃')
print('  前 3 次调用失败,指数退避(50 ms 起,每次翻倍):'); comp_retry(lambda: shop.stock_release('o-r'))
print('  结果:', snap())
print('  服务整体挂 2 秒后恢复,对比两种重试策略(从补偿开始算起):固定间隔 100 ms vs 指数退避 50 ms 起翻倍、上限 1 s')
res = {}
for name, kw in (('固定间隔 100 ms', dict(base=0.1, factor=1.0)), ('指数退避 50 ms 翻倍', dict(base=0.05, factor=2.0, cap=1.0))):
    shop.reset(stock=100, balance=10 ** 6); shop.order_create('o-d'); shop.stock_reserve('o-d', 'sku-1', 1)
    up = time.perf_counter() + 2.0; orig = shop.stock_release
    def flaky(oid, up=up, orig=orig):
        if time.perf_counter() < up: raise Transient('服务不可用')
        return orig(oid)
    shop.stock_release = flaky; k, dt = comp_retry(lambda: shop.stock_release('o-d'), log=lambda *a: None, **kw); shop.stock_release = orig
    res[name] = (k, dt - 2.0)
table([(n, k, f'{max(late, 0) * 1000:.0f} ms') for n, (k, late) in res.items()], ['重试策略', '服务挂 2 秒期间共调用次数', '服务恢复后多久补偿成功'])
kf, ke = res['固定间隔 100 ms'][0], res['指数退避 50 ms 翻倍'][0]
print(f'  固定间隔重试在这 2 秒里调用了 {kf} 次,指数退避只调用了 {ke} 次;代价是服务恢复之后,指数退避最多要多等一个退避间隔才发现')
print('  补偿重试意味着同一个补偿可能被执行多次(比如第一次其实成功了但响应丢了),所以补偿要幂等。对比:')
shop.reset(stock=100, balance=10 ** 6); shop.order_create('o-i'); shop.stock_reserve('o-i', 'sku-1', 1)
shop.stock_release('o-i'); shop.stock_release('o-i'); shop.stock_release('o-i')
print('  带状态检查的释放(RESERVED → RELEASED,只改一次)调用 3 次后:', snap().split(',')[1].strip())
shop.reset(stock=100, balance=10 ** 6); shop.order_create('o-i'); shop.stock_reserve('o-i', 'sku-1', 1)
for _ in range(3): M.q("update stock set qty = qty + 1 where sku = 'sku-1'", db='stock_db')
print('  不检查状态、直接 qty = qty + 1 的释放调用 3 次后:', snap().split(',')[1].strip(), '(预留了 1 件,释放了 3 次,库存比初始多了 2)')

print('== 三:补偿不是回滚:支付扣了 1% 手续费(不退),并且订单创建时发过一条“下单成功”的短信;支付失败的补偿只能“退款 + 再发一条取消短信”')
shop.reset(stock=100, balance=10000)
before = dict(stock=shop.snapshot()['stock'], balance=shop.snapshot()['balance'], notes=M.q('select count(*) from notifications', db='order_db')[0][0], payments=M.q('select count(*) from payments', db='pay_db')[0][0])
oid = 'o-s'; shop.order_create(oid); M.q("insert into notifications(order_id, text) values (%s, '下单成功,请在 30 分钟内支付')", (oid,), db='order_db')
shop.stock_reserve(oid, 'sku-1', 1)
fee = max(1, 80 // 100)
M.q('update wallet set balance = balance - %s where user_id = 1', (80 + fee,), db='pay_db'); M.q("insert into payments values (%s, 1, 80, 'CHARGED')", (oid,), db='pay_db')
mid = shop.snapshot()['balance']
# 订单后续的某一步失败了:补偿
shop.stock_release(oid); M.q('update wallet set balance = balance + 80 where user_id = 1', db='pay_db'); M.q("update payments set status = 'REFUNDED' where order_id = %s", (oid,), db='pay_db')
M.q("insert into notifications(order_id, text) values (%s, '订单已取消,款项已退回')", (oid,), db='order_db'); shop.order_set(oid, 'CANCELLED')
after = dict(stock=shop.snapshot()['stock'], balance=shop.snapshot()['balance'], notes=M.q('select count(*) from notifications', db='order_db')[0][0], payments=M.q('select count(*) from payments', db='pay_db')[0][0])
table([('库存', before['stock'], after['stock'], '相同'), ('用户余额', before['balance'], after['balance'], f'少了 {before["balance"] - after["balance"]}(手续费不退)'),
       ('已发出的短信条数', before['notes'], after['notes'], f'多了 {after["notes"] - before["notes"]} 条(发出去的撤不回来)'), ('支付记录行数', before['payments'], after['payments'], '留下一行 REFUNDED(审计)')], ['被动过的东西', 'Saga 之前', '补偿之后', '差别'])
print(f'  扣款后余额 {mid},退款后 {after["balance"]};补偿把能撤的撤回来了(库存),撤不回来的(手续费、已发出的短信)只能用新的动作去抵消或解释')

print('== 四:有些补偿永远不会成功(比如要退款的账户已经注销)——重试没有意义,要有“人工处理队列”')
shop.reset(stock=10000, balance=10 ** 9)
M.q('delete from saga_log', db='saga_db'); M.q('delete from manual_queue', db='saga_db')
rng = random.Random(11)
def run_saga(oid):
    M.q("insert into saga_log(id, status) values (%s, 'RUNNING')", (oid,), db='saga_db')
    shop.order_create(oid); shop.stock_reserve(oid, 'sku-1', 1)
    pay_fail = rng.random() < 0.25; perm = rng.random() < 0.04; trans = rng.random() < 0.15
    if not pay_fail: shop.order_set(oid, 'CONFIRMED'); M.q("update saga_log set status = 'CONFIRMED' where id = %s", (oid,), db='saga_db'); return
    M.q("update saga_log set status = 'COMPENSATING' where id = %s", (oid,), db='saga_db')
    attempts = 0; err = None
    shop.faults.clear()
    if perm: shop.inject('stock_release', times=10 ** 6, exc=StepFailed)
    elif trans: shop.inject('stock_release', times=2)
    while attempts < 6:
        attempts += 1
        try: shop.stock_release(oid); err = None; break
        except Transient as e: err = f'Transient:{e}'; time.sleep(0.005)
        except StepFailed as e: err = f'永久失败:{e}'; break
    if err is None:
        shop.order_set(oid, 'CANCELLED'); M.q("update saga_log set status = 'CANCELLED', attempts = %s where id = %s", (attempts, oid), db='saga_db')
    else:
        M.q("update saga_log set status = 'COMPENSATION_FAILED', attempts = %s, last_error = %s where id = %s", (attempts, err[:90], oid), db='saga_db')
        M.q("insert into manual_queue(saga_id, step, error, attempts) values (%s, 'stock_release', %s, %s)", (oid, err[:90], attempts), db='saga_db')
        shop.order_set(oid, 'CANCELLING')
for i in range(300): run_saga(f's-{i}')
print('  300 个 saga(25% 支付失败;补偿遇到 15% 的临时错误、4% 的永久失败):')
table([tuple(r) for r in M.q('select status, count(*), coalesce(sum(attempts), 0) from saga_log group by status order by status', db='saga_db')], ['saga 最终状态', '个数', '补偿尝试次数合计'])
print('  人工处理队列(manual_queue)里的内容:')
table([tuple(r) for r in M.q('select saga_id, step, error, attempts from manual_queue order by id limit 5', db='saga_db')], ['saga', '步骤', '错误', '尝试次数'])
nq = M.q('select count(*) from manual_queue', db='saga_db')[0][0]
leak = M.q("select count(*) from stock_db.reservations r join order_db.orders o on o.id = r.order_id where r.status = 'RESERVED' and o.status = 'CANCELLING'")[0][0]
print(f'  manual_queue 共 {nq} 行;对账:订单停在 CANCELLING 且库存仍被占着的 {leak} 笔 —— 和队列行数一致,这部分要靠人(或专门的修复任务)收尾,而不是让 saga 无限重试')

print('== 五:步骤顺序:不能补偿的动作(发通知)放在最前面,后面一旦失败就撤不回来;放到最后(支付成功之后),失败就不会发出去')
M.q('delete from notifications', db='order_db')
def saga_order(variant, oid, rng, pay_fail):
    def notify():
        for k in range(1, 50):
            if rng.random() < 0.3: continue             # 通知服务 30% 的概率临时失败
            M.q("insert into notifications(order_id, text) values (%s, '下单成功')", (oid,), db='order_db'); return k
    shop.order_create(oid); att = None
    if variant == 'A': att = notify()                   # A:先通知,再预留库存、再支付
    shop.stock_reserve(oid, 'sku-1', 1)
    if pay_fail:
        shop.stock_release(oid); shop.order_set(oid, 'CANCELLED'); return att
    shop.order_set(oid, 'CONFIRMED')
    if variant == 'B': att = notify()                   # B:支付成功之后才通知(这一步不会再被补偿,失败就一直重试)
    return att
rows = []
for variant, name in (('A', 'A:通知 → 库存 → 支付'), ('B', 'B:库存 → 支付 → 通知')):
    shop.reset(stock=10000, balance=10 ** 9); M.q('delete from notifications', db='order_db'); rng = random.Random(21); atts = []
    pfr = random.Random(33); PF = [pfr.random() < 0.25 for _ in range(300)]   # 两种顺序面对完全相同的 300 次“支付是否失败”
    for i in range(300):
        a = saga_order(variant, f'{variant}-{i}', rng, PF[i])
        if a: atts.append(a)
    wrong = M.q("select count(*) from order_db.notifications n join order_db.orders o on o.id = n.order_id where o.status = 'CANCELLED'")[0][0]
    nconf = M.q("select count(*) from order_db.orders where status = 'CONFIRMED'")[0][0]; nmiss = M.q("select count(*) from order_db.orders o where o.status = 'CONFIRMED' and not exists (select 1 from order_db.notifications n where n.order_id = o.id)")[0][0]
    rows.append((name, 300, nconf, wrong, nmiss, f'{sum(atts) / len(atts):.2f}'))
table(rows, ['步骤顺序', 'saga 数', '最终 CONFIRMED', '发了“下单成功”却被取消的订单', 'CONFIRMED 却没收到通知', '通知平均尝试次数'])
print('  A 里通知一旦发出就撤不回来,后面支付失败时只能认了;B 把不可补偿的步骤放在不会失败的位置之后(支付成功是“转折点”),它自己失败就一直重试,不再回头补偿别的步骤')
reset(); shutil.rmtree(TT / 'my_t9', ignore_errors=True)
