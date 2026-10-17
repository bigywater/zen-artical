import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s5'); reset_s()
def ok(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(code, srvfn=ok, settings=None, n=0):
    d = sdir('s5')
    with Srv(srvfn) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return s, ev(d), out, stats(out)

print('== 一:默认的 start() 就是把 start_urls 逐个 yield 成 Request(dont_filter=True);start 请求的 meta 里有 is_start_request')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    start_urls = ['@U@/a', '@U@/a', '@U@/b']
    def parse(self, response): EV(url=response.url.rsplit('/', 1)[-1], is_start=response.meta.get('is_start_request'), dont_filter=response.request.dont_filter)
""")
print(f'  start_urls = [/a, /a, /b](/a 重复):服务器收到 {[l["path"] for l in s.log]},共 {len(s.log)} 个请求')
print(f'  parse 看到的:' + ';'.join(f'{x["url"]}(is_start_request={x["is_start"]}, dont_filter={x["dont_filter"]})' for x in E))
print(f'  dupefilter/filtered={st.get("dupefilter/filtered", 0)}')

print('== 二:2.19 里 start_requests() 不再被框架调用:只定义旧的 start_requests 的 spider 会发生什么')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    def start_requests(self):
        EV(e='start_requests 被调用了')
        yield scrapy.Request('@U@/old')
    def parse(self, response): EV(e='parse', url=response.url)
""")
print(f'  只定义 start_requests:服务器收到 {len(s.log)} 个请求;start_requests 被调用:{any("start_requests" in x.get("e", "") for x in E)};finish_reason={st.get("finish_reason")};response_received_count={st.get("response_received_count", 0)}')
print(f'  日志里 WARNING / ERROR 行数:{len([l for l in out.split(chr(10)) if "] WARNING" in l or "] ERROR" in l])}(没有任何警告或提示,spider 安安静静地以 finished 结束)')

print('== 三:start() 不是惰性消费的:yield 300 个请求,并发 4,服务器每个延迟 0.1 s;每次 yield 时已完成多少个下载、调度器里积压了多少个')
BODY3 = """
import scrapy, asyncio
class S(scrapy.Spider):
    name = 's'
    done = 0
    async def start(self):
        eng = self.crawler.engine
        for i in range(N):
            LAZY
            EV(e='yield', i=i, done=self.done, queued=len(eng.scheduler), inflight=len(eng.downloader.active))
            yield scrapy.Request('@U@/p%d' % i)
    def parse(self, response): self.done += 1
"""
for tag, lazy, n in (('直接 yield(300 个)', 'pass', 300), ('每次 yield 前 while engine.needs_backout(): await asyncio.sleep(0.01)(300 个)', 'while eng.needs_backout(): await asyncio.sleep(0.01)', 300)):
    s, E, out, st = go(BODY3.replace('LAZY', lazy).replace('N)', str(n) + ')'), srvfn=lambda h: (time.sleep(0.1), ok(h)), settings={'CONCURRENT_REQUESTS': 4, 'CONCURRENT_REQUESTS_PER_DOMAIN': 4})
    ys = [x for x in E if x['e'] == 'yield']
    print(f'  {tag}')
    print(f'      前 8 次 yield 时 已完成 {[x["done"] for x in ys[:8]]} / 调度器积压 {[x["queued"] for x in ys[:8]]}')
    print(f'      调度器积压的最大值 {max(x["queued"] for x in ys)};第 150 次 yield 在 {ys[150]["t"]:.0f} ms,最后一次(第 {len(ys)} 次)在 {ys[-1]["t"]:.0f} ms;总耗时 {st["elapsed_time_seconds"]:.1f} s(理想 7.5 s);{st["response_received_count"]} 个响应')

print('== 四:start() 里可以 await:每 yield 一个请求就 await asyncio.sleep(0.5),已经 yield 的请求不用等后面的')
s, E, out, st = go("""
import scrapy, asyncio
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for i in range(4):
            EV(e='yield', i=i)
            yield scrapy.Request('@U@/p%d' % i)
            await asyncio.sleep(0.5)
        EV(e='start() 结束')
    def parse(self, response): EV(e='parse', url=response.url.rsplit('/', 1)[-1])
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw)
        sp.f = lambda: EV(e='spider_idle'); crawler.signals.connect(sp.f, scrapy.signals.spider_idle); return sp
""")
for x in E: print(f'  {x["t"]:>7.0f} ms  {x["e"]:<10}' + (f' i={x["i"]}' if 'i' in x else '') + (f' {x["url"]}' if 'url' in x else ''))
print(f'  finish_reason={st["finish_reason"]}(spider_idle 只在 start() 结束之后才出现)')

print('== 五:start() 可以直接 yield item(dict),不经过回调,直接进 pipeline')
s, E, out, st = go("""
import scrapy
class P:
    def process_item(self, item): EV(e='pipeline', item=item); return item
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'ITEM_PIPELINES': {P: 100}}
    async def start(self):
        yield {'from': 'start'}
        yield scrapy.Request('@U@/x')
    def parse(self, response): yield {'from': 'parse'}
""")
print(f'  pipeline 看到的 item:{[x["item"] for x in E]};item_scraped_count={st["item_scraped_count"]};服务器收到 {len(s.log)} 个请求')

print('== 六:start 请求和回调产生的请求,出队顺序不同:start 用 FIFO 队列(SCHEDULER_START_*),其余默认 LIFO;并发 1')
CODE6 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for u in ('a', 'b', 'c'): yield scrapy.Request('@U@/' + u)
    def parse(self, response):
        n = response.url.rsplit('/', 1)[-1]
        if len(n) == 1:
            for k in (1, 2): yield scrapy.Request('@U@/%s%d' % (n, k))
"""
for tag, stt in (('默认设置', {}), ('SCHEDULER_START_MEMORY_QUEUE 改成 LifoMemoryQueue', {'SCHEDULER_START_MEMORY_QUEUE': 'scrapy.squeues.LifoMemoryQueue'})):
    s, E, out, st = go(CODE6, settings=dict(stt, CONCURRENT_REQUESTS=1))
    print(f'  {tag}:服务器收到的顺序 {" ".join(l["path"] for l in s.log)}')

print('== 七:start() 里出错:已经 yield 的请求照常处理,finish_reason 变成 start_error;抛 CloseSpider 则按给定原因关闭')
for tag, exc in (('抛 RuntimeError', "raise RuntimeError('boom in start')"), ('抛 CloseSpider(reason=\"my_reason\")', "from scrapy.exceptions import CloseSpider; raise CloseSpider('my_reason')")):
    s, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/first')
        {exc}
    def parse(self, response): EV(e='parse', url=response.url)
""", settings={'LOG_LEVEL': 'ERROR' if False else 'INFO'})
    L = [l.strip() for l in out.split('\n') if 'Error while reading start' in l]
    print(f'  {tag}:服务器收到 {[l["path"] for l in s.log]};finish_reason={st.get("finish_reason")};spider_exceptions/count={st.get("spider_exceptions/count", 0)};parse 被调用 {len(E)} 次' + (f';日志:{L[0][:80]}' if L else ''))
