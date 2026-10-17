import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d33'); R = {}
models = "from django.db import models\nclass Row(models.Model):\n    a = models.IntegerField()\n    b = models.CharField(max_length=40)\n    c = models.CharField(max_length=40)\n    d = models.TextField()\n"
d = proj('d33', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, time, tracemalloc, gc, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom lab.models import Row\nif not Row.objects.exists():\n    Row.objects.bulk_create([Row(a=i, b=f'bee-{i}', c=f'sea-{i}', d='d' * 200) for i in range(50000)], batch_size=5000)\ndef m(label, fn, reps=3):\n    best = 1e9\n    for _ in range(reps):\n        gc.collect(); t0 = time.perf_counter(); r = fn(); dt = time.perf_counter() - t0; best = min(best, dt)\n    gc.collect(); tracemalloc.start(); r = fn(); cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()\n    print(f'{label:<52} {best*1000:8.1f} ms   峰值内存 {peak/1048576:7.1f} MiB   类型 {type(r[0]).__name__}'); return best*1000, peak/1048576\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:50000 行、4 列(其中一列 200 字节),把全部行读进内存')
o = run("""
m('对象:Row.objects.all()', lambda: list(Row.objects.all()))
m("对象:only('a')", lambda: list(Row.objects.only('a')))
m("values('a', 'b')  → dict", lambda: list(Row.objects.values('a', 'b')))
m("values_list('a', 'b')  → tuple", lambda: list(Row.objects.values_list('a', 'b')))
m("values_list('a', flat=True)  → int", lambda: list(Row.objects.values_list('a', flat=True)))
m("values_list(全部列)  → tuple", lambda: list(Row.objects.values_list()))
m("values()(全部列) → dict", lambda: list(Row.objects.values()))
""")
print(o); R['perf'] = o
print()
print('== 二:每个东西的类型')
o = run("""
r = Row.objects.first(); print('对象     :', type(r).__name__, ' 每个对象带 __dict__ 与 _state:', sorted(r.__dict__)[:6], '…')
print('values   :', Row.objects.values('a', 'b').first())
print('values_list:', Row.objects.values_list('a', 'b').first())
print('flat     :', Row.objects.values_list('a', flat=True).first())
print('named    :', Row.objects.values_list('a', 'b', named=True).first())
""")
print(o); R['types'] = o
print()
print('== 三:values() 不走模型的 Python 逻辑:自定义方法、@property 拿不到;但 Field 的 from_db_value 仍会生效')
o = run("""
print('对象能用模型上的属性(如 __str__ 等),values() 只有列:')
print('  values 的 key:', list(Row.objects.values().first()))
""")
print(o); R['nomodel'] = o
save('d33', R)
