import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d44'); R = {}
pg = PG(9420).start()
models = "from django.db import models\nclass Acct(models.Model):\n    name = models.CharField(max_length=10, unique=True)\n    bal = models.IntegerField(default=0)\n"
d = proj('d44', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, transaction, IntegrityError\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Acct\nimport re\ndef reset(): Acct.objects.all().delete()\ndef show(c):\n    for q in c.captured_queries: print('   ', re.sub(r'\\s+', ' ', q['sql'])[:110])\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:嵌套 atomic 实际发出的 SQL:外层 BEGIN,内层 SAVEPOINT')
o = run("""
reset()
with CaptureQueriesContext(connection) as c:
    with transaction.atomic():
        Acct.objects.create(name='a')
        with transaction.atomic():
            Acct.objects.create(name='b')
        Acct.objects.create(name='c')
show(c)
""")
print(o); R['nested'] = o
print()
print('== 二:内层抛异常被外层捕获:只回滚内层(ROLLBACK TO SAVEPOINT),外层继续并提交')
o = run("""
reset()
with CaptureQueriesContext(connection) as c:
    with transaction.atomic():
        Acct.objects.create(name='a')
        try:
            with transaction.atomic():
                Acct.objects.create(name='b'); raise ValueError('inner fails')
        except ValueError: pass
        Acct.objects.create(name='c')
show(c); print('  最终表里:', sorted(Acct.objects.values_list('name', flat=True)))
""")
print(o); R['inner_fail'] = o
print()
print('== 三:atomic 里吞掉 IntegrityError 却没有内层 atomic:事务已经进入错误状态')
o = run("""
reset(); Acct.objects.create(name='dup')
try:
    with transaction.atomic():
        try: Acct.objects.create(name='dup')
        except IntegrityError as e: print('  捕获到 IntegrityError:', str(e).splitlines()[0][:70])
        Acct.objects.create(name='after')
except Exception as e: print('  之后的查询 →', type(e).__name__ + ':', str(e)[:130])
print('  ——改成内层再包一层 atomic:')
reset(); Acct.objects.create(name='dup')
with transaction.atomic():
    try:
        with transaction.atomic(): Acct.objects.create(name='dup')
    except IntegrityError: print('  捕获到 IntegrityError(只回滚到保存点)')
    Acct.objects.create(name='after')
print('  最终表里:', sorted(Acct.objects.values_list('name', flat=True)))
""")
print(o); R['integrity'] = o
print()
print('== 四:savepoint=False;durable=True;autocommit 下没有 atomic 时每条语句自己提交')
o = run("""
reset()
try:
    with transaction.atomic():
        with transaction.atomic(durable=True): pass
except Exception as e: print('  嵌套在 atomic 里的 durable=True →', type(e).__name__ + ':', str(e)[:100])
with CaptureQueriesContext(connection) as c:
    with transaction.atomic():
        try:
            with transaction.atomic(savepoint=False): Acct.objects.create(name='x'); raise ValueError()
        except ValueError: pass
show(c)
print('  savepoint=False 的内层失败之后,外层被标记 needs_rollback,外层提交时:', end=' ')
reset()
try:
    with transaction.atomic():
        try:
            with transaction.atomic(savepoint=False): Acct.objects.create(name='y'); raise ValueError()
        except ValueError: pass
        Acct.objects.create(name='z')
except Exception as e: print(type(e).__name__ + ':', str(e)[:110])
print('  表里:', sorted(Acct.objects.values_list('name', flat=True)))
reset()
with CaptureQueriesContext(connection) as c: Acct.objects.create(name='auto')
print('  没有 atomic 的单条 create:'); show(c)
""")
print(o); R['misc'] = o
pg.stop(); save('d44', R)
