import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s12'); reset_s()
def srv(h):
    if h.path == '/404': h.reply(404, 'nope', {'Content-Type': 'text/plain'})
    elif h.path == '/list': h.reply(200, '<html>' + ''.join(f'<a href="/i{i}">i{i}</a>' for i in range(4)) + '</html>', {'Content-Type': 'text/html'})
    else: h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s12'):
    d = sdir(tag)
    with Srv(srv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return s, ev(d), out, stats(out)
def table(E):
    for i, x in enumerate(E, 1):
        extra = ' '.join(f'{k}={v}' for k, v in x.items() if k not in ('t', 'm', 'hook'))
        print(f'  {i:>2}. {x["m"]:<8}{x["hook"]:<26}{extra}')

MW = """
import scrapy
def mk(name, inp_raise=False, out_filter=None, exc_recover=False):
    class M:
        async def process_start(self, start):
            EV(m=name, hook='process_start')
            async for x in start: yield x
        def process_spider_input(self, response):
            EV(m=name, hook='process_spider_input')
            if inp_raise: raise ValueError('input rejected by ' + name)
        async def process_spider_output(self, response, result):
            async for x in result:
                kind = 'Request ' + x.url.rsplit('/', 1)[-1] if isinstance(x, scrapy.Request) else 'item ' + str(dict(x))
                EV(m=name, hook='process_spider_output', what=kind)
                if out_filter and out_filter(x): EV(m=name, hook='  丢弃', what=kind); continue
                yield x
        def process_spider_exception(self, response, exception):
            EV(m=name, hook='process_spider_exception', exc=type(exception).__name__)
            if exc_recover: return [{'recovered_by': name}]
            return None
    M.__name__ = M.__qualname__ = 'M' + name
    return M
"""
SP = MW + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'SPIDER_MIDDLEWARES': SM}
    async def start(self): yield scrapy.Request('@U@/list', callback=self.parse)
    def parse(self, response):
        EV(m='spider', hook='callback', url=response.url.rsplit('/', 1)[-1])
        BODY
    def err(self, failure): EV(m='spider', hook='errback', exc=type(failure.value).__name__ + ': ' + str(failure.value))
"""
def run(sm, body="yield {'n': 1}; yield scrapy.Request('@U@/second', callback=self.parse2)", extra='', settings=None):
    code = SP.replace('SM', sm).replace('BODY', body) + "    def parse2(self, response): EV(m='spider', hook='callback', url=response.url.rsplit('/', 1)[-1])\n" + extra
    return go(code, settings)

r = subprocess.run([SPY, '-c', 'from scrapy.settings import default_settings as d; print(d.SPIDER_MIDDLEWARES_BASE)'], capture_output=True, text=True)
base = eval(r.stdout)
print('== 一:内置的 SPIDER_MIDDLEWARES_BASE(数字小的离引擎近),以及 A=100、B=300、C=950 三个自定义中间件的钩子调用顺序')
print('  ' + ' → '.join(f'{k.rsplit(".", 1)[-1]}({v})' for k, v in sorted(base.items(), key=lambda kv: kv[1])))
s, E, out, st = run("{mk('A'): 100, mk('B'): 300, mk('C'): 950}")
table(E)

print('== 二:process_spider_input 里抛异常(B):回调被跳过,直接进 errback;更靠近回调的 C 的 process_spider_input 也不会被调用,process_spider_exception 也不会被调用')
s, E, out, st = run("{mk('A'): 100, mk('B', inp_raise=True): 300, mk('C'): 950}", extra='')
code_err = None
d = None
# 这一节需要回调带 errback:单独写
SP2 = MW + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'SPIDER_MIDDLEWARES': {mk('A'): 100, mk('B', inp_raise=True): 300, mk('C'): 950}}
    async def start(self): yield scrapy.Request('@U@/list', callback=self.parse, errback=self.err)
    def parse(self, response): EV(m='spider', hook='callback')
    def err(self, failure): EV(m='spider', hook='errback', exc=type(failure.value).__name__ + ': ' + str(failure.value))
"""
s, E, out, st = go(SP2)
table(E)
print(f'  spider_exceptions/count={st.get("spider_exceptions/count", 0)}')

print('== 三:process_spider_output 过滤:丢掉 i1、i3 两个子页面的请求和 price < 0 的 item')
BODY3 = """
        for u in response.css('a::attr(href)').getall(): yield scrapy.Request(response.urljoin(u), callback=self.parse2)
        yield {'price': 5}
        yield {'price': -1}
"""
SP3 = MW.replace("if out_filter and out_filter(x):", "if isinstance(x, dict): x['seen_by_' + name] = True\n                if out_filter and out_filter(x):") + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'SPIDER_MIDDLEWARES': {mk('A', out_filter=lambda x: isinstance(x, scrapy.Request) and x.url.endswith(('i1', 'i3')) or (isinstance(x, dict) and x.get('price', 0) < 0)): 100}}
    async def start(self): yield scrapy.Request('@U@/list')
    def parse(self, response):
        for u in response.css('a::attr(href)').getall(): yield scrapy.Request(response.urljoin(u), callback=self.parse2)
        yield {'price': 5}
        yield {'price': -1}
    def parse2(self, response): EV(m='spider', hook='callback', url=response.url.rsplit('/', 1)[-1])
"""
s, E, out, st = go(SP3)
table(E)
print(f'  服务器收到 {[l["path"] for l in s.log]};item_scraped_count={st.get("item_scraped_count")}')

print('== 四:回调里抛异常:process_spider_exception 按“离回调近 → 离引擎近”的顺序调用,谁返回了可迭代对象谁就“救活”了这次输出,返回 None 表示不处理')
BODY4 = "yield {'n': 1}\n        raise RuntimeError('callback boom')"
for tag, sm in (('没有人恢复', "{mk('A'): 100, mk('B'): 300, mk('C'): 950}"), ("B(300)恢复:process_spider_exception 里返回 [{'recovered_by': 'B'}]", "{mk('A'): 100, mk('B', exc_recover=True): 300, mk('C'): 950}")):
    s, E, out, st = run(sm, body=BODY4)
    print(f'  {tag}:')
    table([x for x in E if x['hook'] not in ('process_start',)])
    print(f'      spider_exceptions/count={st.get("spider_exceptions/count", 0)};item_scraped_count={st.get("item_scraped_count", 0)}')

print('== 五:2.19 里 process_spider_output 必须是异步生成器(或另有 _async 版本):只写旧的同步版本会怎样')
SYNC = """
import scrapy
class Old:
    def process_spider_output(self, response, result, spider):
        for x in result: yield x
class New:
    def process_spider_output(self, response, result, spider):
        for x in result: yield x
    async def process_spider_output_async(self, response, result, spider):
        async for x in result: EV(what='async 版本被调用'); yield x
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'SPIDER_MIDDLEWARES': {CLS: 100}}
    async def start(self): yield scrapy.Request('@U@/list')
    def parse(self, response): yield {'n': 1}
"""
for cls in ('Old', 'New'):
    s, E, out, st = go(SYNC.replace('CLS', cls))
    err = [l for l in out.split('\n') if l.startswith('TypeError')]
    print(f'  只有同步版本的 {cls}:' if cls == 'Old' else f'  同步 + process_spider_output_async 的 {cls}:', (err[0][:210] if err else f'正常运行,item_scraped_count={st.get("item_scraped_count")},{E}'))

print('== 六:内置爬虫中间件的效果:HttpError 过滤非 2xx 响应、UrlLength 丢弃超长 URL')
S6 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/404')
        yield scrapy.Request('@U@/ok')
    def parse(self, response):
        EV(what='callback', url=response.url.rsplit('/', 1)[-1])
        if response.url.endswith('ok'): yield scrapy.Request('@U@/' + 'a' * 3000)
"""
s, E, out, st = go(S6)
print(f'  回调被调用的:{[x["url"] for x in E]};服务器收到 {[l["path"][:8] for l in s.log]}')
print('  stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith(('httperror', 'urllength', 'response_received', 'downloader/response_status_count'))))
for l in out.split('\n'):
    if 'Ignoring' in l: print('  日志:' + l.strip()[:160])
