import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s37'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path); p = h.path
        if p == '/robots.txt': h.reply(200, 'User-agent: *\nAllow: /\n', {'Content-Type': 'text/plain'})
        elif p == '/': h.reply(200, '<html><a href="/ok">ok</a><a href="/redir">r</a><a href="/missing">m</a><a href="/boom">b</a><a href="/ok">dup</a></html>', {'Content-Type': 'text/html'})
        elif p == '/redir': h.reply(302, b'', {'Location': '/ok2'})
        elif p == '/missing': h.reply(404, 'nf', {'Content-Type': 'text/plain'})
        elif p == '/big': h.reply(200, b'x' * 300000, {'Content-Type': 'application/octet-stream'})
        else: h.reply(200, f'<html>{p}</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s37'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)

CODE1 = """
import scrapy
from scrapy import signals
from scrapy.exceptions import DropItem
ALL = [n for n in dir(signals) if not n.startswith('_')]
class P:
    def process_item(self, item):
        if item.get('drop'): raise DropItem('no')
        if item.get('err'): raise RuntimeError('pipeline error')
        return item
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'ROBOTSTXT_OBEY': True, 'ITEM_PIPELINES': {P: 1}, 'FEEDS': {'out.jsonl': {'format': 'jsonlines'}}}
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw); sp.fs = []
        for n in ALL:
            def mk(n):
                def f(**kw): EV(sig=n, args=sorted(k for k in kw if k != 'signal' and k != 'sender'))
                return f
            f = mk(n); sp.fs.append(f); crawler.signals.connect(f, getattr(signals, n))
        return sp
    async def start(self): yield scrapy.Request('@U@/')
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall(): yield response.follow(u, callback=self.page)
    def page(self, response):
        if response.url.endswith('/boom'): raise ValueError('callback error')
        yield {'u': response.url}
        if response.url.endswith('/ok'): yield {'drop': True}; yield {'err': True}
"""
print('== 一:2.19 的信号一共多少个,一次抓取(robots.txt + 重复链接 + 302 + 404 + 回调抛异常 + 被丢弃的 item + pipeline 异常 + 导出到文件)里每个信号触发多少次、带哪些参数')
sv, E, out, st = go(CODE1, {'CONCURRENT_REQUESTS': 1})
from collections import Counter, OrderedDict
rs = subprocess.run([SPY, '-c', 'from scrapy import signals; print(" ".join(n for n in dir(signals) if not n.startswith("_")))'], capture_output=True, text=True).stdout.split()
print(f'  scrapy.signals 里有 {len(rs)} 个信号:{" ".join(rs)}')
c = Counter(x['sig'] for x in E); args = {}
for x in E: args.setdefault(x['sig'], x['args'])
print(f'  {"信号":<28}{"次数":>4}  参数(除 sender、signal)')
for n in rs: print(f'  {n:<28}{c.get(n, 0):>4}  {args.get(n, "(没触发)")}')

print('== 二:这次抓取里信号的先后顺序(去掉 bytes_received / headers_received 这类很碎的,保留首次出现)')
seen = []; 
for x in E:
    if x['sig'] not in seen: seen.append(x['sig'])
print('  首次出现的顺序:' + ' → '.join(seen))
last = [x['sig'] for x in E][-6:]
print('  最后 6 个事件:' + ' → '.join(last))

print('== 三:bytes_received 里抛 StopDownload 可以提前中止下载(headers_received 同理):服务器发 300,000 字节,第一个数据块就停')
CODE3 = """
import scrapy
from scrapy import signals
from scrapy.exceptions import StopDownload
class S(scrapy.Spider):
    name = 's'
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw)
        def on_bytes(data, request, spider): EV(sig='bytes_received', n=len(data)); raise StopDownload(fail=FAIL)
        sp.f = on_bytes; crawler.signals.connect(on_bytes, signals.bytes_received); return sp
    async def start(self): yield scrapy.Request('@U@/big', callback=self.ok, errback=self.eb)
    def ok(self, response): EV(who='callback', body=len(response.body), status=response.status)
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__name__, resp=len(failure.value.response.body) if getattr(failure.value, 'response', None) is not None else None)
"""
for fail in (False, True):
    sv, E, out, st = go(CODE3.replace('FAIL', str(fail)))
    print(f'  StopDownload(fail={fail}):{[{k: v for k, v in x.items() if k != "t"} for x in E]};stats downloader/response_bytes={st.get("downloader/response_bytes")}')
sv, E, out, st = go(CODE3.replace('raise StopDownload(fail=FAIL)', 'pass'))
print(f'  不中止:{[{k: v for k, v in x.items() if k != "t"} for x in E][-1:]};bytes_received 触发了 {len([x for x in E if x.get("sig") == "bytes_received"])} 次;response_bytes={st.get("downloader/response_bytes")}')

print('== 四:信号处理函数里抛异常不会让爬虫停(日志 ERROR “Error caught on signal handler”);处理函数写成 async def 时,有的信号会 await 它,有的不会(协程创建了但从来没运行)——给每个信号接一个 await asyncio.sleep(0.3) 的 async 处理函数看哪些真的跑完')
SIGS = ['spider_opened', 'engine_started', 'request_scheduled', 'request_reached_downloader', 'headers_received', 'bytes_received', 'response_downloaded', 'request_left_downloader', 'response_received', 'item_scraped', 'scheduler_empty', 'spider_idle', 'spider_closed', 'feed_slot_closed', 'feed_exporter_closed', 'engine_stopped']
CODE4 = """
import scrapy, asyncio, time
from scrapy import signals
SIGS = %r
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'FEEDS': {'out.jsonl': {'format': 'jsonlines'}}}
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw); sp.fs = []
        def bad(**kw): raise RuntimeError('handler boom')
        sp.fs.append(bad); crawler.signals.connect(bad, signals.response_received)
        for n in SIGS:
            def mk(n):
                async def f(**kw):
                    EV(sig=n, phase='start'); await asyncio.sleep(0.3); EV(sig=n, phase='end')
                return f
            f = mk(n); sp.fs.append(f); crawler.signals.connect(f, getattr(signals, n))
        return sp
    async def start(self): yield scrapy.Request('@U@/ok')
    def parse(self, response): yield {'u': response.url}
""" % SIGS
sv, E, out, st = go(CODE4)
started = {x['sig'] for x in E if x['phase'] == 'start'}; ended = {x['sig'] for x in E if x['phase'] == 'end'}
print(f'  {"信号":<28}{"async 处理函数":<16}')
for n in SIGS: print(f'  {n:<28}{("被 await 到结束" if n in ended else "开始了但没结束" if n in started else "没有运行(协程没被调度)"):<16}')
print(f'  日志:{[l.strip()[:100] for l in out.split(chr(10)) if "Error caught on signal handler" in l][:1]};finish_reason={st["finish_reason"]}(处理函数抛异常没有影响)')

print('== 五:弱引用坑:signals.connect 默认只保存弱引用,连上一个没人持有的 lambda / 局部函数,它会被垃圾回收,信号永远不再触发')
for tag, keep in (('不保存引用的局部函数', False), ('把函数挂到 spider 属性上', True)):
    sv, E, out, st = go(f"""
import scrapy, gc
from scrapy import signals
class S(scrapy.Spider):
    name = 's'
    @classmethod
    def from_crawler(cls, crawler, *a, **kw):
        sp = super().from_crawler(crawler, *a, **kw)
        def f(**kw): EV(sig='response_received 被调用')
        crawler.signals.connect(f, signals.response_received)
        if {keep}: sp.f = f
        gc.collect()
        return sp
    async def start(self): yield scrapy.Request('@U@/ok')
    def parse(self, response): pass
""")
    print(f'  {tag}:处理函数被调用 {len(E)} 次')
