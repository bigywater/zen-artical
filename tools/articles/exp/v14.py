import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v14'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('降级(degradation):依赖出问题时,用一个差一点但可用的结果代替,而不是整个请求失败。“页面”= 一个请求取某个用户的推荐;推荐由一个下游服务 D 提供(本进程里的 HTTP 服务)。降级结果有两种:默认值(空推荐)和缓存(这个用户最近一次成功拿到的推荐,可能已经过期)')

# ============ 一 ============
print('== 一:依赖整段时间不可用。client 以 100 个/秒开环发请求,共 8 秒,50 个用户轮流;D 平时 20 ms,第 2 到 5 秒“挂住 1 秒后回 503”。四种做法:无降级(超时 500 ms,失败就报错)、降级为默认值(超时 200 ms)、降级为缓存(超时 200 ms,没有缓存的用户才报错)、熔断 + 缓存(熔断器连续失败 5 次打开,打开后直接用缓存,不再调用 D)。按阶段统计:正常(0 到 2 秒)、故障中(2 到 5 秒)、恢复后(5 到 8 秒)')
def run1(mode):
    t0 = [0.0]
    def d_app(h):
        t = time.perf_counter() - t0[0]
        if 2.0 <= t < 5.0: time.sleep(1.0); h.reply(503, b'x')
        else: time.sleep(0.02); h.reply(200, h.path.encode())
    D = Svc(d_app, backlog=1024); cache = {}; lk = threading.Lock(); br = Breaker(5, 1.0, 3)
    def page(i):
        u = i % 50; t1 = time.perf_counter()
        def call(to):
            st, body, dt = rpc(D.port, f'/rec/{u}/{time.perf_counter() - t0[0]:.3f}', to)
            if st != 200: raise RuntimeError
            return body
        to = 0.5 if mode == 'none' else 0.2
        try:
            if mode == 'breaker': val = br.call(lambda: call(to))
            else: val = call(to)
            with lk: cache[u] = (time.perf_counter(), val)
            return ('ok', time.perf_counter() - t1, 0.0)
        except (RuntimeError, Open, TooMany):
            if mode == 'none': return ('err', time.perf_counter() - t1, 0.0)
            if mode == 'default': return ('fallback', time.perf_counter() - t1, 0.0)
            with lk: c = cache.get(u)
            if c is None: return ('err', time.perf_counter() - t1, 0.0)
            return ('fallback', time.perf_counter() - t1, time.perf_counter() - c[0])
    t0[0] = time.perf_counter(); br.t0 = t0[0]; res = openloop(page, 100, 8.0, workers=600); D.stop()
    out = {}
    for name, lo, hi in (('正常', 0, 2), ('故障中', 2, 5), ('恢复后', 5, 8)):
        sel = [r for ts, r in res if lo <= ts < hi]; n = len(sel); ok = sum(1 for r in sel if r[0] == 'ok'); fb = sum(1 for r in sel if r[0] == 'fallback'); er = sum(1 for r in sel if r[0] == 'err')
        lat = [r[1] for r in sel]; ages = [r[2] for r in sel if r[0] == 'fallback' and r[2] > 0]
        out[name] = (n, ok, fb, er, pct(lat, 50), pct(lat, 99), statistics.mean(ages) if ages else None)
    return out
rows = []
for mode, name in (('none', '无降级'), ('default', '降级为默认值'), ('cache', '降级为缓存'), ('breaker', '熔断 + 缓存')):
    o = run1(mode)
    for ph in ('正常', '故障中', '恢复后'):
        n, ok, fb, er, p50, p99, age = o[ph]
        rows.append((name if ph == '正常' else '', ph, n, f'{ok / n:.0%}', f'{fb / n:.0%}', f'{er / n:.0%}', f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms', f'{age:.1f} s' if age else '-'))
table(rows, ['做法', '阶段', '请求数', '拿到真实结果', '降级结果', '报错', '延迟中位数', 'p99', '降级用的缓存的平均年龄'])
nerr()

# ============ 二 ============
print('== 二:超时设多少才降级。D 没有故障,只是有长尾:95% 的请求 20 ms,5% 的请求 600 ms。降级为缓存(没有缓存的用户,第一次调用要等到拿到结果)。client 100 个/秒,共 8 秒,统计第 2 秒之后。超时越短,越早降级:降级的比例、延迟、和用到的缓存有多旧')
def run2(to):
    def d_app(h): time.sleep(0.6 if rng.random() < 0.05 else 0.02); h.reply(200, b'x')
    rng = random.Random(8); D = Svc(d_app, backlog=1024); cache = {}; lk = threading.Lock()
    def page(i):
        u = i % 50; t1 = time.perf_counter(); st, _, dt = rpc(D.port, '/', to if u in cache else 3.0)
        if st == 200:
            with lk: cache[u] = time.perf_counter()
            return ('ok', time.perf_counter() - t1, 0.0)
        with lk: c = cache.get(u)
        return ('fallback', time.perf_counter() - t1, time.perf_counter() - c if c else 0.0)
    res = openloop(page, 100, 8.0, workers=400); D.stop(); sel = [r for ts, r in res if ts >= 2.0]
    fb = [r for r in sel if r[0] == 'fallback']; lat = [r[1] for r in sel]
    return len(sel), len(fb) / len(sel), pct(lat, 50), pct(lat, 99), (statistics.mean(r[2] for r in fb) if fb else 0.0)
rows = []
for to in (0.05, 0.1, 0.2, 0.4, 0.8):
    n, fr, p50, p99, age = run2(to); rows.append((f'{to * 1000:.0f} ms', n, f'{fr:.1%}', f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms', f'{age:.2f} s'))
table(rows, ['超时', '请求数', '降级的比例', '延迟中位数', 'p99', '降级用的缓存的平均年龄'])
nerr()

# ============ 三 ============
print('== 三:过载时降级。服务有 4 个工作线程;完整模式每个请求 20 ms(含个性化推荐),简化模式 5 ms(跳过个性化,只返回热门)。client 以 300 个/秒发请求(完整模式的容量约 160/s)共 6 秒,统计第 1 秒之后;500 ms 内回来才算成功。比较:一直完整模式(队列最多 50,队满拒绝)/ 队列长度超过 10 就切到简化模式(其余同上)')
def run3(adaptive):
    q = collections.deque(); cv = threading.Condition(); stop = [False]; cnt = collections.Counter()
    def worker():
        while True:
            with cv:
                while not q and not stop[0]: cv.wait(0.1)
                if stop[0]: return
                r = q.popleft(); degraded = adaptive and len(q) >= 10
            time.sleep(0.005 if degraded else 0.02); r['deg'] = degraded; r['code'] = 200; r['ev'].set()
    ths = [threading.Thread(target=worker, daemon=True) for _ in range(4)]; [t.start() for t in ths]
    def one(i):
        t0 = time.perf_counter(); r = {'ev': threading.Event(), 'code': None, 'deg': False}
        with cv:
            if len(q) >= 50: return ('rej', 0.0, False)
            q.append(r); cv.notify()
        ok = r['ev'].wait(0.5); return ('ok' if ok else 'timeout', time.perf_counter() - t0, r['deg'])
    res = openloop(one, 300, 6.0, workers=600); stop[0] = True
    sel = [r for ts, r in res if ts >= 1.0]; ok = [r for r in sel if r[0] == 'ok']
    return len(sel), len(ok) / 5, sum(1 for r in ok if r[2]) / max(1, len(ok)), pct([r[1] for r in ok], 99) if ok else float('nan')
rows = []
for adaptive, name in ((False, '一直完整模式'), (True, '队列 ≥ 10 就切到简化模式')):
    n, gp, dshare, p99 = run3(adaptive); rows.append((name, n, f'{gp:.0f}/s', f'{dshare:.0%}', f'{p99 * 1000:.0f} ms'))
table(rows, ['做法', '请求数', '成功速率', '成功的里面是简化结果的比例', '成功请求的 p99'])
