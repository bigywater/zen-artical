import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s1'); reset_s()

TRACE = '''
import scrapy
from scrapy import signals
class Ext:
    @classmethod
    def from_crawler(cls, crawler):
        o = cls(); o.fs = []
        for n in ('engine_started', 'spider_opened', 'request_scheduled', 'request_reached_downloader', 'request_left_downloader', 'response_received', 'item_scraped', 'spider_idle', 'spider_closed'):
            f = o.mk(n); o.fs.append(f); crawler.signals.connect(f, getattr(signals, n))
        return o
    def mk(self, n):
        def f(*a, **kw):
            r = kw.get('item') if n == 'item_scraped' else (kw.get('request') or kw.get('response'))
            EV(e='signal:' + n, what=(r.url.rsplit('/', 1)[-1] or '/') if hasattr(r, 'url') else (str(dict(r)) if r is not None else ''))
        return f
class DM:
    def process_request(self, request): EV(e='下载器中间件 process_request', what=request.url.rsplit('/', 1)[-1] or '/')
    def process_response(self, request, response): EV(e='下载器中间件 process_response', what=request.url.rsplit('/', 1)[-1] or '/'); return response
class SM:
    async def process_start(self, start):
        EV(e='爬虫中间件 process_start', what='')
        async for x in start: yield x
    def process_spider_input(self, response): EV(e='爬虫中间件 process_spider_input', what=response.url.rsplit('/', 1)[-1] or '/')
    async def process_spider_output(self, response, result):
        async for x in result:
            EV(e='爬虫中间件 process_spider_output', what=type(x).__name__ if not isinstance(x, scrapy.Request) else 'Request ' + x.url.rsplit('/', 1)[-1])
            yield x
class P:
    def process_item(self, item): EV(e='pipeline process_item', what=str(item)); return item
class S(scrapy.Spider):
    name = 's'
    custom_settings = dict(EXTENSIONS={Ext: 500}, DOWNLOADER_MIDDLEWARES={DM: 543}, SPIDER_MIDDLEWARES={SM: 543}, ITEM_PIPELINES={P: 300})
    async def start(self):
        EV(e='spider.start() 产出', what='/')
        yield scrapy.Request(U + '/', callback=self.parse)
    def parse(self, response):
        EV(e='callback parse', what='/')
        yield {'page': 'home'}
        yield scrapy.Request(U + '/next', callback=self.parse2)
    def parse2(self, response):
        EV(e='callback parse2', what='next')
        yield {'page': 'next'}
'''
def page(h): h.reply(200, '<html><body>ok</body></html>', {'Content-Type': 'text/html'})

print('== 一:一个请求从头走到尾:在每一层都挂上钩子,记录事件顺序(相对时间 ms 是 spider 进程里的)')
d = sdir('s1a')
with Srv(page) as s:
    rc, out, t = runspider(d, f"U = '{s.url('')}'\n" + TRACE, settings={'LOG_LEVEL': 'WARNING'})
E=ev(d)
print(f'  {"序号":>4}  {"相对时间":>8}  事件 / 对象')
for i, x in enumerate(E, 1): print(f'  {i:>4}  {x["t"]:>6.0f}ms  {x["e"]:<34}{x["what"]}')
print(f'  共 {len(E)} 个事件;服务器收到 {len(s.log)} 个请求:{[l["path"] for l in s.log]}')

print('== 二:调度器出队的顺序:默认后进先出(深度优先?);站点是一棵树:/ → /a, /b;/a → /a1, /a2;/b → /b1, /b2;并发 1')
def tree2(h):
    P = {'/': ['/a', '/b'], '/a': ['/a1', '/a2'], '/b': ['/b1', '/b2']}
    h.reply(200, '<html>' + ''.join(f'<a href="{k}">{k}</a>' for k in P.get(h.path, [])) + '</html>', {'Content-Type': 'text/html'})
CODE = lambda u: f"""
import scrapy
class DM:
    def process_request(self, request): EV(e='开始下载', what=request.url.rsplit('/', 1)[-1] or '/')
class S(scrapy.Spider):
    name = 's'
    start_urls = ['{u}/']
    custom_settings = dict(DOWNLOADER_MIDDLEWARES={{DM: 543}})
    def parse(self, response):
        EV(e='  回调开始', what=response.url.rsplit('/', 1)[-1] or '/')
        for u in response.css('a::attr(href)').getall(): yield response.follow(u)
"""
FIFO = {'SCHEDULER_DISK_QUEUE': 'scrapy.squeues.PickleFifoDiskQueue', 'SCHEDULER_MEMORY_QUEUE': 'scrapy.squeues.FifoMemoryQueue'}
RUNS = [('默认', {}), ('只设 DEPTH_PRIORITY=1', {'DEPTH_PRIORITY': 1}), ('只换成 FIFO 队列', FIFO), ('DEPTH_PRIORITY=1 + FIFO 队列', dict(FIFO, DEPTH_PRIORITY=1))]
for tag, st in RUNS:
    d = sdir('s1b'); st = dict(st, CONCURRENT_REQUESTS=1, LOG_LEVEL='WARNING')
    with Srv(tree2) as s:
        rc, out, t = runspider(d, CODE(s.url('')), st)
    print(f'  {tag}:服务器收到请求的顺序  {" ".join(l["path"] for l in s.log)}')
    if tag == '默认':
        E2 = ev(d); print('    默认设置下的交错(下载与回调是流水线,下载器一空出来引擎就取下一个请求,不等上一个回调):')
        print('    ' + '  '.join(f'{x["e"].strip()}{x["what"]}' for x in E2))

print('== 三:引擎同时放出多少个请求:每个请求服务器延迟 0.3 s,起始页有 24 个链接(共 25 个请求),只改 CONCURRENT_REQUESTS')
def slow(h):
    if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">p</a>' for i in range(24)) + '</html>', {'Content-Type': 'text/html'}); return
    time.sleep(0.3); h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
CODE3 = lambda u: f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    start_urls = ['{u}/']
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall(): yield response.follow(u, self.sub)
    def sub(self, response): pass
"""
print(f'  {"CONCURRENT_REQUESTS":>20}{"服务器同时处理的峰值":>16}{"总耗时(秒,页面全部下完)":>26}{"理想值 24×0.3/N":>16}')
for n in (1, 4, 8, 24):
    d = sdir('s1c')
    with Srv(slow) as s:
        rc, out, t = runspider(d, CODE3(s.url('')), {'CONCURRENT_REQUESTS': n, 'CONCURRENT_REQUESTS_PER_DOMAIN': n, 'LOG_LEVEL': 'INFO'})
    st = stats(out); el = st['elapsed_time_seconds']
    print(f'  {n:>20}{s.peak:>16}{el:>26.2f}{24 * 0.3 / n:>16.2f}   (response_received_count={st["response_received_count"]})')

print('== 四:回调可以返回什么:dict / Request / None / 列表 / 其它,各自的结果(日志里的 ERROR 与 stats)')
def ok(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
CODE4 = lambda u, body: f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    start_urls = ['{u}/']
    def parse(self, response):
{body}
"""
CASES = [('yield 一个 dict', '        yield {"a": 1}'), ('yield 一个 Request', '        yield scrapy.Request(response.urljoin("/y"))'), ('return None(什么都不写)', '        pass'),
         ('return 一个列表 [dict, Request]', '        return [{"a": 1}, scrapy.Request(response.urljoin("/y"))]'), ('return 一个字符串', '        return "abc"'), ('yield 一个整数', '        yield 42')]
for tag, body in CASES:
    d = sdir('s1d')
    with Srv(ok) as s:
        rc, out, t = runspider(d, CODE4(s.url(''), body), {'LOG_LEVEL': 'DEBUG'})
    st = stats(out); L = out.split('\n')
    scraped = [L[i + 1].strip() for i, l in enumerate(L) if 'Scraped from' in l]
    errs = [l for l in L if '] ERROR' in l]
    print(f'  {tag}:服务器收到 {[l["path"] for l in s.log]};item_scraped_count={st.get("item_scraped_count", 0)};spider_exceptions/count={st.get("spider_exceptions/count", 0)}')
    print(f'      被当成 item 的内容:{scraped if scraped else "(无)"};' + (f'ERROR:{errs[0][:120]}' if errs else '日志里没有 ERROR'))
print('== 五:什么时候算“跑完”:spider_idle 信号;DontCloseSpider 让引擎别关;idle 会被重复触发,间隔多久')
CODE5 = lambda u: f"""
import scrapy
from scrapy import signals
from scrapy.exceptions import DontCloseSpider
class S(scrapy.Spider):
    name = 's'
    start_urls = ['{u}/']
    n = 0
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw)
        crawler.signals.connect(sp.idle, signals.spider_idle)
        crawler.signals.connect(sp.empty, signals.scheduler_empty)
        sp.empties = 0
        return sp
    def idle(self):
        self.n += 1; EV(e='spider_idle', n=self.n, empties=self.empties)
        if self.n == 2:
            self.crawler.engine.crawl(scrapy.Request('{u}/late', callback=self.late)); EV(e='在第 2 次 idle 里塞进一个新请求')
        if self.n < 4: raise DontCloseSpider
    def empty(self): self.empties += 1
    def parse(self, response): EV(e='parse', url=response.url)
    def late(self, response): EV(e='late 回调', url=response.url)
"""
d = sdir('s1e')
with Srv(ok) as s:
    t0 = time.perf_counter(); rc, out, t = runspider(d, CODE5(s.url('')), {'LOG_LEVEL': 'INFO'})
E5 = ev(d)
for x in E5: print(f'  {x["t"]:>8.0f} ms  ' + '  '.join(f'{k}={v}' for k, v in x.items() if k not in ('t',)))
idles = [x['t'] for x in E5 if x['e'] == 'spider_idle']
print(f'  相邻两次 spider_idle 的间隔(ms):{[round(b - a) for a, b in zip(idles, idles[1:])]};finish_reason={stats(out)["finish_reason"]};服务器收到 {[l["path"] for l in s.log]}')
