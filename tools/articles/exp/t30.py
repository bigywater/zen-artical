import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from saga import *
tee('t30'); reset()
M = MySQL('t30').start(); shop = Shop(M)
M.q('create database saga_db')
M.q("""create table saga_log(id varchar(40) primary key, status varchar(20), step varchar(12), attempts int default 0, last_error varchar(120), owner varchar(20), created datetime(3) default current_timestamp(3), updated_at datetime(3) default current_timestamp(3), done_at datetime(3), key k_status (status, updated_at))""", db='saga_db')
M.q('create table saga_step(id bigint auto_increment primary key, saga_id varchar(40), step varchar(20), attempt int, result varchar(120), at datetime(3) default current_timestamp(3), key k (saga_id))', db='saga_db')
print(f'三个服务各读写自己的库(同一个 MySQL {M.q("select version()")[0][0]} 里的 order_db / stock_db / pay_db);编排器把每个 saga 的状态写进自己的 saga_db(saga_log:当前步骤、尝试次数、最后一个错误、负责的 worker、更新时间;saga_step:每一次尝试一行);本篇的 saga = 创建订单 → 预留库存 → 扣款 → 确认,扣款失败要释放库存')
TL = threading.local()
def sdb():
    if getattr(TL, 'c', None) is None: TL.c = M.conn('saga_db')
    return TL.c
def sq(sql, args=None): cur = sdb().cursor(); cur.execute(sql, args); return cur.fetchall()
class WorkerCrash(Exception): pass
def step_log(sid, step, attempt, result): sq('insert into saga_step(saga_id, step, attempt, result) values (%s, %s, %s, %s)', (sid, step, attempt, result[:120]))
def set_state(sid, **kw):
    cols = ', '.join(f'{k} = %s' for k in kw); sq(f'update saga_log set {cols}, updated_at = now(3) where id = %s', (*kw.values(), sid))
def call_with_retry(sid, step, fn, max_attempts=6, base=0.02):
    for a in range(1, max_attempts + 1):
        try: r = fn(); step_log(sid, step, a, f'ok {r}'); sq('update saga_log set attempts = attempts + %s, updated_at = now(3) where id = %s', (a - 1, sid)) if a > 1 else None; return r
        except Transient as e:
            step_log(sid, step, a, f'transient {e}'); set_state(sid, last_error=f'{step}: {e}'[:120])
            if a == max_attempts: raise
            time.sleep(base * 2 ** (a - 1))
def run_saga(sid, crash_at=None, resume=False):
    """crash_at:某一步做完之后让 worker 悄悄消失(没有更新 saga_log 就退出);resume:从 saga_log 里记的当前步骤继续。"""
    if not resume: sq("insert into saga_log(id, status, step) values (%s, 'RUNNING', 'create')", (sid,))
    st = sq('select status, step from saga_log where id = %s', (sid,))[0]; status, step = st
    try:
        if status == 'RUNNING':
            if step == 'create':
                call_with_retry(sid, 'create', lambda: shop.order_create(sid)); set_state(sid, step='reserve')
                if crash_at == 'create': raise WorkerCrash()
                step = 'reserve'
            if step == 'reserve':
                try: call_with_retry(sid, 'reserve', lambda: shop.stock_reserve(sid, 'sku-1', 1))
                except StepFailed: set_state(sid, status='COMPENSATING', step='cancel', last_error='库存不足'); raise
                set_state(sid, step='charge')
                if crash_at == 'reserve': raise WorkerCrash()
                step = 'charge'
            if step == 'charge':
                try: call_with_retry(sid, 'charge', lambda: shop.pay_charge(sid, 1, 80))
                except StepFailed: set_state(sid, status='COMPENSATING', step='release', last_error='余额不足'); raise
                set_state(sid, step='confirm')
                if crash_at == 'charge': raise WorkerCrash()
                step = 'confirm'
            if step == 'confirm': call_with_retry(sid, 'confirm', lambda: shop.order_set(sid, 'CONFIRMED')); set_state(sid, status='CONFIRMED', step='done', done_at=None); sq('update saga_log set done_at = now(3) where id = %s', (sid,)); return 'CONFIRMED'
        raise StepFailed('进入补偿')
    except StepFailed:
        status, step = sq('select status, step from saga_log where id = %s', (sid,))[0]
        try:
            if step in ('release', 'cancel'):
                if step == 'release': call_with_retry(sid, 'release', lambda: shop.stock_release(sid), max_attempts=8)
                call_with_retry(sid, 'cancel', lambda: shop.order_set(sid, 'CANCELLED'))
            set_state(sid, status='CANCELLED', step='done'); sq('update saga_log set done_at = now(3) where id = %s', (sid,)); return 'CANCELLED'
        except Transient: set_state(sid, status='COMPENSATION_FAILED', last_error='补偿重试用完'); return 'COMPENSATION_FAILED'
        except StepFailed: set_state(sid, status='COMPENSATION_FAILED', last_error='补偿永久失败'); return 'COMPENSATION_FAILED'
    except Transient as e: set_state(sid, last_error=f'重试用完:{e}'[:120]); return 'RETRY_EXHAUSTED'
    except WorkerCrash: return 'WORKER_CRASHED'

def metrics():
    r = sq("""select sum(status in ('RUNNING', 'COMPENSATING')), coalesce(max(case when status in ('RUNNING', 'COMPENSATING') then timestampdiff(microsecond, updated_at, now(3)) / 1e6 end), 0),
                     sum(status in ('RUNNING', 'COMPENSATING') and updated_at < now(3) - interval 2 second), sum(status = 'COMPENSATION_FAILED'), sum(status = 'CONFIRMED'), sum(status = 'CANCELLED'), count(*) from saga_log""")[0]
    return dict(in_flight=int(r[0] or 0), oldest=float(r[1]), stuck=int(r[2] or 0), comp_failed=int(r[3] or 0), confirmed=int(r[4] or 0), cancelled=int(r[5] or 0), total=int(r[6]))

print('== 一:没有状态表的编排器,崩溃之后什么都看不到:一个 saga 在“库存已预留、还没扣款”时 worker 进程消失了——排查的人只能跨三个服务的库去拼')
shop.reset(stock=1000, balance=10 ** 9)
shop.order_create('lost-1'); shop.stock_reserve('lost-1', 'sku-1', 1)
print('  要回答“lost-1 现在卡在哪一步”,得分别去问:订单库', shop.order_status('lost-1'), '、库存库', M.q("select status from reservations where order_id = 'lost-1'", db='stock_db')[0][0], '、支付库', M.q("select count(*) from payments where order_id = 'lost-1'", db='pay_db')[0][0], '条支付;')
print('  订单 PENDING + 库存 RESERVED + 没有支付 → 推断“预留之后、扣款之前挂了”,但这是人在拼三份数据后的推断:没有人知道 worker 是死了还是只是在等,也不知道它重试了几次、上一次错误是什么')

print('== 二:有了状态表(saga_log + saga_step):1000 个 saga,16 个 worker 并发处理;故障:扣款失败 15%(余额不足),任何一步的临时错误 8%(自带重试),worker 在做完某一步之后悄悄消失 2%')
shop.reset(stock=100000, balance=10 ** 9); sq('delete from saga_log'); sq('delete from saga_step')
rng = random.Random(30); N = 1000; jobs = list(range(N)); jl = threading.Lock(); results = {}; rl_ = threading.Lock()
poor = {i for i in range(N) if rng.random() < 0.15}; crash = {i: rng.choice(['create', 'reserve', 'charge']) for i in range(N) if rng.random() < 0.02}
orig = {n: getattr(shop, n) for n in ('order_create', 'stock_reserve', 'pay_charge', 'order_set', 'stock_release')}
frng = random.Random(31); flk = threading.Lock()
def flaky(name):
    def f(*a):
        with flk: fail = frng.random() < 0.08
        if fail: raise Transient(f'{name} 临时不可用')
        if name == 'pay_charge' and a[0] in poor_ids: raise StepFailed('余额不足')
        return orig[name](*a)
    return f
poor_ids = {f'saga-{i}' for i in poor}
for n in orig: setattr(shop, n, flaky(n))
outage = [False]
def worker():
    while True:
        with jl:
            if not jobs: return
            i = jobs.pop(0)
        sid = f'saga-{i}'; r = run_saga(sid, crash_at=crash.get(i))
        with rl_: results[sid] = r
t0 = time.perf_counter(); ths = [threading.Thread(target=worker) for _ in range(16)]; [t.start() for t in ths]; [t.join() for t in ths]; dt = time.perf_counter() - t0
cnt = {}
for r in results.values(): cnt[r] = cnt.get(r, 0) + 1
print(f'  {N} 个 saga 在 {dt:.1f} s 里跑完(worker 的返回值):{dict(sorted(cnt.items()))}')
m = metrics(); print(f'  从状态表里看:{ {k: v for k, v in m.items()} };saga_step 一共 {sq("select count(*) from saga_step")[0][0]} 行,其中临时失败的尝试 {sq("select count(*) from saga_step where result like %s", ("transient%",))[0][0]} 行')
print('  各状态的 saga 个数:' + ',  '.join(f'{r[0]} {r[1]}' for r in sq('select status, count(*) from saga_log group by status order by status')))
stuck_rows = sq("select id, status, step, last_error, timestampdiff(second, updated_at, now(3)) from saga_log where status in ('RUNNING', 'COMPENSATING') order by updated_at limit 5")
print('  卡住的(非终态)saga 里最老的 5 个(id、状态、当前步骤、最后的错误、多少秒没更新):' + str([tuple(r) for r in stuck_rows]))

print('== 三:恢复守护进程:定时扫 saga_log,把“非终态、而且超过 1 秒没更新”的 saga 接管下来继续(用 UPDATE ... WHERE updated_at < ... 抢 owner,避免两个守护进程同时接管)')
time.sleep(1.2); resumed = {'n': 0}; stop = threading.Event()
def recover_once(owner):
    rows = sq("select id from saga_log where status in ('RUNNING', 'COMPENSATING') and updated_at < now(3) - interval 1 second limit 50")
    n = 0
    for (sid,) in rows:
        got = sdb().cursor(); got.execute("update saga_log set owner = %s, updated_at = now(3) where id = %s and status in ('RUNNING', 'COMPENSATING') and updated_at < now(3) - interval 1 second", (owner, sid))
        if got.rowcount == 1: run_saga(sid, resume=True); n += 1
    return n
n1 = recover_once('recovery-1'); n2 = recover_once('recovery-2')
print(f'  第一轮扫描接管并继续了 {n1} 个 saga,第二轮 {n2} 个')
m = metrics(); print(f'  恢复之后状态表:{m}')
print('  各状态的 saga 个数:' + ',  '.join(f'{r[0]} {r[1]}' for r in sq('select status, count(*) from saga_log group by status order by status')))
leak = M.q("select count(*) from stock_db.reservations r join order_db.orders o on o.id = r.order_id where r.status = 'RESERVED' and o.status <> 'CONFIRMED'")[0][0]
paid_cancel = M.q("select count(*) from pay_db.payments p join order_db.orders o on o.id = p.order_id where p.status = 'CHARGED' and o.status = 'CANCELLED'")[0][0]
print(f'  对账:库存仍被占着、但订单不是 CONFIRMED 的 {leak} 个;已扣款、但订单是 CANCELLED 的 {paid_cancel} 个;状态表里 COMPENSATION_FAILED 的 {m["comp_failed"]} 个')

print('== 四:重试了几次、花了多久:saga_step 里每次尝试一行。看每个 saga 的尝试次数分布,以及“有重试的 saga”和“没有重试的 saga”从创建到结束的耗时(不含被恢复守护进程接管过的 saga,它们多等了一段“被丢下”的时间)')
att = {r[0]: r[1] for r in sq("select n, count(*) from (select saga_id, count(*) n from saga_step where step = 'reserve' group by saga_id) t group by n")}
print('  预留库存这一步的尝试次数分布(尝试 n 次的 saga 个数):' + str(dict(sorted(att.items()))))
rows = sq("""select (select count(*) from saga_step s where s.saga_id = l.id and s.result like 'transient%') > 0 as retried, timestampdiff(microsecond, created, done_at) / 1000 from saga_log l where done_at is not null and owner is null""")
lat = {True: [], False: []}
for rt, ms_ in rows: lat[bool(rt)].append(float(ms_))
def pc(l, p): return sorted(l)[max(int(len(l) * p) - 1, 0)]
table([('没有临时失败', len(lat[False]), f'{statistics.median(lat[False]):.0f} ms', f'{pc(lat[False], 0.99):.0f} ms'), ('至少一次临时失败', len(lat[True]), f'{statistics.median(lat[True]):.0f} ms', f'{pc(lat[True], 0.99):.0f} ms')], ['saga', '个数', '创建到结束 中位数', 'p99'])
print('  重试(带指数退避)让有临时失败的 saga 变慢,但都走完了;saga_step 里能直接查到每个 saga 在哪一步试了几次、每次什么错')

print('== 五:告警:模拟支付服务整整中断 3 秒(这段时间每一次扣款都临时失败),600 个 saga 以 150 个/秒进来,24 个 worker 处理,另有恢复守护进程每 0.4 秒接管“超过 1 秒没更新”的 saga。每 0.5 秒取一次指标;告警规则:在途 saga > 40,或最老的非终态 saga 超过 2 秒没更新')
shop.reset(stock=100000, balance=10 ** 9); sq('delete from saga_log'); sq('delete from saga_step')
for n in orig: setattr(shop, n, orig[n])
outage_from = [0.0, 0.0]
def flaky2(name):
    def f(*a):
        if name == 'pay_charge' and outage_from[0] <= time.perf_counter() < outage_from[1]: raise Transient('支付服务中断')
        return orig[name](*a)
    return f
for n in orig: setattr(shop, n, flaky2(n))
import queue as _q
jobq = _q.Queue(); stop = threading.Event(); samples = []; resumed_total = [0]; rl2 = threading.Lock()
def worker2():
    while not stop.is_set():
        try: i = jobq.get(timeout=0.1)
        except _q.Empty: continue
        run_saga(f'o-{i}')
def recovery_daemon():
    while not stop.is_set():
        rows = sq("select id from saga_log where status in ('RUNNING', 'COMPENSATING') and updated_at < now(3) - interval 1 second limit 40")
        def one(sid):
            got = sdb().cursor(); got.execute("update saga_log set owner = 'recovery', updated_at = now(3) where id = %s and status in ('RUNNING', 'COMPENSATING') and updated_at < now(3) - interval 1 second", (sid,))
            if got.rowcount == 1:
                run_saga(sid, resume=True)
                with rl2: resumed_total[0] += 1
        ths = [threading.Thread(target=one, args=(sid,)) for (sid,) in rows[:8]]; [t.start() for t in ths]; [t.join() for t in ths]
        time.sleep(0.4)
def sampler():
    while not stop.is_set(): samples.append((time.perf_counter() - T0, metrics())); time.sleep(0.5)
T0 = time.perf_counter(); outage_from[0] = T0 + 1.0; outage_from[1] = T0 + 4.0
ws = [threading.Thread(target=worker2) for _ in range(24)]; rd = threading.Thread(target=recovery_daemon); smp = threading.Thread(target=sampler)
[t.start() for t in ws + [rd, smp]]
for i in range(600): time.sleep(1 / 150); jobq.put(i)
t_wait = time.perf_counter() + 40
while time.perf_counter() < t_wait:
    m = metrics()
    if m['total'] == 600 and m['in_flight'] == 0: break
    time.sleep(0.3)
time.sleep(0.6); stop.set(); [t.join() for t in ws + [rd, smp]]
rows = []; alerted = None; cleared = None
for t, m in samples:
    fire = m['in_flight'] > 40 or m['oldest'] > 2.0
    if fire and alerted is None: alerted = t
    if alerted is not None and not fire and cleared is None and t > 4.0: cleared = t
    rows.append((f'{t:.1f} s', m['in_flight'], f'{m["oldest"]:.1f} s', m['confirmed'], '告警' if fire else ''))
table(rows[:30], ['时刻', '在途 saga', '最老的非终态 saga 多久没更新', '已确认', '告警'])
fm = metrics()
print(f'  支付服务在 1.0 s 到 4.0 s 中断;第一次告警出现在 {alerted:.1f} s' + (f',告警在 {cleared:.1f} s 解除' if cleared else ',(取样期间一直没有解除)') + f';恢复守护进程一共接管并继续了 {resumed_total[0]} 个 saga;最终状态:' + ',  '.join(f'{r[0]} {r[1]}' for r in sq('select status, count(*) from saga_log group by status order by status')) + f'(共 {fm["total"]} 个)')
retry_rows = sq("select count(distinct saga_id) from saga_step where result like 'transient%'")[0][0]
print(f'  其中 saga_step 里有临时失败记录的 saga {retry_rows} 个;中断期间扣款的退避重试把在途数顶高、让最老的 saga 越来越久没更新,告警在那时出现;重试用完的 saga 停在 RUNNING,由守护进程在支付恢复之后接着跑完')
reset(); shutil.rmtree(TT / 'my_t30', ignore_errors=True)
