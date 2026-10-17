import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d35'); R = {}
pg = PG(9402).start()
models = "from django.db import models\nclass UTag(models.Model):\n    name = models.CharField(max_length=20, unique=True)\n    extra = models.CharField(max_length=20, default='')\nclass PTag(models.Model):\n    name = models.CharField(max_length=20)\n"
d = proj('d35', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, threading, time, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection, connections, transaction\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nT = 8\ndef race(model, n_rounds=20, **kw):\n    created = []; errs = []; lock = threading.Lock()\n    for r in range(n_rounds):\n        model.objects.all().delete(); name = f'x{r}'; bar = threading.Barrier(T); res = []\n        def w():\n            try:\n                bar.wait(); obj, c = model.objects.get_or_create(name=name, **kw); res.append(c)\n            except Exception as e: errs.append(type(e).__name__)\n            finally: connections.close_all()\n        ts = [threading.Thread(target=w) for _ in range(T)]; [t.start() for t in ts]; [t.join() for t in ts]\n        created.append((sum(res), model.objects.filter(name=name).count()))\n    return created, errs\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:get_or_create 内部做了什么(SQL)')
o = run("""
UTag.objects.all().delete()
with CaptureQueriesContext(connection) as c: obj, cr = UTag.objects.get_or_create(name='a', defaults={'extra': 'e'})
print('第一次(不存在,创建) created =', cr); [print('  ', x['sql'][:140]) for x in c.captured_queries]
with CaptureQueriesContext(connection) as c: obj, cr = UTag.objects.get_or_create(name='a', defaults={'extra': 'e'})
print('第二次(已存在) created =', cr); [print('  ', x['sql'][:140]) for x in c.captured_queries]
""")
print(o); R['sql'] = o
print()
print('== 二:8 个线程同时 get_or_create 同一个名字,重复 20 轮:有唯一约束 vs 没有')
o = run("""
c1, e1 = race(UTag); c2, e2 = race(PTag)
print('name 有 unique=True :每轮(返回 created=True 的线程数, 表里该名字的行数) =', sorted(set(c1)), ' 抛出的异常:', sorted(set(e1)) or '无')
print('name 没有唯一约束    :每轮(返回 created=True 的线程数, 表里该名字的行数) =', sorted(set(c2)), ' 抛出的异常:', sorted(set(e2)) or '无')
print('没有唯一约束时表里出现重复行的轮数:', sum(1 for _, n in c2 if n > 1), '/ 20')
""")
print(o); R['race'] = o
print()
print('== 三:重复行造成的后果:之后再 get_or_create 会抛 MultipleObjectsReturned')
o = run("""
PTag.objects.all().delete(); PTag.objects.create(name='dup'); PTag.objects.create(name='dup')
try: PTag.objects.get_or_create(name='dup')
except Exception as e: print('get_or_create(name="dup") →', type(e).__name__ + ':', str(e)[:100])
""")
print(o); R['multi'] = o
print()
print('== 四:update_or_create 同样受唯一约束保护;defaults 里的值只在创建/更新时写入')
o = run("""
UTag.objects.all().delete()
obj, c = UTag.objects.update_or_create(name='u', defaults={'extra': '1'}); print('第一次:', c, obj.extra)
obj, c = UTag.objects.update_or_create(name='u', defaults={'extra': '2'}); print('第二次:', c, obj.extra)
obj, c = UTag.objects.get_or_create(name='u', defaults={'extra': '3'}); print('get_or_create 已存在时 defaults 不生效:', c, obj.extra)
UTag.objects.all().delete()
def upd():
    bar.wait(); UTag.objects.update_or_create(name='hot', defaults={'extra': 'x'}); connections.close_all()
errs = []
def w():
    try: upd()
    except Exception as e: errs.append(type(e).__name__)
bar = threading.Barrier(T); ts = [threading.Thread(target=w) for _ in range(T)]; [t.start() for t in ts]; [t.join() for t in ts]
print('8 线程同时 update_or_create 同一个键:行数 =', UTag.objects.filter(name='hot').count(), ' 异常:', sorted(set(errs)) or '无')
""")
print(o); R['upd'] = o
pg.stop(); save('d35', R)
