import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s41'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path)
        if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">x</a>' for i in range(30)) + '</html>', {'Content-Type': 'text/html'}); return
        time.sleep(0.02); h.reply(200, f'<html>{h.path}</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s41'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'DEBUG', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)
def logs(out, *keys): return [(l.split('] ', 1)[1] if '] ' in l else l).strip()[:110] for l in out.split('\n') if any(k in l for k in keys)]

print('== 一:IgnoreRequest 在不同位置抛出:回调 / errback 是否被调用、有什么日志')
CASES = [
 ('下载器中间件 process_request 抛 IgnoreRequest', "class DM:\n    def process_request(self, request):\n        if request.url.endswith('/target'): raise IgnoreRequest('mw says no')\n", {'DOWNLOADER_MIDDLEWARES': 'DM'}),
 ('下载器中间件 process_response 抛 IgnoreRequest', "class DM:\n    def process_response(self, request, response):\n        if request.url.endswith('/target'): raise IgnoreRequest('resp says no')\n        return response\n", {'DOWNLOADER_MIDDLEWARES': 'DM'}),
 ('爬虫中间件 process_spider_input 抛 IgnoreRequest', "class SM:\n    def process_spider_input(self, response):\n        if response.url.endswith('/target'): raise IgnoreRequest('spider-mw says no')\n", {'SPIDER_MIDDLEWARES': 'SM'}),
 ('回调里抛 IgnoreRequest', "", {}),
]
for tag, defs, kind in CASES:
    cb_body = "raise IgnoreRequest('callback says no')" if tag.startswith('回调') else "EV(who='callback')"
    cfg = {'custom_settings = {' + ('"DOWNLOADER_MIDDLEWARES": {DM: 100}' if 'DOWNLOADER_MIDDLEWARES' in kind else '"SPIDER_MIDDLEWARES": {SM: 100}' if 'SPIDER_MIDDLEWARES' in kind else '') + '}'}
    sv, E, out, st = go(f"""
import scrapy
from scrapy.exceptions import IgnoreRequest
{defs}
class S(scrapy.Spider):
    name = 's'
    {list(cfg)[0]}
    async def start(self): yield scrapy.Request('@U@/target', callback=self.cb, errback=self.eb)
    def cb(self, response): {cb_body}
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__name__ + ': ' + str(failure.value)[:30])
""")
    print(f'  {tag}:' + ('; '.join(f'{x["who"]}' + (f' ({x["exc"]})' if 'exc' in x else '') for x in E) or '回调/errback 都没有被调用') + f';spider_exceptions={st.get("spider_exceptions/count", 0)};日志 {logs(out, "Ignoring", "IgnoreRequest", "Spider error")[:1]}')

print('== 二:CloseSpider(reason) 在不同位置抛出:finish_reason、关闭前处理了多少页(站点 30 个页面,并发 1)')
CS = [
 ('回调里 raise CloseSpider("my_reason")(第 5 个页面)', "    def cb(self, response):\n        self.n = getattr(self, 'n', 0) + 1\n        if self.n == 5: raise CloseSpider('my_reason')\n", {}),
 ('pipeline.process_item 里抛(第 5 个 item)', "    def cb(self, response): yield {'u': response.url}\n", {'ITEM_PIPELINES': True}),
 ('start() 里抛', "    def cb(self, response): pass\n", {'START': True}),
 ('下载器中间件 process_request 里抛(第 5 个请求)', "    def cb(self, response): pass\n", {'DM': True}),
 ('信号处理函数里抛(response_received 的第 5 次)', "    def cb(self, response): pass\n", {'SIG': True}),
]
for tag, cb, opt in CS:
    extra = ''; cs = ''
    if opt.get('ITEM_PIPELINES'): extra = "class P:\n    n = 0\n    def process_item(self, item):\n        P.n += 1\n        if P.n == 5: raise CloseSpider('pipeline_reason')\n        return item\n"; cs = "custom_settings = {'ITEM_PIPELINES': {P: 1}}"
    if opt.get('DM'): extra = "class DM:\n    n = 0\n    def process_request(self, request):\n        DM.n += 1\n        if DM.n == 5: raise CloseSpider('mw_reason')\n"; cs = "custom_settings = {'DOWNLOADER_MIDDLEWARES': {DM: 100}}"
    start = "    async def start(self):\n        yield scrapy.Request('@U@/', callback=self.parse)\n        raise CloseSpider('start_reason')\n" if opt.get('START') else "    async def start(self): yield scrapy.Request('@U@/')\n"
    sig = ""
    if opt.get('SIG'):
        sig = "    @classmethod\n    def from_crawler(cls, crawler, *a, **kw):\n        sp = super().from_crawler(crawler, *a, **kw); sp.k = 0\n        def f(**kw):\n            sp.k += 1\n            if sp.k == 5: raise CloseSpider('signal_reason')\n        sp.f = f; crawler.signals.connect(f, scrapy.signals.response_received); return sp\n"
    sv, E, out, st = go(f"""
import scrapy
from scrapy.exceptions import CloseSpider
{extra}
class S(scrapy.Spider):
    name = 's'
    {cs}
{start}{sig}    def parse(self, response):
        for u in response.css('a::attr(href)').getall(): yield response.follow(u, callback=self.cb)
{cb}
""")
    er = [l.strip() for l in out.split(chr(10)) if '] ERROR' in l or '] WARNING' in l]
    print(f'  {tag}:finish_reason={st.get("finish_reason")};服务器收到 {len(sv.log)} 个请求;item_scraped_count={st.get("item_scraped_count", 0)};日志里的第一条错误:{(re.sub(r"0x[0-9a-f]+", "0x…", er[0].split("] ", 1)[1])[:80] if er else "(无)")}')

print('== 三:NotConfigured:扩展 / 中间件 / pipeline 的 __init__ 或 from_crawler 里抛 NotConfigured → 这个组件被悄悄禁用;给了消息就打一条 WARNING “Disabled …”')
sv, E, out, st = go("""
import scrapy
from scrapy.exceptions import NotConfigured
class QuietExt:
    def __init__(self): raise NotConfigured
class LoudExt:
    def __init__(self): raise NotConfigured('missing LOUD_SETTING')
class DM:
    @classmethod
    def from_crawler(cls, crawler): raise NotConfigured('no config for DM')
class P:
    @classmethod
    def from_crawler(cls, crawler): raise NotConfigured('pipeline off')
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'EXTENSIONS': {QuietExt: 100, LoudExt: 101}, 'DOWNLOADER_MIDDLEWARES': {DM: 100}, 'ITEM_PIPELINES': {P: 1}}
    async def start(self): yield scrapy.Request('@U@/x')
    def parse(self, response): yield {'a': 1}
""", {'LOG_LEVEL': 'INFO'})
print('  日志里的 Disabled 行:' + ' | '.join(logs(out, 'Disabled')))
print(f'  爬虫照常跑完:finish_reason={st["finish_reason"]};item_scraped_count={st.get("item_scraped_count")}')
for l in out.split('\n'):
    if 'Enabled item pipelines' in l: print('  ' + l.strip())
i = out.find('Enabled item pipelines'); print('  ' + out[i:i + 90].split('\n')[1].strip() if i > 0 else '')

print('== 四:不支持的 URL 协议:NotSupported 一类的异常(scheme 没有对应的下载处理器)——errback 拿到什么,会不会重试')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('foo://bar/x', callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback')
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__module__ + '.' + type(failure.value).__name__, msg=str(failure.value)[:70])
""", {'LOG_LEVEL': 'INFO'})
print(f'  foo://bar/x:{[{k: v for k, v in x.items() if k != "t"} for x in E]};retry/count={st.get("retry/count", 0)};downloader/exception_count={st.get("downloader/exception_count", 0)}')
