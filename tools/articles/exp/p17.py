import sys, os, asyncio, resource, tracemalloc; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import aiohttp
tee('p17')
def slow(h): time.sleep(0.1); h.reply(200, b'x' * 100)
def slow_body(h):
    h.send_response(200); h.send_header('Content-Length', '10'); h.end_headers(); h.wfile.flush()
    time.sleep(0.3); h.wfile.write(b'0123456789'); h.wfile.flush()

print('== 一:Semaphore(N) 限制同时在途的请求数(100 个请求,服务器每个停 0.1 秒;服务器统计同时在处理的请求峰值)')
async def bounded(url, n, N):
    sem = asyncio.Semaphore(N)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
        async def one():
            async with sem:
                async with s.get(url) as r: await r.read()
        t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(n)]); return ms(t0)
with Srv(slow) as sv:
    for N in (5, 20, 100):
        sv.reset(); t = asyncio.run(bounded(sv.url('/'), 100, N))
        print(f'  Semaphore({N:>3}):服务器同时在处理的峰值 {sv.peak:>3},总耗时 {t:.0f} ms(理论下限 {100 / N * 100:.0f} ms)')

print('== 二:常见的写法错误:信号量只包住 session.get(),没包住读取响应体(服务器先发响应头,0.3 秒后才发 10 字节的体)')
async def scope(url, n, N, whole):
    sem = asyncio.Semaphore(N)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
        async def one_whole():
            async with sem:
                async with s.get(url) as r: await r.read()
        async def one_head_only():
            async with sem: r = await s.get(url)
            try: await r.read()
            finally: r.release()
        t0 = time.perf_counter(); await asyncio.gather(*[(one_whole if whole else one_head_only)() for _ in range(n)]); return ms(t0)
with Srv(slow_body) as sv:
    for whole, lab in ((True, '信号量包住整个 async with(含 read)'), (False, '信号量只包住 await session.get()')):
        sv.reset(); t = asyncio.run(scope(sv.url('/'), 50, 5, whole))
        print(f'  Semaphore(5),50 个请求,{lab}:服务器同时在处理的峰值 {sv.peak},总耗时 {t:.0f} ms')

print('== 三:TCPConnector(limit) 与 Semaphore 的区别:排队等连接的时间会算进 ClientTimeout(total)')
async def tmo(url, n, mode):
    to = aiohttp.ClientTimeout(total=1.0)
    ok = fail = 0
    if mode == 'limit':
        conn = aiohttp.TCPConnector(limit=10)
    else:
        conn = aiohttp.TCPConnector(limit=0)
    sem = asyncio.Semaphore(10)
    async with aiohttp.ClientSession(connector=conn, timeout=to) as s:
        async def one():
            nonlocal ok, fail
            try:
                if mode == 'sem':
                    async with sem:
                        async with s.get(url) as r: await r.read()
                else:
                    async with s.get(url) as r: await r.read()
                ok += 1
            except asyncio.TimeoutError: fail += 1
        t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(n)]); return ok, fail, ms(t0)
with Srv(slow) as sv:
    for mode, lab in (('limit', 'TCPConnector(limit=10),total 超时 1.0 秒'), ('sem', 'TCPConnector(limit=0) + Semaphore(10),total 超时 1.0 秒')):
        ok, fail, t = asyncio.run(tmo(sv.url('/'), 200, mode))
        print(f'  {lab}:200 个请求(每个 0.1 秒,10 并发理论上要 2 秒)→ 成功 {ok},超时 {fail},总耗时 {t:.0f} ms')

print('== 四:一次创建很多任务的代价:20 万个协程用 gather + 信号量 对比 100 个 worker 从队列取')
def peak_mib(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
import subprocess
CODE = r'''
import asyncio, sys, time, resource
mode, n = sys.argv[1], int(sys.argv[2])
async def work(): await asyncio.sleep(0.001)
async def gather_mode():
    sem = asyncio.Semaphore(100)
    async def one():
        async with sem: await work()
    await asyncio.gather(*[one() for _ in range(n)])
async def queue_mode():
    q = asyncio.Queue(maxsize=1000)
    async def worker():
        while True:
            x = await q.get()
            if x is None: return
            await work()
    ws = [asyncio.create_task(worker()) for _ in range(100)]
    for i in range(n): await q.put(i)
    for _ in ws: await q.put(None)
    await asyncio.gather(*ws)
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
t0 = time.perf_counter(); asyncio.run(gather_mode() if mode == 'gather' else queue_mode())
print(f"{base:.1f} {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576:.1f} {(time.perf_counter() - t0):.2f}")
'''
d = pdir('p17'); (d / 'm.py').write_text(CODE)
for n in (20000, 200000):
    row = []
    for mode in ('gather', 'queue'):
        o = subprocess.run([sys.executable, str(d / 'm.py'), mode, str(n)], capture_output=True, text=True, timeout=300)
        b, pk, t = o.stdout.split()
        row.append(f'{mode}:峰值内存 {pk} MiB(起点 {b}),耗时 {t} s')
    print(f'  {n} 个任务(每个只 sleep 1 ms,信号量/worker 都是 100):' + ';'.join(row))

print('== 五:Semaphore 唤醒等待者的顺序(先到先得吗)')
async def order():
    sem = asyncio.Semaphore(2); started = []
    async def one(i):
        async with sem:
            started.append(i); await asyncio.sleep(0.01)
    await asyncio.gather(*[one(i) for i in range(12)]); return started
st = asyncio.run(order()); print(f'  Semaphore(2),12 个任务按 0..11 顺序创建,实际获得信号量的顺序:{st}')
print(f'  与创建顺序一致:{st == sorted(st)}')
purge()
