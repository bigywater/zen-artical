import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s48'); reset_s()
d = sdir('s48')
def P(title, code, tag=None):
    if title: print(title)
    rc, out, t = py(d, 'import time, statistics\nimport scrapy\nfrom itemadapter import ItemAdapter, is_item\n' + code, env={'PYTHONWARNINGS': 'ignore'})
    print(out)
print('== 一:四种 item 类型:dict、scrapy.Item、dataclass、attrs——ItemAdapter 给它们同一套接口(itemadapter ' + subprocess.run([SPY, '-c', 'import itemadapter; print(itemadapter.__version__)'], capture_output=True, text=True).stdout.strip() + ')')
P('', """
import dataclasses, attr
class SItem(scrapy.Item):
    name = scrapy.Field()
    price = scrapy.Field(serializer=lambda v: f'¥{v}')
@dataclasses.dataclass
class DItem:
    name: str = None
    price: float = None
    extra: list = dataclasses.field(default_factory=list, metadata={'note': 'meta'})
@attr.s
class AItem:
    name = attr.ib(default=None)
    price = attr.ib(default=None, metadata={'serializer': str})
objs = {'dict': {'name': 'a', 'price': 1.5}, 'scrapy.Item': SItem(name='a', price=1.5), 'dataclass': DItem(name='a', price=1.5), 'attrs': AItem(name='a', price=1.5)}
print(f'  {"类型":<14}{"is_item":<9}{"field_names()":<34}{"asdict()":<42}get("price")  get("zzz", "默认")')
for k, o in objs.items():
    a = ItemAdapter(o)
    print(f'  {k:<14}{str(is_item(o)):<9}{str(list(a.field_names())):<34}{str(a.asdict()):<42}{a.get("price")!s:<12}{a.get("zzz", "默认")}')
print('  字段元数据 get_field_meta("price"):' + '; '.join(f'{k}={dict(ItemAdapter(o).get_field_meta("price")) if k != "dict" else "(dict 没有元数据)"}' for k, o in objs.items() if k != 'dict'))
print('  不是 item 的东西:is_item(42)=', is_item(42), ' is_item("s")=', is_item('s'), ' is_item([1])=', is_item([1]), ' is_item(object())=', is_item(object()))
""")
print('== 二:scrapy.Item 的严格性:没声明的字段不能赋值(KeyError),dataclass / dict 不限制;类型也都不检查')
P('', """
import dataclasses
class SItem(scrapy.Item):
    name = scrapy.Field()
@dataclasses.dataclass
class DItem:
    name: str = None
for tag, f in (('scrapy.Item 赋值未声明字段', lambda: SItem(name='a', zzz=1)), ('scrapy.Item item["zzz"] = 1', lambda: SItem().__setitem__('zzz', 1)), ('scrapy.Item 读未赋值的字段 item["name"]', lambda: SItem()['name']), ('scrapy.Item item.get("name")', lambda: SItem().get('name')), ('dataclass 传未声明字段 DItem(zzz=1)', lambda: DItem(zzz=1)), ('dataclass 给 name 赋整数(类型标注 str)', lambda: DItem(name=123)), ('dict 随便加字段', lambda: {}.update(zzz=1))):
    try: r = f(); print(f'  {tag:<44}→ 通过,结果 {r!r}')
    except Exception as e: print(f'  {tag:<44}→ 抛 {type(e).__name__}: {e}')
a = ItemAdapter(SItem()); 
try: a['zzz'] = 1
except Exception as e: print(f'  ItemAdapter(SItem())["zzz"] = 1  → 抛 {type(e).__name__}: {e}')
""")
print('== 三:同一批数据用四种 item 类型导出(FEEDS):csv / jsonlines 的输出与字段元数据 serializer 的作用')
CODE3 = """
import scrapy, dataclasses, attr
class SItem(scrapy.Item):
    name = scrapy.Field()
    price = scrapy.Field(serializer=lambda v: f'¥{v}')
@dataclasses.dataclass
class DItem:
    name: str = None
    price: float = None
    extra: list = dataclasses.field(default_factory=list)
@attr.s
class AItem:
    name = attr.ib(default=None)
    price = attr.ib(default=None)
class S(scrapy.Spider):
    name = 's'
    custom_settings = {'FEEDS': {'o.jsonl': {'format': 'jsonlines', 'encoding': 'utf-8'}, 'o.csv': {'format': 'csv'}}}
    async def start(self): yield scrapy.Request('data:,x')
    def parse(self, response):
        yield {'name': '字典', 'price': 1.5}
        yield SItem(name='Item', price=2.5)
        yield DItem(name='dataclass', price=3.5, extra=['x'])
        yield AItem(name='attrs', price=4.5)
"""
rc, out, t = runspider(sdir('s48c'), CODE3, {'LOG_LEVEL': 'INFO'})
dd = SD / 's48c'
print('  o.jsonl:'); print('\n'.join('    ' + l for l in (dd / 'o.jsonl').read_text().strip().split('\n')))
print('  o.csv:'); print('\n'.join('    ' + l for l in (dd / 'o.csv').read_text().strip().split('\n')))
print(f'  item_scraped_count={stats(out).get("item_scraped_count")}(四个类型都被接受)')
print('  说明:csv 表头取自第一个 item(字典)的键 name,price;scrapy.Item 的 serializer 在 jsonlines 里生效(price 变成 “¥2.5”),dataclass 的 extra 字段在 csv 里被丢掉(列头里没有)')

print('== 四:创建一个 item 并填 3 个字段的耗时(10 万次,中位数毫秒/万次):dict、scrapy.Item、dataclass、attrs、dataclass(slots=True)')
P('', """
import dataclasses, attr, timeit
class SItem(scrapy.Item):
    a = scrapy.Field(); b = scrapy.Field(); c = scrapy.Field()
@dataclasses.dataclass
class DItem: a: int = None; b: int = None; c: int = None
@dataclasses.dataclass(slots=True)
class DSItem: a: int = None; b: int = None; c: int = None
@attr.s
class AItem:
    a = attr.ib(default=None); b = attr.ib(default=None); c = attr.ib(default=None)
@attr.s(slots=True)
class ASItem:
    a = attr.ib(default=None); b = attr.ib(default=None); c = attr.ib(default=None)
N = 100000
def t(f, rep=5):
    ts = []
    for _ in range(rep): t0 = time.perf_counter(); f(); ts.append((time.perf_counter() - t0) * 1000 / (N / 10000))
    return statistics.median(ts)
res = {
 'dict': t(lambda: [{'a': 1, 'b': 2, 'c': 3} for _ in range(N)]),
 'scrapy.Item': t(lambda: [SItem(a=1, b=2, c=3) for _ in range(N)]),
 'dataclass': t(lambda: [DItem(a=1, b=2, c=3) for _ in range(N)]),
 'dataclass(slots=True)': t(lambda: [DSItem(a=1, b=2, c=3) for _ in range(N)]),
 'attrs': t(lambda: [AItem(a=1, b=2, c=3) for _ in range(N)]),
 'attrs(slots=True)': t(lambda: [ASItem(a=1, b=2, c=3) for _ in range(N)]),
}
base = res['dict']
for k, v in res.items(): print(f'  {k:<24}{v:>8.1f} ms / 万次  {v / base:>5.1f}× dict')
import sys as _s
objs = {'dict': {'a': 1, 'b': 2, 'c': 3}, 'scrapy.Item': SItem(a=1, b=2, c=3), 'dataclass': DItem(1, 2, 3), 'dataclass(slots=True)': DSItem(1, 2, 3), 'attrs': AItem(1, 2, 3), 'attrs(slots=True)': ASItem(1, 2, 3)}
import tracemalloc
print('  每个对象占的内存(tracemalloc,10 万个实例的平均字节):')
for k, f in (('dict', lambda: {'a': 1, 'b': 2, 'c': 3}), ('scrapy.Item', lambda: SItem(a=1, b=2, c=3)), ('dataclass', lambda: DItem(a=1, b=2, c=3)), ('dataclass(slots=True)', lambda: DSItem(a=1, b=2, c=3)), ('attrs', lambda: AItem(a=1, b=2, c=3)), ('attrs(slots=True)', lambda: ASItem(a=1, b=2, c=3))):
    tracemalloc.start(); keep = [f() for _ in range(N)]; cur, _ = tracemalloc.get_traced_memory(); tracemalloc.stop(); del keep
    print(f'    {k:<24}{cur / N:>7.0f} 字节/个')
""")
