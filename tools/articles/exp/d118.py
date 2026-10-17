import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d118'); R = {}
pg = PG(9473).start()
models = "from django.db import models\nclass Counter(models.Model):\n    n = models.IntegerField(default=0)\n"
d = proj('d118', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'], middleware=[])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
T, M = 10, 200
def run(code, timeout=300): rc, out = pyscript(d, "import logging, threading, time; logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections, transaction\nfrom django.db.models import F\nfrom lab.models import Counter\nT, M = %d, %d\nfrom concurrent.futures import ThreadPoolExecutor\ndef bench(name, worker):\n    Counter.objects.all().delete(); Counter.objects.create(pk=1, n=0)\n    def th():\n        try:\n            for _ in range(M): worker()\n        finally: connections.close_all()\n    t0 = time.perf_counter()\n    with ThreadPoolExecutor(T) as ex: [f.result() for f in [ex.submit(th) for _ in range(T)]]\n    ms = (time.perf_counter() - t0) * 1000\n    n = Counter.objects.get(pk=1).n\n    print(f'  {name:<44} 最终 n = {n:>5} / 期望 {T * M}   丢失 {T * M - n:>4}   {ms:6.0f} ms')\n" % (T, M) + code, timeout); return out.rstrip()
print(f'== 一:{T} 个线程各对同一行计数器 +1 共 {M} 次(期望 {T * M});PostgreSQL 默认隔离级别 read committed')
o = run("""
def a():
    c = Counter.objects.get(pk=1); c.n += 1; c.save()
def b():
    with transaction.atomic():
        c = Counter.objects.get(pk=1); c.n += 1; c.save()
def c_():
    Counter.objects.filter(pk=1).update(n=F('n') + 1)
def d_():
    with transaction.atomic():
        c = Counter.objects.select_for_update().get(pk=1); c.n += 1; c.save()
def e():
    c = Counter.objects.get(pk=1); c.n = F('n') + 1; c.save()
bench('get → n += 1 → save()', a)
bench('同上,外面包 atomic()', b)
bench('filter().update(n=F("n") + 1)', c_)
bench('atomic + select_for_update().get → +1 → save', d_)
bench('get → c.n = F("n") + 1 → save()', e)
""")
print(o); R['bench'] = o
print()
print('== 二:F() 表达式赋给实例之后,内存里的 n 是什么?')
o = run("""
Counter.objects.all().delete(); c = Counter.objects.create(pk=1, n=5)
c.n = F('n') + 1; c.save()
print('  save() 之后 c.n 的类型:', type(c.n).__name__, ' 库里的值:', Counter.objects.get(pk=1).n)
c.refresh_from_db(); print('  refresh_from_db() 之后 c.n =', c.n)
""")
print(o); R['f'] = o
pg.stop(); save('d118', R)
