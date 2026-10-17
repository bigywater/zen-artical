import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s26'); reset_s()
d = sdir('s26a')
print('== 一:allowed_domains 怎么匹配主机名(OffsiteMiddleware.should_follow;正则 ^(.*\\.)?(域名1|域名2)$)——直接用中间件对一批 URL 判断')
rc, out, t = py(d, """
from scrapy import Request, Spider
from scrapy.utils.test import get_crawler
from scrapy.downloadermiddlewares.offsite import OffsiteMiddleware
def mk(allowed):
    class S(Spider):
        name = 's'
    S.allowed_domains = allowed
    c = get_crawler(S); sp = S.from_crawler(c) if hasattr(S, 'from_crawler') else S()
    c.spider = sp
    mw = OffsiteMiddleware.from_crawler(c)
    return mw, sp
URLS = ['http://example.org/a', 'http://www.example.org/a', 'http://bob.www.example.org/a', 'http://EXAMPLE.ORG/a', 'http://example.org:8080/a', 'http://notexample.org/a', 'http://example.org.evil.com/a', 'http://example.orgx/a', 'http://api.example.org/a', 'http://[::1]/a', 'http://127.0.0.1:9000/a']
for allowed in (['example.org'], ['www.example.org'], ['example.org', 'other.com'], ['example.org:8080'], ['http://example.org'], ['127.0.0.1'], []):
    mw, sp = mk(allowed)
    ok = []
    for u in URLS:
        mw._update_host_regex(sp)
        ok.append('✓' if mw.should_follow(Request(u), sp) else '✗')
    print(f'  allowed_domains={allowed!s:<36}' + ' '.join(ok))
print(f'  {"(下面编号对应的 URL)":<51}' + ' '.join(str(i % 10) for i in range(1, len(URLS) + 1)))
for i, u in enumerate(URLS, 1): print(f'    {i:>2}. {u}')
""")
print(out)

class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path); p = h.path.split('?')[0]; port = h.server.srv.port
        if p == '/to-local': h.reply(302, b'', {'Location': f'http://localhost:{port}/landed'}); return
        h.reply(200, f'<html><a href="http://localhost:{port}/off1">1</a><a href="http://localhost:{port}/off2">2</a><a href="http://127.0.0.1:{port}/on">3</a></html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s26'):
    dd = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(dd, code.replace('@U@', s.url('').rstrip('/')).replace('@L@', f'http://localhost:{s.port}'), dict({'LOG_LEVEL': 'DEBUG', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(dd), out, stats(dd and out)
def of(st): return {k.split('offsite/')[1]: v for k, v in sorted(st.items()) if k.startswith('offsite/')}

print('== 二:真实抓取:页面里有 2 个去 localhost 的链接和 1 个站内链接,allowed_domains = ["127.0.0.1"]:被过滤的请求、stats、日志(同一个域名只记第一条)')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    allowed_domains = ['127.0.0.1']
    async def start(self): yield scrapy.Request('@U@/')
    def parse(self, response):
        EV(p=response.url.rsplit('/', 1)[-1] or '/')
        for u in response.css('a::attr(href)').getall(): yield scrapy.Request(u, callback=self.parse)
""")
print(f'  回调被调用的页面:{[x["p"] for x in E]};服务器收到 {sv.log};offsite stats {of(st)}')
for l in out.split('\n'):
    if 'Filtered offsite' in l: print('  日志:' + l.strip()[:130])

print('== 三:绕过的三种办法:meta allow_offsite、dont_filter=True、不设 allowed_domains')
for tag, extra, al in (('meta allow_offsite = True', ", meta={'allow_offsite': True}", "['127.0.0.1']"), ('dont_filter = True', ", dont_filter=True", "['127.0.0.1']"), ('不设 allowed_domains', "", "[]")):
    sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    allowed_domains = {al}
    async def start(self): yield scrapy.Request('@U@/')
    def parse(self, response):
        EV(p=response.url.rsplit('/', 1)[-1] or '/')
        if response.url.endswith(':'+response.url.split(':')[-1].split('/')[0]+'/'):
            for u in response.css('a::attr(href)').getall(): yield scrapy.Request(u, callback=self.cb{extra})
    def cb(self, response): EV(p=response.url.rsplit('/', 1)[-1])
""", {'LOG_LEVEL': 'INFO'})
    print(f'  {tag:<28}服务器收到 {sv.log};offsite stats {of(st)}')

print('== 四:起始请求和重定向也受限制:start_urls 在站外会被过滤;站内请求被 302 到站外 localhost,重定向产生的请求同样被过滤')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    allowed_domains = ['127.0.0.1']
    async def start(self):
        yield scrapy.Request('@L@/start-offsite', errback=self.eb)
        yield scrapy.Request('@U@/to-local', callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback', url=response.url)
    def eb(self, failure): EV(who='errback', url=failure.request.url.rsplit('/', 1)[-1], exc=type(failure.value).__name__ + ': ' + str(failure.value))
""")
print(f'  回调/errback 被调用的次数:{len(E)}(被过滤的请求既没有回调也没有 errback,静默丢弃)' if not E else f'  事件:{E}')
print(f'  服务器收到 {sv.log};offsite stats {of(st)}')

print('== 五:Request.dont_filter=True 的 start() 默认请求不受影响(start_urls 里写站外地址,默认 dont_filter=True)')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    allowed_domains = ['127.0.0.1']
    start_urls = ['@L@/via-start-urls']
    def parse(self, response): EV(who='callback', url=response.url.rsplit('/', 1)[-1])
""", {'LOG_LEVEL': 'INFO'})
print(f'  start_urls 指向站外 localhost:回调 {[x["url"] for x in E]};服务器收到 {sv.log};offsite stats {of(st)}')
