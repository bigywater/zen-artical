import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v3'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('重试间隔的四种算法(来自 AWS 架构博客的写法):无抖动的指数退避 sleep = min(cap, base × 2^n);Full Jitter sleep = random(0, min(cap, base × 2^n));Equal Jitter sleep = t/2 + random(0, t/2)(t = min(cap, base × 2^n));Decorrelated Jitter sleep = min(cap, random(base, 上次的 sleep × 3))。另外对照“固定间隔”。n 从 0 开始数第几次重试')

def sleeper(algo, base, cap, rng):
    st = {'prev': base, 'n': 0}
    def nxt():
        n = st['n']; st['n'] += 1; t = min(cap, base * 2 ** n)
        if algo == 'fixed': s = base
        elif algo == 'exp': s = t
        elif algo == 'full': s = rng.uniform(0, t)
        elif algo == 'equal': s = t / 2 + rng.uniform(0, t / 2)
        else: s = min(cap, rng.uniform(base, st['prev'] * 3)); st['prev'] = s
        return s
    return nxt
NAMES = {'fixed': '固定间隔', 'exp': '指数退避(无抖动)', 'full': 'Full Jitter', 'equal': 'Equal Jitter', 'decor': 'Decorrelated Jitter'}

# ============ 一 ============
print('== 一:每次重试前等多久。base = 100 ms,cap = 3200 ms,每个算法抽 20000 条重试序列,看第 n 次重试之前的等待:平均值,以及 5% / 95% 分位(毫秒)')
rows = []
for algo in ('fixed', 'exp', 'full', 'equal', 'decor'):
    rng = random.Random(3); seqs = [[sleeper(algo, 100, 3200, rng)() for _ in range(1)] for _ in range(1)]
    cols = [[] for _ in range(7)]
    for _ in range(20000):
        f = sleeper(algo, 100, 3200, rng)
        for k in range(7): cols[k].append(f())
    rows.append((NAMES[algo],) + tuple(f'{statistics.mean(c):.0f} ({pct(c, 5):.0f}~{pct(c, 95):.0f})' for c in cols))
table(rows, ['算法', 'n=0', 'n=1', 'n=2', 'n=3', 'n=4', 'n=5', 'n=6'])
print('  括号里是 5%~95% 分位。无抖动时每个 client 的等待完全相同(区间宽度为 0);Full Jitter 的下限是 0,所以有的 client 几乎立刻重试;Equal Jitter 的下限是一半;Decorrelated 依赖上一次的等待')

# ============ 二 ============
print('== 二:同时被拒的 200 个 client。服务最多同时处理 4 个请求、每个 20 ms(容量 200 个/秒),忙时立刻回 503;前 300 ms 整个服务不可用(全部 503)。200 个 client 几乎同时发第一个请求(Python 起 200 个线程大约要 100 ms 才全部发出,所以第一个窗口里只有一部分),失败就按算法等待后重试,直到成功。base = 100 ms,cap = 3200 ms。统计服务端看到的到达情况(每 100 ms 一个窗口)')
def herd(algo, n=200, base=100, cap=3200, outage=0.3, seed=7):
    arrivals = []; lk = threading.Lock(); T0 = [0.0]
    sem = threading.Semaphore(4)
    def app(h):
        if h.path == '/warm': return h.reply(200, b'w')              # 先让每个 client 把连接建好(200 个连接同时握手会超出内核的 accept 队列,出现与重试算法无关的 reset)
        t = time.perf_counter() - T0[0]
        with lk: arrivals.append(t)
        if t < outage or not sem.acquire(blocking=False): return h.reply(503, b'x')
        try: time.sleep(0.02)
        finally: sem.release()
        h.reply(200, b'ok')
    S = Svc(app, backlog=1024); done = [None] * n; tries = [0] * n; bar = threading.Barrier(n + 1)
    def cl(i):
        rng = random.Random(seed * 1000 + i); f = sleeper(algo, base, cap, rng); time.sleep(i * 0.004); rpc(S.port, '/warm', 5.0); bar.wait()
        while True:
            tries[i] += 1; st, _, _ = rpc(S.port, '/', 5.0)
            if st == 200: done[i] = time.perf_counter() - T0[0]; return
            if tries[i] > 60: done[i] = float('inf'); return
            time.sleep(f() / 1000)
    ths = [threading.Thread(target=cl, args=(i,)) for i in range(n)]; [t.start() for t in ths]
    time.sleep(1.3); T0[0] = time.perf_counter(); bar.wait(); [t.join() for t in ths]; S.stop()
    wins = collections.Counter(int(t / 0.1) for t in arrivals)
    return done, tries, arrivals, wins
rows = []; wintab = {}
for algo in ('fixed', 'exp', 'full', 'equal', 'decor'):
    seeds = (7,) if algo in ('fixed', 'exp') else (7, 8, 9); R = []
    for sd in seeds:
        done, tries, arr, wins = herd(algo, seed=sd); fin = [d for d in done if d != float('inf')]
        R.append(dict(total=len(arr), mean=statistics.mean(tries), mx=max(tries), peak=max(wins.values()), p50=pct(fin, 50), p99=pct(fin, 99), last=max(fin)))
        if sd == 7: wintab[algo] = [wins.get(k, 0) for k in range(0, 20)]
    def med(k, fmt):
        v = [r[k] for r in R]; m = statistics.median(v)
        return fmt(m) + (f' ({fmt(min(v))}~{fmt(max(v))})' if len(R) > 1 else '')
    rows.append((NAMES[algo], len(R), med('total', lambda x: f'{x:.0f}'), med('mean', lambda x: f'{x:.1f}'), med('peak', lambda x: f'{x:.0f}'), med('p50', lambda x: f'{x:.2f} s'), med('p99', lambda x: f'{x:.2f} s'), med('last', lambda x: f'{x:.2f} s')))
table(rows, ['算法', '轮数', '服务端收到的请求总数(中位数,括号是范围)', '平均每个 client 试几次', '最忙的 100 ms 窗口收到', '完成时间中位数', 'p99', '最后一个完成'])
print('  服务端每个 100 ms 窗口收到的请求数(从 0 开始的前 20 个窗口,取第一轮):')
table([(NAMES[a],) + tuple(w) for a, w in wintab.items()], ['算法'] + [str(i) for i in range(20)])

# ============ 三 ============
print('== 三:base 和 cap 的影响(Full Jitter,同样的 200 个 client,每个配置跑一轮)。base 太小退避没有拉开,cap 太小则后面的重试又挤在一起')
rows = []
for base, cap in ((20, 3200), (100, 3200), (400, 3200), (100, 400), (100, 800)):
    done, tries, arr, wins = herd('full', base=base, cap=cap); fin = [d for d in done if d != float('inf')]
    rows.append((f'base {base} ms / cap {cap} ms', len(arr), max(wins.values()), f'{pct(fin, 50):.2f} s', f'{max(fin):.2f} s'))
table(rows, ['参数', '服务端收到的请求总数', '最忙的 100 ms 窗口收到', '完成时间中位数', '最后一个完成'])
nerr()
