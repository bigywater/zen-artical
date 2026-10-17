import sys, os, collections, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s45'); reset_s()
class Back:
    def __init__(self, delay=0.0): self.delay = delay; self.log = []; self.lock = threading.Lock(); self.cur = 0; self.peak = 0
    def __call__(self, h):
        with self.lock: self.cur += 1; self.peak = max(self.peak, self.cur)
        if self.delay and h.path != '/seed': time.sleep(self.delay)
        h.reply(200, '<html>' + h.path + '</html>', {'Content-Type': 'text/html'})
        with self.lock: self.cur -= 1
H2 = {'https': 'scrapy.core.downloader.handlers.http2.H2DownloadHandler'}
def go(nx_url, n, settings=None, tag='s45', code_extra=''):
    d = sdir(tag)
    code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{nx_url}/seed')
    def parse(self, response):
        if response.url.endswith('/seed'):
            EV(e='seed', protocol=response.protocol, ip=str(response.ip_address), cert=type(response.certificate).__name__)
            for i in range({n}): yield scrapy.Request('{nx_url}/p%d' % i, callback=self.sub)
    def sub(self, response): pass
{code_extra}
"""
    rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 20, 'CONCURRENT_REQUESTS_PER_DOMAIN': 20}, **(settings or {})))
    return ev(d), out, stats(out)
def conns(nx):
    ent = [e for e in nx.entries() if '/p' in e[4]]
    ids = collections.Counter(e[0] for e in ent)
    return len(ids), max(ids.values()) if ids else 0, collections.Counter(e[2] for e in nx.entries()), collections.Counter(e[3] for e in nx.entries())

print('== 一:同样的 41 个 https 请求(并发 20),HTTP/1.1 处理器 vs H2DownloadHandler:nginx 访问日志里的连接数、协议、TLS 版本')
back = Back(); d0 = pdir('s45nx'); cert, key = make_cert(d0)
with Srv(back) as s:
    for tag, st in (('默认 HTTP11DownloadHandler', {}), ('H2DownloadHandler', {'DOWNLOAD_HANDLERS': json.dumps(H2)})):
        with Nginx('s45' + str(abs(hash(tag)) % 100), s.port, cert, key) as nx:
            E, out, stt = go(nx.url('').rstrip('/'), 40, st)
            nc, mx, protos, tls = conns(nx)
            seed = [e for e in E if e.get('e') == 'seed'][0]
            print(f'  {tag}:nginx 记录的连接数 {nc}(其中一条连接上最多 {mx} 个请求);协议 {dict(protos)};TLS {dict(tls)};response.protocol={seed["protocol"]}、ip_address={seed["ip"]}、certificate 类型={seed["cert"]};总耗时 {stt["elapsed_time_seconds"]:.2f} s')

print('== 二:证书校验:DOWNLOAD_VERIFY_CERTIFICATES 默认值,以及自签名证书在 False / True 下的结果')
r = subprocess.run([SPY, '-c', 'from scrapy.settings import default_settings as d; print(d.DOWNLOAD_VERIFY_CERTIFICATES)'], capture_output=True, text=True).stdout.strip()
print(f'  DOWNLOAD_VERIFY_CERTIFICATES 默认 = {r}')
with Srv(back) as s, Nginx('s45v', s.port, cert, key) as nx:
    for tag, st in (('默认(不校验)', {}), ('DOWNLOAD_VERIFY_CERTIFICATES=True', {'DOWNLOAD_VERIFY_CERTIFICATES': 'True'})):
        d = sdir('s45b')
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{nx.url("/x")}', callback=self.cb, errback=self.eb)
    def cb(self, r): EV(who='callback', status=r.status)
    def eb(self, f): EV(who='errback', exc=type(f.value).__name__, msg=str(f.value)[:100])
"""
        rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'ERROR', 'RETRY_ENABLED': 0}, **st))
        print(f'  {tag}:{[{k: v for k, v in x.items() if k != "t"} for x in ev(d)]}')

print('== 三:最大并发流:nginx http2_max_concurrent_streams=4 时,Scrapy 想同时发 20 个(服务器每个 0.3 s)——后端看到的并发峰值与总耗时')
back2 = Back(0.3)
with Srv(back2) as s:
    for tag, streams, st in (('H2 + 流上限 128', 128, {'DOWNLOAD_HANDLERS': json.dumps(H2)}), ('H2 + 流上限 4', 4, {'DOWNLOAD_HANDLERS': json.dumps(H2)}), ('HTTP11 + nginx 流上限 4(对 1.1 无影响)', 4, {})):
        back2.peak = 0
        with Nginx('s45s' + str(streams) + str(len(tag)), s.port, cert, key, streams=streams) as nx:
            E, out, stt = go(nx.url('').rstrip('/'), 40, st)
            nc, mx, protos, tls = conns(nx)
            print(f'  {tag}:后端并发峰值 {back2.peak};nginx 连接数 {nc};总耗时 {stt["elapsed_time_seconds"]:.2f} s(40 个请求 × 0.3 s ÷ 并发)')

print('== 四:H2 处理器不支持代理:给 https 请求设 meta proxy 会怎样')
with Srv(back) as s, Nginx('s45p', s.port, cert, key) as nx:
    d = sdir('s45d')
    code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{nx.url("/x")}', meta={{'proxy': 'http://127.0.0.1:1'}}, callback=self.cb, errback=self.eb)
    def cb(self, r): EV(who='callback', status=r.status, protocol=r.protocol)
    def eb(self, f): EV(who='errback', exc=type(f.value).__name__, msg=str(f.value)[:100])
"""
    rc, out, t = runspider(d, code, {'LOG_LEVEL': 'ERROR', 'RETRY_ENABLED': 0, 'DOWNLOAD_HANDLERS': json.dumps(H2)})
    print(f'  H2 处理器 + meta proxy:{[{k: v for k, v in x.items() if k != "t"} for x in ev(d)]}')
