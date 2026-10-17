import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s10'); reset_s()
def site(h):
    p = h.path
    L = {'/a': ['/b', '/c'], '/b': ['/a', '/c'], '/c': ['/a']}
    if p in L: h.reply(200, '<html>' + ''.join(f'<a href="{x}">{x}</a>' for x in L[p]) + '</html>', {'Content-Type': 'text/html'})
    elif p == '/go': h.reply(302, b'', {'Location': '/target'})
    elif p == '/target': h.reply(200, '<html>target</html>', {'Content-Type': 'text/html'})
    elif p == '/flaky':
        n = sum(1 for l in h.server.srv.log if l['path'] == '/flaky')
        h.reply(503 if n <= 2 else 200, 'x', {'Content-Type': 'text/html'})
    elif p == '/robots.txt': h.reply(200, 'User-agent: *\nAllow: /\n', {'Content-Type': 'text/plain'})
    else: h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s10'):
    d = sdir(tag)
    with Srv(site) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return s, ev(d), out, stats(out)

CYC = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/a', dont_filter=DF)
    def parse(self, response):
        for u in response.css('a::attr(href)').getall(): yield response.follow(u, self.parse, dont_filter=DF)
"""
print('== 一:站点有环(/a → /b,/c;/b → /a,/c;/c → /a):默认去重时抓 3 个页面就停;全部 dont_filter=True 时会一直抓下去,要靠别的开关刹车')
for tag, df, stt in (('默认(去重)', False, {}), ('dont_filter=True,CLOSESPIDER_PAGECOUNT=50', True, {'CLOSESPIDER_PAGECOUNT': 50}), ('dont_filter=True,DEPTH_LIMIT=4', True, {'DEPTH_LIMIT': 4}), ('dont_filter=True,CLOSESPIDER_TIMEOUT=1', True, {'CLOSESPIDER_TIMEOUT': 1})):
    s, E, out, st = go(CYC.replace('DF', str(df)), stt)
    print(f'  {tag}:服务器收到 {len(s.log)} 个请求;finish_reason={st.get("finish_reason")};dupefilter/filtered={st.get("dupefilter/filtered", 0)};request_depth_max={st.get("request_depth_max")}')

print('== 二:Scrapy 自己产生的请求的 dont_filter:重试、重定向、robots.txt、start() 默认请求')
s, E, out, st = go("""
import scrapy
class DM:
    def process_request(self, request):
        EV(what=request.url.rsplit('/', 1)[-1], dont_filter=request.dont_filter, retry=request.meta.get('retry_times', 0), redirected=bool(request.meta.get('redirect_urls')))
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'DOWNLOADER_MIDDLEWARES': {DM: 100}, 'ROBOTSTXT_OBEY': True, 'RETRY_TIMES': 2}
    async def start(self):
        yield scrapy.Request('@U@/flaky')
        yield scrapy.Request('@U@/go')
    def parse(self, response): pass
""")
print(f'  {"请求":<14}{"dont_filter":<14}{"已重试次数":<8}{"重定向产生的"}')
for x in E: print(f'  /{x["what"]:<13}{str(x["dont_filter"]):<14}{x["retry"]:<10}{x["redirected"]}')

print('== 三:重定向目标已经被抓过时:重定向产生的请求也要过去重,于是被过滤——页面先链接 /target,再链接会重定向到 /target 的 /go')
for tag, df_go in (('/go 的请求 dont_filter=False(默认)', False), ('/go 的请求 dont_filter=True', True)):
    s, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/target', callback=self.got)
    def got(self, response):
        yield scrapy.Request('@U@/go', callback=self.got2, dont_filter={df_go})
    def got2(self, response): EV(e='/go 的回调被调用', final=response.url.rsplit('/', 1)[-1])
""")
    print(f'  {tag}:服务器收到 {[l["path"] for l in s.log]};/go 的回调{"被调用" if E else "没有被调用"};dupefilter/filtered={st.get("dupefilter/filtered", 0)};finish_reason={st.get("finish_reason")}')

print('== 四:轮询同一个 URL(状态页):每次都要重新请求,必须 dont_filter=True')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    n = 0
    async def start(self): yield scrapy.Request('@U@/status')
    def parse(self, response):
        self.n += 1
        if self.n < 5: yield scrapy.Request('@U@/status', callback=self.parse)
""")
print(f'  不加 dont_filter:{len(s.log)} 个请求(想轮询 5 次),dupefilter/filtered={st.get("dupefilter/filtered", 0)}')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    n = 0
    async def start(self): yield scrapy.Request('@U@/status')
    def parse(self, response):
        self.n += 1
        if self.n < 5: yield scrapy.Request('@U@/status', callback=self.parse, dont_filter=True)
""")
print(f'  dont_filter=True:{len(s.log)} 个请求,dupefilter/filtered={st.get("dupefilter/filtered", 0)}')
