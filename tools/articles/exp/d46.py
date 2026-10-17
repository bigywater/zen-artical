import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d46'); R = {}
pg = PG(9422).start()
models = "from django.db import models\nclass Task(models.Model):\n    name = models.CharField(max_length=10)\n    done_by = models.CharField(max_length=10, default='')\n    stock = models.IntegerField(default=10)\n"
d = proj('d46', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, warnings, threading, time, re; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections, transaction, DatabaseError\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Task\ndef th(fn):\n    out = []\n    def w():\n        try: out.append(fn())\n        except Exception as e: out.append(type(e).__name__ + ': ' + str(e).splitlines()[0][:80])\n        finally: connections.close_all()\n    t = threading.Thread(target=w); t.start(); return t, out\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:SQL 与必须在事务里')
o = run("""
Task.objects.all().delete(); t = Task.objects.create(name='t')
try: list(Task.objects.select_for_update().filter(pk=t.pk))
except Exception as e: print('不在 atomic 里 →', type(e).__name__ + ':', str(e)[:90])
with transaction.atomic():
    with CaptureQueriesContext(connection) as c: list(Task.objects.select_for_update().filter(pk=t.pk))
print('atomic 里的 SQL:', c.captured_queries[-1]['sql'][-70:])
""")
print(o); R['sql'] = o
print()
print('== 二:两个事务抢同一行:阻塞 vs nowait vs skip_locked')
o = run("""
Task.objects.all().delete(); t = Task.objects.create(name='t')
hold = threading.Event(); release = threading.Event()
def holder():
    with transaction.atomic():
        Task.objects.select_for_update().get(pk=t.pk); hold.set(); release.wait(10)
th_h, _ = th(holder); hold.wait(5)
def blocking():
    t0 = time.perf_counter()
    with transaction.atomic(): Task.objects.select_for_update().get(pk=t.pk)
    return f'拿到锁,等了 {time.perf_counter() - t0:.2f} s'
def nowait():
    t0 = time.perf_counter()
    with transaction.atomic(): Task.objects.select_for_update(nowait=True).get(pk=t.pk)
    return '拿到锁'
def skip():
    with transaction.atomic(): r = list(Task.objects.select_for_update(skip_locked=True).filter(pk=t.pk))
    return f'skip_locked 返回 {len(r)} 行'
tb, ob = th(blocking); time.sleep(0.05)
tn, on = th(nowait); tsk, osk = th(skip); tn.join(); tsk.join()
print('持锁事务持有 1.0 s 期间:'); print('  nowait=True    →', on[0]); print('  skip_locked=True →', osk[0])
time.sleep(1.0); release.set(); tb.join(); th_h.join()
print('  普通 select_for_update →', ob[0], '(释放锁之后才返回)')
""")
print(o); R['contend'] = o
print()
print('== 三:skip_locked 做任务队列:30 个任务、3 个工作线程,每个任务是否恰好被处理一次')
o = run("""
Task.objects.all().delete(); Task.objects.bulk_create([Task(name=f't{i}') for i in range(30)])
def worker(wid):
    n = 0
    while True:
        with transaction.atomic():
            t = Task.objects.select_for_update(skip_locked=True).filter(done_by='').order_by('id').first()
            if t is None: return n
            time.sleep(0.01); t.done_by = wid; t.save(update_fields=['done_by']); n += 1
res = []
ts = [th(lambda w=w: worker(w)) for w in ('w1', 'w2', 'w3')]; [t.join() for t, _ in ts]
counts = [o[0] for _, o in ts]; print('各工作线程处理的任务数:', counts, ' 合计', sum(counts))
from django.db.models import Count
print('每个任务被几个人处理过(done_by 非空):', Task.objects.exclude(done_by='').count(), '/ 30 ;done_by 分布:', dict(Task.objects.values_list('done_by').annotate(n=Count('id'))))
""")
print(o); R['queue'] = o
print()
print('== 四:of=("self",) 在有 JOIN 时只锁指定的表;无 atomic 不允许')
o = run("""
Task.objects.all().delete(); Task.objects.create(name='a')
with transaction.atomic():
    with CaptureQueriesContext(connection) as c: list(Task.objects.select_for_update(of=('self',)).filter(name='a'))
print('of=("self") 的 SQL 尾部:', c.captured_queries[-1]['sql'][-40:])
""")
print(o); R['of'] = o
pg.stop(); save('d46', R)
