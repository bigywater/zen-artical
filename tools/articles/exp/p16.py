import sys, os, asyncio, threading, resource, concurrent.futures as cf; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, aiohttp
tee('p16')
DELAY = 0.1
def slow(h): time.sleep(DELAY); h.reply(200, b'x' * 200)

def rss_mib(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576

def run_threads(url, n, workers):
    s = requests.Session(); s.mount('http://', requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=workers))
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(workers) as ex: list(ex.map(lambda _: s.get(url).status_code, range(n)))
    return ms(t0)

async def _aio(url, n, conc):
    sem = asyncio.Semaphore(conc)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
        async def one():
            async with sem:
                async with s.get(url) as r: await r.read()
        t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(n)]); return ms(t0)
def run_aio(url, n, conc): return asyncio.run(_aio(url, n, conc))

print('== 一:1000 个请求,服务器每个请求停 0.1 秒;不同并发量下 线程池(requests)与 asyncio(aiohttp)的总耗时')
print(f'  理论下限 = 1000 / 并发 × 0.1 秒')
print(f'  {"并发":>6}{"理论下限":>10}{"线程池 requests":>16}{"asyncio aiohttp":>16}')
with Srv(slow) as sv:
    U = sv.url('/')
    for c in (1, 10, 50, 100, 200, 300):
        n = 1000 if c >= 10 else 40
        if c == 10: n = 200
        lb = n / c * DELAY * 1000
        try:
            th = median([run_threads(U, n, c) for _ in range(2)]); th_s = f'{th:>12.0f} ms'
        except Exception as e: th_s = f'{"失败:" + type(e).__name__:>15}'
        try:
            ai = median([run_aio(U, n, c) for _ in range(2)]); ai_s = f'{ai:>12.0f} ms'
        except Exception as e: ai_s = f'{"失败:" + type(e).__name__:>15}'
        print(f'  {c:>6}{lb:>8.0f} ms{th_s}{ai_s}   (请求数 {n})')
print('  说明:macOS 监听队列上限 128(kern.ipc.somaxconn),并发连接一次涌入太多时测试服务器会重置连接,所以并发更高的数据不可靠,没有测')

print('== 二:服务器不延迟(响应立刻返回),3000 个请求,并发 50:纯客户端开销')
def fast(h): h.reply(200, b'x' * 200)
with Srv(fast) as sv:
    U = sv.url('/')
    th = [run_threads(U, 3000, 50) for _ in range(3)]; ai = [run_aio(U, 3000, 50) for _ in range(3)]
    print(f'  线程池 requests:每个请求平均 {median(th) / 3000:.3f} ms(总耗时 {median(th):.0f} ms)')
    print(f'  asyncio aiohttp:每个请求平均 {median(ai) / 3000:.3f} ms(总耗时 {median(ai):.0f} ms)')

print('== 三:并发数增大时的内存(各在独立的子进程里跑,取该进程的峰值内存 ru_maxrss)')
import subprocess, json
CODE = r'''
import sys, time, asyncio, resource, concurrent.futures as cf, requests, aiohttp
kind, port, n, conc = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
url = f"http://127.0.0.1:{port}/"
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
if kind == "thread":
    s = requests.Session(); s.mount("http://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=conc))
    with cf.ThreadPoolExecutor(conc) as ex: list(ex.map(lambda _: s.get(url).status_code, range(n)))
else:
    async def main():
        sem = asyncio.Semaphore(conc)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
            async def one():
                async with sem:
                    async with s.get(url) as r: await r.read()
            await asyncio.gather(*[one() for _ in range(n)])
    asyncio.run(main())
print(base, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576)
'''
d = pdir('p16'); (d / 'm.py').write_text(CODE)
env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
with Srv(slow) as sv:
    print(f'  {"并发":>6}{"线程池 requests 峰值内存":>24}{"asyncio aiohttp 峰值内存":>26}   (起点:导入库之后的内存)')
    for c in (10, 100, 200):
        out = {}
        for kind in ('thread', 'aio'):
            o = subprocess.run([sys.executable, str(d / 'm.py'), kind, str(sv.port), str(max(c * 2, 200)), str(c)], capture_output=True, text=True, env=env, timeout=120)
            out[kind] = o.stdout.split() if o.returncode == 0 else ['err', o.stderr.strip()[-80:]]
        if out['thread'][0] == 'err' or out['aio'][0] == 'err': print(f'  {c}: {out}'); continue
        t0_, t1_ = (float(x) for x in out['thread']); a0_, a1_ = (float(x) for x in out['aio'])
        print(f'  {c:>6}{t1_:>20.1f} MiB{a1_:>22.1f} MiB   (起点 {t0_:.1f} / {a0_:.1f} MiB;比起点多出 {t1_ - t0_:.1f} / {a1_ - a0_:.1f} MiB)')
purge()
