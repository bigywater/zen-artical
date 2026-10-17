import sys, os, gzip, zlib, brotli; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
from compression import zstd
tee('s27'); reset_s()
TEXT = (b'<html><body>' + b'scrapy compression test line. ' * 400 + b'</body></html>')
def rawdeflate(b): c = zlib.compressobj(wbits=-15); return c.compress(b) + c.flush()
ENC = {'gzip': (gzip.compress(TEXT), 'gzip'), 'x-gzip': (gzip.compress(TEXT), 'x-gzip'), 'deflate(zlib 封装)': (zlib.compress(TEXT), 'deflate'), 'deflate(裸 deflate)': (rawdeflate(TEXT), 'deflate'), 'br': (brotli.compress(TEXT), 'br'), 'zstd': (zstd.compress(TEXT), 'zstd'),
       '叠加 gzip, br(先 gzip 再 br)': (brotli.compress(gzip.compress(TEXT)), 'gzip, br'), '不支持的 compress': (b'\x1f\x9dxxxxxxxx', 'compress'), '声称 gzip 其实没压缩': (TEXT, 'gzip'), '截断的 gzip': (gzip.compress(TEXT)[:60], 'gzip'), '无压缩': (TEXT, None)}
class Site:
    def __init__(self): self.log = []; self.big = None
    def __call__(self, h):
        self.log.append((h.path, dict(h.hdrs).get('Accept-Encoding')))
        k = h.path.split('?k=')[-1].replace('%20', ' ').replace('%28', '(').replace('%29', ')')
        from urllib.parse import unquote
        k = unquote(h.path.split('?k=')[-1])
        if k == 'BOMB': 
            body, e = self.big
            h.reply(200, body, {'Content-Type': 'text/html', 'Content-Encoding': e}); return
        body, e = ENC[k]
        hd = {'Content-Type': 'text/html'}
        if e: hd['Content-Encoding'] = e
        h.reply(200, body, hd)
def go(code, settings=None, tag='s27', sv=None):
    d = sdir(tag); sv = sv or Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return sv, ev(d), out, stats(out)
import urllib.parse as up
print(f'== 一:服务器按 Content-Encoding 压缩正文(原文 {len(TEXT):,} 字节),Scrapy 解压后回调拿到的 body、Content-Encoding 头、stats')
keys = list(ENC)
sv, E, out, st = go(f"""
import scrapy
KEYS = {keys!r}
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        import urllib.parse as up
        for k in KEYS: yield scrapy.Request('@U@/x?k=' + up.quote(k), callback=self.cb, errback=self.eb, cb_kwargs={{'k': k}}, dont_filter=True)
    def cb(self, response, k): EV(k=k, n=len(response.body), same=response.body == {TEXT!r}, ce=response.headers.get('Content-Encoding', b'').decode(), cls=type(response).__name__, raw_len=response.headers.get('Content-Length', b'').decode())
    def eb(self, failure, k=None): EV(k=failure.request.cb_kwargs['k'], err=type(failure.value).__name__ + ': ' + str(failure.value)[:60])
""")
print(f'  {"服务器的编码":<28}{"传输字节":>9}{"回调 body":>10}{"与原文相同":>10}  Content-Encoding 头(解压后)  响应类 / 错误')
order = {k: i for i, k in enumerate(keys)}
for x in sorted(E, key=lambda x: order[x['k']]):
    tb = len(ENC[x['k']][0])
    if 'err' in x: print(f'  {x["k"]:<28}{tb:>9}{"-":>10}{"-":>10}  {x["err"]}')
    else: print(f'  {x["k"]:<28}{tb:>9}{x["n"]:>10}{"是" if x["same"] else "否":>10}  {x["ce"] or "(无)":<24}{x["cls"]}')
print('  服务器看到的 Accept-Encoding:' + str(sorted({a for _, a in sv.log})))
print('  stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith('httpcompression')))
print('  警告:' + ' | '.join(l.strip()[:150] for l in out.split('\n') if 'cannot decode' in l))

print('== 二:“解压炸弹”:20 KB 的 gzip 解压成 20 MiB;DOWNLOAD_MAXSIZE 超过就丢弃响应,DOWNLOAD_WARNSIZE 超过只警告')
big = b'A' * (20 * 1024 * 1024)
bomb = gzip.compress(big, 9)
sv0 = Site(); sv0.big = (bomb, 'gzip')
print(f'  服务器发送 {len(bomb):,} 字节(gzip),解压后 {len(big):,} 字节')
for tag, stt in (('默认(MAXSIZE 1 GiB、WARNSIZE 32 MiB)', {}), ('DOWNLOAD_WARNSIZE = 10 MiB', {'DOWNLOAD_WARNSIZE': 10 * 1024 * 1024}), ('DOWNLOAD_MAXSIZE = 10 MiB', {'DOWNLOAD_MAXSIZE': 10 * 1024 * 1024})):
    sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/x?k=BOMB', callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback', n=len(response.body))
    def eb(self, failure): EV(who='errback', exc=type(failure.value).__name__ + ': ' + str(failure.value)[:70])
""", stt, sv=sv0)
    msgs = [l.strip()[:150] for l in out.split('\n') if ('Ignored response' in l or 'larger than' in l or 'download warning' in l)]
    print(f'  {tag}:{E[0]["who"] if E else "-"} {E[0].get("n", E[0].get("exc", "")) if E else ""};日志 {msgs[:1]};stats {({k: v for k, v in st.items() if k.startswith("httpcompression")})}')

print('== 三:HEAD 请求不解压;COMPRESSION_ENABLED = 0 时不发 Accept-Encoding,也不解压(服务器仍然压缩时回调拿到压缩字节)')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/x?k=gzip', method='HEAD', callback=self.cb)
    def cb(self, response): EV(n=len(response.body), ce=response.headers.get('Content-Encoding', b'').decode())
""")
print(f'  HEAD /x?k=gzip:回调 {E}')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/x?k=gzip', callback=self.cb)
    def cb(self, response): EV(n=len(response.body), ce=response.headers.get('Content-Encoding', b'').decode(), magic=response.body[:2].hex())
""", {'COMPRESSION_ENABLED': 0})
print(f'  COMPRESSION_ENABLED = 0:服务器看到的 Accept-Encoding = {sv.log[0][1]};服务器仍发了 gzip,回调拿到 {E[0]["n"]} 字节(开头 {E[0]["magic"]} = gzip 魔数 1f8b),Content-Encoding = {E[0]["ce"]}')
