import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d31'); R = {}
pg = PG(9401).start()
models = "from django.db import models\nclass Counter(models.Model):\n    name = models.CharField(max_length=20)\n    n = models.IntegerField(default=0)\n"
d = proj('d31', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, threading, time, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections, transaction\nfrom django.db.models import F\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Counter\nT, K = 8, 200\ndef fresh():\n    Counter.objects.all().delete(); return Counter.objects.create(name='c').pk\ndef run_threads(fn):\n    bar = threading.Barrier(T); errs = []\n    def w():\n        try:\n            bar.wait(); fn()\n        except Exception as e: errs.append(type(e).__name__ + ': ' + str(e)[:80])\n        finally: connections.close_all()\n    ts = [threading.Thread(target=w) for _ in range(T)]; t0 = time.perf_counter(); [t.start() for t in ts]; [t.join() for t in ts]; return time.perf_counter() - t0, errs\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:两种写法各自的 SQL')
o = run("""
pk = fresh()
c = Counter.objects.get(pk=pk)
with CaptureQueriesContext(connection) as q:
    c.n = c.n + 1; c.save()
print('读出来再 +1 再 save():'); [print('  ', x['sql'][:150]) for x in q.captured_queries]
with CaptureQueriesContext(connection) as q:
    Counter.objects.filter(pk=pk).update(n=F('n') + 1)
print('update(n=F("n") + 1):'); [print('  ', x['sql'][:150]) for x in q.captured_queries]
c = Counter.objects.get(pk=pk); c.n = F('n') + 1
with CaptureQueriesContext(connection) as q: c.save()
print('对象上 c.n = F("n") + 1; c.save():'); [print('  ', x['sql'][:150]) for x in q.captured_queries]
print('save 之后 c.n 的类型:', type(c.n).__name__, ' → refresh_from_db() 之后:', (c.refresh_from_db(), c.n)[1])
""")
print(o); R['sql'] = o
print()
print('== 二:8 个线程 × 每个 200 次 +1(PostgreSQL,默认 READ COMMITTED),期望最终 1600')
o = run("""
def racy():
    for _ in range(K):
        c = Counter.objects.get(pk=pk); c.n = c.n + 1; c.save()
def safe():
    for _ in range(K): Counter.objects.filter(pk=pk).update(n=F('n') + 1)
for label, fn in (('读-改-写(c.n + 1; save)', racy), ('update(n=F("n") + 1)', safe)):
    pk = fresh(); dt, errs = run_threads(fn); final = Counter.objects.get(pk=pk).n
    print(f'{label:<28} 最终 n = {final:>5}(期望 {T*K}),丢失 {T*K-final:>5} 次,用时 {dt:.2f} s,线程错误 {len(errs)}')
""")
print(o); R['race'] = o
print()
print('== 三:重复 5 轮,丢失更新的次数(读-改-写)')
o = run("""
res = []
for i in range(5):
    pk = fresh()
    def racy():
        for _ in range(K):
            c = Counter.objects.get(pk=pk); c.n = c.n + 1; c.save()
    dt, errs = run_threads(racy); res.append(T * K - Counter.objects.get(pk=pk).n)
print('每轮丢失:', res)
""")
print(o); R['rounds'] = o
print()
print('== 四:F() 表达式不能解决的事:需要读到新值时要 refresh,或用 RETURNING;update() 返回受影响行数')
o = run("""
pk = fresh()
n = Counter.objects.filter(pk=pk).update(n=F('n') + 5); print('update() 返回受影响行数 =', n)
n = Counter.objects.filter(pk=999999).update(n=F('n') + 5); print('更新不存在的行,返回 =', n)
c = Counter.objects.get(pk=pk); print('库里现在的值 =', c.n)
Counter.objects.filter(pk=pk).update(n=F('n') * 2 + F('n')); print('n = n*2 + n →', Counter.objects.get(pk=pk).n)
""")
print(o); R['misc'] = o
pg.stop(); save('d31', R)
