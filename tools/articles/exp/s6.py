import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s6'); reset_s()
def srv(h):
    p = h.path
    if p == '/ok': h.reply(200, '<html>ok</html>', {'Content-Type': 'text/html'})
    elif p == '/404': h.reply(404, 'nope', {'Content-Type': 'text/plain'})
    elif p == '/500': h.reply(500, 'err', {'Content-Type': 'text/plain'})
    elif p == '/slow': time.sleep(3); h.reply(200, 'late')
    elif p == '/red': h.reply(302, b'', {'Location': '/ok'})
    elif p == '/flaky':
        n = sum(1 for l in h.server.srv.log if l['path'] == '/flaky')
        h.reply(503 if n <= 2 else 200, 'x', {'Content-Type': 'text/html'})
    else: h.reply(200, 'x', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s6'):
    d = sdir(tag)
    with Srv(srv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO', 'RETRY_TIMES': 2}, **(settings or {})))
    return s, ev(d), out, stats(out)

print('== 一:errback 什么时候被调用:200、404、500、连接被拒、超时、DNS 失败、重定向——每个请求谁先被调用(callback 还是 errback),errback 拿到的 Failure 是什么')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'DOWNLOAD_TIMEOUT': 1, 'RETRY_ENABLED': False}
    async def start(self):
        for tag, u in (('200', '@U@/ok'), ('404', '@U@/404'), ('500', '@U@/500'), ('超时(服务器睡 3 s)', '@U@/slow'), ('连接被拒', 'http://127.0.0.1:1/x'), ('DNS 失败', 'http://no-such-host.invalid/x'), ('302→200', '@U@/red')):
            yield scrapy.Request(u, callback=self.ok, errback=self.err, cb_kwargs={'tag': tag}, dont_filter=True)
    def ok(self, response, tag): EV(tag=tag, who='callback', info='status=%d' % response.status)
    def err(self, failure):
        v = failure.value
        EV(tag=failure.request.cb_kwargs['tag'], who='errback', info=type(v).__module__ + '.' + type(v).__name__ + (' status=%d' % v.response.status if hasattr(v, 'response') and v.response is not None else ''))
""")
order = ['200', '404', '500', '超时(服务器睡 3 s)', '连接被拒', 'DNS 失败', '302→200']
R = {x['tag']: x for x in E}
print(f'  {"请求":<20}{"谁被调用":<10}  信息')
for k in order: print(f'  {k:<20}{R[k]["who"]:<10}  {R[k]["info"]}')
print(f'  stats:downloader/exception_count={st.get("downloader/exception_count")};downloader/exception_type_count/*:{ {k.split("/")[-1]: v for k, v in st.items() if "exception_type_count" in k} }')

print('== 二:回调自己抛异常:errback 不会被调用(errback 只管下载阶段和 spider 中间件 input 阶段的错误)')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/ok', callback=self.ok, errback=self.err)
    def ok(self, response): EV(who='callback 开始'); raise ValueError('回调里出错了')
    def err(self, failure): EV(who='errback', info=repr(failure.value))
""")
print(f'  事件:{[x["who"] + (":" + x["info"] if "info" in x else "") for x in E]}')
print(f'  spider_exceptions/count={st.get("spider_exceptions/count")};spider_exceptions/ValueError={st.get("spider_exceptions/ValueError")};日志:{[l.strip()[:90] for l in out.split(chr(10)) if "Spider error processing" in l][:1]}')

print('== 三:传数据:cb_kwargs 变成回调的关键字参数,meta 是字典;经过重定向和重试后各自还在不在')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/red', callback=self.after, cb_kwargs={'a': 1, 'b': [2]}, meta={'m': 'x'})
        yield scrapy.Request('@U@/flaky', callback=self.after, cb_kwargs={'a': 1, 'b': [2]}, meta={'m': 'x'})
    def after(self, response, a, b):
        EV(url=response.url.rsplit('/', 1)[-1], a=a, b=b, m=response.meta.get('m'), meta_keys=sorted(response.meta), cb_kwargs_on_request=response.request.cb_kwargs)
""")
for x in E:
    print(f'  /{x["url"]}:回调收到 a={x["a"]} b={x["b"]},response.meta["m"]={x["m"]!r}')
    print(f'      response.meta 的全部键:{x["meta_keys"]}')
print(f'  重定向次数 redirect_count={st.get("response_status_count/302", st.get("downloader/response_status_count/302"))},重试 retry/count={st.get("retry/count")}')

print('== 四:cb_kwargs 和回调签名对不上:缺参数、多参数各自的结果')
for tag, kw, sig in (('缺少必需参数 b', "{'a': 1}", 'def cb(self, response, a, b): pass'), ('cb_kwargs 里多了回调不接受的 c', "{'a': 1, 'c': 3}", 'def cb(self, response, a): pass'), ('回调有 **kwargs 兜底', "{'a': 1, 'c': 3}", 'def cb(self, response, a, **kw): EV(ok=True, kw=kw)')):
    s, E, out, st = go(f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/ok', callback=self.cb, cb_kwargs={kw})
    {sig}
""")
    te = [l.strip() for l in out.split('\n') if l.startswith('TypeError')]
    print(f'  {tag}:spider_exceptions/count={st.get("spider_exceptions/count", 0)};' + (te[-1][:130] if te else f'回调正常执行,**kw 收到 {E[0]["kw"]}'))

print('== 五:response.follow / response.urljoin 不带 meta 和 cb_kwargs;Request.replace 和 copy 会带')
s, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/ok', callback=self.first, meta={'k': 'v'}, cb_kwargs={'c': 1})
    def first(self, response, c):
        r1 = response.follow('/a'); r2 = response.request.replace(url=response.urljoin('/b')); r3 = response.request.copy()
        EV(e='follow', meta=r1.meta, cb_kwargs=r1.cb_kwargs)
        EV(e='request.replace(url=…)', meta={k: (v if k == 'k' else '…') for k, v in r2.meta.items()}, cb_kwargs=r2.cb_kwargs)
        EV(e='request.copy()', meta={k: (v if k == 'k' else '…') for k, v in r3.meta.items()}, cb_kwargs=r3.cb_kwargs, same_meta_object=r3.meta is response.request.meta)
""")
for x in E: print(f'  {x["e"]:<24} meta={x["meta"]}  cb_kwargs={x["cb_kwargs"]}' + (f'  与原 meta 是同一个对象:{x["same_meta_object"]}' if 'same_meta_object' in x else ''))
