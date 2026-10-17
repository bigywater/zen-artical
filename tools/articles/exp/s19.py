import sys, os, socket, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s19'); reset_s()
r = subprocess.run([SPY, '-c', 'from scrapy.settings import default_settings as d; print(d.RETRY_ENABLED, d.RETRY_TIMES, d.RETRY_HTTP_CODES, d.RETRY_PRIORITY_ADJUST, d.RETRY_GIVE_UP_LOG_LEVEL); print(d.RETRY_EXCEPTIONS)'], capture_output=True, text=True)
a, b = r.stdout.strip().split('\n')
print('== 一:默认值')
print('  RETRY_ENABLED / RETRY_TIMES / RETRY_HTTP_CODES / RETRY_PRIORITY_ADJUST / RETRY_GIVE_UP_LOG_LEVEL = ' + a)
print('  RETRY_EXCEPTIONS = ' + b)

class Srv2:
    """按路径返回状态码的服务器,记录每个路径的请求次数和到达时间。"""
    def __init__(self): self.log = []; self.lock = threading.Lock()
    def __call__(self, h):
        with self.lock: self.log.append((h.path, time.perf_counter()))
        p = h.path.split('?')[0].strip('/')
        if p.isdigit(): h.reply(int(p), 'x', {'Content-Type': 'text/html'}); return
        if p == 'slow': time.sleep(2); h.reply(200, 'late'); return
        if p == 'ok': h.reply(200, '<html>ok</html>', {'Content-Type': 'text/html'}); return
        if p == 'empty': h.reply(200, '', {'Content-Type': 'text/html'}); return
        h.reply(200, 'x', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s19', srv=None):
    d = sdir(tag); sv = srv or Srv2()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')).replace('@P@', str(s.port)), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)

print('== 二:每种状态码下,服务器收到几次请求(一个请求,服务器永远返回该状态码);回调/errback 谁被调用;stats')
SP = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/CODE', callback=self.ok, errback=self.err)
    def ok(self, response): EV(who='callback', status=response.status)
    def err(self, failure): EV(who='errback', exc=type(failure.value).__name__)
"""
print(f'  {"状态码":<8}{"服务器收到":>10}{"retry/count":>12}{"max_reached":>12}  谁被调用')
for code in (500, 502, 503, 504, 522, 524, 408, 429, 404, 403, 400, 301):
    sv, E, out, st = go(SP.replace('CODE', str(code)), {'REDIRECT_ENABLED': 0})
    print(f'  {code:<8}{len(sv.log):>10}{st.get("retry/count", 0):>12}{st.get("retry/max_reached", 0):>12}  {E[0]["who"] if E else "-"}' + (f'({E[0].get("exc", E[0].get("status"))})' if E else ''))
print('  重试之间的间隔(500 的三次请求到达时间差):', end='')
sv, E, out, st = go(SP.replace('CODE', '500'))
ts = [t for _, t in sv.log]; print(' '.join(f'{(b - a) * 1000:.0f} ms' for a, b in zip(ts, ts[1:])) + '(没有退避)')
print('  stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith('retry/')))
print('  日志:' + ' | '.join(l.strip()[:110] for l in out.split('\n') if 'Gave up' in l))

print('== 三:异常:连接被拒、读取超时(服务器睡 2 s,DOWNLOAD_TIMEOUT=0.5)、服务器收到请求后直接断开、DNS 失败——各重试几次')
class Hang:
    """原始套接字服务器:读到请求后直接关闭连接(不返回任何字节)。"""
    def __init__(self):
        self.n = 0; self.s = socket.socket(); self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); self.s.bind(('127.0.0.1', 0)); self.s.listen(16); self.port = self.s.getsockname()[1]
        threading.Thread(target=self.loop, daemon=True).start()
    def loop(self):
        while True:
            c, _ = self.s.accept(); self.n += 1
            try: c.recv(4096)
            except Exception: pass
            c.close()
hang = Hang()
SP3 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'DOWNLOAD_TIMEOUT': 0.5}
    async def start(self): yield scrapy.Request('URL', callback=self.ok, errback=self.err)
    def ok(self, response): EV(who='callback')
    def err(self, failure): EV(who='errback', exc=type(failure.value).__module__ + '.' + type(failure.value).__name__)
"""
print(f'  {"情形":<22}{"重试次数":>8}  {"errback 里的异常类型"}')
for tag, url, srvobj in (('连接被拒', 'http://127.0.0.1:1/x', None), ('读取超时', '@U@/slow', None), ('收到请求后断开连接', f'http://127.0.0.1:{hang.port}/x', hang), ('DNS 失败', 'http://no-such-host.invalid/x', None)):
    sv, E, out, st = go(SP3.replace('URL', url))
    cnt = (hang.n if srvobj else len([1 for p, _ in sv.log if p == '/slow']) if tag == '读取超时' else None)
    print(f'  {tag:<22}{st.get("retry/count", 0):>8}  {E[0].get("exc") if E else "-"}' + (f'  (服务器收到 {cnt} 次)' if cnt is not None else ''))
    if tag == '收到请求后断开连接': hang.n = 0
    rs = {k.replace("retry/reason_count/", ""): v for k, v in st.items() if k.startswith("retry/reason_count/")}
    if rs: print(f'      retry/reason_count: {rs}')

print('== 四:用 meta 控制单个请求:dont_retry、max_retry_times、priority_adjust(500,服务器收到几次)')
SP4 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/500?tag=default', errback=self.err)
        yield scrapy.Request('@U@/500?tag=dont', meta={'dont_retry': True}, errback=self.err)
        yield scrapy.Request('@U@/500?tag=five', meta={'max_retry_times': 5}, errback=self.err)
        yield scrapy.Request('@U@/500?tag=zero', meta={'max_retry_times': 0}, errback=self.err)
    def err(self, failure): pass
"""
sv, E, out, st = go(SP4)
from collections import Counter
c = Counter(p.split('tag=')[-1] for p, _ in sv.log)
print('  各请求被服务器收到的次数:' + ', '.join(f'{k}={c.get(k, 0)}' for k in ('default', 'dont', 'five', 'zero')) + '(路径里 /500?tag=… 带了 query 所以按 query 统计)')

print('== 五:重试请求优先级 −1 并放回调度器重排,dont_filter=True;并发 1 时服务器收到的顺序(a 返回 500,b、c、d 正常)')
class Mix:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path)
        if h.path == '/a': h.reply(500, 'x', {'Content-Type': 'text/html'})
        else: h.reply(200, '<html>ok</html>', {'Content-Type': 'text/html'})
SP5 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        for p in ('a', 'b', 'c', 'd'): yield scrapy.Request('@U@/' + p, errback=self.err)
    def err(self, failure): pass
    def parse(self, response): pass
"""
for tag, stt in (('默认 RETRY_PRIORITY_ADJUST = -1', {}), ('RETRY_PRIORITY_ADJUST = +10', {'RETRY_PRIORITY_ADJUST': 10})):
    sv, E, out, st = go(SP5, stt, srv=Mix())
    print(f'  {tag}:服务器收到的顺序 {" ".join(p[1:] for p in sv.log)}')

print('== 六:在回调里手动重试:200 但内容为空——get_retry_request(response.request, spider=self, reason="empty")')
SP6 = """
import scrapy
from scrapy.downloadermiddlewares.retry import get_retry_request
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/empty')
    def parse(self, response):
        if not response.body:
            r = get_retry_request(response.request, spider=self, reason='empty')
            EV(e='retry' if r else '放弃', retry_times=response.request.meta.get('retry_times', 0), new_priority=getattr(r, 'priority', None), dont_filter=getattr(r, 'dont_filter', None))
            return r
"""
sv, E, out, st = go(SP6)
for x in E: print(f'  {x}')
print(f'  服务器收到 {len(sv.log)} 次;stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith('retry/')))
print('  日志:' + ' | '.join(l.strip()[:120] for l in out.split('\n') if 'Gave up' in l))
