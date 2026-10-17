import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d49'); R = {}
pg = PG(9424).start()
models = "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=30)\n    created = models.IntegerField(db_index=True)\n"
d = proj('d49', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pg.psql("insert into lab_item (name, created) select 'n' || g, g from generate_series(1, 1000000) g"); pg.psql('analyze lab_item')
pre = "import logging, warnings, time; warnings.simplefilter('always'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.core.paginator import Paginator, EmptyPage\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Item\ndef t(fn, reps=5):\n    best = 1e9\n    for _ in range(reps):\n        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)\n    return best * 1000\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:Paginator.page() 发出的 SQL(100 万行的表)')
o = run("""
qs = Item.objects.order_by('id'); p = Paginator(qs, 25)
with CaptureQueriesContext(connection) as c: pg = p.page(3); list(pg.object_list)
for q in c.captured_queries: print('  ', re.sub(r'\\s+', ' ', q['sql'])[:120]) if False else print('  ', ' '.join(q['sql'].split())[:120])
with CaptureQueriesContext(connection) as c: p.page(4); n4 = len(c)
print('同一个 Paginator 再取第 4 页时,新增的 COUNT 查询:', sum('COUNT' in q['sql'] for q in c.captured_queries), '(count 是缓存的)')
print('p.count =', p.count, ' p.num_pages =', p.num_pages)
""")
print(o); R['sql'] = o
print()
print('== 二:各部分的耗时(每项 5 次取最快)')
o = run("""
qs = Item.objects.order_by('id')
print('SELECT COUNT(*):                          %.1f ms' % t(lambda: Item.objects.count()))
print('第 1 页(LIMIT 25):                        %.2f ms' % t(lambda: list(qs[0:25])))
print('第 20000 页(OFFSET 499975):               %.1f ms' % t(lambda: list(qs[499975:500000])))
print('第 40000 页(OFFSET 999975):               %.1f ms' % t(lambda: list(qs[999975:1000000])))
print('Paginator(qs, 25).page(1) 整体(含 COUNT):   %.1f ms' % t(lambda: list(Paginator(qs, 25).page(1))))
print('Paginator(qs, 25).page(40000) 整体:        %.1f ms' % t(lambda: list(Paginator(qs, 25).page(40000))))
print('用 keyset(WHERE created > 999975 ORDER BY 索引列 LIMIT 25): %.2f ms' % t(lambda: list(Item.objects.filter(created__gt=999975).order_by('created')[:25])))
print('过滤后的 COUNT(created < 500000 条件):     %.1f ms' % t(lambda: Item.objects.filter(created__lt=500000).count()))
""")
print(o); R['time'] = o
print()
print('== 三:没有排序的 QuerySet;越界页;自己提供 count')
o = run("""
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always'); Paginator(Item.objects.all(), 25).page(1)
print('未排序的 QuerySet:', [str(x.message)[:110] for x in w][:1] or '无警告')
try: Paginator(Item.objects.order_by('id'), 25).page(999999)
except EmptyPage as e: print('越界页 → EmptyPage:', e)
class FastCount(Paginator):
    count = 1000000
    from django.utils.functional import cached_property
with CaptureQueriesContext(connection) as c: FastCount(Item.objects.order_by('id'), 25).page(2)
print('子类里把 count 写死之后,COUNT 查询数:', sum('COUNT' in q['sql'] for q in c.captured_queries))
""")
print(o); R['misc'] = o
pg.stop(); save('d49', R)
