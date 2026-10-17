import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s39'); reset_s()
class Site:
    def __init__(self, size): self.size = size; self.log = []
    def __call__(self, h):
        self.log.append(h.path)
        if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">x</a>' for i in range(NPAGES)) + '</html>', {'Content-Type': 'text/html'}); return
        h.reply(200, b'<html>' + b'x' * self.size + b'</html>', {'Content-Type': 'text/html'})
NPAGES = 400
SP = """
import scrapy, asyncio, resource
class S(scrapy.Spider):
    name = 's'
    peak = 0; peak_n = 0; samples = 0
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw)
        from scrapy import signals
        def on_rr(**kw):
            sl = sp.crawler.engine.scraper.slot
            if sl is not None:
                sp.peak = max(sp.peak, sl.active_size); sp.peak_n = max(sp.peak_n, len(sl.queue) + len(sl.active))
        sp.f = on_rr; crawler.signals.connect(on_rr, signals.response_received); return sp
    async def start(self):
        yield scrapy.Request('@U@/')
        asyncio.ensure_future(self.sampler())
    async def sampler(self):
        while True:
            sl = self.crawler.engine.scraper.slot
            if sl is not None:
                n = len(sl.queue) + len(sl.active)
                self.peak = max(self.peak, sl.active_size); self.peak_n = max(self.peak_n, n); self.samples += 1
            await asyncio.sleep(0.005)
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall(): yield response.follow(u, callback=self.page)
    async def page(self, response):
        await asyncio.sleep(SLEEP)
        yield {'u': response.url}
    def closed(self, reason): EV(peak_active_size=self.peak, peak_responses=self.peak_n, rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576, 1), samples=self.samples)
"""
def go(size, sleep, settings=None, npages=400, tag='s39'):
    global NPAGES; NPAGES = npages
    d = sdir(tag); sv = Site(size)
    with Srv(sv) as s:
        rc, out, t = runspider(d, SP.replace('@U@', s.url('').rstrip('/')).replace('SLEEP', str(sleep)), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 16, 'CONCURRENT_REQUESTS_PER_DOMAIN': 16}, **(settings or {})))
    E = ev(d)
    return E[-1] if E else {}, stats(out)
def row(tag, E, st):
    print(f'  {tag:<46}峰值 active_size {E["peak_active_size"]:>10,} 字节;同时滞留的响应 {E["peak_responses"]:>5} 个;进程峰值 RSS {E["rss_mb"]:>6} MiB;总耗时 {st["elapsed_time_seconds"]:.1f} s')

print('== 一:回调很慢(async,await 0.5 s)而下载很快:响应在 scraper 里堆积,堆积量由 SCRAPER_SLOT_MAX_ACTIVE_SIZE 决定。400 个 100 KB 的页面(共 40 MB),并发 16')
for tag, mx in (('SCRAPER_SLOT_MAX_ACTIVE_SIZE = 1,000,000', 1000000), ('默认 5,000,000', None), ('SCRAPER_SLOT_MAX_ACTIVE_SIZE = 20,000,000', 20000000), ('= 100,000,000(基本不限)', 100000000)):
    E, st = go(100000, 0.5, {'SCRAPER_SLOT_MAX_ACTIVE_SIZE': mx} if mx else {})
    row(tag, E, st)

print('== 二:同样的负载,回调很快(不 sleep)——没有堆积,背压不起作用')
E, st = go(100000, 0.0)
row('默认设置,回调不等待', E, st)

print('== 三:小响应按 1024 字节算(Slot.MIN_RESPONSE_SIZE):6000 个 200 字节的页面,回调 await 1 s,并发 100;active_size 总是 1024 的整数倍')
for tag, st in (('默认 SCRAPER_SLOT_MAX_ACTIVE_SIZE = 5,000,000', {}), ('SCRAPER_SLOT_MAX_ACTIVE_SIZE = 500,000', {'SCRAPER_SLOT_MAX_ACTIVE_SIZE': 500000})):
    E, st_ = go(200, 1.0, npages=6000, settings=dict({'CONCURRENT_REQUESTS': 100, 'CONCURRENT_REQUESTS_PER_DOMAIN': 100}, **st))
    print(f'  {tag}:峰值 active_size {E["peak_active_size"]:,} = {E["peak_active_size"] // 1024} × 1024 + {E["peak_active_size"] % 1024};同时滞留的响应 {E["peak_responses"]} 个;进程峰值 RSS {E["rss_mb"]} MiB;总耗时 {st_["elapsed_time_seconds"]:.1f} s')
print('  500,000 ÷ 1024 = %.0f 个;在途下载最多 100 个,所以峰值会超过一点' % (500000 / 1024))
