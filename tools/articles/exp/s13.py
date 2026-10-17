import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s13'); reset_s()
def srv(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s13'):
    d = sdir(tag)
    with Srv(srv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO'}, **(settings or {})))
    return s, ev(d), out, stats(out)
def table(E, keys=('p', 'hook')):
    for i, x in enumerate(E, 1):
        extra = ' '.join(f'{k}={v}' for k, v in x.items() if k not in ('t',) + keys)
        print(f'  {i:>2}. {x["t"]:>6.0f} ms  {x["p"]:<6}{x["hook"]:<14}{extra}')

PIPES = """
import scrapy, asyncio
from scrapy.exceptions import DropItem
def mk(name, drop_if=None, raise_if=None, ret_none=False, opens=0.0, closes=0.0, proc=0.0):
    class P:
        async def open_spider(self):
            EV(p=name, hook='open_spider 开始')
            if opens: await asyncio.sleep(opens)
            EV(p=name, hook='open_spider 结束')
        async def close_spider(self):
            EV(p=name, hook='close_spider 开始')
            if closes: await asyncio.sleep(closes)
            EV(p=name, hook='close_spider 结束')
        async def process_item(self, item):
            EV(p=name, hook='process_item', item=(dict(item) if item is not None else None))
            if proc: await asyncio.sleep(proc)
            if drop_if and drop_if(item): raise DropItem('price must be positive')
            if raise_if and raise_if(item): raise RuntimeError('pipeline boom')
            if ret_none: return None
            if item is None: return None
            item = dict(item); item['via_' + name] = True
            return item
    P.__name__ = P.__qualname__ = 'P' + name
    return P
"""
SP = PIPES + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'ITEM_PIPELINES': @PIPES@}
    async def start(self): yield scrapy.Request('@U@/x')
    def parse(self, response):
        for p in (5, -1, 7): yield {'price': p}
"""
def run(pipes, settings=None, code=SP):
    return go(code.replace('@PIPES@', pipes), settings)

print('== 一:process_item 按数字从小到大;DropItem 丢弃(后面的管道不再调用);其它异常记 ERROR;item 经过每个管道时被改写')
s, E, out, st = run("{mk('A'): 100, mk('B', drop_if=lambda i: i['price'] < 0): 200, mk('C'): 300}")
table([x for x in E if x['hook'] == 'process_item'])
print('  stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith('item_')))
print('  日志:' + ' | '.join(l.strip()[:120] for l in out.split('\n') if 'Dropped' in l))

print('== 二:抛 DropItem 之外的异常(RuntimeError):日志 ERROR,item 同样不会继续,stats 里怎么记')
s, E, out, st = run("{mk('A'): 100, mk('B', raise_if=lambda i: i['price'] < 0): 200, mk('C'): 300}")
table([x for x in E if x['hook'] == 'process_item'])
print('  stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith(('item_', 'spider_exc'))))
print('  日志:' + ' | '.join(l.strip()[:140] for l in out.split('\n') if 'Error processing' in l)[:300])

print('== 三:open_spider / close_spider 是并行的,不是按顺序:三个管道的 open_spider 分别 await 0.3、0.2、0.1 秒')
s, E, out, st = run("{mk('A', opens=0.3, closes=0.1): 100, mk('B', opens=0.2, closes=0.2): 200, mk('C', opens=0.1, closes=0.3): 300}")
table([x for x in E if x['hook'].startswith(('open', 'close'))])

print('== 四:process_item 返回 None 会怎样(B 返回 None,C 在它后面)')
s, E, out, st = run("{mk('A'): 100, mk('B', ret_none=True): 200, mk('C'): 300}")
table([x for x in E if x['hook'] == 'process_item'][:6])
print('  stats:' + ', '.join(f'{k}={v}' for k, v in sorted(st.items()) if k.startswith(('item_', 'spider_exc'))))
errs = [l.strip() for l in out.split('\n') if 'ERROR' in l or l.startswith(('TypeError', 'AttributeError'))]
print('  日志:' + (' | '.join(errs)[:260] if errs else '(没有 ERROR)'))

print('== 五:同一个回调产出的 50 个 item 在 pipeline 里是并行处理的(受 CONCURRENT_ITEMS 限制):process_item 里 await 0.1 s')
SP5 = PIPES + """
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'ITEM_PIPELINES': {mk('A', proc=0.1): 100}}
    async def start(self): yield scrapy.Request('@U@/x')
    def parse(self, response):
        for p in range(50): yield {'price': p}
"""
print(f'  {"CONCURRENT_ITEMS":>18}{"总耗时 s":>10}{"理想值 50×0.1/N":>16}')
for n in (1, 10, 100):
    s, E, out, st = go(SP5, {'CONCURRENT_ITEMS': n, 'LOG_LEVEL': 'INFO'})
    print(f'  {n:>18}{st["elapsed_time_seconds"]:>10.2f}{50 * 0.1 / n:>16.2f}   (item_scraped_count={st["item_scraped_count"]})')

print('== 六:旧写法 process_item(self, item, spider) 在 2.19 里还能用吗')
SP6 = """
import scrapy
class Old:
    def process_item(self, item, spider): EV(what='旧签名被调用', spider=spider.name); return item
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'ITEM_PIPELINES': {Old: 100}}
    async def start(self): yield scrapy.Request('@U@/x')
    def parse(self, response): yield {'a': 1}
"""
s, E, out, st = go(SP6)
print(f'  事件:{[(x.get("what"), x.get("spider")) for x in E]};item_scraped_count={st.get("item_scraped_count")}')
print('  警告:' + (' | '.join(l.split('ScrapyDeprecationWarning: ')[-1].strip()[:170] for l in out.split('\n') if 'ScrapyDeprecationWarning' in l) or '(没有警告)'))
