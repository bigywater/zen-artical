import sys, os, threading, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s15'); reset_s()
class Track:
    """服务器端:每个 Host 头(主机名,不含端口)同时在处理的请求数的峰值,以及总峰值。"""
    def __init__(self, delay=0.3):
        self.lock = threading.Lock(); self.cur = collections.Counter(); self.peak = collections.Counter(); self.tot = 0; self.totpeak = 0; self.delay = delay; self.t = []
    def __call__(self, h):
        host = dict(h.hdrs)['Host'].split(':')[0]
        with self.lock:
            self.cur[host] += 1; self.tot += 1; self.t.append(time.perf_counter())
            self.peak[host] = max(self.peak[host], self.cur[host]); self.totpeak = max(self.totpeak, self.tot)
        if h.path != '/seed': time.sleep(self.delay)
        h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
        with self.lock: self.cur[host] -= 1; self.tot -= 1
PROBE = '''
from scrapy.core.downloader import Downloader
_orig = Downloader._download
async def _patched(self, slot, request):
    EV(e='start', conc=slot.concurrency, transferring=len(slot.transferring) + 1, queued=len(slot.queue))
    return await _orig(self, slot, request)
Downloader._download = _patched
'''
def crawl(hosts, per_host, settings, delay=0.3, probe=False):
    d = sdir('s15'); tr = Track(delay)
    with Srv(tr) as s:
        urls = [f'http://{h}:{s.port}/p{i}' for h in hosts for i in range(per_host)]
        code = f"""
import scrapy
URLS = {urls!r}
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://{hosts[0]}:{s.port}/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for u in URLS: yield scrapy.Request(u, callback=self.sub)
    def sub(self, response): pass
"""
        if probe: code = PROBE + code
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO'}, **settings))
    return tr, stats(out), ev(d), out
RE = {'asyncio reactor(默认)': {}, 'SelectReactor': {'TWISTED_REACTOR': 'twisted.internet.selectreactor.SelectReactor'}, '无 reactor': {'TWISTED_REACTOR_ENABLED': 'False'}}

print('== 一:CONCURRENT_REQUESTS_PER_DOMAIN 是否真的限制了单个域名的并发:单域名 48 个请求,服务器每个延迟 0.3 s,全局并发 100;服务器端看到的同时处理峰值(括号里是总耗时 s)')
print(f'  {"每域名并发":>10}' + ''.join(f'{k:>26}' for k in RE) + f'{"理想耗时 48×0.3/N":>20}')
for n in (1, 2, 4, 8, 16):
    row = f'  {n:>10}'
    for k, st in RE.items():
        tr, s_, E, out = crawl(['127.0.0.1'], 48, dict(CONCURRENT_REQUESTS=100, CONCURRENT_REQUESTS_PER_DOMAIN=n, **st))
        row += f'{"峰值 " + str(tr.peak["127.0.0.1"]) + "(" + format(s_["elapsed_time_seconds"], ".2f") + ")":>26}'
    print(row + f'{48 * 0.3 / n:>20.1f}')

print('== 二:原因:每个下载槽有 concurrency 和 transferring;放行条件是 free_transfer_slots() = concurrency − len(transferring) > 0,而 transferring 要等 _download 真正开始(asyncio 下是 create_task 排的队)才增加——给 Downloader._download 打补丁,记录每次开始下载时槽里 transferring 的数')
for k, st in (('asyncio reactor(默认)', {}), ('SelectReactor', RE['SelectReactor'])):
    tr, s_, E, out = crawl(['127.0.0.1'], 16, dict(CONCURRENT_REQUESTS=100, CONCURRENT_REQUESTS_PER_DOMAIN=4, **st), probe=True)
    es = [x for x in E if x.get('e') == 'start']
    print(f'  {k}:槽的 concurrency = {es[0]["conc"]};共 {len(es)} 次开始下载;各次开始时槽里 transferring(含自己)依次是 {[x["transferring"] for x in es]};服务器峰值 {tr.peak["127.0.0.1"]}')

print('== 三:全局限制 CONCURRENT_REQUESTS 是在引擎层面按“在途请求数”算的,asyncio reactor 下照样生效:两个主机名各 16 个请求,每域名并发 100')
print(f'  {"全局并发":>10}{"服务器总峰值":>14}{"各主机峰值":>28}{"总耗时 s":>10}')
for g in (4, 6, 16):
    tr, s_, E, out = crawl(['127.0.0.1', 'localhost'], 16, dict(CONCURRENT_REQUESTS=g, CONCURRENT_REQUESTS_PER_DOMAIN=100))
    print(f'  {g:>10}{tr.totpeak:>14}{" ".join(f"{h}={tr.peak[h]}" for h in sorted(tr.peak)):>28}{s_["elapsed_time_seconds"]:>10.2f}')

print('== 四:DOWNLOAD_DELAY 走另一条路径(每次只放出一个,下一个要等 delay),在 asyncio reactor 下也生效:单域名 24 个请求,服务器延迟 0.3 s,每域名并发 8')
print(f'  {"DOWNLOAD_DELAY":>16}{"服务器峰值":>12}{"总耗时 s":>10}{"相邻请求到达间隔的中位数 ms":>26}')
for dl in (0, 0.1, 0.2):
    tr, s_, E, out = crawl(['127.0.0.1'], 24, dict(CONCURRENT_REQUESTS=100, CONCURRENT_REQUESTS_PER_DOMAIN=8, DOWNLOAD_DELAY=dl, DOWNLOAD_DELAY_JITTER=0))
    ts = sorted(tr.t)[1:]
    gaps = sorted((b - a) * 1000 for a, b in zip(ts, ts[1:]))
    print(f'  {dl:>16}{tr.peak["127.0.0.1"]:>12}{s_["elapsed_time_seconds"]:>10.2f}{gaps[len(gaps) // 2]:>26.0f}')

print('== 五:CONCURRENT_REQUESTS_PER_IP 和 DOWNLOAD_SLOTS 里的 concurrency 是同一条路径,同样的现象(单域名 48 个请求,限制设成 3)')
for tag, st in (('PER_IP=3(ScrapyPriorityQueue)', dict(CONCURRENT_REQUESTS_PER_IP=3, SCHEDULER_PRIORITY_QUEUE='scrapy.pqueues.ScrapyPriorityQueue')), ('DOWNLOAD_SLOTS={"127.0.0.1": {"concurrency": 3}}', {'DOWNLOAD_SLOTS': '{"127.0.0.1": {"concurrency": 3}}'})):
    row = f'  {tag:<50}'
    for k, rs in RE.items():
        tr, s_, E, out = crawl(['127.0.0.1'], 48, dict(CONCURRENT_REQUESTS=100, CONCURRENT_REQUESTS_PER_DOMAIN=100, **st, **rs))
        row += f' {k.split("(")[0]}:峰值 {tr.peak["127.0.0.1"]}'
    print(row)
print('== 六:无 reactor 模式下每域名限制为什么生效:aiohttp 下载处理器自己的连接器带 limit_per_host(源码 scrapy/core/downloader/handlers/_aiohttp.py)')
src = open(os.path.join(os.path.dirname(SPY), '..', 'lib', 'python3.14', 'site-packages', 'scrapy', 'core', 'downloader', 'handlers', '_aiohttp.py')).read().split(chr(10))
for i, l in enumerate(src, 1):
    if 55 <= i <= 66: print(f'  {i:>4}  {l}')
