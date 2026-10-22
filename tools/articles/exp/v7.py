import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v7'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('熔断器用第 5 篇里的手写版(连续失败 5 次打开,打开 1 s 后半开,半开放行 3 个、3 个连续成功关闭);重试 = 失败后等一会儿再试,最多共 3 次;下游是本进程里的小 HTTP 服务。这一篇看三样东西放在一起时配错了会怎样')

# ============ 一 ============
print('== 一:重试放在熔断器里面还是外面。下游一直失败(503)。里面 = 熔断器包着“重试 3 次”,一个逻辑请求只在熔断器里记 1 次失败;外面 = “重试 3 次”包着熔断器,每次尝试都经过熔断器、各记 1 次。逻辑请求一个接一个地发,共 12 个。统计:熔断器打开之前有几个逻辑请求打到下游、下游一共收到几次调用、熔断器打开的时刻是第几个逻辑请求')
def run1(placement):
    hits = [0]
    def app(h): hits[0] += 1; h.reply(503, b'x')
    S = Svc(app); b = Breaker(5, 60.0, 3); opened_at = None; reached_logical = 0; rejected = 0
    def attempt():
        st, _, _ = rpc(S.port, '/', 2.0)
        if st != 200: raise RuntimeError
    for k in range(12):
        before = hits[0]
        if placement == 'inside':
            def retried():
                for n in range(3):
                    try: return attempt()
                    except RuntimeError: pass
                raise RuntimeError
            try: b.call(retried)
            except Open: rejected += 1
            except RuntimeError: pass
        else:
            for n in range(3):
                try: b.call(attempt); break
                except Open: rejected += 1; break
                except RuntimeError: pass
        if hits[0] > before: reached_logical += 1
        if opened_at is None and b.state == 'open': opened_at = k + 1
    n_hits = hits[0]; S.stop(); return opened_at, reached_logical, n_hits, rejected
rows = []
for name, pl in (('重试在熔断器里面(熔断器包着重试)', 'inside'), ('重试在熔断器外面(重试包着熔断器)', 'outside')):
    o, rl, h, rj = run1(pl); rows.append((name, f'第 {o} 个逻辑请求之后', rl, h, rj))
table(rows, ['放法', '熔断器打开', '到达下游的逻辑请求数', '下游收到的调用', '被熔断器拒绝的尝试'])

# ============ 二 ============
print('== 二:超时越长,熔断器越晚知道。下游一直挂住不回(服务端睡 10 s),分别用 20 个并发线程和 1 个线程闭环调用;熔断器连续失败 5 次才打开,失败是在调用超时返回时才记录。比较调用超时 0.2 s / 1 s / 3 s。“打开用了多久”是从开始到熔断器打开,“被拖住的线程时间”是这期间所有调用占用的线程时间之和')
def run2(timeout, nth=20):
    def app(h): time.sleep(10); h.reply(200, b'x')
    S = Svc(app); b = Breaker(5, 60.0, 3); lk = threading.Lock(); cnt = collections.Counter(); held = [0.0]; t0 = time.perf_counter(); opened = [None]
    def cl():
        while opened[0] is None and time.perf_counter() - t0 < 30:
            def fn():
                st, _, dt = rpc(S.port, '/', timeout)
                with lk: cnt['reached'] += 1; held[0] += dt
                if st != 200: raise RuntimeError
            try: b.call(fn)
            except (Open, TooMany): pass
            except RuntimeError: pass
            if b.state == 'open' and opened[0] is None: opened[0] = time.perf_counter() - t0
    ths = [threading.Thread(target=cl) for _ in range(nth)]; [t.start() for t in ths]; [t.join() for t in ths]; S.stop()
    return opened[0], cnt['reached'], held[0]
rows = []
for to in (0.2, 1.0, 3.0):
    o20, r20, h20 = run2(to, 20); o1, r1, h1 = run2(to, 1)
    rows.append((f'{to:g} s', f'{o20:.2f} s', r20, f'{h20:.1f} s', f'{o1:.2f} s', r1, f'{h1:.1f} s'))
table(rows, ['调用超时', '20 线程:打开用了多久', '到达下游的调用', '被拖住的线程时间', '1 线程:打开用了多久', '到达下游的调用', '被拖住的线程时间'])
nerr()

# ============ 三 ============
print('== 三:重试碰上已经打开的熔断器。熔断器已经打开(打开 60 s 不会进半开),调用方“失败就退避重试 3 次”,退避 50 ms、100 ms、200 ms(共 350 ms)。比较:把“熔断器打开”也当作可以重试的错误 / 熔断器打开就直接放弃。各发 50 个请求,统计调用方等了多久才拿到失败')
def run3(retry_on_open):
    b = Breaker(1, 60.0, 3); 
    try: b.call(lambda: (_ for _ in ()).throw(RuntimeError()))
    except Exception: pass
    assert b.state == 'open'; lat = []
    for _ in range(50):
        t0 = time.perf_counter()
        for n, back in enumerate((0.05, 0.1, 0.2, None)):
            try: b.call(lambda: 'ok'); break
            except Open:
                if not retry_on_open or back is None: break
                time.sleep(back)
        lat.append(time.perf_counter() - t0)
    return lat
rows = []
for name, ro in (('熔断器打开也重试', True), ('熔断器打开就放弃', False)):
    lat = run3(ro); rows.append((name, f'{statistics.median(lat) * 1000:.1f} ms', f'{pct(lat, 99) * 1000:.1f} ms'))
table(rows, ['策略', '拿到失败的延迟中位数', 'p99'])

# ============ 四 ============
print('== 四:超时设得比下游的正常尾延迟还短。下游其实是健康的:80% 的请求 30 ms、20% 的请求 300 ms,全部返回 200。10 个并发线程闭环调用 20 秒;熔断器:最近 50 次、至少 50 次、失败率 ≥ 10% 打开(第 6 篇的计数窗口;这一节为了简单,打开 1 s 后直接关闭并清空窗口,没有半开)。比较调用超时 100 ms 与 1 s。“服务端白干”= 客户端已经超时、服务端仍然把请求处理完的次数')
def run4(timeout):
    lk = threading.Lock(); cnt = collections.Counter(); rng = random.Random(5)
    def app(h):
        with lk: slow = rng.random() < 0.2
        time.sleep(0.3 if slow else 0.03); h.reply(200, b'x')
        with lk: cnt['server_done'] += 1
    S = Svc(app); wb = {'w': collections.deque(), 'state': 'closed', 'opened': 0.0}; t0 = time.perf_counter(); trips = [0]; blk = threading.Lock()
    def allow():
        with blk:
            if wb['state'] == 'open':
                if time.perf_counter() - wb['opened'] >= 1.0: wb['state'] = 'closed'; wb['w'].clear()
                else: return False
            return True
    def rec(ok):
        with blk:
            wb['w'].append(ok)
            if len(wb['w']) > 50: wb['w'].popleft()
            if wb['state'] == 'closed' and len(wb['w']) >= 50 and sum(1 for o in wb['w'] if not o) / len(wb['w']) >= 0.1:
                wb['state'] = 'open'; wb['opened'] = time.perf_counter(); trips[0] += 1
    def cl():
        while time.perf_counter() - t0 < 20:
            if not allow(): cnt['rejected'] += 1; time.sleep(0.01); continue
            st, _, dt = rpc(S.port, '/', timeout); cnt['sent'] += 1; rec(st == 200)
            if st == 'timeout': cnt['timeouts'] += 1
    ths = [threading.Thread(target=cl) for _ in range(10)]; [t.start() for t in ths]; [t.join() for t in ths]; time.sleep(0.5); S.stop()
    return trips[0], cnt
rows = []
for to in (0.1, 1.0):
    tr, c = run4(to); rows.append((f'{to * 1000:.0f} ms', tr, f'{tr * 1.0:.0f} s / 20 s', c['sent'], c['sent'] - c['timeouts'], c['timeouts'], c['server_done'] - (c['sent'] - c['timeouts'])))
table(rows, ['调用超时', '熔断器打开的次数', '熔断器处于打开的时间(次数 × 1 s)', '发出的调用', '其中拿到 200', '其中超时', '服务端白干(客户端已超时仍处理完)'])
nerr()
print('  下游完全健康,但超时 100 ms 把 20% 的慢请求全算成失败,熔断器反复打开;被拒的请求本来都能成功(打开期间调用方什么也拿不到)。超时要比下游的正常尾延迟长')
