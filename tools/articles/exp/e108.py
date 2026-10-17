import threading, time, json, os, collections, statistics
from concurrent.futures import ThreadPoolExecutor

class Open(Exception): pass

class Breaker:
    def __init__(self, threshold=5, reset_timeout=0.5, log=None):
        self.threshold, self.reset_timeout = threshold, reset_timeout
        self.state = 'closed'; self.fails = 0; self.opened_at = 0.0; self.lock = threading.Lock(); self.log = log if log is not None else []
        self.t0 = time.perf_counter(); self.probing = False
    def _set(self, s):
        if s != self.state: self.log.append((round(time.perf_counter() - self.t0, 3), self.state, s)); self.state = s
    def call(self, f):
        with self.lock:
            if self.state == 'open':
                if time.perf_counter() - self.opened_at >= self.reset_timeout and not self.probing:
                    self._set('half_open'); self.probing = True
                else: raise Open()
            elif self.state == 'half_open' and self.probing: raise Open()
        try: r = f()
        except Exception:
            with self.lock:
                if self.state == 'half_open': self.probing = False; self.opened_at = time.perf_counter(); self._set('open')
                else:
                    self.fails += 1
                    if self.fails >= self.threshold: self.opened_at = time.perf_counter(); self._set('open')
            raise
        with self.lock:
            if self.state == 'half_open': self.probing = False; self._set('closed')
            self.fails = 0
        return r

T0 = [0.0]
OUT_START, OUT_END, SLOW = 0.5, 1.5, 0.15
def downstream():
    t = time.perf_counter() - T0[0]
    if OUT_START <= t < OUT_END:
        time.sleep(SLOW); raise ConnectionError("下游超时")     # 故障期: 每次调用都要等 0.15 s 才失败
    time.sleep(0.005); return "ok"

def run(use_breaker, rate=50, dur=3.0, workers=8):
    br = Breaker(); rows = []; calls = [0]; lock = threading.Lock()
    def handle(t_submit):
        try:
            if use_breaker:
                def f():
                    with lock: calls[0] += 1
                    return downstream()
                br.call(f)
            else:
                with lock: calls[0] += 1
                downstream()
            res = 'ok'
        except Open: res = 'fast_fail'
        except ConnectionError: res = 'fail'
        rows.append((t_submit, time.perf_counter() - T0[0], res))
    T0[0] = time.perf_counter(); br.t0 = T0[0]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        n = int(rate * dur)
        for i in range(n):
            target = T0[0] + i / rate
            d = target - time.perf_counter()
            if d > 0: time.sleep(d)
            ex.submit(handle, time.perf_counter() - T0[0])
    lat = [(s, e - s, r) for s, e, r in rows]
    return {'calls': calls[0], 'total': len(rows), 'rows': lat, 'log': br.log, 'finish': max(e for _, e, _ in rows)}

print("== 一、熔断器状态机(closed → open → half_open → closed) ==")
res = {}
res['with'] = run(True); res['without'] = run(False)
print("  状态转换日志(相对开始的秒数):")
for t, a, b in res['with']['log']: print(f"    {t:6.3f} s  {a:<9} → {b}")
print("\n== 二、有无熔断器的对照(50 请求/秒 × 3 秒, 8 个工作线程; 0.5–1.5 s 下游故障, 每次调用要等 0.15 s 才失败) ==")
def stats(r):
    lat = sorted(l for _, l, _ in r['rows']); cnt = collections.Counter(x for *_, x in r['rows'])
    outage = [l for s, l, _ in r['rows'] if 0.5 <= s < 1.5]; after = [l for s, l, _ in r['rows'] if 1.5 <= s < 2.5]
    return dict(calls=r['calls'], ok=cnt['ok'], fail=cnt['fail'], fast_fail=cnt['fast_fail'], p50_out=statistics.median(outage) * 1000, max_out=max(outage) * 1000, p50_after=statistics.median(after) * 1000, max_after=max(after) * 1000, max_all=max(lat) * 1000, finish=r['finish'])
S = {k: stats(v) for k, v in res.items()}
for k, label in (('without', '无熔断器'), ('with', '有熔断器')):
    s = S[k]; print(f"  {label}: 真正打到下游 {s['calls']:>3} 次 | 成功 {s['ok']:>3} | 下游报错 {s['fail']:>3} | 快速失败 {s['fast_fail']:>3} | 故障期内请求的延迟 中位 {s['p50_out']:7.1f} ms 最大 {s['max_out']:7.1f} ms | 故障恢复后 1 秒内请求的延迟 中位 {s['p50_after']:7.1f} ms 最大 {s['max_after']:7.1f} ms | 全部处理完 {s['finish']:.2f} s")
print("\n== 三、每 0.5 秒窗口内请求的结果(50 请求/秒; 有熔断器 / 无熔断器) ==")
def windows(r):
    d = collections.defaultdict(collections.Counter)
    for s, l, x in r['rows']: d[int(s / 0.5)][x] += 1
    return [dict(d[i]) for i in range(6)]
W = {k: windows(v) for k, v in res.items()}
for i in range(6): print(f"  {i*0.5:.1f}–{i*0.5+0.5:.1f} s   有熔断器 {W['with'][i]}   无熔断器 {W['without'][i]}")

print("\n== 四、请求速率超过线程池处理能力(100 请求/秒 × 8 个线程 ≈ 15 个并发, 故障期每次调用占用线程 0.15 s) ==")
res2 = {'with': run(True, rate=100, dur=3.0), 'without': run(False, rate=100, dur=3.0)}
S2 = {k: stats(v) for k, v in res2.items()}
for k, label in (('without', '无熔断器'), ('with', '有熔断器')):
    s = S2[k]; print(f"  {label}: 打到下游 {s['calls']:>3} 次 | 成功 {s['ok']:>3} | 下游报错 {s['fail']:>3} | 快速失败 {s['fast_fail']:>3} | 故障期请求延迟 中位 {s['p50_out']:7.1f} ms 最大 {s['max_out']:7.1f} ms | 恢复后 1 秒内延迟 中位 {s['p50_after']:7.1f} ms 最大 {s['max_after']:7.1f} ms | 全部处理完 {s['finish']:.2f} s")
print("  故障结束(1.5 s)之后, 「无熔断器」那一组里还在排队的请求从什么时候才被处理完:")
for k in ('without', 'with'):
    rows = res2[k]['rows']; late = [e for e in ((s + l) for s, l, _ in rows) if e > 1.5]
    healthy_after = max((s + l) for s, l, _ in rows if s < 1.5)
    print(f"    {'无熔断器' if k=='without' else '有熔断器'}: 故障期间提交的最后一个请求 {healthy_after:.2f} s 才处理完; 其中 1.5 s 之后才处理完的请求 {len(late)} 个")
W2 = {k: windows(v) for k, v in res2.items()}
json.dump({'S': S, 'S2': S2, 'log': res['with']['log'], 'log2': res2['with']['log'], 'W': W, 'W2': W2}, open(os.path.join(os.environ['HERE'], 'out/108.json'), 'w'))
