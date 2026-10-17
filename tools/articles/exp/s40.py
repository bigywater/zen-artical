import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s40'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path)
        if h.path.startswith('/fail'): h.reply(500, 'x', {'Content-Type': 'text/plain'}); return
        h.reply(200, f'<html>{h.path}</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s40'):
    d = sdir(tag); sv = Site()
    with Srv(sv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return sv, ev(d), out, stats(out)
HEAD = """
import scrapy, asyncio
class P:
    def process_item(self, item): EV(e='pipeline', item=item); return item
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'ITEM_PIPELINES': {P: 1}}
    async def start(self): yield scrapy.Request('@U@/x', callback=self.cb)
"""
print('== 一:回调的各种写法,返回/产出的东西怎么处理(pipeline 看到的 item、新请求是否被调度)')
FORMS = [
 ('def,return 一个 dict', "    def cb(self, response): return {'k': 1}"),
 ('def,return 列表 [dict, Request]', "    def cb(self, response): return [{'k': 2}, scrapy.Request(response.urljoin('/y'), callback=self.cb2)]"),
 ('def 生成器,yield', "    def cb(self, response):\n        yield {'k': 3}"),
 ('async def,return 一个 dict', "    async def cb(self, response): return {'k': 4}"),
 ('async def,return 列表', "    async def cb(self, response): return [{'k': 5}, {'k': 6}]"),
 ('async def,await 之后 return', "    async def cb(self, response):\n        await asyncio.sleep(0.05); return {'k': 7}"),
 ('async def 异步生成器,yield', "    async def cb(self, response):\n        yield {'k': 8}\n        yield {'k': 9}"),
 ('async def,return None', "    async def cb(self, response): return None"),
]
for tag, body in FORMS:
    sv, E, out, st = go(HEAD + body + "\n    def cb2(self, response): EV(e='cb2', url=response.url.rsplit('/', 1)[-1])\n")
    items = [x['item']['k'] for x in E if x.get('e') == 'pipeline']
    print(f'  {tag:<32}item={items};cb2={"被调用" if any(x.get("e") == "cb2" for x in E) else "-"};spider_exceptions={st.get("spider_exceptions/count", 0)}')

print('== 二:异步生成器是流式处理的:yield 第一个 item 之后 await 1 s 再 yield 第二个,pipeline 什么时候看到第一个')
sv, E, out, st = go(HEAD + """
    async def cb(self, response):
        EV(e='cb 开始')
        yield {'k': 'first'}
        await asyncio.sleep(1.0)
        yield {'k': 'second'}
""")
for x in E: print(f'  {x["t"]:>7.0f} ms  {x["e"]}' + (f' {x["item"]}' if 'item' in x else ''))

print('== 三:回调并行:20 个响应,每个回调 await 0.3 s;async 回调互不阻塞,总耗时 ≈ 0.3 s;同步 time.sleep(0.3) 则串行 ≈ 6 s')
for tag, body in (('async def + await asyncio.sleep(0.3)', "    async def cb(self, response): await asyncio.sleep(0.3)"), ('def + time.sleep(0.3)', "    def cb(self, response): __import__('time').sleep(0.3)")):
    sv, E, out, st = go(f"""
import scrapy, asyncio
class S(scrapy.Spider):
    name = 's'
    custom_settings = {{'CONCURRENT_REQUESTS': 20, 'CONCURRENT_REQUESTS_PER_DOMAIN': 20}}
    async def start(self):
        for i in range(20): yield scrapy.Request('@U@/p%d' % i, callback=self.cb)
{body}
""")
    print(f'  {tag:<40}总耗时 {st["elapsed_time_seconds"]:.2f} s')

print('== 四:在 asyncio reactor 下 await Twisted 的 Deferred 要转换:直接 await 会怎样,maybe_deferred_to_future / deferred_to_future 怎么用')
sv, E, out, st = go("""
import scrapy, asyncio
from twisted.internet import reactor, task
from scrapy.utils.defer import maybe_deferred_to_future, deferred_to_future
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/x', callback=self.cb)
    async def cb(self, response):
        d = task.deferLater(reactor, 0.1, lambda: 'deferred-result')
        try:
            r = await d; EV(how='直接 await Deferred', result=r)
        except Exception as e: EV(how='直接 await Deferred', exc=type(e).__name__ + ': ' + str(e)[:70])
        d2 = task.deferLater(reactor, 0.1, lambda: 'deferred-result')
        EV(how='await maybe_deferred_to_future(d)', result=await maybe_deferred_to_future(d2))
        d3 = task.deferLater(reactor, 0.1, lambda: 'deferred-result')
        EV(how='await deferred_to_future(d)', result=await deferred_to_future(d3))
""")
for x in E: print(f'  {x["how"]:<34}→ ' + re.sub(r'0x[0-9a-f]+', '0x…', str(x.get("result", x.get("exc")))))

print('== 五:回调里用 aiohttp(同一个 asyncio 事件循环):对另一个 URL 发请求再 yield item;20 个回调并发,总耗时')
sv, E, out, st = go("""
import scrapy, asyncio, aiohttp
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'CONCURRENT_REQUESTS': 20, 'CONCURRENT_REQUESTS_PER_DOMAIN': 20}
    async def start(self):
        for i in range(20): yield scrapy.Request('@U@/p%d' % i, callback=self.cb)
    async def cb(self, response):
        async with aiohttp.ClientSession() as s:
            async with s.get(response.urljoin('/extra/' + response.url.rsplit('/', 1)[-1])) as r:
                body = await r.text()
        yield {'extra': body[:20]}
""")
print(f'  服务器收到 {len(sv.log)} 个请求(20 + 20 个 aiohttp 请求);item_scraped_count={st.get("item_scraped_count")};总耗时 {st["elapsed_time_seconds"]:.2f} s')

print('== 六:async errback 和回调里的异常')
sv, E, out, st = go(HEAD.replace("callback=self.cb)", "callback=self.cb, errback=self.eb)").replace("'@U@/x'", "'@U@/fail'") + """
    async def cb(self, response): pass
    async def eb(self, failure):
        await asyncio.sleep(0.05)
        yield {'from_errback': failure.value.response.status}
""")
print(f'  500 响应(HttpError)→ async errback 产出的 item:{[x["item"] for x in E if x.get("e") == "pipeline"]};stats spider_exceptions={st.get("spider_exceptions/count", 0)}')
sv, E, out, st = go(HEAD + """
    async def cb(self, response):
        await asyncio.sleep(0.05)
        raise ValueError('async boom')
""")
print(f'  async 回调抛异常:spider_exceptions/ValueError={st.get("spider_exceptions/ValueError")};日志 ' + str([l.strip()[:100] for l in out.split(chr(10)) if 'Spider error processing' in l][:1]))
