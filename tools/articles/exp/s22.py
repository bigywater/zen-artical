import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
from urllib.parse import urlparse, parse_qs
tee('s22'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        u = urlparse(h.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.log.append(dict(path=h.path, cookie=dict(h.hdrs).get('Cookie')))
        hd = {'Content-Type': 'text/html'}
        if u.path == '/login':
            hd['Set-Cookie'] = f'sid={q.get("u", "anon")}; Path=/'
        elif u.path == '/setc':  # /setc?c=<完整 Set-Cookie 值>
            hd['Set-Cookie'] = q['c']
        h.reply(200, f'<html>{u.path}</html>', hd)
def go(code, settings=None, tag='s22'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')).replace('@P@', str(s.port)), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)
def cookies_seen(sv): return [(l['path'], l['cookie'] or '(无)') for l in sv.log]

print('== 一:默认(COOKIES_ENABLED=1):/login 返回 Set-Cookie: sid=alice,之后同一个爬虫的请求自动带上 Cookie;关掉后不带')
CODE1 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/login?u=alice', callback=self.after)
    def after(self, response):
        yield scrapy.Request('@U@/me', callback=self.p, dont_filter=True)
        yield scrapy.Request('@U@/other', callback=self.p, dont_filter=True)
    def p(self, response): pass
"""
for tag, st in (('COOKIES_ENABLED=1(默认)', {}), ('COOKIES_ENABLED=0', {'COOKIES_ENABLED': 0})):
    sv, E, out, stt = go(CODE1, st)
    print(f'  {tag}:' + ';'.join(f'{p} 带 Cookie={c}' for p, c in cookies_seen(sv)))

print('== 二:给请求手动加 Cookie:headers={"Cookie": …} 会被中间件覆盖掉,要用 cookies={…} 参数;cookies 参数设置的 cookie 会留在 jar 里,影响之后的请求')
CODE2 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/h', headers={'Cookie': 'via=header'}, callback=self.p)
        yield scrapy.Request('@U@/c', cookies={'via': 'cookies-param'}, callback=self.p)
        yield scrapy.Request('@U@/later', callback=self.p)
    def p(self, response): pass
"""
sv, E, out, stt = go(CODE2)
for p, c in sorted(cookies_seen(sv)): print(f'  {p:<8}→ 服务器收到 Cookie: {c}')
sv, E, out, stt = go(CODE2, {'COOKIES_ENABLED': 0})
print('  COOKIES_ENABLED=0:' + ';'.join(f'{p} → {c}' for p, c in sorted(cookies_seen(sv))))

print('== 三:多个 cookiejar:meta["cookiejar"]=alice / bob 各登录一个用户;后续请求必须自己把 cookiejar 带上,response.follow 之类不会自动继承')
CODE3 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for u in ('alice', 'bob'): yield scrapy.Request('@U@/login?u=' + u, meta={'cookiejar': u}, callback=self.after, dont_filter=True)
    def after(self, response):
        jar = response.meta['cookiejar']
        yield scrapy.Request('@U@/me?jar=' + jar, meta={'cookiejar': jar}, callback=self.p, dont_filter=True)
        yield scrapy.Request('@U@/forgot?jar=' + jar, callback=self.p, dont_filter=True)           # 忘了带 cookiejar → 落到默认 jar(键 None)
        yield response.follow('/follow?jar=' + jar, callback=self.p, dont_filter=True)              # response.follow 也不带 meta
    def p(self, response): pass
"""
sv, E, out, stt = go(CODE3)
for p, c in sorted(cookies_seen(sv), key=lambda x: x[0]): print(f'  {p:<20}→ Cookie: {c}')

print('== 四:cookie 的作用域和过期:Path、Secure、Domain、Max-Age 各自的效果(/setc 设置 cookie,然后请求不同路径)')
for tag, attrs, urls in (('Path=/admin', 'a=1; Path=/admin', ['/admin/x', '/public/x']), ('Secure(http 协议)', 'a=1; Path=/; Secure', ['/x']), ('Domain=localhost(请求在 127.0.0.1)', 'a=1; Path=/; Domain=localhost', ['/x']), ('Max-Age=1:立即请求一次,等 2 秒再请求一次', 'a=1; Path=/; Max-Age=1', ['/x', 'WAIT', '/x']), ('Max-Age=0(删除)', 'a=1; Path=/; Max-Age=0', ['/x']), ('HttpOnly + SameSite=Lax', 'a=1; Path=/; HttpOnly; SameSite=Lax', ['/x'])):
    seq = ', '.join(repr(u) for u in urls)
    sv, E, out, stt = go(f"""
import scrapy, asyncio, urllib.parse
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/setc?c=' + urllib.parse.quote({attrs!r}), meta={{'cookiejar': 1}})
    async def parse(self, response):
        for u in [{seq}]:
            if u == 'WAIT': await asyncio.sleep(2); continue
            yield scrapy.Request('@U@' + u, meta={{'cookiejar': 1}}, callback=self.p, dont_filter=True)
            await asyncio.sleep(0.2)
    def p(self, response): pass
""")
    print(f'  {tag:<36}Set-Cookie: {attrs:<32}→ ' + ';'.join(f'{p} 带 {c}' for p, c in cookies_seen(sv)[1:]))

print('== 五:COOKIES_DEBUG=1 的日志(DEBUG 级别)')
sv, E, out, stt = go(CODE1, {'COOKIES_DEBUG': 1, 'LOG_LEVEL': 'DEBUG'})
L = out.split('\n'); shown = 0
for i, l in enumerate(L):
    if 'Sending cookies to' in l or 'Received cookies from' in l:
        print('  ' + l.strip().replace('[scrapy.downloadermiddlewares.cookies] DEBUG: ', '')[:100])
        if i + 1 < len(L) and ('Cookie' in L[i + 1]): print('    ' + L[i + 1].strip())
        shown += 1
        if shown >= 3: break

print('== 六:meta dont_merge_cookies=True:这个请求既不带 jar 里的 cookie,也不把响应里的 Set-Cookie 存进 jar(并发 1,按顺序:carol 登录[不合并] → /me1 → dave 登录[合并] → /me3 → /me4[不合并])')
sv, E, out, stt = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/login?u=carol', meta={'dont_merge_cookies': True}, callback=self.c1)
    def c1(self, response): yield scrapy.Request('@U@/me1', callback=self.c2)
    def c2(self, response): yield scrapy.Request('@U@/login?u=dave', callback=self.c3)
    def c3(self, response): yield scrapy.Request('@U@/me3', callback=self.c4)
    def c4(self, response): yield scrapy.Request('@U@/me4', meta={'dont_merge_cookies': True}, callback=self.c5)
    def c5(self, response): pass
""")
for p, c in cookies_seen(sv): print(f'  {p:<18}→ Cookie: {c}')
