import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d47'); R = {}
pg = PG(9423).start()
models = "from django.db import models\nclass Acct(models.Model):\n    name = models.CharField(max_length=10)\n    bal = models.IntegerField(default=0)\n"
def proj_iso(level):
    extra = '' if level is None else ", 'OPTIONS': {'isolation_level': __import__('psycopg').IsolationLevel.%s}" % level
    return proj('d47', files={'lab/models.py': models}, databases=pg.databases(extra), apps=['django.contrib.contenttypes', 'lab'])
d = proj_iso(None); manage(d, 'migrate', '--run-syncdb')
pre = "import logging, warnings, threading, time; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections, transaction\nfrom django.db.models import F\nfrom lab.models import Acct\ndef th(fn):\n    out = []\n    def w():\n        try: out.append(fn())\n        except Exception as e: out.append(type(e).__name__ + ': ' + str(e).splitlines()[0][:100])\n        finally: connections.close_all()\n    t = threading.Thread(target=w); t.start(); return t, out\n"
def run(code, level): 
    dd = proj_iso(level); rc, out = pyscript(dd, pre + code); return out.rstrip()
print('== 零:Django 自己的默认:看 SHOW transaction_isolation')
print(' ', run("from django.db import connection\nc = connection.cursor(); c.execute('show transaction_isolation'); print(c.fetchone()[0])", None)); R['default'] = run("from django.db import connection\nc = connection.cursor(); c.execute('show transaction_isolation'); print(c.fetchone()[0])", None)
def nonrepeat():
    return """
Acct.objects.all().delete(); a = Acct.objects.create(name='a', bal=100)
step1 = threading.Event(); step2 = threading.Event()
def other():
    step1.wait(5); Acct.objects.filter(pk=a.pk).update(bal=200); step2.set()
t, _ = th(other)
with transaction.atomic():
    first = Acct.objects.get(pk=a.pk).bal; step1.set(); step2.wait(5); time.sleep(0.2)
    second = Acct.objects.get(pk=a.pk).bal
t.join(); print('同一个事务里两次读同一行:第一次 =', first, ' 第二次 =', second, '→', '不可重复读(读到了别人提交的修改)' if first != second else '可重复读(看到同一个快照)')
"""
def lost_update():
    return """
Acct.objects.all().delete(); a = Acct.objects.create(name='a', bal=100)
step1 = threading.Event(); step2 = threading.Event()
def other():
    step1.wait(5); Acct.objects.filter(pk=a.pk).update(bal=200); step2.set()
t, _ = th(other)
try:
    with transaction.atomic():
        v = Acct.objects.get(pk=a.pk).bal; step1.set(); step2.wait(5); time.sleep(0.2)
        Acct.objects.filter(pk=a.pk).update(bal=F('bal') + 1)
    print('事务提交成功,最终 bal =', Acct.objects.get(pk=a.pk).bal)
except Exception as e: print('提交失败:', type(e).__name__ + ':', str(e).splitlines()[0][:110])
t.join()
"""
R['nr'] = {}; R['lu'] = {}
for label, lvl in (('READ COMMITTED(默认)', None), ('REPEATABLE READ', 'REPEATABLE_READ'), ('SERIALIZABLE', 'SERIALIZABLE')):
    print(f'== 隔离级别 {label}')
    o1 = run(nonrepeat(), lvl); print(' ', o1); R['nr'][label] = o1
    o2 = run(lost_update(), lvl); print('  更新一行(事务开始后别人先改了它):', o2); R['lu'][label] = o2
pg.stop(); save('d47', R)
