import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s25'); reset_s()
class Tree:
    """二叉树站点:/t<编号>,节点 n 的子节点是 2n+1、2n+2,深度由编号决定;深度到 MAXD 的节点没有子节点。/red 重定向到 /t0。"""
    MAXD = 5
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path)
        p = h.path.split('?')[0]
        if p == '/red': h.reply(302, b'', {'Location': '/leaf'}); return
        if p.startswith('/t'):
            n = int(p[2:]); d = (n + 1).bit_length() - 1
            kids = [2 * n + 1, 2 * n + 2] if d < self.MAXD else []
            h.reply(200, '<html>' + ''.join(f'<a href="/t{k}">k</a>' for k in kids) + '</html>', {'Content-Type': 'text/html'}); return
        h.reply(200, '<html>' + (f'<a href="{p}x">x</a>' if len(p) < 6 else '') + '</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s25', sv=None):
    d = sdir(tag); sv = sv or Tree()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'DEBUG', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)
TREE = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/t0')
    def parse(self, response):
        EV(p=response.url.rsplit('/', 1)[-1], depth=response.meta.get('depth'))
        for u in response.css('a::attr(href)').getall(): yield response.follow(u)
"""
def depth_of(p): n = int(p.split('t')[-1]); return (n + 1).bit_length() - 1

print('== 一:DEPTH_LIMIT 限制的是“从起始请求数起的跳数”:二叉树站点(第 d 层有 2^d 个页面,共 6 层),DEPTH_LIMIT = 0(不限)、1、2、3、4')
print(f'  {"DEPTH_LIMIT":>12}{"服务器收到":>10}{"request_depth_max":>19}  各层请求数(层 0、1、2…)')
for lim in (0, 1, 2, 3, 4):
    sv, E, out, st = go(TREE, {'DEPTH_LIMIT': lim, 'DEPTH_STATS_VERBOSE': 1})
    per = [st.get(f'request_depth_count/{i}', 0) for i in range(7)]
    print(f'  {lim:>12}{len(sv.log):>10}{st.get("request_depth_max"):>19}  {[x for x in per if x] or per[:1]}')
sv, E, out, st = go(TREE, {'DEPTH_LIMIT': 2})
print('  DEPTH_LIMIT=2 的日志:' + ' | '.join(l.strip()[:90] for l in out.split('\n') if 'Ignoring link (depth' in l))
print('  response.meta["depth"] 与页面所在层(DEPTH_LIMIT=2):' + ', '.join(f'{x["p"]}:{x["depth"]}' for x in E[:7]) + ' …')

print('== 二:DEPTH_PRIORITY 把请求优先级减去 深度×DEPTH_PRIORITY:并发 1 时服务器收到页面的“层号序列”(默认后进先出 → 深度优先)')
for tag, stt in (('默认(DEPTH_PRIORITY = 0)', {}), ('DEPTH_PRIORITY = 1', {'DEPTH_PRIORITY': 1}), ('DEPTH_PRIORITY = 1 + FIFO 队列', {'DEPTH_PRIORITY': 1, 'SCHEDULER_DISK_QUEUE': 'scrapy.squeues.PickleFifoDiskQueue', 'SCHEDULER_MEMORY_QUEUE': 'scrapy.squeues.FifoMemoryQueue'}), ('DEPTH_PRIORITY = -1(深度越深优先级越高)', {'DEPTH_PRIORITY': -1})):
    sv, E, out, st = go(TREE.replace("response.follow(u)", "response.follow(u)"), dict({'DEPTH_LIMIT': 3}, **stt))
    seq = [depth_of(p) for p in sv.log]
    print(f'  {tag:<36}{"".join(str(x) for x in seq)}  (共 {len(seq)} 个页面,每个字符是该页面所在层)')

print('== 三:depth 是怎么传的:重定向沿用同一个深度;depth_reset 归零;不能用 meta 在回调里手动指定(会被覆盖)')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/t0')
    def parse(self, response):
        EV(p=response.url.rsplit('/', 1)[-1], depth=response.meta.get('depth'), reasons=response.meta.get('redirect_reasons'))
        if response.url.endswith('/t0'):
            yield response.follow('/t1')                                         # 深度 1
            yield response.follow('/red')                                        # 深度 1,再被重定向到 /leaf(仍是深度 1)
            yield response.follow('/t2', meta={'depth_reset': True})             # 深度重置为 0
            yield response.follow('/t3', meta={'depth': 50})                     # 想手动指定 50:会被覆盖
""", {'DEPTH_LIMIT': 1})
for x in sorted(E, key=lambda x: x['p']): print(f'  {x["p"]:<8}response.meta["depth"] = {x["depth"]}' + (f'(redirect_reasons={x["reasons"]})' if x['reasons'] else ''))
print(f'  服务器收到:{sv.log}')

print('== 四:起始请求本身带 depth:start() 里 Request(meta={"depth": 3}) 不会被改写——它的子请求从 4 开始数')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/t0', meta={'depth': 3})
    def parse(self, response):
        EV(p=response.url.rsplit('/', 1)[-1], depth=response.meta.get('depth'))
        if response.url.endswith('/t0'): yield response.follow('/t1')
""", {'DEPTH_LIMIT': 4})
for x in E: print(f'  {x["p"]}: depth = {x["depth"]}')
sv, E, out, st = go("""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        yield scrapy.Request('@U@/t0', meta={'depth': 3})
    def parse(self, response):
        EV(p=response.url.rsplit('/', 1)[-1], depth=response.meta.get('depth'))
        if response.url.endswith('/t0'): yield response.follow('/t1')
""", {'DEPTH_LIMIT': 3})
print(f'  同样的代码,DEPTH_LIMIT=3:回调被调用的页面 {[x["p"] for x in E]}(子请求深度 4 > 3 被丢弃)')

print('== 五:换了域名要不要重新数:depth_reset 让跨域名的链接从 0 开始,不被 DEPTH_LIMIT 误伤(链:127.0.0.1 上的 /t0 → localhost 上的 /t1 → /t3,DEPTH_LIMIT = 1)')
for tag, meta in (('不加 depth_reset', ''), ('跨域链接加 depth_reset', ", meta={'depth_reset': True}")):
    d = sdir('s25e'); sv = Tree()
    with Srv(sv) as s:
        code = f"""
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://127.0.0.1:{s.port}/t0')
    def parse(self, response):
        EV(p=response.url.split('{s.port}')[-1], host=response.url.split('//')[1].split(':')[0], depth=response.meta.get('depth'))
        if response.url.endswith('/t0'): yield scrapy.Request('http://localhost:{s.port}/t1'{meta}, callback=self.parse)
        elif response.url.endswith('/t1'): yield response.follow('/t3')
"""
        rc, out, t = runspider(d, code, {'LOG_LEVEL': 'INFO', 'DEPTH_LIMIT': 1, 'CONCURRENT_REQUESTS': 1})
    print(f'  {tag}:回调被调用 {[(x["host"][0], x["p"], x["depth"]) for x in ev(d)]}(h=127.0.0.1/localhost 首字母)')
