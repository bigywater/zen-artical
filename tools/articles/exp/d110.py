import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d110'); R = {}
models = "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=20)\n    n = models.IntegerField(default=0)\nclass Plain(models.Model):\n    name = models.CharField(max_length=20)\n"
d = proj('d110', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, time; logging.disable(logging.CRITICAL)\nfrom django.db import connection, transaction\nfrom django.db.models.signals import pre_save, post_save, pre_delete, post_delete\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\nC = {}\ndef cnt(name): \n    def f(sender, **kw): C[name] = C.get(name, 0) + 1\n    return f\nfor s, nm in ((pre_save, 'pre_save'), (post_save, 'post_save'), (pre_delete, 'pre_delete'), (post_delete, 'post_delete')): s.connect(cnt(nm), sender=Item, weak=False, dispatch_uid=nm)\ndef show(label, fn):\n    C.clear()\n    with CaptureQueriesContext(connection) as q: fn()\n    print(f'{label:<34} 信号触发 {dict(C) or \"无\"}  SQL 语句数 {len(q)}')\n" 
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:哪些写入操作会发信号(100 行)')
o = run("""
objs = [Item(name=f'i{i}') for i in range(100)]
show('save() × 100(逐个)', lambda: [Item(name='s').save() for _ in range(100)])
show('bulk_create(100 行)', lambda: Item.objects.bulk_create(objs))
its = list(Item.objects.all()[:100])
for i in its: i.n = 5
show('bulk_update(100 行)', lambda: Item.objects.bulk_update(its, ['n']))
show('queryset.update()', lambda: Item.objects.all().update(n=9))
""")
print(o); R['write'] = o
print()
print('== 二:删除 2000 行:没有 delete 信号时是一条 DELETE(快速删除);有 delete 信号时要把对象全取出来,逐个发信号')
o = run("""
Plain.objects.bulk_create([Plain(name=f'd{i}') for i in range(2000)])
show('delete() 2000 行,没有 delete 信号', lambda: Plain.objects.all().delete())
Plain.objects.bulk_create([Plain(name=f'd{i}') for i in range(2000)])
pd = cnt('post_delete'); post_delete.connect(pd, sender=Plain, weak=False, dispatch_uid='pd')
show('delete() 2000 行,有 post_delete receiver', lambda: Plain.objects.all().delete())
""")
print(o); R['delete'] = o
print()
print('== 三:bulk 操作绕过信号,要靠自己补发')
o = run("""
Item.objects.bulk_create([Item(name=f'x{i}') for i in range(5)])
show('遍历 5 行手动 post_save.send', lambda: [post_save.send(sender=Item, instance=i, created=True) for i in Item.objects.filter(name__startswith='x')])
""")
print(o); R['manual'] = o
print()
print('== 四:删除 2 万行的耗时:有无 delete 信号(每种 3 次取中位)')
o = run("""
import statistics
def bench(with_signal):
    post_delete.disconnect(sender=Plain, dispatch_uid='pd')
    if with_signal: post_delete.connect(cnt('post_delete'), sender=Plain, weak=False, dispatch_uid='pd')
    xs = []
    for _ in range(3):
        Plain.objects.all().delete(); Plain.objects.bulk_create([Plain(name='b') for _ in range(20000)])
        t0 = time.perf_counter(); Plain.objects.all().delete(); xs.append((time.perf_counter() - t0) * 1000)
    return statistics.median(xs)
print(f'  没有 delete 信号 {bench(False):8.1f} ms'); print(f'  有 post_delete    {bench(True):8.1f} ms')
""")
print(o); R['bench'] = o
save('d110', R)
