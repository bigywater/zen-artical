import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s11'); reset_s()
def srv(h):
    if h.path == '/gz': h.reply(200, gz(b'<html>' + b'compressible ' * 200 + b'</html>'), {'Content-Type': 'text/html', 'Content-Encoding': 'gzip'})
    else: h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s11'):
    d = sdir(tag)
    with Srv(srv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return s, ev(d), out, stats(out)

MWS = """
import scrapy
def mk(name, ret_req=None, ret_resp_in_req=False, resp_ret_request=False, exc_ret=None):
    calls = []
    class M:
        def process_request(self, request):
            EV(m=name, hook='process_request', url=request.url.rsplit('/', 1)[-1])
            if ret_resp_in_req: return scrapy.http.HtmlResponse(request.url, body=b'<html>from ' + name.encode() + b'</html>', request=request)
            if ret_req and request.url.endswith('/page'): return scrapy.Request(ret_req)
        def process_response(self, request, response):
            EV(m=name, hook='process_response', url=request.url.rsplit('/', 1)[-1], body=len(response.body))
            calls.append(1)
            if resp_ret_request and len(calls) == 1: return scrapy.Request('@U@/replaced', dont_filter=True)
            return response
        def process_exception(self, request, exception):
            EV(m=name, hook='process_exception', exc=type(exception).__name__)
            if exc_ret: return scrapy.http.HtmlResponse(request.url, body=b'rescued', request=request)
    M.__name__ = M.__qualname__ = 'M' + name
    return M
"""
CODE = MWS + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'DOWNLOADER_MIDDLEWARES': MW}
    async def start(self): yield scrapy.Request('@U@/page')
    def parse(self, response): EV(m='spider', hook='callback', url=response.url.rsplit('/', 1)[-1], body=response.text)
"""
def run(mw_expr, extra='', settings=None, body=None):
    code = (CODE if body is None else MWS + body).replace('MW', mw_expr)
    return go(code, settings)
def table(E, w=22):
    for i, x in enumerate(E, 1):
        extra = ' '.join(f'{k}={v}' for k, v in x.items() if k not in ('t', 'm', 'hook'))
        print(f'  {i:>2}. {x["m"]:<8}{x["hook"]:<20}{extra}')

print('== 一:process_request 按数字从小到大,process_response 反过来从大到小;中间件 A=100、B=300、C=550、D=750、E=900')
s, E, out, st = run("{mk('A'): 100, mk('B'): 300, mk('C'): 550, mk('D'): 750, mk('E'): 900}")
table(E)
print(f'  服务器收到 {len(s.log)} 个请求')
L = out.split(chr(10)); i = [k for k, l in enumerate(L) if 'Enabled downloader middlewares' in l][0]
names = []
for l in L[i + 1:i + 30]:
    end = l.strip().endswith(']')
    l = l.strip().lstrip('[').rstrip(']').rstrip(',')
    names.append(l.replace("'", '').replace("<class spider.M", '自定义 ').replace('>', ''))
    if end: break
names = [n.replace('scrapy.downloadermiddlewares.', '') for n in names]
print('  日志里 “Enabled downloader middlewares” 的顺序(就是 process_request 的调用顺序,process_response 反着来):')
for ln in textwrap.wrap(' → '.join(names), 96): print('    ' + ln)

print('== 二:同一个响应,放在 HttpCompressionMiddleware(590)两侧的中间件看到的 body 不一样(服务器发 gzip,解压后约 2.6 KB)')
S2 = MWS + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'DOWNLOADER_MIDDLEWARES': {mk('L585'): 585, mk('H595'): 595}}
    async def start(self): yield scrapy.Request('@U@/gz')
    def parse(self, response): EV(m='spider', hook='callback', body=len(response.body))
"""
s, E, out, st = go(S2)
table([x for x in E if x['hook'] != 'process_request'])
print('  → 响应方向先经过 595(离下载器近),再经过 590 解压,最后到 585:595 看到 gzip 压缩后的字节,585 看到解压后的')

print('== 三:process_request 里直接返回 Response(C=550):后面的 process_request 和真正的下载都跳过,但所有中间件的 process_response 仍然都会被调用')
s, E, out, st = run("{mk('A'): 100, mk('B'): 300, mk('C', ret_resp_in_req=True): 550, mk('D'): 750, mk('E'): 900}")
table(E)
print(f'  服务器收到 {len(s.log)} 个请求(没有真正去下载)')

print('== 四:process_request 里返回 Request(C=550):原请求作废,新请求回到调度器重新走一遍')
s, E, out, st = run("{mk('A'): 100, mk('C', ret_req='@U@/other'): 550, mk('E'): 900}")
table(E)
print(f'  服务器收到 {[l["path"] for l in s.log]};scheduler/enqueued={st.get("scheduler/enqueued")}')

print('== 五:process_response 里返回 Request(D=750):更靠近引擎的中间件(C、B、A)的 process_response 不再被调用')
s, E, out, st = run("{mk('A'): 100, mk('B'): 300, mk('C'): 550, mk('D', resp_ret_request=True): 750, mk('E'): 900}")
table(E)
print(f'  共 {len(E)} 个事件;服务器收到 {[l["path"] for l in s.log]}')

print('== 六:下载失败(连接被拒)时 process_exception 的顺序,以及 D 把异常“救”成一个 Response')
S6 = MWS + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'DOWNLOADER_MIDDLEWARES': MW, 'RETRY_ENABLED': False}
    async def start(self): yield scrapy.Request('http://127.0.0.1:1/x', errback=self.err)
    def parse(self, response): EV(m='spider', hook='callback', body=response.text)
    def err(self, failure): EV(m='spider', hook='errback', exc=type(failure.value).__name__)
"""
for tag, mw in (('没有谁处理异常', "{mk('A'): 100, mk('C'): 550, mk('E'): 900}"), ('D=750 在 process_exception 里返回 Response', "{mk('A'): 100, mk('C'): 550, mk('D', exc_ret=True): 750, mk('E'): 900}")):
    s, E, out, st = go(S6.replace('MW', mw))
    print(f'  {tag}:')
    table([x for x in E if x['hook'] != 'process_request'])
