import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d34'); R = {}
models = "from django.db import models\nclass Row(models.Model):\n    a = models.IntegerField(db_index=True)\n    b = models.CharField(max_length=40)\n    d = models.TextField()\n"
d = proj('d34', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, time, tracemalloc, gc, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Row\nN = 200000\nif Row.objects.count() != N:\n    Row.objects.all().delete(); Row.objects.bulk_create([Row(a=i, b=f'bee-{i}', d='d' * 100) for i in range(N)], batch_size=5000)\ndef m(label, fn, reps=3):\n    best = 1e9\n    for _ in range(reps):\n        gc.collect(); t0 = time.perf_counter(); r = fn(); dt = time.perf_counter() - t0; best = min(best, dt)\n    gc.collect(); tracemalloc.start(); r = fn(); cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()\n    print(f'{label:<50} {best*1000:9.2f} ms   峰值内存 {peak/1048576:7.2f} MiB   → {r}'); return best*1000, peak/1048576\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:20 万行:「有没有」「有几个」用不同写法的代价(SQLite,本机)')
o = run("""
qs = lambda: Row.objects.filter(a__gte=100)
m('qs.exists()', lambda: qs().exists())
m('bool(qs)(if qs:)', lambda: bool(qs()))
m('qs.count()', lambda: qs().count())
m('len(qs)', lambda: len(qs()))
m('len(list(qs.values_list("a", flat=True)))', lambda: len(list(qs().values_list('a', flat=True))))
""")
print(o); R['perf'] = o
print()
print('== 二:各自发的 SQL')
o = run("""
def sql(label, fn):
    with CaptureQueriesContext(connection) as c: fn()
    print(f'{label:<14}', c.captured_queries[-1]['sql'][:130])
q = lambda: Row.objects.filter(a__gte=100)
sql('exists()', lambda: q().exists()); sql('count()', lambda: q().count()); sql('len()', lambda: len(q())); sql('bool()', lambda: bool(q()))
""")
print(o); R['sql'] = o
print()
print('== 三:已经求值过的 QuerySet:count() / exists() / len() 都不再查询;没求值时 count() 之后再 len() 会查两次')
o = run("""
qs = Row.objects.filter(a__lt=1000)
with CaptureQueriesContext(connection) as c: qs.count(); n1 = len(c)
with CaptureQueriesContext(connection) as c: len(qs); n2 = len(c)
with CaptureQueriesContext(connection) as c: qs.count(); qs.exists(); len(qs); n3 = len(c)
print('全新 qs:count() 查询', n1, '次;然后 len(qs) 又查询', n2, '次(填充缓存);之后 count/exists/len 再查询', n3, '次')
""")
print(o); R['cache'] = o
save('d34', R)
