import sys, os, asyncio, threading, concurrent.futures as cf; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, aiohttp, socket
tee('p11')
_orig = socket.getaddrinfo
S = dict(delay=0.0, calls={}, active=0, peak=0, lock=threading.Lock())
def gai(host, *a, **k):
    if isinstance(host, str) and host.endswith('.test'):
        with S['lock']:
            S['calls'][host] = S['calls'].get(host, 0) + 1; S['active'] += 1; S['peak'] = max(S['peak'], S['active'])
        try:
            time.sleep(S['delay']); return _orig('127.0.0.1', *a, **k)
        finally:
            with S['lock']: S['active'] -= 1
    return _orig(host, *a, **k)
socket.getaddrinfo = gai
def reset(delay=0.0): S.update(delay=delay, calls={}, active=0, peak=0)
def ncalls(): return sum(S['calls'].values())

def ok(h): h.reply(200, b'ok')
print('(说明:下面用包装过的 socket.getaddrinfo 统计各个库调用它的次数,并按需加 sleep 模拟慢的 DNS;被统计的只有 *.test 主机名,全部解析到 127.0.0.1)')
with Srv(ok) as sv:
    P = sv.port
    print('== 一:requests/urllib3 自己不缓存 DNS:每建立一条新连接就调用一次 getaddrinfo(模拟 DNS 每次 100 ms)')
    for label, fn in (
        ('20 次 requests.get(每次新连接)', lambda: [requests.get(f'http://a.test:{P}/') for _ in range(20)]),
        ('一个 Session 发 20 次(复用 1 条连接)', lambda: (lambda s: [s.get(f'http://a.test:{P}/') for _ in range(20)])(requests.Session())),
        ('一个 Session 发 20 次,每次 Connection: close', lambda: (lambda s: [s.get(f'http://a.test:{P}/', headers={'Connection': 'close'}) for _ in range(20)])(requests.Session())),
    ):
        reset(0.1); t0 = time.perf_counter(); fn(); t = ms(t0)
        print(f'  {label}:getaddrinfo 调用 {ncalls()} 次,总耗时 {t:.0f} ms')

    print('== 二:aiohttp 的 TCPConnector 自带 DNS 缓存(use_dns_cache=True,ttl_dns_cache=10 秒);force_close=True 让每个请求都新建连接')
    async def aio(n, gap=0.0, **ckw):
        reset(0.1)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True, **ckw)) as s:
            t0 = time.perf_counter()
            for _ in range(n):
                async with s.get(f'http://b.test:{P}/') as r: await r.read()
                if gap: await asyncio.sleep(gap)
            return ms(t0) - gap * n * 1000
    async def defaults():
        c = aiohttp.TCPConnector(); r = (c._use_dns_cache, c._cached_hosts._ttl); await c.close(); return r
    d1, d2 = asyncio.run(defaults()); print(f'  默认值:use_dns_cache={d1} ttl_dns_cache={d2}')
    for label, n, gap, kw in (('默认(缓存开)', 20, 0, {}), ('use_dns_cache=False', 20, 0, dict(use_dns_cache=False)), ('ttl_dns_cache=1,每次请求后等 0.4 秒', 10, 0.4, dict(ttl_dns_cache=1))):
        t = asyncio.run(aio(n, gap, **kw))
        print(f'  {label}:{n} 个新连接,getaddrinfo 调用 {ncalls()} 次,请求本身累计耗时(不含主动等待)约 {t:.0f} ms')

    print('== 三:getaddrinfo 是阻塞调用,aiohttp 把它放到线程池:并发的解析数被线程池大小卡住(100 个不同主机名,模拟每次解析 200 ms)')
    print(f'  本机 os.cpu_count() = {os.cpu_count()},asyncio 默认线程池大小的文档公式 min(32, cpu+4) = {min(32, (os.cpu_count() or 1) + 4)}')
    async def many(workers=None):
        reset(0.2)
        loop = asyncio.get_running_loop()
        if workers: loop.set_default_executor(cf.ThreadPoolExecutor(workers))
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
            async def one(i):
                async with s.get(f'http://h{i}.test:{P}/') as r: await r.read()
            t0 = time.perf_counter(); await asyncio.gather(*[one(i) for i in range(100)]); return ms(t0)
    for label, w in (('默认线程池', None), ('换成 100 个线程的线程池', 100)):
        t = asyncio.run(many(w))
        print(f'  {label}:同时在解析的数量峰值 {S["peak"]},100 个请求全部完成 {t:.0f} ms')

print('== 四:localhost 会解析出 IPv6 与 IPv4 两个地址,服务器只听 IPv4 时每次新连接要先试 ::1')
res = socket.getaddrinfo('localhost', 80, type=socket.SOCK_STREAM)
print('  getaddrinfo("localhost") 的顺序:' + ', '.join(f'{r[4][0]}' for r in res))
with Srv(ok) as sv:
    A, B = [], []
    for rnd in range(5):
        for who in (('A', 'localhost'), ('B', '127.0.0.1')) if rnd % 2 == 0 else (('B', '127.0.0.1'), ('A', 'localhost')):
            t0 = time.perf_counter()
            for _ in range(200): requests.get(f'http://{who[1]}:{sv.port}/')
            (A if who[0] == 'A' else B).append(ms(t0) / 200)
    print(f'  200 次新连接 × 5 轮,每次请求平均:localhost {median(A):.2f} ms,127.0.0.1 {median(B):.2f} ms')
    def per(fn, n=2000):
        t0 = time.perf_counter()
        for _ in range(n): fn()
        return ms(t0) / n
    g1 = median([per(lambda: _orig('localhost', sv.port, type=socket.SOCK_STREAM)) for _ in range(5)])
    g2 = median([per(lambda: _orig('127.0.0.1', sv.port, type=socket.SOCK_STREAM)) for _ in range(5)])
    def refused():
        try: socket.create_connection(('::1', sv.port), timeout=1)
        except OSError: pass
    r6 = median([per(refused, 500) for _ in range(5)])
    print(f'  拆开测:getaddrinfo("localhost") 每次 {g1:.3f} ms,getaddrinfo("127.0.0.1") 每次 {g2:.3f} ms;对 ::1 发起连接被拒绝(服务器没听 IPv6)每次 {r6:.3f} ms')
purge()
