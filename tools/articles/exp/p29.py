import sys, os, asyncio, random, aiohttp; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p29')
N = 200; OUTAGE = 1.0; CAP = 20; WORK = 0.05; MAXTRY = 12
T0 = [0.0]
def server(h):
    t = time.perf_counter() - T0[0]
    if t < OUTAGE: return h.reply(503, b'down')
    if h.server.srv.inflight > CAP: return h.reply(503, b'busy')
    time.sleep(WORK); h.reply(200, b'ok')

def strat(name, rng):
    def f(attempt, prev):
        if name == '立刻重试': return 0.0
        if name == '固定延迟 0.5 秒': return 0.5
        if name == '指数退避(无抖动)': return min(5.0, 0.1 * 2 ** attempt)
        if name == '指数退避 + 完全抖动': return rng.uniform(0, min(5.0, 0.1 * 2 ** attempt))
        if name == '去相关抖动': return min(5.0, rng.uniform(0.1, max(0.1, prev * 3)))
    return f

async def run(name, seed=1):
    rng = random.Random(seed); f = strat(name, rng)
    with Srv(server) as sv:
        T0[0] = time.perf_counter(); sv.reset(); results = []
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
            async def client(i):
                prev = 0.1
                for attempt in range(MAXTRY):
                    async with s.get(sv.url('/')) as r:
                        await r.read()
                        if r.status == 200: results.append((i, attempt + 1, time.perf_counter() - T0[0])); return
                    d = f(attempt, prev); prev = max(d, 0.1)
                    if d: await asyncio.sleep(d)
                    else: await asyncio.sleep(0)
                results.append((i, None, time.perf_counter() - T0[0]))
            await asyncio.gather(*[client(i) for i in range(N)])
        ts = sorted(l['t'] for l in sv.log); base = T0[0]; ts = [t - base for t in ts]
        def peak(w):
            best = 0; j = 0
            for i in range(len(ts)):
                while ts[i] - ts[j] > w: j += 1
                best = max(best, i - j + 1)
            return best
        ok = [r for r in results if r[1]]; fail = N - len(ok)
        return dict(attempts=len(ts), peak01=peak(0.1), peak1=peak(1.0), done=max(r[2] for r in ok) if ok else None, fail=fail, maxtry=max((r[1] for r in ok), default=0), t_after=sum(1 for t in ts if t >= OUTAGE))

print(f'(实验设置:{N} 个客户端同时开始,每个只要成功一次;服务器前 {OUTAGE} 秒整体故障(直接回 503),之后同时处理的请求超过 {CAP} 个就回 503(处理一个请求 {WORK} 秒);每个客户端最多尝试 {MAXTRY} 次)')
print('== 一:五种重试策略(同样的随机种子 1)')
print(f'  {"策略":<18}{"服务器收到请求":>14}{"任意 0.1 秒内最多":>16}{"任意 1 秒内最多":>16}{"全部成功于":>11}{"放弃的客户端":>12}{"最多尝试":>8}')
res = {}
for name in ('立刻重试', '固定延迟 0.5 秒', '指数退避(无抖动)', '指数退避 + 完全抖动', '去相关抖动'):
    r = asyncio.run(run(name)); res[name] = r
    print(f'  {name:<16}{r["attempts"]:>12} 个{r["peak01"]:>14} 个{r["peak1"]:>14} 个' + (f'{r["done"]:>9.1f} 秒' if r['done'] else f'{"—":>11}') + f'{r["fail"]:>12}{r["maxtry"]:>8}')
print('== 二:同一种策略(指数退避,无抖动 与 完全抖动),换 4 个随机种子重复,看结果稳不稳')
for name in ('指数退避(无抖动)', '指数退避 + 完全抖动'):
    rs = [asyncio.run(run(name, seed)) for seed in (2, 3, 4, 5)]
    print(f'  {name}:服务器收到请求 {[r["attempts"] for r in rs]};任意 0.1 秒内最多 {[r["peak01"] for r in rs]};全部成功于 {[round(r["done"], 1) if r["done"] else None for r in rs]} 秒')
purge()
