import threading, time, random, json, os, collections, statistics

class Server:
    """0 ~ 0.30 s 完全宕机; 之后每 20 ms 的窗口只处理 CAP 个请求, 多出来的被拒绝(503)。"""
    CAP = 15; WINDOW = 0.02
    def __init__(self):
        self.t0 = None; self.lock = threading.Lock(); self.win = {}; self.log = []      # (相对时间, 结果)
    def start(self): self.t0 = time.perf_counter()
    def request(self):
        with self.lock:
            t = time.perf_counter() - self.t0
            if t < 0.30: self.log.append((t, 'down')); return False
            w = int(t / self.WINDOW); self.win[w] = self.win.get(w, 0) + 1
            ok = self.win[w] <= self.CAP; self.log.append((t, 'ok' if ok else 'reject')); return ok

def delays(strategy, rng, n):
    for k in range(n):
        if strategy == 'fixed': yield 0.05
        elif strategy == 'exp': yield min(0.02 * 2 ** k, 0.32)
        elif strategy == 'exp_jitter': yield rng.uniform(0, min(0.02 * 2 ** k, 0.32))

def client(server, strategy, seed, done_at, N=60):
    rng = random.Random(seed)
    it = delays(strategy, rng, N)
    for _ in range(N):
        if server.request(): done_at.append(time.perf_counter() - server.t0); return
        time.sleep(next(it))
    done_at.append(None)

def experiment(strategy, clients=100):
    s = Server(); done = []; ths = [threading.Thread(target=client, args=(s, strategy, i, done)) for i in range(clients)]
    barrier_start = time.perf_counter(); s.start()
    for t in ths: t.start()
    for t in ths: t.join()
    ts = [t for t, _ in s.log]; bins = collections.Counter(int(t / 0.05) for t in ts)
    res = collections.Counter(r for _, r in s.log)
    fine = collections.Counter(int(t / 0.01) for t, _ in s.log)
    return {'strategy': strategy, 'attempts': len(s.log), 'down': res['down'], 'reject': res['reject'], 'ok': res['ok'],
            'finish': max(d for d in done if d is not None), 'peak10ms': max(fine.values()), 'bins': [bins.get(i, 0) for i in range(0, 16)], 'unfinished': sum(1 for d in done if d is None)}

print("== 一、三种策略生成的等待时间序列(前 8 次) ==")
for st in ('fixed', 'exp', 'exp_jitter'):
    d = list(delays(st, random.Random(1), 8)); print(f"  {st:<12} " + "  ".join(f"{x*1000:6.1f}" for x in d) + "  (ms)")
print("\n== 二、100 个客户端同时开始, 服务先宕机 0.30 s, 之后每 20 ms 只能处理 15 个请求 ==")
results = {}
for st in ('fixed', 'exp', 'exp_jitter'):
    runs = [experiment(st) for _ in range(3)]; r = sorted(runs, key=lambda x: x['attempts'])[1]; results[st] = r
    print(f"  {st:<12} 总请求 {r['attempts']:>5} | 宕机期间 {r['down']:>5} | 被限流拒绝 {r['reject']:>5} | 成功 {r['ok']:>3} | 全部完成用时 {r['finish']*1000:6.0f} ms | 任意 10 ms 内最多 {r['peak10ms']:>3} 个请求 (3 次取总请求数居中的一次)")
print("\n== 三、请求时间分布(每 50 ms 一格, 从 0 开始的 16 格) ==")
for st, r in results.items(): print(f"  {st:<12} {r['bins']}")
print("\n== 四、只重试「暂时性」错误 ==")
class Transient(Exception): pass
def retry(f, retry_on, tries=4):
    calls = 0
    for k in range(tries):
        calls += 1
        try: return f(), calls
        except retry_on:
            if k == tries - 1: raise
    return None
def flaky(): raise Transient()
def bad_input(): raise ValueError("参数错了, 重试一万次也没用")
for name, f in (("Transient", flaky), ("ValueError", bad_input)):
    c = [0]
    def g(f=f): c[0] += 1; return f()
    try: retry(g, Transient)
    except Exception as e: print(f"  {name:<10} 函数被调用 {c[0]} 次后抛出 {type(e).__name__}(retry_on=Transient)")
json.dump(results, open(os.path.join(os.environ['HERE'], 'out/107.json'), 'w'))
