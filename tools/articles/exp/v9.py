import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import tracemalloc, math
tee('v9'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('五种限流器都限制到 100 个/秒:固定窗口、滑动窗口日志(记下每个放行请求的时刻)、滑动窗口计数(上一个窗口的计数按重叠比例折算)、令牌桶(速率 100/s、桶容量 burst)、漏桶(请求进队列,按每 10 ms 一个的固定间隔放出,队列最多 capacity 个,满了就拒绝)。前四节用虚拟时钟(同一份实现,不真的 sleep),最后一节是 Go 手写的令牌桶中间件加真实的 HTTP 流量')

class FixedWindow:
    def __init__(s, limit, win=1.0): s.limit, s.win, s.cur, s.n = limit, win, -1, 0
    def allow(s, t):
        w = int(t // s.win)
        if w != s.cur: s.cur, s.n = w, 0
        if s.n < s.limit: s.n += 1; return True, t
        return False, None
class SlidingLog:
    def __init__(s, limit, win=1.0): s.limit, s.win, s.q = limit, win, collections.deque()
    def allow(s, t):
        while s.q and s.q[0] <= t - s.win: s.q.popleft()
        if len(s.q) < s.limit: s.q.append(t); return True, t
        return False, None
class SlidingCounter:
    def __init__(s, limit, win=1.0): s.limit, s.win, s.cur, s.n, s.prev = limit, win, -1, 0, 0
    def allow(s, t):
        w = int(t // s.win)
        if w != s.cur: s.prev = s.n if w == s.cur + 1 else 0; s.cur, s.n = w, 0
        est = s.prev * (1 - (t % s.win) / s.win) + s.n
        if est < s.limit: s.n += 1; return True, t
        return False, None
class TokenBucket:
    def __init__(s, rate, burst): s.rate, s.burst, s.tok, s.last = rate, burst, burst, 0.0
    def allow(s, t):
        s.tok = min(s.burst, s.tok + (t - s.last) * s.rate); s.last = t
        if s.tok >= 1: s.tok -= 1; return True, t
        return False, None
class LeakyBucket:
    """请求进队列,按 1/rate 的间隔放出;返回 (是否接受, 放出时刻)。队列里排着的请求数 = (下一个空闲时刻 - 现在) × rate,超过 capacity 就拒绝"""
    def __init__(s, rate, capacity): s.rate, s.cap, s.free = rate, capacity, 0.0
    def allow(s, t):
        start = max(t, s.free)
        if (start - t) * s.rate >= s.cap: return False, None
        s.free = start + 1.0 / s.rate; return True, start
def make(name, **kw):
    return {'固定窗口': lambda: FixedWindow(100), '滑动窗口日志': lambda: SlidingLog(100), '滑动窗口计数': lambda: SlidingCounter(100),
            '令牌桶': lambda: TokenBucket(100, kw.get('burst', 100)), '漏桶': lambda: LeakyBucket(100, kw.get('cap', 100))}[name]()
ALGOS = ['固定窗口', '滑动窗口日志', '滑动窗口计数', '令牌桶', '漏桶']
def drive(lim, times):
    out = []
    for t in times:
        ok, rel = lim.allow(t); out.append((t, ok, rel))
    return out
def maxwin(rels, w):
    rels = sorted(rels); best = 0; j = 0
    for i, x in enumerate(rels):
        while rels[j] <= x - w: j += 1
        best = max(best, i - j + 1)
    return best

# ============ 一 ============
print('== 一:窗口边界上的突发。系统空闲很久之后,0.9 s 到 1.0 s 之间均匀来 100 个请求,紧接着 1.0 s 到 1.1 s 之间又均匀来 100 个(窗口边界在 1.0 s)。限制是 100 个/秒。统计:放行的总数,以及任意 1 秒内(滑动着看)最多放行了多少个。令牌桶的桶容量取 100 和 20 两种')
times = [0.9 + i / 1000 for i in range(100)] + [1.0 + i / 1000 for i in range(100)]
rows = []
for name, kw in [(a, {}) for a in ALGOS[:3]] + [('令牌桶', {'burst': 100}), ('令牌桶', {'burst': 20}), ('漏桶', {'cap': 100}), ('漏桶', {'cap': 20})]:
    r = drive(make(name, **kw), times); acc = [x for x in r if x[1]]; rel = [x[2] for x in acc]
    label = name + (f'(burst {kw["burst"]})' if 'burst' in kw else f'(capacity {kw["cap"]})' if 'cap' in kw else '')
    rows.append((label, len(acc), maxwin(rel, 1.0)))
table(rows, ['限流器', '放行(接受)的请求', '任意 1 秒内最多放出多少个'])
print('  固定窗口在 1.0 s 前后各放行一整个窗口的额度,1 秒里放出了 200 个(两倍限额);滑动窗口日志是精确的;滑动窗口计数是近似(上一窗口的计数按比例折算);令牌桶允许的突发由桶容量决定,漏桶(队列)把放出的节奏拉平到每 10 ms 一个')

# ============ 二 ============
print('== 二:持续过载下放行的速率。请求以 150 个/秒到达,持续 10 秒:一种是均匀到达,一种是泊松到达(随机间隔,平均 150 个/秒)。限制 100 个/秒;令牌桶 burst = 100,漏桶 capacity = 100。统计 2 到 10 秒(跳过开头的突发)每秒放行(放出)数的最小值、平均值、最大值')
def arrivals(kind, rate=150, dur=10, seed=2):
    if kind == 'uniform': return [i / rate for i in range(rate * dur)]
    rng = random.Random(seed); t = 0.0; out = []
    while t < dur: t += rng.expovariate(rate); out.append(t)
    return out[:-1]
rows = []
for kind in ('uniform', 'poisson'):
    for name in ALGOS:
        r = drive(make(name), arrivals(kind)); c = collections.Counter(int(x[2]) for x in r if x[1] and x[2] is not None and x[2] < 10)
        v = [c.get(s, 0) for s in range(2, 10)]
        rows.append(('均匀' if kind == 'uniform' else '泊松', name, min(v), f'{statistics.mean(v):.1f}', max(v)))
table(rows, ['到达方式', '限流器', '每秒放行 最小', '平均', '最大'])

# ============ 三 ============
print('== 三:周期性的突发。每秒钟的开头一次性来 50 个请求(其余时间没有请求),共 10 秒;限制 100 个/秒(平均速率远低于限制)。令牌桶 burst = 50 与 burst = 10,漏桶 capacity = 50 与 10。看有多少请求被拒绝,以及被接受的请求在队列里等了多久(只有漏桶会排队)')
times = [s + 0.0 for s in range(10) for _ in range(50)]
rows = []
for name, kw in [('固定窗口', {}), ('滑动窗口日志', {}), ('滑动窗口计数', {}), ('令牌桶', {'burst': 50}), ('令牌桶', {'burst': 10}), ('漏桶', {'cap': 50}), ('漏桶', {'cap': 10})]:
    r = drive(make(name, **kw), times); acc = [x for x in r if x[1]]; delays = [x[2] - x[0] for x in acc]
    label = name + (f'(burst {kw["burst"]})' if 'burst' in kw else f'(capacity {kw["cap"]})' if 'cap' in kw else '')
    rows.append((label, f'{len(r) - len(acc)} / {len(r)}', f'{pct(delays, 50) * 1000:.0f} ms', f'{pct(delays, 99) * 1000:.0f} ms'))
table(rows, ['限流器', '被拒绝', '接受的请求等待时间 中位数', 'p99'])

# ============ 四 ============
print('== 四:每个 key 的状态和速度。1000 个 key,每个 key 先来 100 次请求(限制 100,全部放行),然后测 200000 次随机 key 上的 allow 调用的速度;状态大小用 tracemalloc 量 10000 个 key 各来 100 次请求之后多占的内存(Python 对象,不是 C/Go 里的字节数,只看相对大小)')
rows = []
for name in ALGOS:
    lims = {k: make(name) for k in range(1000)}
    for k in range(1000):
        for i in range(100): lims[k].allow(0.5 + i * 0.001)
    rng = random.Random(1); ks = [rng.randrange(1000) for _ in range(200000)]; t = 1.0
    t0 = time.perf_counter()
    for k in ks: t += 0.00001; lims[k].allow(t)
    dt = time.perf_counter() - t0
    tracemalloc.start(); base = tracemalloc.get_traced_memory()[0]
    L = [make(name) for _ in range(10000)]
    for l in L:
        for i in range(100): l.allow(0.5 + i * 0.001)
    mem = tracemalloc.get_traced_memory()[0] - base; tracemalloc.stop(); del L
    rows.append((name, f'{200000 / dt / 1000:.0f} 千次/秒', f'{mem / 10000:.0f} 字节'))
table(rows, ['限流器', 'allow() 速度', '每个 key 的状态(Python 对象)'])
print('  滑动窗口日志要为每个放行的请求存一个时间戳,所以每个 key 的状态随限额线性增长;固定窗口、滑动窗口计数、令牌桶、漏桶每个 key 只存常数个数字')

# ============ 五 ============
print('== 五:Go 手写的令牌桶中间件(net/http,每个 X-Client 一个桶,sync.Mutex 保护,按流逝时间补令牌)。速率 100/s、burst 20,Python 客户端以 200 个/秒的开环速率发 5 秒(共 1000 个请求,同一个 key);再用 8 个并发线程不限速地发 3 秒,检验并发下总放行数是否仍然符合 速率 × 时间 + burst')
def run5(mode):
    port = free_port(); p = subprocess.Popen([str(HERE / 'vtmp/rl/rlsrv'), str(port), '100', '20'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); wait_port(port, 10)
    def stat(): c = http.client.HTTPConnection('127.0.0.1', port, timeout=3); c.request('GET', '/stats'); d = json.loads(c.getresponse().read()); c.close(); return d
    t0 = time.perf_counter()
    if mode == 'open':
        res = openloop(lambda i: rpc(port, '/', 3.0, {'X-Client': 'u1'})[0], 200, 5.0, workers=300); codes = collections.Counter(r for _, r in res)
    else:
        stop = threading.Event(); cc = collections.Counter(); lk = threading.Lock()
        def w():
            while not stop.is_set():
                st = rpc(port, '/', 3.0, {'X-Client': 'u1'})[0]
                with lk: cc[st] += 1
        ths = [threading.Thread(target=w) for _ in range(8)]; [t.start() for t in ths]; time.sleep(3.0); stop.set(); [t.join() for t in ths]; codes = cc
    el = time.perf_counter() - t0; s = stat(); p.terminate(); p.wait(5)
    return codes, el, s
rows = []
for mode, label in (('open', '200/s 开环,5 s'), ('closed', '8 线程不限速,3 s')):
    codes, el, s = run5(mode); allowed = s['allowed']
    ps = s['per_sec']; per = [ps.get(str(k), 0) for k in range(int(el) + 1)]
    rows.append((label, sum(codes.values()), allowed, s['denied'], f'{100 * el + 20:.0f}', per))
table(rows, ['场景', '请求总数', '放行', '429', '理论上界 速率 × 时间 + burst', '每秒放行数'])
nerr()
