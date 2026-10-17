import sys, os, ssl, asyncio, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from curl_cffi import requests as cr, CurlOpt
import warnings; warnings.filterwarnings('ignore')
tee('p10')
d = pdir('p10'); CERT, KEY = make_cert(d)
def backend(h):
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query); dl = float(q.get('d', ['0'])[0])
    if dl: time.sleep(dl)
    h.reply(200, b'ok')

async def burst(nx, ver, mc, n, delay, path_fn=None, warm=False):
    """并发发 n 个请求;返回 (总耗时 ms, 每个请求完成的时刻 ms 列表)。"""
    async with cr.AsyncSession(verify=False, http_version=ver, max_clients=mc, curl_options={CurlOpt.PIPEWAIT: 1} if ver == 'v2' else {}) as s:
        nx.clear(); t0 = time.perf_counter(); done = []
        async def one(i):
            await s.get(nx.url(path_fn(i) if path_fn else f'/m{i}?d={delay}')); done.append((i, ms(t0)))
        await asyncio.gather(*[one(i) for i in range(n)])
        total = ms(t0)
    await asyncio.sleep(0.15)
    return total, done

def conns(nx):
    e = nx.entries(); per = {}
    for x in e: per[x[0]] = per.get(x[0], 0) + 1
    return len(per), len(e), sorted(per.values(), reverse=True)[:3], {x[2] for x in e}

def trial(nx, ver, mc, n, delay, reps=3, **kw):
    ts, last = [], None
    for _ in range(reps):
        t, done = asyncio.run(burst(nx, ver, mc, n, delay, **kw)); ts.append(t); last = (done, conns(nx))
    return median(ts), last

with Srv(backend) as be, Nginx('p10', be.port, CERT, KEY) as nx:
    print('== 一:协议协商(ALPN):同一个 nginx,客户端声明的协议不同,协商结果不同')
    for label, alpn in (('声明 h2 和 http/1.1', ['h2', 'http/1.1']), ('只声明 http/1.1', ['http/1.1'])):
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE; ctx.set_alpn_protocols(alpn)
        with socket.create_connection(('127.0.0.1', nx.port)) as s, ctx.wrap_socket(s) as t:
            print(f'  {label} → 协商结果 {t.selected_alpn_protocol()},TLS 版本 {t.version()}')
    import requests; requests.packages.urllib3.disable_warnings()
    nx.clear(); requests.get(nx.url('/r'), verify=False); cr.get(nx.url('/c'), verify=False, http_version='v2'); time.sleep(0.15)
    print('  nginx 访问日志里的协议列:' + ', '.join(f'{x[4]} → {x[2]}' for x in nx.entries()) + '(requests 只会说 HTTP/1.1,curl_cffi 指定了 v2)')

    print('== 二:50 个请求,服务器每个请求停 0.1 秒;用同一个客户端库(curl_cffi)的 HTTP/1.1 与 HTTP/2,并发数(max_clients)对齐')
    print(f'  {"协议":<9}{"并发数":>6}{"连接数":>8}{"总耗时中位数":>12}')
    for ver, mc, reps in (('v1', 1, 1), ('v1', 6, 3), ('v1', 50, 3), ('v2', 1, 1), ('v2', 10, 3), ('v2', 50, 3)):
        t, (done, c) = trial(nx, ver, mc, 50, 0.1, reps)
        print(f'  {"HTTP/1.1" if ver == "v1" else "HTTP/2":<9}{mc:>6}{c[0]:>8}{t:>10.0f} ms' + ('(只跑了 1 次)' if reps == 1 else ''))

    print('== 三:服务器不延迟,600 个请求,看建立连接本身的开销:并发 50 个 HTTP/1.1 连接 对比 一条 HTTP/2 连接')
    for ver, mc in (('v1', 50), ('v2', 50), ('v1', 6), ('v2', 6)):
        t, (done, c) = trial(nx, ver, mc, 600, 0, 5)
        print(f'  {"HTTP/1.1" if ver == "v1" else "HTTP/2":<9}并发 {mc:>2}:{c[0]:>2} 条连接,每条连接上的请求数(前 3 大)={c[2]},总耗时中位数 {t:.0f} ms')

print('== 四:服务器限制 http2_max_concurrent_streams:并发 50、每个请求 0.1 秒')
for streams in (128, 10, 2):
    with Srv(backend) as be, Nginx(f'p10s{streams}', be.port, CERT, KEY, streams=streams) as nx:
        try:
            t, (done, c) = trial(nx, 'v2', 50, 50, 0.1, 3)
            print(f'  max_concurrent_streams={streams:<3}:客户端用了 {c[0]} 条连接(每条上的请求数前 3 大 {c[2]}),总耗时中位数 {t:.0f} ms')
        except Exception as e: print(f'  max_concurrent_streams={streams:<3}:客户端报错 {type(e).__name__}:{str(e)[:80]}')

print('== 五:队头阻塞:第 1 个请求很慢(0.5 秒),后面 20 个很快(0.02 秒)')
with Srv(backend) as be, Nginx('p10h', be.port, CERT, KEY) as nx:
    pf = lambda i: f'/s{i}?d=' + ('0.5' if i == 0 else '0.02')
    for ver, mc, label in (('v1', 1, 'HTTP/1.1 一条连接(串行)'), ('v1', 6, 'HTTP/1.1 六条连接'), ('v2', 21, 'HTTP/2 一条连接')):
        res = []
        for _ in range(3):
            total, done = asyncio.run(burst(nx, ver, mc, 21, 0, path_fn=pf))
            slow = next(t for k, t in done if k == 0); fast = sorted(t for k, t in done if k != 0)
            res.append((total, slow, fast))
        total, slow, fast = sorted(res, key=lambda r: r[0])[1]
        print(f'  {label}:慢请求完成于 {slow:.0f} ms;20 个快请求最早完成于 {fast[0]:.0f} ms、最晚完成于 {fast[-1]:.0f} ms;全部 21 个完成于 {total:.0f} ms')
purge()
