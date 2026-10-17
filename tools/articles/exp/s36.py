import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s36'); reset_s()
class Site:
    def __init__(self, delay=0.05): self.log = []; self.delay = delay
    def __call__(self, h):
        self.log.append(h.path); p = h.path.split('?')[0]
        if p == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">x</a>' for i in range(200)) + '</html>', {'Content-Type': 'text/html'}); return
        time.sleep(self.delay)
        h.reply(200, f'<html>{p}</html>', {'Content-Type': 'text/html'})
def go(parse_body, settings=None, tag='s36', delay=0.05):
    d = sdir(tag); sv = Site(delay)
    with Srv(sv) as s:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{s.url("/")}')
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall(): yield response.follow(u, callback=self.page, errback=self.eb)
    def page(self, response):
{parse_body}
    def eb(self, failure): pass
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 16, 'CONCURRENT_REQUESTS_PER_DOMAIN': 16}, **(settings or {})))
    return sv, ev(d), out, stats(out)
def line(st, sv):
    return f'finish_reason={st["finish_reason"]};服务器收到 {len(sv.log)} 个请求(含起始页);response_received_count={st.get("response_received_count")};item_scraped_count={st.get("item_scraped_count", 0)};scheduler/enqueued={st.get("scheduler/enqueued")};dequeued={st.get("scheduler/dequeued")};耗时 {st["elapsed_time_seconds"]:.2f} s'

print('== 一:CLOSESPIDER_PAGECOUNT:站点有 200 个页面,并发 16,每页 0.05 s;到数目后关闭,但已经发出去的请求会怎么样')
for n in (10, 50):
    sv, E, out, st = go("        yield {'u': response.url}", {'CLOSESPIDER_PAGECOUNT': n})
    print(f'  PAGECOUNT={n}:{line(st, sv)}')
sv, E, out, st = go("        yield {'u': response.url}")
print(f'  不限制:{line(st, sv)}')

print('== 二:CLOSESPIDER_ITEMCOUNT(每页产出 1 个 item)与超出量')
for n in (10, 50):
    sv, E, out, st = go("        yield {'u': response.url}", {'CLOSESPIDER_ITEMCOUNT': n})
    print(f'  ITEMCOUNT={n}:{line(st, sv)}')

print('== 三:CLOSESPIDER_ERRORCOUNT:只数 spider_error(回调里抛的异常),下载错误、404 不算——回调对每个页面抛异常 vs 服务器对每个页面返回 404')
sv, E, out, st = go("        raise ValueError('boom')", {'CLOSESPIDER_ERRORCOUNT': 5})
print(f'  回调抛异常,ERRORCOUNT=5:{line(st, sv)};spider_exceptions/count={st.get("spider_exceptions/count")}')
class Always404(Site):
    def __call__(self, h):
        self.log.append(h.path)
        if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">x</a>' for i in range(60)) + '</html>', {'Content-Type': 'text/html'}); return
        time.sleep(self.delay); h.reply(404, 'nf')
d = sdir('s36c'); sv404 = Always404()
with Srv(sv404) as s:
    rc, out, t = runspider(d, f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{s.url("/")}')
    def parse(self, response):
        for u in response.css('a::attr(href)').getall(): yield response.follow(u, callback=self.page)
    def page(self, response): pass
""", {'LOG_LEVEL': 'INFO', 'CLOSESPIDER_ERRORCOUNT': 5, 'CONCURRENT_REQUESTS': 16, 'CONCURRENT_REQUESTS_PER_DOMAIN': 16})
st = stats(out); print(f'  服务器全返回 404,ERRORCOUNT=5:{line(st, sv404)}(404 不算 spider_error)')

print('== 四:时间类:CLOSESPIDER_TIMEOUT(从 spider 打开起算的秒数)、CLOSESPIDER_TIMEOUT_NO_ITEM(这么多秒内没有新 item 就关)、CLOSESPIDER_PAGECOUNT_NO_ITEM(连续这么多个页面没有 item 就关)')
sv, E, out, st = go("        yield {'u': response.url}", {'CLOSESPIDER_TIMEOUT': 1, 'CONCURRENT_REQUESTS': 2, 'CONCURRENT_REQUESTS_PER_DOMAIN': 2}, delay=0.1)
print(f'  TIMEOUT=1 s(并发 2,每页 0.1 s):{line(st, sv)}')
sv, E, out, st = go("        pass", {'CLOSESPIDER_TIMEOUT_NO_ITEM': 2, 'CONCURRENT_REQUESTS': 2, 'CONCURRENT_REQUESTS_PER_DOMAIN': 2}, delay=0.1)
print(f'  TIMEOUT_NO_ITEM=2 s(页面不产出 item,并发 2,每页 0.1 s):{line(st, sv)}')
sv, E, out, st = go("        if response.url.endswith(('p0', 'p1', 'p2')): yield {'u': response.url}", {'CLOSESPIDER_PAGECOUNT_NO_ITEM': 20, 'CONCURRENT_REQUESTS': 1, 'CONCURRENT_REQUESTS_PER_DOMAIN': 1}, delay=0.0)
print(f'  PAGECOUNT_NO_ITEM=20(只有 p0~p2 产出 item,并发 1):{line(st, sv)}')

print('== 五:MemoryUsage:MEMUSAGE_LIMIT_MB 超过就以 memusage_exceeded 关闭;WARNING_MB 只发信号和 WARNING 日志;内存读数是进程的峰值 RSS(ru_maxrss,只增不减)')
ALLOC = "        global KEEP\n        KEEP.append(bytearray(10 * 1024 * 1024))\n        yield {'n': len(KEEP)}"
for tag, stt in (('不设限', {}), ('MEMUSAGE_WARNING_MB=110', {'MEMUSAGE_WARNING_MB': 110, 'MEMUSAGE_CHECK_INTERVAL_SECONDS': 0.2}), ('MEMUSAGE_LIMIT_MB=130(每个页面分配 10 MiB 并一直保留)', {'MEMUSAGE_LIMIT_MB': 130, 'MEMUSAGE_CHECK_INTERVAL_SECONDS': 0.2})):
    d = sdir('s36e'); sv = Site(0.05)
    with Srv(sv) as s:
        code = f"""
import scrapy
KEEP = []
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{s.url("/")}')
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall()[:40]: yield response.follow(u, callback=self.page)
    def page(self, response):
{ALLOC}
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1, 'CONCURRENT_REQUESTS_PER_DOMAIN': 1}, **stt))
    st = stats(out)
    mb = lambda v: f'{v / 1024 / 1024:.0f} MiB' if v else '-'
    msgs = [l.split('] ', 1)[1][:90] for l in out.split('\n') if 'Memory usage exceeded' in l or 'Memory usage reached' in l]
    print(f'  {tag}:finish_reason={st["finish_reason"]};item_scraped_count={st.get("item_scraped_count", 0)};memusage/startup={mb(st.get("memusage/startup"))};max={mb(st.get("memusage/max"))};limit_reached={st.get("memusage/limit_reached")};warning_reached={st.get("memusage/warning_reached")};{msgs[:1]}')
