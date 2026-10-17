import sys, os, json, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s34'); reset_s()
SP = """
import scrapy
class S(scrapy.Spider):
    name = 'demo'
    async def start(self): yield scrapy.Request('data:,x')
    def parse(self, response):
        for i in range(N):
            yield {'id': i, 'name': '商品%d' % i, 'price': round(1.5 * i, 2), 'tags': ['a', 'b'], 'note': None if i % 2 else 'ok'}
"""
def run(feeds, n=5, settings=None, tag='s34'):
    d = sdir(tag)
    rc, out, t = runspider(d, SP.replace('N)', str(n) + ')'), dict({'LOG_LEVEL': 'INFO', 'FEEDS': json.dumps(feeds)}, **(settings or {})))
    return d, out, stats(out)
def head(p, n=3, w=110):
    t = p.read_text(errors='replace') if p.suffix not in ('.pickle', '.marshal') else None
    if t is None: return f'(二进制 {p.stat().st_size} 字节)'
    L = t.split('\n'); return ' ⏎ '.join(l[:w] for l in L[:n]) + (' …' if len(L) > n else '')
def fs(st): return {k.split('feedexport/')[1]: v for k, v in sorted(st.items()) if k.startswith('feedexport/')}

print('== 一:同一批 5 个商品 item(字段 id、name 含中文、price、tags 列表、note 有的是 None),FEEDS 里同时写六种格式:文件大小与开头')
fmts = {'o.json': 'json', 'o.jsonl': 'jsonlines', 'o.csv': 'csv', 'o.xml': 'xml', 'o.pickle': 'pickle', 'o.marshal': 'marshal'}
d, out, st = run({k: {'format': v} for k, v in fmts.items()})
for k in fmts: print(f'  {k:<10}{(d / k).stat().st_size:>5} 字节  {head(d / k, 2, 90)}')
print(f'  stats:{fs(st)}')

print('== 二:编码与缩进:默认的 json 把中文转义成 \\uXXXX;encoding="utf-8" 输出原字符;indent=2 缩进;FEED_EXPORT_ENCODING 设置的全局默认')
d, out, st = run({'a.json': {'format': 'json'}, 'b.json': {'format': 'json', 'encoding': 'utf-8'}, 'c.json': {'format': 'json', 'encoding': 'utf-8', 'indent': 2}, 'd.csv': {'format': 'csv', 'encoding': 'utf-8'}, 'e.csv': {'format': 'csv'}}, n=2)
for k in ('a.json', 'b.json', 'c.json', 'd.csv', 'e.csv'): print(f'  {k:<8}{(d / k).stat().st_size:>4} 字节  {head(d / k, 3, 70)}')
d, out, st = run({'f.json': {'format': 'json'}}, n=2, settings={'FEED_EXPORT_ENCODING': 'utf-8'})
print(f'  只设 FEED_EXPORT_ENCODING=utf-8:f.json {head(d / "f.json", 2, 70)}')

print('== 三:fields 选列与排序(csv / json);没有 fields 时 csv 的列 = 第一个 item 的键;后面 item 多出的键被丢掉')
d, out, st = run({'a.csv': {'format': 'csv', 'fields': ['price', 'id']}, 'b.json': {'format': 'json', 'fields': ['name', 'id'], 'encoding': 'utf-8'}, 'c.csv': {'format': 'csv'}}, n=3)
for k in ('a.csv', 'b.json', 'c.csv'): print(f'  {k:<7}{head(d / k, 4, 100)}')
d = sdir('s34c'); 
code = """
import scrapy
class S(scrapy.Spider):
    name = 'demo'
    async def start(self): yield scrapy.Request('data:,x')
    def parse(self, response):
        yield {'a': 1}
        yield {'a': 2, 'b': 'extra'}
        yield {'b': 'only-b'}
"""
runspider(d, code, {'LOG_LEVEL': 'INFO', 'FEEDS': json.dumps({'x.csv': {'format': 'csv'}, 'x.jsonl': {'format': 'jsonlines'}})})
print(f'  item 键不一致({{a}}、{{a,b}}、{{b}}):csv → {head(d / "x.csv", 4, 40)};jsonlines → {head(d / "x.jsonl", 4, 60)}')

print('== 四:overwrite 与追加:再跑一次同一个文件——默认(本地文件)是追加还是覆盖?')
d = sdir('s34d')
for i in (1, 2):
    rc, out, t = runspider(d, SP.replace('N)', '2)'), {'LOG_LEVEL': 'INFO', 'FEEDS': json.dumps({'o.jsonl': {'format': 'jsonlines'}, 'p.jsonl': {'format': 'jsonlines', 'overwrite': True}, 'q.json': {'format': 'json'}})})
    print(f'  第 {i} 次运行后:o.jsonl {len((d / "o.jsonl").read_text().splitlines())} 行;p.jsonl(overwrite=True){len((d / "p.jsonl").read_text().splitlines())} 行;q.json 开头 {head(d / "q.json", 1, 30)}')
try: json.loads((d / 'q.json').read_text()); ok = '合法'
except Exception as e: ok = '不合法:' + str(e)[:50]
print(f'  q.json(json 格式,默认追加)跑两次后:{ok}')

print('== 五:批量输出 batch_item_count 与 URI 里的占位符(%(batch_id)d、%(batch_time)s、%(name)s、%(time)s)')
d, out, st = run({'out-%(batch_id)d-%(name)s.jsonl': {'format': 'jsonlines', 'batch_item_count': 10}}, n=25)
print('  25 个 item,batch_item_count=10:' + str(sorted(p.name for p in d.glob('out-*'))) + ';每个文件行数 ' + str([len(p.read_text().splitlines()) for p in sorted(d.glob('out-*'))]))
print(f'  stats:{fs(st)}')

print('== 六:item_classes / item_filter、store_empty、postprocessing(gzip)、stdout')
d, out, st = run({'all.jsonl': {'format': 'jsonlines'}, 'some.jsonl': {'format': 'jsonlines', 'item_classes': ['nonexistent.Class']}}, n=3)
print(f'  item_classes 里写不存在的类:all.jsonl {"存在" if (d / "all.jsonl").exists() else "不存在"};错误:' + ([l.strip() for l in out.split(chr(10)) if l.startswith(("ModuleNotFoundError", "ImportError", "NameError", "AttributeError"))] or ['(无)'])[-1][:100])
d, out, st = run({'all.jsonl': {'format': 'jsonlines'}, 'dicts.jsonl': {'format': 'jsonlines', 'item_classes': ['builtins.dict']}, 'other.jsonl': {'format': 'jsonlines', 'item_classes': ['scrapy.Item']}}, n=3)
print(f'  item_classes: dict → dicts.jsonl {len((d / "dicts.jsonl").read_text().splitlines())} 行;scrapy.Item → other.jsonl {len((d / "other.jsonl").read_text().splitlines()) if (d / "other.jsonl").exists() else "不存在"} 行(item 都是 dict,被过滤掉)')
d, out, st = run({'z.jsonl.gz': {'format': 'jsonlines', 'postprocessing': ['scrapy.extensions.postprocessing.GzipPlugin']}}, n=100)
import gzip
raw = (d / 'z.jsonl.gz').read_bytes(); txt = gzip.decompress(raw).decode()
print(f'  postprocessing=GzipPlugin,100 个 item:文件 {len(raw)} 字节,解压后 {len(txt)} 字节,{len(txt.splitlines())} 行')
d, out, st = run({'stdout:': {'format': 'jsonlines'}}, n=2)
print('  FEEDS 的键是 “stdout:”(标准输出):' + ' | '.join(l[:60] for l in out.split(chr(10)) if l.startswith('{"id"')) + ';stats ' + str(fs(st)))
d = sdir('s34f')
rc, out, t = runspider(d, SP.replace('N)', '0)'), {'LOG_LEVEL': 'INFO', 'FEEDS': json.dumps({'e1.json': {'format': 'json'}, 'e2.json': {'format': 'json', 'store_empty': False}, 'e3.csv': {'format': 'csv'}, 'e4.jsonl': {'format': 'jsonlines'}})})
print('  没有任何 item 时(默认 store_empty=True):' + ', '.join(f'{p.name}={p.stat().st_size}字节' for p in sorted(d.glob('e*'))) + ';e2.json(store_empty=False)' + ('存在' if (d / 'e2.json').exists() else '不存在'))
