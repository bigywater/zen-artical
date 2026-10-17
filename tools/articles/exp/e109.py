import time, threading, json, os, collections, sys
from collections import deque

class Fixed:
    def __init__(s, limit, window=1.0): s.limit, s.window, s.count, s.start = limit, window, 0, None
    def allow(s, t):
        w = int(t // s.window)
        if s.start != w: s.start, s.count = w, 0
        if s.count < s.limit: s.count += 1; return True
        return False
class SlidingLog:
    def __init__(s, limit, window=1.0): s.limit, s.window, s.q = limit, window, deque()
    def allow(s, t):
        while s.q and s.q[0] <= t - s.window: s.q.popleft()
        if len(s.q) < s.limit: s.q.append(t); return True
        return False
class TokenBucket:
    def __init__(s, rate, cap): s.rate, s.cap, s.tokens, s.last = rate, cap, cap, 0.0
    def allow(s, t):
        s.tokens = min(s.cap, s.tokens + (t - s.last) * s.rate); s.last = t
        if s.tokens >= 1: s.tokens -= 1; return True
        return False
class LeakyMeter:
    def __init__(s, rate, cap): s.rate, s.cap, s.level, s.last = rate, cap, 0.0, 0.0
    def allow(s, t):
        s.level = max(0.0, s.level - (t - s.last) * s.rate); s.last = t
        if s.level + 1 <= s.cap: s.level += 1; return True
        return False
def make():
    return {'固定窗口': Fixed(10), '滑动窗口日志': SlidingLog(10), '令牌桶(速率10/s, 容量5)': TokenBucket(10, 5), '漏桶(泄漏10/s, 容量5)': LeakyMeter(10, 5)}
def run(arrivals):
    out = {}
    for name, lim in make().items(): out[name] = [t for t in arrivals if lim.allow(t)]
    return out
def max_in_window(ts, w):
    best = 0; j = 0
    for i, t in enumerate(ts):
        while ts[j] <= t - w: j += 1
        best = max(best, i - j + 1)
    return best

print("== 一、边界突发: 0.9–0.999 s 来 10 个, 1.0–1.09 s 又来 10 个(限制是每秒 10 个) ==")
arr = [0.9 + i * 0.0099 for i in range(10)] + [1.0 + i * 0.009 for i in range(10)]
r = run(arr); A = {}
for n, ts in r.items():
    A[n] = (len(ts), max_in_window(ts, 0.2)); print(f"  {n:<28} 放行 {len(ts):>2}/20 个 | 其中任意 0.2 秒内最多放行 {A[n][1]:>2} 个")
print("\n== 二、t=0 瞬间来 50 个请求 ==")
arr = [0.0] * 50; r = run(arr); B = {}
for n, ts in r.items(): B[n] = len(ts); print(f"  {n:<28} 放行 {len(ts)}/50 个")
print("\n== 三、持续高压: 100 个请求/秒, 持续 5 秒 ==")
arr = [i / 100 for i in range(500)]; r = run(arr); C = {}
for n, ts in r.items():
    per_sec = [sum(1 for t in ts if k <= t < k + 1) for k in range(5)]
    C[n] = (per_sec, max_in_window(ts, 0.1)); print(f"  {n:<28} 每秒放行 {per_sec} | 任意 0.1 秒内最多 {C[n][1]:>2} 个")
print("\n== 四、空闲后突发: 前 3 秒无请求, 之后瞬间来 30 个 ==")
arr = [3.0] * 30; r = {}
for name, lim in make().items():
    r[name] = [t for t in arr if lim.allow(t)]
D = {n: len(ts) for n, ts in r.items()}
for n, k in D.items(): print(f"  {n:<28} 放行 {k}/30 个")

print("\n== 五、内存: 限制 10 万次/窗口时, 每种算法要保存多少东西 ==")
big = SlidingLog(100000)
for i in range(100000): big.allow(i * 1e-6)
print(f"  滑动窗口日志: 保存 {len(big.q):,} 个时间戳 | 固定窗口: 保存 2 个整数 (count, start) | 令牌桶 / 漏桶: 保存 2 个浮点数 (tokens 或 level, last)")

print("\n== 六、真实时间 + 多线程: 8 个线程 2 秒内拼命请求, 令牌桶 rate=200/s capacity=20 ==")
class RT:
    def __init__(s, rate, cap, lock): s.b = TokenBucket(rate, cap); s.b.last = time.perf_counter(); s.lock = lock
    def allow(s):
        t = time.perf_counter()
        if s.lock:
            with s.lock: return s.b.allow(t)
        return s.b.allow(t)
def hammer(lock, dur=2.0, threads=8):
    rt = RT(200, 20, lock); acc = [0] * threads; att = [0] * threads; end = time.perf_counter() + dur
    def w(i):
        while time.perf_counter() < end:
            att[i] += 1
            if rt.allow(): acc[i] += 1
    ths = [threading.Thread(target=w, args=(i,)) for i in range(threads)]
    for t in ths: t.start()
    for t in ths: t.join()
    return sum(acc), sum(att)
theo = 200 * 2.0 + 20
a1, t1 = hammer(threading.Lock()); a2, t2 = hammer(None)
print(f"  理论最多放行 ≈ rate×时长+容量 = {theo:.0f}")
print(f"  加锁:   放行 {a1} 个 / 尝试 {t1:,} 次")
print(f"  不加锁: 放行 {a2} 个 / 尝试 {t2:,} 次  (超出理论上限 {max(0, a2 - theo):.0f} 个)")
tt = time.perf_counter(); lim = TokenBucket(1e9, 1e9)
for i in range(300000): lim.allow(i * 1e-9)
print(f"  单次 allow() 的开销约 {(time.perf_counter()-tt)/300000*1e9:.0f} ns(纯 Python 令牌桶, 不含锁)")
json.dump({'A': A, 'B': B, 'C': {k: v[0] for k, v in C.items()}, 'Cmax': {k: v[1] for k, v in C.items()}, 'D': D, 'rt': [a1, t1, a2, t2, theo]}, open(os.path.join(os.environ['HERE'], 'out/109.json'), 'w'), ensure_ascii=False)
