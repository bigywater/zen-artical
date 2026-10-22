import sys, os, json, difflib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import ql
from saga import *
import pika
tee('t8'); reset(); ql.reset()
M = MySQL('t8').start(); shop = Shop(M)
RQ = ql.Node('t8_rq'); RQ.start()
print(f'三个服务(订单、库存、支付)各自读写自己的库(同一个 MySQL {M.q("select version()")[0][0]} 里的 order_db / stock_db / pay_db,没有跨库事务);事件走真实的 RabbitMQ(端口 {RQ.amqp});每个本地动作用 order_id 做主键,天然幂等')
TR = []; T0 = [0.0]; TL = threading.Lock(); PUB = [0]
def tr(who, msg):
    with TL: TR.append((time.perf_counter() - T0[0], who, msg))
def show_trace(limit=40):
    for t, who, msg in TR[:limit]: print(f'    {t * 1000:7.1f} ms  [{who}] {msg}')

# ------------------------------------------------------------------ 编排式
ACTS = {'stock_reserve': lambda s, o: s.stock_reserve(o, 'sku-1', 1), 'stock_release': lambda s, o: s.stock_release(o),
        'pay_charge': lambda s, o: s.pay_charge(o, 1, 80), 'pay_refund': lambda s, o: s.pay_refund(o),
        'points_grant': lambda s, o: s.points_grant(o), 'points_release': lambda s, o: s.points_release(o)}
STEPS3 = [('库存', 'stock_reserve', 'stock_release'), ('支付', 'pay_charge', 'pay_refund')]
STEPS4 = [('库存', 'stock_reserve', 'stock_release'), ('积分', 'points_grant', 'points_release'), ('支付', 'pay_charge', 'pay_refund')]
def orchestrate(oid, steps, retries=0, backoff=0.3, say=True):
    tr('编排器', f'调用订单服务:创建订单 {oid}(PENDING)'); shop.order_create(oid); done = []
    for name, act, comp in steps:
        for attempt in range(retries + 1):
            try:
                ACTS[act](shop, oid); tr('编排器', f'调用 {name}服务 {act} → 成功'); done.append((name, comp)); break
            except StepFailed as e:
                tr('编排器', f'调用 {name}服务 {act} → 失败:{e}');
                for n2, c2 in reversed(done): ACTS[c2](shop, oid); tr('编排器', f'补偿:调用 {n2}服务 {c2}')
                shop.order_set(oid, 'CANCELLED'); tr('编排器', '订单 → CANCELLED'); return 'CANCELLED'
            except Transient as e:
                tr('编排器', f'调用 {name}服务 {act} → 临时错误({attempt + 1}/{retries + 1})')
                if attempt == retries:
                    for n2, c2 in reversed(done): ACTS[c2](shop, oid); tr('编排器', f'补偿:调用 {n2}服务 {c2}')
                    shop.order_set(oid, 'CANCELLED'); tr('编排器', '重试用完,订单 → CANCELLED'); return 'CANCELLED'
                time.sleep(backoff)
    shop.order_set(oid, 'CONFIRMED'); tr('编排器', '订单 → CONFIRMED'); return 'CONFIRMED'

# ------------------------------------------------------------------ 协同式(事件驱动)
def h_reserve(oid):
    try: shop.stock_reserve(oid, 'sku-1', 1); return 'stock.reserved'
    except StepFailed: return 'stock.failed'
def h_release(oid): shop.stock_release(oid); return 'stock.released'
def h_charge(oid):
    try: shop.pay_charge(oid, 1, 80); return 'payment.succeeded'
    except StepFailed: return 'payment.failed'
def h_grant(oid): shop.points_grant(oid); return 'points.granted'
def h_points_release(oid): shop.points_release(oid); return 'points.released'
DONE = {}
def h_confirm(oid): shop.order_set(oid, 'CONFIRMED'); DONE.setdefault(oid, threading.Event()).set(); return None
def h_cancel(oid): shop.order_set(oid, 'CANCELLED'); DONE.setdefault(oid, threading.Event()).set(); return None
HANDLERS = {('库存', 'order.created'): h_reserve, ('库存', 'payment.failed'): h_release, ('库存', 'points.released'): h_release,
            ('支付', 'stock.reserved'): h_charge, ('支付', 'points.granted'): h_charge,
            ('积分', 'stock.reserved'): h_grant, ('积分', 'payment.failed'): h_points_release,
            ('订单', 'payment.succeeded'): h_confirm, ('订单', 'stock.failed'): h_cancel, ('订单', 'stock.released'): h_cancel}
TOPO3 = {'订单': ['payment.succeeded', 'stock.failed', 'stock.released'], '库存': ['order.created', 'payment.failed'], '支付': ['stock.reserved']}
TOPO4 = {'订单': ['payment.succeeded', 'stock.failed', 'stock.released'], '库存': ['order.created', 'points.released'], '积分': ['stock.reserved', 'payment.failed'], '支付': ['points.granted']}
class Svc(threading.Thread):
    def __init__(self, name, binds):
        super().__init__(daemon=True); self.name_ = name; self.binds = binds; self.paused = threading.Event(); self.ready = threading.Event(); self.stop_ = threading.Event()
    def run(self):
        conn = RQ.conn(); ch = conn.channel(); q = f'q.{self.name_}.{id(self)}'
        ch.queue_declare(q, exclusive=True)
        for b in self.binds: ch.queue_bind(q, 'saga', b)
        ch.basic_qos(prefetch_count=1)
        def cb(c, m, props, body):
            if self.paused.is_set(): c.basic_nack(m.delivery_tag, requeue=True); time.sleep(0.05); return
            oid = json.loads(body)['order_id']; ev = m.routing_key
            tr(self.name_ + '服务', f'收到 {ev}')
            nxt = HANDLERS[(self.name_, ev)](oid)
            if nxt:
                c.basic_publish('saga', nxt, json.dumps({'order_id': oid})); PUB[0] += 1; tr(self.name_ + '服务', f'发出 {nxt}')
            c.basic_ack(m.delivery_tag)
        ch.basic_consume(q, cb); self.ready.set()
        while not self.stop_.is_set(): conn.process_data_events(time_limit=0.05)
        try: conn.close()
        except Exception: pass
def start_topo(topo):
    c = RQ.conn(); ch = c.channel(); ch.exchange_declare('saga', 'topic'); c.close()
    svcs = {n: Svc(n, b) for n, b in topo.items()}
    for s in svcs.values(): s.start()
    for s in svcs.values(): s.ready.wait(10)
    return svcs
def stop_topo(svcs):
    for s in svcs.values(): s.stop_.set()
    for s in svcs.values(): s.join(5)
pubconn = RQ.conn(); pubch = pubconn.channel()
def choreo_start(oid):
    shop.order_create(oid); DONE[oid] = threading.Event(); tr('订单服务', f'创建订单 {oid}(PENDING)')
    pubch.basic_publish('saga', 'order.created', json.dumps({'order_id': oid})); PUB[0] += 1; tr('订单服务', '发出 order.created')
def choreo_wait(oid, timeout=10): DONE[oid].wait(timeout); return shop.order_status(oid)
def run_scn(kind, topo_or_steps, label, setup=None):
    shop.reset(stock=100, balance=10 ** 6); TR.clear(); PUB[0] = 0
    if setup: setup()
    T0[0] = time.perf_counter(); oid = f'o-{kind}-{label}'
    if kind == 'orch': r = orchestrate(oid, topo_or_steps)
    else: choreo_start(oid); r = choreo_wait(oid); time.sleep(0.15)
    return r

def snap_line(): s = shop.snapshot(); return f'订单 {s["orders"]},库存 {s["stock"]}(预留中 {s["reserved"]}),余额 {s["balance"]}(已扣款 {s["charged"]} 笔)'

print('== 一:正常成功的一单:编排式 vs 协同式,逐步看谁在调用谁(商品 80 元,库存 100)')
r = run_scn('orch', STEPS3, 'ok'); print(f'  编排式(一个编排器按顺序调用三个服务)→ {r}:'); show_trace(); print('   ', snap_line()); orch_calls = sum('调用' in x[2] for x in TR)
svcs = start_topo(TOPO3)
r = run_scn('choreo', None, 'ok'); print(f'  协同式(服务之间通过 RabbitMQ 事件接力)→ {r}:'); show_trace(); print('   ', snap_line()); print(f'    协同式这一单在 RabbitMQ 上走了 {PUB[0]} 条消息;编排式没有消息,编排器直接发起了 {orch_calls} 次调用(创建订单、库存、支付),最后一次订单状态更新是本地调用')

print('== 二:支付失败(余额只有 50):补偿怎么走')
def poor(): M.q('update wallet set balance = 50 where user_id = 1', db='pay_db')
stop_topo(svcs)
r = run_scn('orch', STEPS3, 'poor', poor); print(f'  编排式 → {r}:'); show_trace(); print('   ', snap_line())
svcs = start_topo(TOPO3)
r = run_scn('choreo', None, 'poor', poor); print(f'  协同式 → {r}:'); show_trace(); print('   ', snap_line()); print(f'    共 {PUB[0]} 条消息;补偿由 payment.failed 事件触发库存服务自己释放,再由 stock.released 触发订单服务取消')

print('== 三:库存不足(库存 0)')
def empty(): M.q('update stock set qty = 0 where sku = %s', ('sku-1',), db='stock_db')
stop_topo(svcs)
r = run_scn('orch', STEPS3, 'empty', empty); print(f'  编排式 → {r}:'); show_trace(); print('   ', snap_line())
svcs = start_topo(TOPO3)
r = run_scn('choreo', None, 'empty', empty); print(f'  协同式 → {r}:'); show_trace(); print('   ', snap_line())

print('== 四:库存服务挂了 2 秒(每 50 ms 看一次订单状态,只记录变化):编排器知道“这一步没成”,协同式里消息只是排在队列里没人处理')
def poll(oid, secs=3.0):
    out = []; t0 = time.perf_counter(); last = None
    while time.perf_counter() - t0 < secs:
        st = shop.order_status(oid)
        if st != last: out.append((time.perf_counter() - t0, st)); last = st
        time.sleep(0.05)
    return out
shop.reset(); TR.clear()
down_until = [time.perf_counter() + 2.0]
orig = shop.stock_reserve
def flaky(oid, sku, qty):
    if time.perf_counter() < down_until[0]: shop._enter('x'); raise Transient('库存服务不可用')
    return orig(oid, sku, qty)
shop.stock_reserve = flaky
T0[0] = time.perf_counter(); th = threading.Thread(target=lambda: orchestrate('o-down-orch', STEPS3, retries=2, backoff=0.3)); th.start(); tl_ = poll('o-down-orch', 3.0); th.join()
print('  编排式(每步最多重试 2 次、间隔 0.3 秒,用完就补偿并取消):订单状态变化 ' + ',  '.join(f'{t:.2f}s → {st}' for t, st in tl_))
for t, who, msg in TR: print(f'    {t * 1000:7.1f} ms  [{who}] {msg}')
shop.reset(); TR.clear(); shop.stock_reserve = orig
svcs['库存'].paused.set(); T0[0] = time.perf_counter(); choreo_start('o-down-choreo')
threading.Timer(2.0, svcs['库存'].paused.clear).start()
tl_ = poll('o-down-choreo', 3.5)
print('  协同式(库存服务的消费者暂停 2 秒,消息留在队列里):订单状态变化 ' + ',  '.join(f'{t:.2f}s → {st}' for t, st in tl_))
print('    协同式里没有谁“知道”这单卡住了:订单一直 PENDING,直到库存服务回来、消息被处理;编排式里编排器在第一次失败时就知道,并按自己的重试 / 补偿策略做决定')

print('== 五:谁知道这一单走到哪了:想回答“订单 o-1 现在处在哪一步”,各需要查几个地方')
shop.reset(); stop_topo(svcs); orchestrate('o-1', STEPS3)
def where_orch(oid): return {'编排器的记录': 1}
def where_choreo(oid):
    out = {'订单服务': shop.order_status(oid)}
    out['库存服务'] = M.q('select status from reservations where order_id = %s', (oid,), db='stock_db')[0][0]
    out['支付服务'] = M.q('select status from payments where order_id = %s', (oid,), db='pay_db')[0][0]
    return out
print('  协同式:要分别去 3 个服务的库里查:', where_choreo('o-1'))
print('  编排式:编排器如果把每个 saga 的当前步骤存在自己的表里,查 1 个地方就够(本篇的编排器没有持久化步骤,只在内存里;持久化与观察放到第 30 篇)')

print('== 六:各跑 150 笔成功的订单(顺序执行),端到端耗时:编排式是函数调用,协同式要经过 3 次 RabbitMQ 往返')
shop.reset(stock=10 ** 6, balance=10 ** 9); lat_o = []
for i in range(150):
    t0 = time.perf_counter(); orchestrate(f'bo-{i}', STEPS3); lat_o.append(time.perf_counter() - t0)
TR.clear()
svcs = start_topo(TOPO3); lat_c = []
for i in range(150):
    t0 = time.perf_counter(); choreo_start(f'bc-{i}'); choreo_wait(f'bc-{i}'); lat_c.append(time.perf_counter() - t0)
TR.clear()
def pct(l, p): return sorted(l)[int(len(l) * p) - 1]
table([('编排式', ms(statistics.median(lat_o)), ms(pct(lat_o, 0.99))), ('协同式(RabbitMQ)', ms(statistics.median(lat_c)), ms(pct(lat_c, 0.99)))], ['写法', '中位数', 'p99'])
print('  协同式慢在每一跳都是“发布 → 经 broker → 被消费”,同时它不要求调用方在线,下游挂了消息还在')

print('== 七:加一个“积分”步骤(放在库存和支付之间),已有的东西要改几处')
stop_topo(svcs)
def changed(a, b): return [l for l in difflib.unified_diff(a, b, lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
orch_old = [f'{n} {a} {c}' for n, a, c in STEPS3]; orch_new = [f'{n} {a} {c}' for n, a, c in STEPS4]
d = changed(orch_old, orch_new)
print(f'  编排式:流程定义是一张步骤表。改动 {len(d)} 行,全部在编排器里,库存、支付服务的代码不动:'); [print('    ', l) for l in d]
tot_services = 0
for svc in ['订单', '库存', '支付']:
    d = changed(sorted(TOPO3[svc]), sorted(TOPO4[svc]))
    if d: tot_services += 1; print(f'  协同式:已有的 {svc}服务要改它订阅的事件:' + ';'.join(d))
print(f'  协同式:新增 积分服务 订阅 {TOPO4["积分"]};已有服务里有 {tot_services} 个必须改订阅(库存的补偿触发源、支付的触发源);订单服务不变')
svcs = start_topo(TOPO4)
r = run_scn('choreo', None, 'p4poor', poor); print(f'  四个服务的协同式,支付失败 → {r},事件链:'); [print(f'    {t * 1000:7.1f} ms  [{who}] {msg}') for t, who, msg in TR if '发出' in msg]
stop_topo(svcs); reset(); ql.reset()
shutil.rmtree(TT / 'my_t8', ignore_errors=True)
