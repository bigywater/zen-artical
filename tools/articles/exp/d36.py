import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d36'); R = {}
models = '''
from django.db import models
from django.db.models.signals import post_save, pre_save
class Item(models.Model):
    name = models.CharField(max_length=30)
    n = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
class Uniq(models.Model):
    code = models.CharField(max_length=10, unique=True)
    v = models.IntegerField(default=0)
class Base(models.Model):
    x = models.IntegerField(default=0)
class Child(Base):
    y = models.IntegerField(default=0)
FIRED = {'pre': 0, 'post': 0}
def _pre(sender, **kw): FIRED['pre'] += 1
def _post(sender, **kw): FIRED['post'] += 1
pre_save.connect(_pre, sender=Item); post_save.connect(_post, sender=Item)
'''
d = proj('d36', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'migrate', '--run-syncdb')
pre = "import logging, time, warnings; warnings.simplefilter('ignore'); logging.disable(logging.CRITICAL)\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nN = 5000\ndef clear(): Item.objects.all().delete(); Uniq.objects.all().delete(); Child.objects.all().delete(); Base.objects.all().delete(); FIRED['pre'] = FIRED['post'] = 0; connection.queries_log.clear()\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:5000 条:循环 save() vs bulk_create(默认)vs bulk_create(batch_size=1000):查询次数与耗时')
o = run("""
def t(label, fn):
    clear()
    with CaptureQueriesContext(connection) as c: t0 = time.perf_counter(); fn(); dt = time.perf_counter() - t0
    print(f'{label:<38} 查询 {len(c):>5} 次  {dt*1000:8.1f} ms   表里 {Item.objects.count()} 行   pre_save/post_save 信号 {FIRED["pre"]}/{FIRED["post"]}')
t('循环 Item(...).save()', lambda: [Item(name=f'n{i}').save() for i in range(N)])
t('bulk_create(默认)', lambda: Item.objects.bulk_create([Item(name=f'n{i}') for i in range(N)]))
t('bulk_create(batch_size=1000)', lambda: Item.objects.bulk_create([Item(name=f'n{i}') for i in range(N)], batch_size=1000))
""")
print(o); R['perf'] = o
print()
print('== 二:bulk_create 之后 pk 有没有被设置;auto_now_add 有没有生效')
o = run("""
clear(); objs = Item.objects.bulk_create([Item(name='a'), Item(name='b')])
print('返回的对象 pk =', [o.pk for o in objs], '  created 字段(auto_now_add)=', [str(o.created)[:19] for o in objs])
""")
print(o); R['pk'] = o
print()
print('== 三:bulk_update:SQL 长什么样;batch_size 影响的查询数;耗时对比逐个 save()')
o = run("""
clear(); objs = Item.objects.bulk_create([Item(name=f'n{i}') for i in range(N)])
for o in objs: o.n = o.pk * 2
with CaptureQueriesContext(connection) as c: t0 = time.perf_counter(); Item.objects.bulk_update(objs, ['n']); dt = time.perf_counter() - t0
print(f'bulk_update(5000 个对象, ["n"])(默认):查询 {len(c)} 次,{dt*1000:.0f} ms')
print('  第一条 SQL 前 200 字符:', c.captured_queries[0]['sql'][:200])
print('不同 batch_size 下更新 5000 个对象(每种取 3 次中最快;查询数含 BEGIN / COMMIT):')
for bs in (100, 500, 1000, 5000):
    best = 1e9
    for _ in range(3):
        with CaptureQueriesContext(connection) as c: t0 = time.perf_counter(); Item.objects.bulk_update(objs, ['n'], batch_size=bs); dt = time.perf_counter() - t0
        best = min(best, dt)
    print(f'  batch_size={bs:<5} 查询 {len(c):>3} 次  {best*1000:7.0f} ms')
with CaptureQueriesContext(connection) as c: t0 = time.perf_counter(); [o.save(update_fields=['n']) for o in objs]; dt = time.perf_counter() - t0
print(f'逐个 save(update_fields=["n"]):查询 {len(c)} 次,{dt*1000:.0f} ms')
print('信号:', FIRED)
""")
print(o); R['upd'] = o
print()
print('== 四:冲突处理:ignore_conflicts / update_conflicts')
o = run("""
clear(); Uniq.objects.create(code='a', v=1)
rows = [Uniq(code='a', v=100), Uniq(code='b', v=2)]
try: Uniq.objects.bulk_create(rows)
except Exception as e: print('默认(遇到重复):', type(e).__name__ + ':', str(e)[:80])
out = Uniq.objects.bulk_create([Uniq(code='a', v=100), Uniq(code='b', v=2)], ignore_conflicts=True)
print('ignore_conflicts=True:表里 =', sorted(Uniq.objects.values_list('code', 'v')), '  返回对象的 pk =', [o.pk for o in out])
out = Uniq.objects.bulk_create([Uniq(code='a', v=100), Uniq(code='c', v=3)], update_conflicts=True, unique_fields=['code'], update_fields=['v'])
print('update_conflicts=True:表里 =', sorted(Uniq.objects.values_list('code', 'v')))
""")
print(o); R['conf'] = o
print()
print('== 五:限制:多表继承、多对多、不调用 save()/信号')
o = run("""
clear()
try: Child.objects.bulk_create([Child(x=1, y=2)])
except Exception as e: print('多表继承的子类 bulk_create →', type(e).__name__ + ':', str(e)[:100])
clear(); Item.objects.bulk_create([Item(name='s')]); print('bulk_create 触发的信号(pre/post):', FIRED['pre'], FIRED['post'])
Item(name='s').save(); print('对比一次 save():', FIRED['pre'], FIRED['post'])
""")
print(o); R['limits'] = o
save('d36', R)
