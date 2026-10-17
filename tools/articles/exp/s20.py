import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s20'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(dict(path=h.path, method=h.command, body=h.body, hdrs=dict(h.hdrs), t=time.perf_counter()))
        p = h.path.split('?')[0]
        port = h.server.srv.port
        if p.startswith('/r') and p[2:5].isdigit():  # /r301 -> 301 -> /target
            h.reply(int(p[2:5]), b'', {'Location': '/target'}); return
        if p == '/hop1': h.reply(302, b'', {'Location': '/hop2'}); return
        if p == '/hop2': h.reply(301, b'', {'Location': f'http://127.0.0.1:{port}/hop3#frag'}); return
        if p == '/hop3': h.reply(307, b'', {'Location': '/target'}); return
        if p == '/l':
            i = int(h.path.split('i=')[-1]) if 'i=' in h.path else 0
            h.reply(302, b'', {'Location': '/l?i=%d' % (i + 1)}); return
        if p == '/xhost': h.reply(302, b'', {'Location': f'http://localhost:{port}/target'}); return
        if p == '/nolocation': h.reply(302, b'', {}); return
        if p == '/ftp': h.reply(302, b'', {'Location': 'ftp://example.com/x'}); return
        if p == '/protorel': h.reply(302, b'', {'Location': f'//localhost:{port}/target'}); return
        if p.startswith('/meta'):
            n = p[5:] or '0'; h.reply(200, f'<html><head><meta http-equiv="refresh" content="{n}; url=/target"></head><body>m</body></html>', {'Content-Type': 'text/html'}); return
        h.reply(200, '<html>target</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s20'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')).replace('@P@', str(s.port)), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return sv, ev(d), out, stats(out)

print('== 一:状态码与请求方法:GET 和带请求体的 POST 遇到 301/302/303/307/308,跳转后的请求方法与请求体')
print(f'  {"状态码":<8}{"原请求":<8}{"跳转后方法":<10}{"跳转后请求体":<14}')
for code in (301, 302, 303, 307, 308):
    for m in ('GET', 'POST'):
        sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/r{code}', method='{m}', body='a=1' if '{m}' == 'POST' else '', headers={{'Content-Type': 'application/x-www-form-urlencoded'}} if '{m}' == 'POST' else {{}})
    def parse(self, response): EV(final=response.url.rsplit('/', 1)[-1])
""")
        t = [x for x in sv.log if x['path'] == '/target']
        print(f'  {code:<8}{m:<8}{t[0]["method"] if t else "-":<10}{t[0]["body"].decode() or "(空)" if t else "-":<14}')

print('== 二:meta 里的跳转记录:/hop1 → 302 → /hop2 → 301 → http://…/hop3#frag → 307 → /target')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/hop1')
    def parse(self, response):
        m = response.meta
        EV(final_url=response.url, request_url=response.request.url, redirect_urls=m['redirect_urls'], redirect_reasons=m['redirect_reasons'], redirect_times=m['redirect_times'], redirect_ttl=m['redirect_ttl'], status=response.status)
""")
x = E[0]
for k in ('final_url', 'request_url', 'redirect_urls', 'redirect_reasons', 'redirect_times', 'redirect_ttl', 'status'): print(f'  {k:<16}= {x[k]}')
print('  服务器收到的路径:' + ' → '.join(l['path'] for l in sv.log))

print('== 三:循环重定向和 REDIRECT_MAX_TIMES(默认 20):服务器收到几次,回调/errback 谁被调用,stats')
for mx in (20, 3):
    sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/l?i=0', errback=self.err)
    def parse(self, response): EV(who='callback')
    def err(self, failure): EV(who='errback', exc=type(failure.value).__name__ + ': ' + str(failure.value))
""", {'REDIRECT_MAX_TIMES': mx})
    who = f'{E[0]["who"]}:{E[0].get("exc", "")}' if E else '回调和 errback 都没有被调用'
    sx = {k: v for k, v in st.items() if 'ignore' in k.lower() or 'redirect' in k.lower() or k == 'finish_reason'}
    print(f'  REDIRECT_MAX_TIMES={mx}:服务器收到 {len(sv.log)} 次请求;{who}')

print('== 四:不想自动跳转:meta dont_redirect / handle_httpstatus_list——回调直接拿到 302 响应和 Location 头')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/r302', meta={'dont_redirect': True}, callback=self.cb, errback=self.err)
        yield scrapy.Request('@U@/r302?b', meta={'handle_httpstatus_list': [302], 'dont_redirect': False}, callback=self.cb, errback=self.err)
    def cb(self, response): EV(who='callback', url=response.url, status=response.status, location=response.headers.get('Location', b'').decode())
    def err(self, failure): EV(who='errback', exc=type(failure.value).__name__)
""")
for x in sorted(E, key=lambda x: x['url'] if 'url' in x else ''): print('  ' + str({k: v for k, v in x.items() if k != 't'}))
print(f'  服务器收到:{[l["path"] for l in sv.log]}')

print('== 五:跳转后请求头(COOKIES_ENABLED=0 以便看到原始 Cookie 头):Cookie / Authorization 跨主机(127.0.0.1 → localhost)被删除,同主机保留;Referer;优先级 +2')
for tag, path in (('跳到另一个主机名 localhost', '/xhost'), ('同主机跳转 /r302', '/r302')):
    sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@{path}', headers={{'Cookie': 'sid=abc', 'Authorization': 'Bearer t0k', 'X-Custom': 'keep'}})
    def parse(self, response): pass
""", {'COOKIES_ENABLED': 0})
    t = [x for x in sv.log if x['path'] == '/target'][0]['hdrs']
    print(f'  {tag}:目标请求的头 Cookie={t.get("Cookie", "(无)")}、Authorization={t.get("Authorization", "(无)")}、X-Custom={t.get("X-Custom", "(无)")}、Referer={t.get("Referer", "(无)")}')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'CONCURRENT_REQUESTS': 1}
    async def start(self):
        yield scrapy.Request('@U@/r302?a', callback=self.p)
        yield scrapy.Request('@U@/plain1', callback=self.p)
        yield scrapy.Request('@U@/plain2', callback=self.p)
    def p(self, response): pass
""")
print(f'  优先级 +2 的效果(并发 1):服务器收到的顺序 {" ".join(l["path"] for l in sv.log)}')

print('== 六:Location 的各种写法:相对路径、协议相对(//host/path)、没有 Location、非 http 协议(ftp)')
for tag, path in (('相对路径 /r302', '/r302'), ('协议相对 //localhost:端口/target', '/protorel'), ('302 没有 Location', '/nolocation'), ('Location 是 ftp://', '/ftp')):
    sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@{path}', callback=self.cb, errback=self.err, meta={{'handle_httpstatus_list': [302]}} if '{path}' in ('/nolocation', '/ftp') else {{}})
    def cb(self, response): EV(who='callback', status=response.status, url=response.url.rsplit('/', 1)[-1])
    def err(self, failure): EV(who='errback', exc=type(failure.value).__name__)
""")
    print(f'  {tag}:回调看到 status={E[0].get("status")} url=…/{E[0].get("url")}' if E and E[0]['who'] == 'callback' else f'  {tag}:{E}')

print('== 七:HTML 里的 <meta http-equiv="refresh">(MetaRefreshMiddleware):延迟 0、5、99、100、101 秒各会不会跳转,等不等')
print(f'  {"content 属性":<18}{"最终 url":<12}{"耗时 s":>8}  跳转记录')
for n in (0, 5, 99, 100, 101):
    sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/meta{n}')
    def parse(self, response): EV(final=response.url.rsplit('/', 1)[-1], reasons=response.meta.get('redirect_reasons'))
""")
    print(f'  {str(n) + "; url=/target":<18}{E[0]["final"]:<12}{st["elapsed_time_seconds"]:>8.2f}  {E[0]["reasons"]}')
