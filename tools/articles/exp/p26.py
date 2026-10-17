import sys, os, asyncio, aiohttp; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p26')
LAT = 0.05
def srv(h): time.sleep(LAT); h.reply(200, b'ok')

class FixedInterval:
    """全局:任意两个请求的开始时间至少相隔 interval。"""
    def __init__(self, interval): self.i = interval; self.next = 0.0; self.lock = asyncio.Lock()
    async def acquire(self):
        async with self.lock:
            now = time.monotonic(); wait = max(0.0, self.next - now)
            if wait: await asyncio.sleep(wait)
            self.next = max(now, self.next) + self.i if wait == 0 else self.next + self.i
class TokenBucket:
    def __init__(self, rate, burst): self.rate = rate; self.cap = burst; self.tokens = burst; self.last = time.monotonic(); self.lock = asyncio.Lock()
    async def acquire(self):
        async with self.lock:
            while True:
                now = time.monotonic(); self.tokens = min(self.cap, self.tokens + (now - self.last) * self.rate); self.last = now
                if self.tokens >= 1: self.tokens -= 1; return
                await asyncio.sleep((1 - self.tokens) / self.rate)

def stats(sv):
    ts = sorted(l['t'] for l in sv.log); t0 = ts[0]; ts = [t - t0 for t in ts]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    def mx(win):
        best = 0; j = 0
        for i in range(len(ts)):
            while ts[i] - ts[j] > win: j += 1
            best = max(best, i - j + 1)
        return best
    return dict(n=len(ts), dur=ts[-1], rate=(len(ts) - 1) / ts[-1] if ts[-1] else 0, gmin=min(gaps) * 1000, gmed=median(gaps) * 1000, w1=mx(1.0), w01=mx(0.1))
def fmt(s): return f'{s["n"]} 个请求用了 {s["dur"]:.2f} 秒,平均 {s["rate"]:.1f} 个/秒;相邻请求最小间隔 {s["gmin"]:.1f} ms,中位 {s["gmed"]:.1f} ms;任意 1 秒内最多 {s["w1"]} 个,任意 0.1 秒内最多 {s["w01"]} 个'

async def drive(url, total, workers, limiter=None, sleep_between=0.0):
    q = asyncio.Queue()
    for i in range(total): q.put_nowait(i)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
        async def worker():
            while True:
                try: q.get_nowait()
                except asyncio.QueueEmpty: return
                if limiter: await limiter.acquire()
                async with s.get(url) as r: await r.read()
                if sleep_between: await asyncio.sleep(sleep_between)
        await asyncio.gather(*[worker() for _ in range(workers)])

def run(coro_fn):
    with Srv(srv) as sv:
        asyncio.run(coro_fn(sv.url('/'))); return stats(sv)

print('== 一:想把速度限制在 10 个/秒。做法 A:每个 worker 各自在请求之间 sleep(0.1)(服务器每个请求耗时 0.05 秒)')
for w in (1, 5, 20):
    s = run(lambda u: drive(u, 100 if w < 20 else 200, w, None, 0.1)); print(f'  {w:>2} 个 worker:{fmt(s)}')

print('== 二:做法 B:全局固定间隔(任意两个请求的开始至少隔 0.1 秒),不管有几个 worker')
for w in (1, 5, 20):
    s = run(lambda u: drive(u, 60, w, FixedInterval(0.1))); print(f'  {w:>2} 个 worker:{fmt(s)}')

print('== 三:做法 C:令牌桶 rate=10/秒,桶容量(burst)不同;20 个 worker,100 个请求')
for b in (1, 5, 20):
    s = run(lambda u: drive(u, 100, 20, TokenBucket(10, b))); print(f'  burst={b:>2}:{fmt(s)}')

print('== 四:令牌桶空闲一段时间之后:先发 30 个,停 2 秒让桶重新装满,再发 30 个;burst=10,rate=10/秒;看每一批的前 0.5 秒内有多少个请求')
async def idle_test(url):
    tb = TokenBucket(10, 10)
    await drive(url, 30, 20, tb); await asyncio.sleep(2.0); await drive(url, 30, 20, tb)
with Srv(srv) as sv:
    asyncio.run(idle_test(sv.url('/'))); ts = sorted(l['t'] for l in sv.log)
    b1 = [t - ts[0] for t in ts[:30]]; b2 = [t - ts[30] for t in ts[30:]]
    print(f'  第一批(桶是满的):前 0.5 秒内 {sum(1 for t in b1 if t <= 0.5)} 个,前 0.1 秒内 {sum(1 for t in b1 if t <= 0.1)} 个,30 个用了 {b1[-1]:.2f} 秒')
    print(f'  第二批(空闲 2 秒之后桶又满了):前 0.5 秒内 {sum(1 for t in b2 if t <= 0.5)} 个,前 0.1 秒内 {sum(1 for t in b2 if t <= 0.1)} 个,30 个用了 {b2[-1]:.2f} 秒')

print('== 五:"间隔"从哪里算起:每个请求完成后再等 0.1 秒(完成到下一个开始) 对比 两次开始之间隔 0.1 秒;服务器耗时 0.05 秒 与 0.5 秒两种')
async def after_done(url, lat_gap=0.1, n=30):
    async with aiohttp.ClientSession() as s:
        for _ in range(n):
            async with s.get(url) as r: await r.read()
            await asyncio.sleep(lat_gap)
async def start_to_start(url, n=30):
    async with aiohttp.ClientSession() as s:
        fi = FixedInterval(0.1)
        async def one():
            await fi.acquire()
            async with s.get(url) as r: await r.read()
        await asyncio.gather(*[one() for _ in range(n)])
for lat in (0.05, 0.5):
    LAT = lat
    s1 = run(lambda u: after_done(u)); s2 = run(lambda u: start_to_start(u))
    print(f'  服务器耗时 {lat} 秒:完成后再等 0.1 秒 → 平均 {s1["rate"]:.1f} 个/秒(相邻开始间隔中位 {s1["gmed"]:.0f} ms);开始到开始隔 0.1 秒(允许重叠)→ 平均 {s2["rate"]:.1f} 个/秒(中位 {s2["gmed"]:.0f} ms)')
purge()
