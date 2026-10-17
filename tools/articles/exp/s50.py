import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s50'); reset_s()
class Site:
    def __init__(self, delay=0.0): self.log = []; self.delay = delay
    def __call__(self, h):
        self.log.append(h.path)
        if self.delay and h.path != '/seed': time.sleep(self.delay)
        h.reply(200, f'<html>{h.path}</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s50', delay=0.0):
    d = sdir(tag); sv = Site(delay)
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return sv, ev(d), out, stats(out)

print('== 一:priority 可以填什么:整数、负数、超大整数、浮点数、布尔、字符串、None——能不能构造请求,调度器怎么排(种子页回调里一次产生一批,并发 1)')
VALS = [('0', '0'), ('5', '5'), ('-5', '-5'), ('10**30', '10**30'), ('2.5(浮点)', '2.5'), ('True', 'True'), ("'7'(字符串)", "'7'"), ('None', 'None')]
code = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed')
    def parse(self, response):
        if not response.url.endswith('/seed'): return
        for i, p in enumerate(PR):
            try: yield scrapy.Request('@U@/r%d' % i, priority=p)
            except Exception as e: EV(i=i, p=repr(p), exc=type(e).__name__ + ': ' + str(e)[:70])
""".replace('PR', '[' + ', '.join(v for _, v in VALS) + ']')
sv, E, out, st = go(code)
print('  构造时报错的:' + (str([{k: v for k, v in x.items() if k != "t"} for x in E]) if E else '(无)') + f';服务器收到的顺序(r<产生序号>):{[p[1:] for p in sv.log[1:]]};finish_reason={st["finish_reason"]};spider_exceptions={st.get("spider_exceptions/count", 0)}')
print('  对应关系:' + ', '.join(f'r{i}={t}' for i, (t, _) in enumerate(VALS)))
print('  日志里的错误:' + str([l.strip()[:120] for l in out.split(chr(10)) if '] ERROR' in l][:2]))

print('== 二:并发会破坏严格的优先级顺序:一个种子页的回调里一次产生 60 个随机优先级的请求,统计服务器收到的顺序里“低优先级先于高优先级”的逆序对数')
random.seed(7); PRS = [random.randint(0, 9) for _ in range(60)]
code2 = f"""
import scrapy
PR = {PRS!r}
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed')
    def parse(self, response):
        if response.url.endswith('/seed'):
            for i, p in enumerate(PR): yield scrapy.Request('@U@/r%d' % i, priority=p)
"""
def inversions(sv):
    order = [int(p[2:]) for p in sv.log[1:]]
    pr = [PRS[i] for i in order]
    return sum(1 for a in range(len(pr)) for b in range(a + 1, len(pr)) if pr[a] < pr[b])
print(f'  {"CONCURRENT_REQUESTS":>20}{"逆序对数":>10}   服务器收到的优先级序列(前 24 个)')
for c in (1, 4, 16, 60):
    sv, E, out, st = go(code2, {'CONCURRENT_REQUESTS': c, 'CONCURRENT_REQUESTS_PER_DOMAIN': c}, delay=0.05)
    order = [int(p[2:]) for p in sv.log[1:]]
    print(f'  {c:>20}{inversions(sv):>10}   {[PRS[i] for i in order][:24]}')

print('== 三:优先级只在“出队那一刻”比较队列里已有的请求:高优先级链(每个响应才产生下一个高优先级请求)和 10 个已排队的低优先级请求并发 1 时交替出现;如果高优先级请求一开始就全部排好队,则全部先于低优先级')
CH = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed', callback=self.seed)
    def seed(self, response):
        for i in range(10): yield scrapy.Request('@U@/low%d' % i, priority=0)
        yield scrapy.Request('@U@/hi0', priority=10, callback=self.hi)
    def hi(self, response):
        n = int(response.url.rsplit('hi', 1)[-1])
        if n < 9: yield scrapy.Request('@U@/hi%d' % (n + 1), priority=10, callback=self.hi)
"""
sv, E, out, st = go(CH)
print(f'  (a) 高优先级链(hi0 → hi1 → … → hi9,每个在上一个响应之后才产生):服务器收到 {[p[1:] for p in sv.log[1:]]}')
ALL = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed', callback=self.seed)
    def seed(self, response):
        for i in range(10): yield scrapy.Request('@U@/low%d' % i, priority=0)
        for i in range(10): yield scrapy.Request('@U@/hi%d' % i, priority=10)
"""
sv, E, out, st = go(ALL)
print(f'  (b) 10 个高优先级请求和 10 个低优先级请求同时排队:服务器收到 {[p[1:] for p in sv.log[1:]]}')
