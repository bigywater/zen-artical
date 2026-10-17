import sys, os, socket, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s42'); reset_s()
def raw_server(mode):
    n = [0]
    def fn(conn, addr):
        data = read_request(conn)
        if not data: return
        n[0] += 1
        if mode == 'empty': return                                # 收到请求后直接关闭,不回任何字节
        if mode == 'truncated': conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 100\r\n\r\n<html>only 10'); return   # 声明 100 字节,只发 15 字节就关闭
        if mode == 'badchunk': conn.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: text/html\r\n\r\nZZZ\r\nnot-a-hex-size\r\n'); return
        if mode == 'garbage': conn.sendall(b'this is not http\r\n\r\n'); return
        if mode == 'big': conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5000\r\n\r\n' + b'x' * 5000); return
        if mode == 'slow': time.sleep(2); return
    srv = RawSrv(fn); srv.n = n; return srv
def classify(url, settings=None, tag='s42'):
    d = sdir(tag)
    code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('{url}', callback=self.cb, errback=self.eb)
    def cb(self, response): EV(who='callback', status=response.status, n=len(response.body))
    def eb(self, failure):
        v = failure.value
        EV(who='errback', type=failure.type.__module__ + '.' + failure.type.__name__, msg=str(v)[:90], has_response=getattr(v, 'response', None) is not None)
"""
    rc, out, t = runspider(d, code, dict({'LOG_LEVEL': 'ERROR', 'RETRY_ENABLED': 0, 'DOWNLOAD_TIMEOUT': 1}, **(settings or {})))
    return ev(d), out

print('== 一:各种故障,errback 里 failure.type / failure.value 是什么(关了重试,DOWNLOAD_TIMEOUT=1)')
class Plain:
    def __call__(self, h):
        if h.path == '/500': h.reply(500, 'e', {'Content-Type': 'text/plain'})
        elif h.path == '/404': h.reply(404, 'n', {'Content-Type': 'text/plain'})
        else: h.reply(200, '<html>ok</html>', {'Content-Type': 'text/html'})
rows = []
with Srv(Plain()) as s:
    rows.append(('服务器返回 500', *classify(s.url('/500'))))
    rows.append(('服务器返回 404', *classify(s.url('/404'))))
rows.append(('连接被拒(127.0.0.1:1)', *classify('http://127.0.0.1:1/x')))
rows.append(('DNS 解析失败(.invalid)', *classify('http://no-such-host.invalid/x')))
for mode, tag in (('slow', '读取超时(服务器睡 2 s,超时 1 s)'), ('empty', '收到请求后直接关闭连接'), ('truncated', '声明 Content-Length: 100 只发 15 字节就关闭'), ('badchunk', '分块编码的块大小不是十六进制'), ('garbage', '回的根本不是 HTTP'), ('big', '正文 5000 字节,DOWNLOAD_MAXSIZE=1000')):
    r = raw_server(mode)
    with r:
        st = {'DOWNLOAD_MAXSIZE': 1000} if mode == 'big' else {}
        rows.append((tag, *classify(f'http://127.0.0.1:{r.port}/x', st)))
with Srv(Plain()) as s:
    rows.append(('https 请求打到明文 http 端口', *classify(f'https://127.0.0.1:{s.port}/x')))
rows.append(('URL 缺少协议', None, ''))
for tag, E, out in rows:
    if E is None: continue
    x = E[0] if E else {}
    if x.get('who') == 'errback': print(f'  {tag:<36}{x["type"]:<48}{"带 response " if x["has_response"] else "无 response "}{x["msg"] or "(空消息)"}')
    elif x: print(f'  {tag:<36}回调被调用(status={x["status"]}, {x["n"]} 字节)')
    else: print(f'  {tag:<36}回调和 errback 都没被调用;日志:{[l.strip()[:90] for l in out.split(chr(10)) if "ERROR" in l][:1]}')
try:
    import scrapy_unused  # noqa
except Exception: pass
rc, out, t = py(sdir('s42x'), "import scrapy\ntry: scrapy.Request('bar')\nexcept Exception as e: print('  URL 缺少协议(Request(\"bar\")):构造时就抛', type(e).__name__ + ': ' + str(e))")
print(out)

print('== 二:Failure 对象怎么用:failure.type、failure.value、failure.check(…)、failure.request、failure.value.response、failure.getErrorMessage()、getTraceback')
d = sdir('s42b')
with Srv(Plain()) as s:
    code = f"""
import scrapy
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.exceptions import DownloadTimeoutError, DownloadConnectionRefusedError
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for u in ('{s.url("/500")}', 'http://127.0.0.1:1/x'): yield scrapy.Request(u, errback=self.eb)
    def eb(self, failure):
        EV(url=failure.request.url.rsplit('/', 1)[-1], check_HttpError=bool(failure.check(HttpError)), check_refused=bool(failure.check(DownloadConnectionRefusedError)), check_either=str(failure.check(HttpError, DownloadConnectionRefusedError).__name__),
           status=failure.value.response.status if failure.check(HttpError) else None, errmsg=failure.getErrorMessage()[:60], tb_last=failure.getTraceback().strip().split(chr(10))[-1][:80], tb_lines=len(failure.getTraceback().strip().split(chr(10))), cause=type(failure.value.__cause__).__name__)
"""
    rc, out, t = runspider(d, code, {'LOG_LEVEL': 'ERROR', 'RETRY_ENABLED': 0})
for x in ev(d): print(f"  {x['url']:<5}check(HttpError)={x['check_HttpError']};check(DownloadConnectionRefusedError)={x['check_refused']};check(两者)→{x['check_either']};failure.value.response.status={x['status']}\n       getErrorMessage()={x['errmsg']!r};getTraceback() 共 {x['tb_lines']} 行,最后一行 {x['tb_last']!r};value.__cause__ 的类型 {x['cause']}")

print('== 三:errback 的返回值怎么处理:None(吞掉)、返回/产出 item、返回 Request(重新调度)、不定义 errback(默认日志)、errback 自己抛异常')
BODY = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://127.0.0.1:1/x', callback=self.cb, errback=self.eb, dont_filter=True)
    def cb(self, response): pass
    def parse(self, response): EV(who='retry callback', url=response.url)
@@
"""
for tag, eb in (('return None(什么都不做)', "    def eb(self, failure): pass"), ('yield 一个 item', "    def eb(self, failure):\n        yield {'failed': failure.request.url}"), ('返回一个新 Request(换个地址)', "    def eb(self, failure):\n        return scrapy.Request('@U@/ok', callback=self.parse)"), ('不定义 errback', None), ('errback 自己抛异常', "    def eb(self, failure): raise ValueError('errback boom')")):
    d = sdir('s42c')
    with Srv(Plain()) as s:
        code = BODY.replace('@@', eb or '').replace('@U@', s.url('').rstrip('/'))
        if eb is None: code = code.replace(', errback=self.eb', '')
        class PItem: pass
        code = "class P:\n    def process_item(self, item): EV(who='item', item=item); return item\n" + code.replace("name = 's'", "name = 's'\n    custom_settings = {'ITEM_PIPELINES': {P: 1}, 'RETRY_ENABLED': False}")
        rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO'})
    st = stats(out)
    E = ev(d)
    errs = [l.split('] ', 1)[1].strip()[:90] for l in out.split('\n') if '] ERROR' in l]
    print(f'  {tag:<26}事件 {[{k: v for k, v in x.items() if k != "t"} for x in E]};ERROR 日志 {errs[:1]};stats downloader/exception_count={st.get("downloader/exception_count")}, spider_exceptions={st.get("spider_exceptions/count", 0)}')
