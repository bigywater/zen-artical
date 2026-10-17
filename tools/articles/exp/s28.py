import sys, os, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s28'); reset_s()
class Proxy:
    """假代理(原始套接字):记录请求行和头;普通请求回 200 “via-proxy”;CONNECT 回 200 后关闭;mode='407' 一律回 407。"""
    def __init__(self, mode='ok'):
        self.reqs = []; self.mode = mode
        def fn(conn, addr):
            data = read_request(conn)
            if not data: return
            lines = data.decode('latin-1').split('\r\n')
            hdrs = dict(l.split(': ', 1) for l in lines[1:] if ': ' in l)
            self.reqs.append((lines[0], hdrs))
            if self.mode == '407': conn.sendall(b'HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="x"\r\nContent-Length: 0\r\n\r\n'); return
            if lines[0].startswith('CONNECT'): conn.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n'); time.sleep(0.2); return
            conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 20\r\n\r\n<html>via-proxy</html>')
        self.srv = RawSrv(fn)
    def __enter__(self): self.srv.__enter__(); return self
    def __exit__(self, *a): self.srv.__exit__()
    @property
    def port(self): return self.srv.port
class Origin:
    def __init__(self): self.log = []
    def __call__(self, h): self.log.append(h.path); h.reply(200, '<html>origin</html>', {'Content-Type': 'text/html'})
def run(proxy, spider_body, env=None, settings=None, tag='s28', origin=None):
    d = sdir(tag); og = origin or Origin()
    with Srv(og) as s:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
{spider_body.replace('@O@', s.url('').rstrip('/')).replace('@PX@', str(proxy.port))}
"""
        e = {k: v for k, v in (env or {}).items()}
        for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'no_proxy', 'NO_PROXY', 'ALL_PROXY', 'all_proxy'): e.setdefault(k, None)
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'RETRY_ENABLED': 0}, **(settings or {})), env=e)
    return og, ev(d), out, stats(out)
def hdr(h, k): return h.get(k, '(无)')

print('== 一:meta["proxy"]:http 请求经代理发出时,请求行变成绝对 URI;代理 URL 里的用户名密码变成 Proxy-Authorization: Basic …(解码后),百分号编码会还原')
with Proxy() as px:
    og, E, out, st = run(px, """
    async def start(self):
        yield scrapy.Request('@O@/a', meta={'proxy': 'http://127.0.0.1:@PX@'}, callback=self.cb)
        yield scrapy.Request('@O@/b', meta={'proxy': 'http://user:p%40ss:w@127.0.0.1:@PX@'}, callback=self.cb)
    def cb(self, response): EV(url=response.url.rsplit('/', 1)[-1], body=response.text)
""")
    for line, h in px.reqs:
        auth = h.get('Proxy-Authorization')
        dec = base64.b64decode(auth.split()[1]).decode() if auth else None
        print(f'  代理收到:{line}')
        print(f'      Host={hdr(h, "Host")}  Proxy-Authorization={auth or "(无)"}' + (f' → 解码 {dec!r}' if dec else ''))
print(f'  源站直接收到的请求:{og.log}(经过代理的请求没有直连源站);回调拿到的正文:{[x["body"] for x in E]}')

print('== 二:环境变量:Scrapy 启动时读取 http_proxy / https_proxy / no_proxy(urllib 的 getproxies),按请求协议选择;meta["proxy"] 优先;meta["proxy"] = None 对这一个请求关掉代理')
BODY2 = """
    async def start(self):
        yield scrapy.Request('@O@/env', callback=self.cb)
        yield scrapy.Request('@O@/meta-override', meta={'proxy': 'http://127.0.0.1:@PX@/other'}, callback=self.cb)
        yield scrapy.Request('@O@/meta-none', meta={'proxy': None}, callback=self.cb)
    def cb(self, response): EV(url=response.url.rsplit('/', 1)[-1], body=response.text[:20])
"""
with Proxy() as px:
    og, E, out, st = run(px, BODY2, env={'http_proxy': f'http://127.0.0.1:{px.port}'})
    print(f'  http_proxy=http://127.0.0.1:<代理>:代理收到 {[l.split()[1].rsplit("/", 1)[-1] for l, _ in px.reqs]}(含 meta-override);源站直接收到 {og.log}(meta-none 绕过了环境变量代理)')
with Proxy() as px:
    og, E, out, st = run(px, BODY2, env={'https_proxy': f'http://127.0.0.1:{px.port}'})
    print(f'  只设 https_proxy:代理收到 {[l.split()[1].rsplit("/", 1)[-1] for l, _ in px.reqs]};源站直接收到 {og.log}(http 请求不走 https_proxy;meta-override 仍走 meta 里指定的代理)')
with Proxy() as px:
    og, E, out, st = run(px, BODY2, env={'http_proxy': f'http://127.0.0.1:{px.port}', 'no_proxy': '127.0.0.1'})
    print(f'  http_proxy + no_proxy=127.0.0.1:代理收到 {[l.split()[1].rsplit("/", 1)[-1] for l, _ in px.reqs]};源站直接收到 {og.log}(命中 no_proxy 的主机不走环境变量代理,meta 指定的仍走)')
with Proxy() as px:
    og, E, out, st = run(px, BODY2, env={'HTTP_PROXY': f'http://127.0.0.1:{px.port}'})
    print(f'  只设大写 HTTP_PROXY:代理收到 {[l.split()[1].rsplit("/", 1)[-1] for l, _ in px.reqs]};源站直接收到 {og.log}')
with Proxy() as px:
    og, E, out, st = run(px, BODY2, env={'http_proxy': f'http://127.0.0.1:{px.port}'}, settings={'HTTPPROXY_ENABLED': 0})
    print(f'  HTTPPROXY_ENABLED=0:代理收到 {[l.split()[1].rsplit("/", 1)[-1] for l, _ in px.reqs]};源站直接收到 {og.log}')

print('== 三:https 请求经代理:先发 CONNECT host:443(带 Proxy-Authorization),代理回 200 后才在隧道里握手 TLS——这里的假代理握手后直接关闭,所以请求失败,能看到 CONNECT 的内容')
with Proxy() as px:
    og, E, out, st = run(px, """
    async def start(self): yield scrapy.Request('https://secure.example.test/page', meta={'proxy': 'http://alice:s3cret@127.0.0.1:@PX@'}, callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback')
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__module__ + '.' + type(failure.value).__name__, msg=str(failure.value)[:80])
""")
    for line, h in px.reqs:
        auth = h.get('Proxy-Authorization'); dec = base64.b64decode(auth.split()[1]).decode() if auth else None
        print(f'  代理收到:{line};Host={hdr(h, "Host")};Proxy-Authorization 解码={dec!r};Proxy-Connection={hdr(h, "Proxy-Connection")}')
    print(f'  回调/errback:{E}')

print('== 四:代理返回 407 Proxy Authentication Required(http 请求)')
with Proxy('407') as px:
    og, E, out, st = run(px, """
    async def start(self): yield scrapy.Request('@O@/x', meta={'proxy': 'http://127.0.0.1:@PX@'}, callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback', status=response.status)
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__name__, status=getattr(getattr(failure.value, 'response', None), 'status', None))
""")
    print(f'  事件 {[{k: v for k, v in x.items() if k != "t"} for x in E]};代理收到 {len(px.reqs)} 次;源站收到 {og.log}')
