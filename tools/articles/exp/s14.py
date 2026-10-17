import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s14'); reset_s()
d = sdir('s14')
def P(title, code, extra=''):
    print(title)
    rc, out, t = py(d, 'from itemloaders import ItemLoader\nfrom itemloaders.processors import *\nimport scrapy\nfrom scrapy.loader import ItemLoader as SL\nfrom scrapy.http import HtmlResponse\nfrom scrapy import Selector\n' + code)
    print(out)

P('== 一:输入处理器在每次 add_value 时调用,输出处理器只在 load_item 时调用一次(每个字段);默认两个都是 Identity,所以值总是列表', """
calls = []
def inp(v): calls.append(('输入', v)); return [x.strip() for x in v]
def outp(v): calls.append(('输出', v)); return v
class L(ItemLoader):
    default_input_processor = staticmethod(inp)
    default_output_processor = staticmethod(outp)
l = L()
l.add_value('name', ' a ')
l.add_value('name', [' b ', ' c '])
l.add_value('price', '9.9')
print('  add_value 之后,collected:', {k: l.get_collected_values(k) for k in ('name', 'price')})
print('  调用记录(add_value 阶段):', calls)
item = l.load_item()
print('  load_item 之后的 item:', item)
print('  调用记录(完整):', calls)
l2 = ItemLoader()
l2.add_value('name', 'x'); l2.add_value('name', 'y')
print('  不设处理器(Identity):', l2.load_item(), ';get_output_value =', l2.get_output_value('name'))
""")

P('== 二:常用处理器各自的行为(输入是一个列表)', """
def show(tag, proc, v): 
    try: print(f'  {tag:<46}{v!r:<34}→ {proc(v)!r}')
    except Exception as e: print(f'  {tag:<46}{v!r:<34}→ 抛 {type(e).__name__}: {e}')
show('Identity()', Identity(), ['a', 'b'])
show('TakeFirst()', TakeFirst(), [None, '', 'a', 'b'])
show('TakeFirst()(全空)', TakeFirst(), [None, ''])
show('TakeFirst()(0 和 False)', TakeFirst(), [0, False, 5])
show("Join()", Join(), ['a', 'b', 'c'])
show("Join(', ')", Join(', '), ['a', 'b', 'c'])
show('MapCompose(str.strip)', MapCompose(str.strip), [' a ', ' b'])
show('MapCompose(str.strip, str.upper)', MapCompose(str.strip, str.upper), [' a ', ' b'])
show('MapCompose(lambda x: None 当 x 为空)', MapCompose(lambda x: x or None), ['a', '', 'b'])
show('MapCompose(lambda x: x.split(","))(返回列表→展平)', MapCompose(lambda x: x.split(',')), ['a,b', 'c'])
show('MapCompose(int)(遇到非数字)', MapCompose(int), ['1', 'x'])
show('Compose(lambda v: v[0])', Compose(lambda v: v[0]), ['a', 'b'])
show('Compose(lambda v: v[0])(空列表)', Compose(lambda v: v[0]), [])
show('Compose(…, stop_on_none=False)(空列表)', Compose(lambda v: v[0] if v else None, str.upper, stop_on_none=False), [])
show('Compose(…)(默认 stop_on_none=True,遇到 None 就停)', Compose(lambda v: v[0] if v else None, str.upper), [])
""")

P('== 三:谁说了算:Loader 里的 字段名_in / 字段名_out,Item 字段元数据 input_processor / output_processor,default_*_processor——同时存在时的优先级', """
class It(scrapy.Item):
    name = scrapy.Field(input_processor=MapCompose(lambda x: 'meta:' + x), output_processor=Join('|'))
    tag = scrapy.Field(input_processor=MapCompose(lambda x: 'meta:' + x))
    other = scrapy.Field()
class L(ItemLoader):
    default_item_class = It
    default_input_processor = MapCompose(lambda x: 'default:' + x)
    default_output_processor = Join('+')
    name_in = MapCompose(lambda x: 'loader:' + x)
l = L()
for f in ('name', 'tag', 'other'): l.add_value(f, ['1', '2'])
print('  name  (loader 的 name_in + Field 元数据 + default):', l.get_output_value('name'))
print('  tag   (只有 Field 元数据的 input_processor + default 输出):', l.get_output_value('tag'))
print('  other (什么都没有 → 全用 default_*):', l.get_output_value('other'))
print('  item =', dict(l.load_item()))
""")

P('== 四:带选择器:add_css / add_xpath / add_value,nested_css,以及 loader_context 里的值传给处理器', """
html = '<html><body><div id=p><h1>  Python 入门 </h1><span class=price>价格: 59.9 元</span><ul><li>a</li><li>b</li></ul></div></body></html>'
resp = HtmlResponse('http://x/', body=html.encode(), encoding='utf-8')
def pr(value, loader_context): return float(value.split(':')[-1].replace('元', '')) * loader_context['rate']
class L(SL):
    default_item_class = dict
    title_in = MapCompose(str.strip)
    title_out = TakeFirst()
    price_in = MapCompose(pr)
    price_out = TakeFirst()
    tags_out = Join(',')
l = L(response=resp, rate=2)
l.add_css('title', 'h1::text')
l.add_xpath('price', '//span[@class="price"]/text()')
l.add_css('tags', 'li::text')
l.add_value('src', resp.url)
print('  loader_context 里的 rate=2 传给了 price_in:', dict(l.load_item()))
n = L(response=resp, rate=1)
nl = n.nested_css('#p')
nl.add_css('title', 'h1::text'); nl.add_css('tags', 'li::text')
print('  nested_css("#p") 里再 add_css:', dict(n.load_item()))
print('  loader.context 的键:', sorted(l.context))
""")

P('== 五:空值和缺失:没有收集到值的字段不会出现在 item 里;None / 空串 / 空列表 add_value 会被怎么处理', """
l = ItemLoader()
l.add_value('a', None)
l.add_value('b', '')
l.add_value('c', [])
l.add_value('d', [None, ''])
l.add_value('e', 0)
l.add_value('f', False)
print('  add_value(None / "" / [] / [None, ""] / 0 / False) → collected:', {k: l.get_collected_values(k) for k in 'abcdef'})
print('  load_item():', dict(l.load_item()))
l2 = ItemLoader()
l2.add_value('x', 'old'); l2.replace_value('x', 'new'); l2.add_value('y', 'abc123', re=r'\\d+')
print('  replace_value 之后:', dict(l2.load_item()), ';add_value(re=…):', l2.get_collected_values('y'))
print('  get_value("a b", re="b"):', ItemLoader().get_value('a b', re='b'))
""")

P('== 六:scrapy.loader.ItemLoader 的默认 item 类是 scrapy.Item:往没声明的字段里放值会怎样;换成 dict 或声明字段', """
class Declared(scrapy.Item):
    title = scrapy.Field()
l = SL()
try: l.add_value('title', 'x')
except Exception as e: print('  SL()(默认 scrapy.Item,没有任何字段)add_value("title"):抛', type(e).__name__, e)
l = SL(item=Declared())
l.add_value('title', 'x')
try: l.add_value('other', 'y')
except Exception as e: print('  SL(item=Declared()) 里 add_value("other")(没声明):抛', type(e).__name__, e)
print('  声明了 title 的 item:', dict(l.load_item()), type(l.load_item()).__name__)
class DL(SL): default_item_class = dict
l = DL(); l.add_value('anything', 'z'); print('  default_item_class = dict:', l.load_item(), type(l.load_item()).__name__)
""")
