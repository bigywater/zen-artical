import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s43'); reset_s()
SRC = pathlib.Path(SPY).parent.parent / 'lib' / 'python3.14' / 'site-packages' / 'scrapy'
print('== 一:Scrapy 2.19 源码里读写的 request.meta 键(grep meta.get("…") / meta["…"] / meta.setdefault / meta.pop;下划线开头的是内部键)')
keys = {}
for p in SRC.rglob('*.py'):
    t = p.read_text()
    for m in re.finditer(r'meta(?:\.get|\.setdefault|\.pop|)\(?\[?["\']([A-Za-z_][A-Za-z0-9_]*)["\']', t):
        keys.setdefault(m.group(1), set()).add(str(p.relative_to(SRC)).split('/')[0] + '/' + p.stem)
pub = sorted(k for k in keys if not k.startswith('_')); priv = sorted(k for k in keys if k.startswith('_'))
print(f'  共 {len(keys)} 个键,其中公开 {len(pub)} 个、内部(下划线){len(priv)} 个')
print('  公开键:' + ' '.join(pub))
print('  内部键:' + ' '.join(priv))
IN = ['allow_offsite', 'autothrottle_dont_adjust_delay', 'bindaddress', 'cookiejar', 'depth_reset', 'dont_cache', 'dont_merge_cookies', 'dont_obey_robotstxt', 'dont_redirect', 'dont_retry', 'download_maxsize', 'download_slot', 'download_timeout', 'download_warnsize', 'give_up_log_level', 'handle_httpstatus_all', 'handle_httpstatus_list', 'http_auth_domain', 'http_pass', 'http_user', 'max_retry_times', 'priority_adjust', 'proxy', 'referrer_policy', 'verbatim_url']
OUT = ['cache_timestamp', 'depth', 'download_latency', 'is_start_request', 'link_text', 'redirect_reasons', 'redirect_times', 'redirect_ttl', 'redirect_urls', 'retry_times', 'rule']
print(f'  按用途分:你设置的输入键 {len([k for k in IN if k in keys])} 个({" ".join(k for k in IN if k in keys)});Scrapy 写入的输出键 {len([k for k in OUT if k in keys])} 个({" ".join(k for k in OUT if k in keys)})')
print('  源码里出现但上面两组都没列的公开键:' + (' '.join(k for k in pub if k not in IN and k not in OUT) or '(无)'))

class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append((h.path, dict(h.hdrs), h.client_address))
        p = h.path.split('?')[0]
        if p == '/slow': time.sleep(1.0)
        if p == '/big': h.reply(200, b'x' * 5000, {'Content-Type': 'text/html'}); return
        if p in ('/e404', '/e500', '/e503'): h.reply(int(p[2:]), 'x', {'Content-Type': 'text/plain'}); return
        if p == '/link': h.reply(200, '<html><a href="/landing">go</a></html>', {'Content-Type': 'text/html'}); return
        h.reply(200, f'<html>{p}</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s43'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        st_ = {k: (v.replace('@PORT@', str(s.port)) if isinstance(v, str) else v) for k, v in dict({'LOG_LEVEL': 'INFO', 'RETRY_ENABLED': 0}, **(settings or {})).items()}
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')).replace('@PORT@', str(s.port)), st_)
    return sv, ev(d), out, stats(out)

print('== 二:几个没在前面文章单独验证过的输入键,逐个设到请求上看效果')
CODE = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for path, meta in CASES: yield scrapy.Request('@U@' + path, meta=meta, callback=self.cb, errback=self.eb, cb_kwargs={'tag': path + ' ' + str(sorted(meta.items()))}, dont_filter=True)
    def cb(self, response, tag): EV(tag=tag, who='callback', status=response.status, n=len(response.body))
    def eb(self, failure, tag=None): EV(tag=failure.request.cb_kwargs['tag'], who='errback', exc=type(failure.value).__name__)
"""
CASES = "[('/slow', {}), ('/slow', {'download_timeout': 0.3}), ('/big', {}), ('/big', {'download_maxsize': 1000}), ('/e404', {}), ('/e404', {'handle_httpstatus_all': True}), ('/e500', {'handle_httpstatus_list': [500]}), ('/e503', {'handle_httpstatus_list': [500]})]"
sv, E, out, st = go("CASES = " + CASES + CODE)
for x in sorted(E, key=lambda x: x['tag']):
    print(f'  {x["tag"]:<60}→ ' + (f'回调 status={x["status"]} {x["n"]} 字节' if x['who'] == 'callback' else f'errback {x["exc"]}'))

print('== 三:bindaddress(本地出口地址):服务器看到的客户端地址;给一个本机没有的地址会怎样')
for tag, ba in (('不设', None), ("('127.0.0.1', 0)", "('127.0.0.1', 0)"), ("('10.255.255.1', 0)(本机没有这个地址)", "('10.255.255.1', 0)")):
    meta = '{}' if ba is None else '{"bindaddress": ' + ba + '}'
    sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/x', meta={meta}, callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback')
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__name__, msg=str(failure.value)[:70])
""")
    print(f'  {tag:<36}→ {[{k: v for k, v in x.items() if k != "t"} for x in E]};服务器看到的客户端地址 {sv.log[0][2][0] if sv.log else "(没收到)"}')

print('== 四:referrer_policy:页面 /link 上有一个到 /landing 的链接;跟随时发出的 Referer 头(默认策略 scrapy-default 是完整 URL)')
for pol in (None, 'no-referrer', 'origin', 'same-origin', 'strict-origin-when-cross-origin', 'unsafe-url'):
    meta = "" if pol is None else f", meta={{'referrer_policy': {pol!r}}}"
    sv, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/link?q=1#frag')
    def parse(self, response): yield response.follow('/landing'{meta})
""")
    ref = [h.get('Referer', '(无)') for p, h, _ in sv.log if p == '/landing']
    print(f'  {str(pol):<34}→ 目标请求的 Referer = {ref[0].replace(sv.log[0][1]["Host"], "主机") if ref else "?"}')

print('== 五:http_user / http_pass / http_auth_domain(请求级 Basic 认证),以及设置级 HTTPAUTH_USER / PASS / DOMAIN')
import base64
def auth(sv, p): 
    for pp, h, _ in sv.log:
        if pp == p: 
            a = h.get('Authorization'); return base64.b64decode(a.split()[1]).decode() if a else '(无)'
    return '?'
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/a', meta={'http_user': 'alice', 'http_pass': 's3cret'})
        yield scrapy.Request('@U@/b', meta={'http_user': 'alice', 'http_pass': 's3cret', 'http_auth_domain': 'localhost'})
        yield scrapy.Request('@U@/c', meta={'http_user': 'alice', 'http_pass': 's3cret'}, headers={'Authorization': 'Bearer own'})
    def parse(self, response): pass
""")
print(f'  meta http_user/http_pass:/a → {auth(sv, "/a")};加 http_auth_domain=localhost(请求在 127.0.0.1)/b → {auth(sv, "/b")};请求自带 Authorization 头 /c → {[h.get("Authorization") for p, h, _ in sv.log if p == "/c"]}')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/a')
    def parse(self, response): pass
""", {'HTTPAUTH_USER': 'bob', 'HTTPAUTH_PASS': 'pw'})
print(f'  只设 HTTPAUTH_USER / HTTPAUTH_PASS(没设 HTTPAUTH_DOMAIN):退出码≠0?{"是" if not sv.log else "否"};服务器收到 {len(sv.log)} 个请求;错误:' + ([l.strip()[:150] for l in out.split(chr(10)) if l.startswith("ValueError")] or ['(无)'])[0])
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/a')
    def parse(self, response): pass
""", {'HTTPAUTH_USER': 'bob', 'HTTPAUTH_PASS': 'pw', 'HTTPAUTH_DOMAIN': '127.0.0.1'})
print(f'  HTTPAUTH_DOMAIN=127.0.0.1(不带端口,请求 URL 带端口):/a → {auth(sv, "/a")}')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/a')
    def parse(self, response): pass
""", {'HTTPAUTH_USER': 'bob', 'HTTPAUTH_PASS': 'pw', 'HTTPAUTH_DOMAIN': 'localhost'})
print(f'  HTTPAUTH_DOMAIN=localhost(请求在 127.0.0.1):/a → {auth(sv, "/a")}')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/a')
    def parse(self, response): pass
""", {'HTTPAUTH_USER': 'bob', 'HTTPAUTH_PASS': 'pw', 'HTTPAUTH_DOMAIN': '127.0.0.1:@PORT@'})
print(f'  HTTPAUTH_DOMAIN=127.0.0.1:<端口>(域名带上端口):/a → {auth(sv, "/a")}  ← 匹配用的是 URL 的 netloc(含端口),所以 URL 里有端口时域名也得带端口')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/b', meta={'http_user': 'alice', 'http_pass': 'pw', 'http_auth_domain': '127.0.0.1:@PORT@'})
    def parse(self, response): pass
""")
print(f'  meta http_auth_domain=127.0.0.1:<端口>:/b → {auth(sv, "/b")}')

print('== 六:response.meta 里最后有哪些键:一个请求经过起始请求、重定向、重试、cookie、深度、下载器之后')
class Site2(Site):
    def __call__(self, h):
        self.log.append((h.path, dict(h.hdrs), h.client_address)); p = h.path.split('?')[0]
        if p == '/r': h.reply(302, b'', {'Location': '/flaky'}); return
        if p == '/flaky':
            n = sum(1 for q, _, _ in self.log if q.split('?')[0] == '/flaky')
            h.reply(503 if n == 1 else 200, 'x', {'Content-Type': 'text/html', 'Set-Cookie': 'a=1'}); return
        h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
d = sdir('s43f'); sv2 = Site2()
with Srv(sv2) as s:
    rc, out, t = runspider(d, f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    custom_settings = {{'RETRY_ENABLED': True, 'RETRY_TIMES': 2}}
    async def start(self): yield scrapy.Request('{s.url("/r")}', meta={{'mine': 'x'}})
    def parse(self, response): EV(keys=sorted(response.meta), vals={{k: (v if k in ('retry_times', 'redirect_times', 'redirect_ttl', 'depth', 'redirect_reasons', 'is_start_request', 'mine', 'download_slot') else '…') for k, v in response.meta.items()}})
""", {'LOG_LEVEL': 'INFO'})
x = ev(d)[0]
print(f'  response.meta 共 {len(x["keys"])} 个键:{x["keys"]}')
print(f'  其中的取值:{x["vals"]}')
