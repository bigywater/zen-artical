import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s2'); reset_s()
MODES = [('asyncio reactor(默认)', {}), ('SelectReactor', {'TWISTED_REACTOR': 'twisted.internet.selectreactor.SelectReactor'}), ('无 reactor', {'TWISTED_REACTOR_ENABLED': 'False'})]
def ok(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})

print('== 一:同一个 spider 用三种方式启动,日志里的 reactor / 事件循环 / 下载处理器各是什么')
d = sdir('s2a'); code = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    start_urls = ['%s/']
    def parse(self, response): pass
"""
for tag, st in MODES:
    with Srv(ok) as s:
        rc, out, t = runspider(d, code % s.url('').rstrip('/'), dict(st, LOG_LEVEL='DEBUG'))
    print(f'  [{tag}] 设置 {st or "(无)"},退出码 {rc}')
    seen = []
    for l in keep(out, 'Using AsyncCrawlerProcess', 'Using CrawlerProcess', 'Using reactor', 'Not using a Twisted reactor', 'Using asyncio event loop', 'AiohttpDownloadHandler').split('\n'):
        if l not in seen: seen.append(l); print('      ' + l.strip() + ('(http 与 https 各打印一次)' if 'Aiohttp' in l else ''))
print(f'  默认值:TWISTED_REACTOR = {__import__("subprocess").run([SPY, "-c", "from scrapy.settings import default_settings as d; print(d.TWISTED_REACTOR, d.TWISTED_REACTOR_ENABLED, d.ASYNCIO_EVENT_LOOP, d.REACTOR_THREADPOOL_MAXSIZE)"], capture_output=True, text=True).stdout.strip()}  (依次:TWISTED_REACTOR、TWISTED_REACTOR_ENABLED、ASYNCIO_EVENT_LOOP、REACTOR_THREADPOOL_MAXSIZE)')

print('== 二:单线程同时处理几百个请求:100 个页面,服务器每个延迟 0.5 s,CONCURRENT_REQUESTS=100;三种方式的总耗时、回调所在线程、进程里的线程数')
def slow(h):
    if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">p</a>' for i in range(100)) + '</html>', {'Content-Type': 'text/html'}); return
    time.sleep(0.5); h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
CODE2 = lambda u: f"""
import scrapy, threading
class S(scrapy.Spider):
    name = 's'
    start_urls = ['{u}/']
    def parse(self, response):
        for u in response.css('a::attr(href)').getall(): yield response.follow(u, self.sub)
    def sub(self, response):
        EV(th=threading.current_thread().name, n=threading.active_count())
"""
print(f'  {"方式":<24}{"总耗时 s":>9}{"服务器并发峰值":>14}{"回调线程":>22}{"线程数(最大)":>12}{"成功响应":>9}')
for tag, st in MODES:
    d = sdir('s2b')
    with Srv(slow) as s:
        rc, out, t = runspider(d, CODE2(s.url('')), dict(st, CONCURRENT_REQUESTS=100, CONCURRENT_REQUESTS_PER_DOMAIN=100, LOG_LEVEL='INFO'))
    E = ev(d); sx = stats(out)
    print(f'  {tag:<24}{sx["elapsed_time_seconds"]:>9.2f}{s.peak:>14}{",".join(sorted({x["th"] for x in E})):>22}{max(x["n"] for x in E):>12}{sx["downloader/response_status_count/200"]:>9}')

print('== 三:回调里的同步阻塞:20 个页面,服务器每个延迟 0.3 s,全部并发(CONCURRENT_REQUESTS=20);回调里 time.sleep(0.1) 之后总耗时')
def slow3(h):
    if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">p</a>' for i in range(20)) + '</html>', {'Content-Type': 'text/html'}); return
    time.sleep(0.3); h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
CODE3 = lambda u, body: f"""
import scrapy, time, asyncio
class S(scrapy.Spider):
    name = 's'
    start_urls = ['{u}/']
    def parse(self, response):
        for u in response.css('a::attr(href)').getall(): yield response.follow(u, self.sub)
{body}
"""
CASES3 = [('回调什么都不做', '    def sub(self, response): pass'), ('回调里 time.sleep(0.1)', '    def sub(self, response): time.sleep(0.1)'), ('回调里 time.sleep(0.1),并发改成 1', '    def sub(self, response): time.sleep(0.1)'),
          ('async def 回调里 await asyncio.sleep(0.1)', '    async def sub(self, response): await asyncio.sleep(0.1)')]
print(f'  {"情形":<44}{"总耗时 s":>9}  理想值')
for i, (tag, body) in enumerate(CASES3):
    d = sdir('s2c'); conc = 1 if '改成 1' in tag else 20
    with Srv(slow3) as s:
        rc, out, t = runspider(d, CODE3(s.url(''), body), dict(CONCURRENT_REQUESTS=conc, CONCURRENT_REQUESTS_PER_DOMAIN=conc, LOG_LEVEL='INFO'))
    sx = stats(out)
    ideal = {0: '0.3+≈0', 1: '0.3+20×0.1=2.3', 2: '20×(0.3+0.1)=8', 3: '0.3+0.1'}[i]
    print(f'  {tag:<44}{sx["elapsed_time_seconds"]:>9.2f}  {ideal}(状态码 200 的响应 {sx["downloader/response_status_count/200"]} 个)')

print('== 四:async def 回调里 await asyncio.sleep:在三种方式下各自的结果')
for tag, st in MODES:
    d = sdir('s2d')
    with Srv(slow3) as s:
        rc, out, t = runspider(d, CODE3(s.url(''), '    async def sub(self, response): await asyncio.sleep(0.1)'), dict(st, CONCURRENT_REQUESTS=20, CONCURRENT_REQUESTS_PER_DOMAIN=20, LOG_LEVEL='INFO'))
    sx = stats(out); L = out.split('\n')
    rt = [l for l in L if l.startswith('RuntimeError')]
    print(f'  [{tag}] 总耗时 {sx.get("elapsed_time_seconds", 0):.2f} s;spider_exceptions/count={sx.get("spider_exceptions/count", 0)};response_received_count={sx.get("response_received_count")}')
    if rt: print('      异常:' + rt[0][:200])

print('== 五:换事件循环:ASYNCIO_EVENT_LOOP=uvloop.Loop(uvloop 0.23.0 装在虚拟环境里);300 个零延迟请求,各跑 3 次取中位数')
def fast(h):
    if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">p</a>' for i in range(300)) + '</html>', {'Content-Type': 'text/html'}); return
    h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
for tag, st in (('默认事件循环', {}), ('uvloop', {'ASYNCIO_EVENT_LOOP': 'uvloop.Loop'})):
    ts = []
    for _ in range(3):
        d = sdir('s2e')
        with Srv(fast) as s:
            rc, out, t = runspider(d, CODE2(s.url('')), dict(st, CONCURRENT_REQUESTS=100, CONCURRENT_REQUESTS_PER_DOMAIN=100, LOG_LEVEL='DEBUG'))
        ts.append(stats(out)['elapsed_time_seconds'])
    loop = keep(out, 'Using asyncio event loop').strip()
    print(f'  {tag}:{loop.split(": ")[-1]};3 次的 elapsed_time_seconds {[round(x, 3) for x in ts]},中位数 {median(ts):.3f} s;{stats(out)["response_received_count"]} 个响应')
