import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s17'); reset_s()

print('== 一:下载槽(slot)的名字怎么来:默认是 URL 的主机名(不含端口和协议);设了 CONCURRENT_REQUESTS_PER_IP 就是解析后的 IP;request.meta["download_slot"] 优先')
CASES1 = [('http://a.com/x', {}), ('https://a.com:8443/y', {}), ('http://www.a.com/z', {}), ('http://A.COM/p', {}), ('http://[::1]:8080/', {}), ('http://a.com/x', {'download_slot': 'myslot'})]
for tag, st in (('默认', {}), ('CONCURRENT_REQUESTS_PER_IP=2(需要 ScrapyPriorityQueue)', {'CONCURRENT_REQUESTS_PER_IP': 2, 'SCHEDULER_PRIORITY_QUEUE': 'scrapy.pqueues.ScrapyPriorityQueue'})):
    d = sdir('s17a'); tr = Track(0.0)
    with Srv(tr) as s:
        code = f"""
import scrapy
from scrapy import Request
CASES = {CASES1!r} + [('http://localhost:{s.port}/h', {{}}), ('http://127.0.0.1:{s.port}/h', {{}})]
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield Request('http://localhost:{s.port}/seed')
        yield Request('http://127.0.0.1:{s.port}/seed')
    def parse(self, response):
        if response.url.startswith('http://127.0.0.1'):
            dl = self.crawler.engine.downloader
            for u, m in CASES: EV(u=u.replace(':{s.port}', ':端口'), meta=m, key=dl.get_slot_key(Request(u, meta=m)))
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO'}, **st))
    print(f'  [{tag}]')
    for x in ev(d): print(f'    {x["u"]:<26}meta={x["meta"]!s:<28}→ 槽名 {x["key"]!r}')
    w = [l.split('ScrapyDeprecationWarning: ')[-1].strip() for l in out.split(chr(10)) if 'CONCURRENT_REQUESTS_PER_IP' in l and 'deprecated' in l]
    if w: print('    警告:' + w[0])

print('== 二:用 meta["download_slot"] 合并或拆开槽:DOWNLOAD_DELAY = 0.2、无抖动;(a) 两个主机名各 20 个请求(默认两个槽);(b) 全部指定同一个槽名 shared;(c) 一个主机名 40 个请求,按奇偶拆成两个槽')
def crawl(code_body, hosts, settings, per=20):
    d = sdir('s17b'); tr = Track(0.0)
    with Srv(tr) as s:
        urls = [(h, f'http://{h}:{s.port}/p{i}') for h in hosts for i in range(per)]
        code = f"""
import scrapy
URLS = {urls!r}
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://{hosts[0]}:{s.port}/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for i, (h, u) in enumerate(URLS):
                {code_body}
    def sub(self, response): pass
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'DOWNLOAD_DELAY': 0.2, 'DOWNLOAD_DELAY_JITTER': 0, 'CONCURRENT_REQUESTS': 100, 'CONCURRENT_REQUESTS_PER_DOMAIN': 100}, **settings))
    return tr, stats(out)
for tag, body, hosts, per in (('(a) 两个主机名各 20 个,默认槽', "yield scrapy.Request(u, callback=self.sub)", ['127.0.0.1', 'localhost'], 20), ('(b) 同上,全部 meta download_slot="shared"', "yield scrapy.Request(u, callback=self.sub, meta={'download_slot': 'shared'})", ['127.0.0.1', 'localhost'], 20), ('(c) 一个主机名 40 个,按奇偶拆成槽 even / odd', "yield scrapy.Request(u, callback=self.sub, meta={'download_slot': 'even' if i % 2 == 0 else 'odd'})", ['127.0.0.1'], 40)):
    tr, st = crawl(body, hosts, {}, per)
    print(f'  {tag}:共 {len(tr.t) - 1} 个请求,总耗时 {st["elapsed_time_seconds"]:.1f} s')
print('  理想值:(a) 20×0.2 = 4.0 s(两个槽并行);(b) 40×0.2 = 8.0 s(一个槽);(c) 20×0.2 = 4.0 s(两个槽并行)')

print('== 三:DOWNLOAD_SLOTS 的键可以是主机名,也可以是你自己起的槽名(再用 meta 指过去)')
tr, st = crawl("yield scrapy.Request(u, callback=self.sub, meta={'download_slot': 'api'})", ['127.0.0.1'], {'DOWNLOAD_SLOTS': '{"api": {"delay": 0.05}}'}, 20)
ts = sorted(tr.t)[1:]; g = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
print(f'  DOWNLOAD_SLOTS={{"api": {{"delay": 0.05}}}},20 个请求都指到槽 api:间隔中位数 {sorted(g)[len(g) // 2]:.0f} ms,总耗时 {st["elapsed_time_seconds"]:.1f} s(全局 DOWNLOAD_DELAY 是 0.2,若不生效应是 4.0 s)')

print('== 四:空闲的槽会被回收:Downloader._slot_gc 每 60 秒检查一次,回收“没有活动请求且最后一次放行距今超过 60 秒”的槽(下面真实等待 130 秒,每 10 秒记录一次槽的个数)')
d = sdir('s17d'); tr = Track(0.0)
with Srv(tr) as s:
    code = f"""
import scrapy, asyncio
from scrapy import signals
from scrapy.exceptions import DontCloseSpider
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('http://127.0.0.1:{s.port}/a')
        yield scrapy.Request('http://localhost:{s.port}/b')
        asyncio.ensure_future(self.sampler())
    async def sampler(self):
        import time
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 130:
            EV(slots=sorted(self.crawler.engine.downloader.slots))
            await asyncio.sleep(10)
        self.done = True
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw); sp.done = False
        sp.f = lambda: (_ for _ in ()).throw(DontCloseSpider()) if not sp.done else None
        crawler.signals.connect(sp.f, signals.spider_idle)
        return sp
    def parse(self, response):
        if response.url.endswith('/a'): EV(e='/a 完成')
"""
    rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO'}, timeout=200)
E4 = [x for x in ev(d) if 'slots' in x]
for x in E4: print(f'  {x["t"] / 1000:>6.0f} s  槽 {x["slots"]}')
