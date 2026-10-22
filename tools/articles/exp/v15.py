import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v15'); reset()
print('5 个副本的后端,每个副本最多同时处理 4 个请求(信号量),每个请求约 40 ms(乘以一个对数正态噪声,σ = 0.25),超过 4 个的在副本里排队;“慢节点”= 其中一个副本的处理时间变成 3 倍(约 120 ms,它自己的容量只有约 33/s);第三节另有一种“偶发长尾”:任何副本上 3% 的请求会慢 10 倍(约 400 ms)。副本和 client 都在本进程里(请求是函数调用,没有网络),client 以固定速率开环发请求;理论总容量 5 × 4 ÷ 40 ms = 500/s,实测要低一些')

class Cluster:
    def __init__(s, slow=(), n=5, conc=4, seed=1, tail=0.0):
        s.tail = tail; s.n, s.slow, s.sems = n, set(slow), [threading.Semaphore(conc) for _ in range(n)]; s.inflight = [0] * n; s.lk = threading.Lock(); s.rng = random.Random(seed); s.work = [0] * n; s.hits = [0] * n
    def svc(s, r):
        with s.lk: x = s.rng.lognormvariate(0, 0.25); tl_ = s.rng.random() < s.tail
        return 0.04 * x * (3 if r in s.slow else 1) * (10 if tl_ else 1)
    def pick(s, policy, exclude=None):
        with s.lk:
            c = [i for i in range(s.n) if i != exclude]
            if policy == 'random': r = s.rng.choice(c)
            else: m = min(s.inflight[i] for i in c); r = s.rng.choice([i for i in c if s.inflight[i] == m])
            s.inflight[r] += 1; s.hits[r] += 1; return r
    def run(s, r):
        with s.sems[r]: time.sleep(s.svc(r))
        with s.lk: s.inflight[r] -= 1; s.work[r] += 1

def request(cl, policy, hedge):
    t0 = time.perf_counter(); done = threading.Event(); first = [None]
    def go(r):
        cl.run(r)
        if first[0] is None: first[0] = time.perf_counter() - t0
        done.set()
    r1 = cl.pick(policy); threading.Thread(target=go, args=(r1,), daemon=True).start(); sent = 1
    if hedge and not done.wait(hedge):
        r2 = cl.pick(policy, exclude=r1); threading.Thread(target=go, args=(r2,), daemon=True).start(); sent = 2
    done.wait(); return first[0], sent
def bench(cl, policy, hedge, rate, dur=6.0):
    out = openloop(lambda i: request(cl, policy, hedge), rate, dur, workers=800); time.sleep(0.5)
    sel = [r for ts, r in out if ts >= 1.0]; lat = [r[0] for r in sel]; sent = sum(r[1] for r in sel)
    return lat, sent / len(sel)
fm = lambda x: f'{x * 1000:.0f} ms'

# ============ 一 ============
print('== 一:一个慢节点对尾延迟的影响。client 100 个/秒,共 6 秒(统计第 1 秒之后的 500 个请求),不做 hedging。三种情况:5 个副本都正常 / 有 1 个慢节点,随机挑副本 / 有 1 个慢节点,挑在途请求最少的副本。“落在慢节点的请求”看实际有多少比例的请求发给了它')
rows = []
for name, slow, pol in (('全部正常 · 随机', (), 'random'), ('1 个慢节点 · 随机', (0,), 'random'), ('1 个慢节点 · 挑在途最少的', (0,), 'least')):
    cl = Cluster(slow); lat, _ = bench(cl, pol, None, 100); share = cl.hits[0] / sum(cl.hits)
    rows.append((name, fm(pct(lat, 50)), fm(pct(lat, 90)), fm(pct(lat, 99)), fm(pct(lat, 99.9)), f'{share:.0%}'))
table(rows, ['情况', 'p50', 'p90', 'p99', 'p99.9', '发给副本 0 的请求比例'])

# ============ 二 ============
print('== 二:hedging(对冲请求)。1 个慢节点,随机挑副本,client 100/s。做法:发出第一个请求后,等 delay 还没回来,就再挑另一个副本发第二个,取先回来的那个(另一个不取消,仍会处理完)。delay 取 60 / 100 / 150 / 250 ms(正常副本上请求的 p50 约 42 ms,慢节点上约 125 ms)。“额外请求”= 平均每个请求多发了几个')
rows = []
for hd in (None, 0.06, 0.1, 0.15, 0.25):
    cl = Cluster((0,)); lat, avg = bench(cl, 'random', hd, 100)
    rows.append(('不对冲' if hd is None else f'{hd * 1000:.0f} ms', fm(pct(lat, 50)), fm(pct(lat, 99)), fm(pct(lat, 99.9)), f'{avg - 1:.1%}'))
table(rows, ['对冲 delay', 'p50', 'p99', 'p99.9', '额外请求'])

# ============ 三 ============
print('== 三:负载高的时候对冲会反过来添乱。这一节没有慢节点,5 个副本都正常,只有偶发长尾(任何副本上 3% 的请求慢 10 倍);随机挑副本;对冲 delay = 100 ms vs 不对冲;到达速率 100 / 250 / 400 个/秒(理论容量约 500/s,即利用率约 20% / 50% / 80%,实际因为调度开销容量更低)。统计 p50 / p99 / p99.9 以及额外请求')
rows = []
for rate in (100, 250, 400):
    for hd in (None, 0.1):
        cl = Cluster(tail=0.03); lat, avg = bench(cl, 'random', hd, rate)
        rows.append((f'{rate}/s', '不对冲' if hd is None else '100 ms', fm(pct(lat, 50)), fm(pct(lat, 99)), fm(pct(lat, 99.9)), f'{avg - 1:.1%}'))
table(rows, ['到达速率', '对冲', 'p50', 'p99', 'p99.9', '额外请求'])
