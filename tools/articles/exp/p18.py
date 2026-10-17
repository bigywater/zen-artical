import sys, os, asyncio, socket; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import aiohttp, threading
tee('p18')
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda host, *a, **k: _orig('127.0.0.1' if isinstance(host, str) and host.endswith('.test') else host, *a, **k)
def slow(h): time.sleep(0.1); h.reply(200, b'x')

async def burst(url_fn, n, **ckw):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(**ckw)) as s:
        async def one(i):
            async with s.get(url_fn(i)) as r: await r.read()
        t0 = time.perf_counter(); await asyncio.gather(*[one(i) for i in range(n)]); return ms(t0)

async def defaults():
    c = aiohttp.TCPConnector(); r = (c.limit, c.limit_per_host); await c.close(); return r
print('== 一:默认值')
print('  aiohttp.TCPConnector() 默认 limit=%d,limit_per_host=%d(0 表示不限)' % asyncio.run(defaults()))

print('== 二:同一个主机 200 个请求(每个 0.1 秒),默认 limit=100:服务器看到的同时连接/请求峰值')
with Srv(slow) as sv:
    for kw, lab in ((dict(), '默认(limit=100,limit_per_host=0)'), (dict(limit=0), 'limit=0(不限)'), (dict(limit=20), 'limit=20'), (dict(limit_per_host=5), 'limit_per_host=5')):
        sv.reset(); t = asyncio.run(burst(lambda i: sv.url('/'), 200, **kw))
        print(f'  {lab}:服务器同时在处理的峰值 {sv.peak},累计连接数 {sv.n_conn},总耗时 {t:.0f} ms')

print('== 三:三个不同主机各 100 个请求(三个本机端口,对 aiohttp 来说是三个"主机"),limit 是总数上限,limit_per_host 是每个主机的上限')
G = dict(n=0, peak=0, lock=threading.Lock())
def slow_g(h):
    with G['lock']: G['n'] += 1; G['peak'] = max(G['peak'], G['n'])
    time.sleep(0.1)
    with G['lock']: G['n'] -= 1
    h.reply(200, b'x')
S3 = [Srv(slow_g) for _ in range(3)]
for x in S3: x.th.start()
try:
    for kw, lab in ((dict(limit=30), 'limit=30'), (dict(limit=0, limit_per_host=5), 'limit=0,limit_per_host=5'), (dict(limit=30, limit_per_host=5), 'limit=30,limit_per_host=5')):
        for x in S3: x.reset()
        G['peak'] = 0
        async def three(**ckw):
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(**ckw)) as s:
                async def one(i):
                    async with s.get(S3[i % 3].url('/')) as r: await r.read()
                t0 = time.perf_counter(); await asyncio.gather(*[one(i) for i in range(300)]); return ms(t0)
        t = asyncio.run(three(**kw))
        print(f'  {lab}:三台服务器各自的并发峰值 {[x.peak for x in S3]},三台合起来同时在处理的峰值 {G["peak"]},总耗时 {t:.0f} ms')
finally:
    for x in S3: x.stop()

print('== 四:同一个服务器,但用不同的主机名访问,算不算同一个"主机":limit_per_host 的键')
S1 = Srv(slow); S1.th.start()
try:
    async def names(**ckw):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(**ckw)) as s:
            hosts = ['a.test', 'b.test', 'c.test', 'd.test']
            async def one(i):
                async with s.get(f'http://{hosts[i % 4]}:{S1.port}/') as r: await r.read()
            t0 = time.perf_counter(); await asyncio.gather(*[one(i) for i in range(200)]); return ms(t0)
    async def same(**ckw):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(**ckw)) as s:
            async def one(i):
                async with s.get(f'http://127.0.0.1:{S1.port}/') as r: await r.read()
            t0 = time.perf_counter(); await asyncio.gather(*[one(i) for i in range(200)]); return ms(t0)
    S1.reset(); t = asyncio.run(same(limit=0, limit_per_host=5)); print(f'  用同一个主机名(127.0.0.1)访问,limit_per_host=5:服务器同时处理的峰值 {S1.peak},{t:.0f} ms')
    S1.reset(); t = asyncio.run(names(limit=0, limit_per_host=5)); print(f'  用 4 个不同主机名(都解析到同一台服务器)访问,limit_per_host=5:服务器同时处理的峰值 {S1.peak},{t:.0f} ms')
finally: S1.stop()

print('== 五:limit 是每个 TCPConnector 自己的上限:多个 ClientSession(各有各的连接器)同时跑,上限会叠加')
with Srv(slow) as sv:
    async def two_sessions(k):
        async def run_one():
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as s:
                async def one():
                    async with s.get(sv.url('/')) as r: await r.read()
                await asyncio.gather(*[one() for _ in range(100)])
        t0 = time.perf_counter(); await asyncio.gather(*[run_one() for _ in range(k)]); return ms(t0)
    async def shared(k):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as s:
            async def one():
                async with s.get(sv.url('/')) as r: await r.read()
            t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(100 * k)]); return ms(t0)
    for k in (1, 3):
        sv.reset(); t = asyncio.run(two_sessions(k)); print(f'  {k} 个 ClientSession,每个 limit=10,各发 100 个请求:服务器同时处理的峰值 {sv.peak},总耗时 {t:.0f} ms')
    sv.reset(); t = asyncio.run(shared(3)); print(f'  同样 300 个请求但共用 1 个 ClientSession(limit=10):服务器同时处理的峰值 {sv.peak},总耗时 {t:.0f} ms')
purge()
