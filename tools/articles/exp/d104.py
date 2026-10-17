import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d104'); R = {}
models = "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=20)\n    n = models.IntegerField(default=0)\n"
d = proj('d104', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.db import connection, transaction\nfrom django.db.models.signals import pre_save, post_save, pre_delete, post_delete\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import Item\nLOG = []\ndef on(name):\n    def f(sender, instance=None, created=None, raw=None, update_fields=None, **kw): LOG.append(f'{name}(pk={instance.pk}, created={created}, update_fields={sorted(update_fields) if update_fields else None})')\n    return f\nfor sig, nm in ((pre_save, 'pre_save'), (post_save, 'post_save'), (pre_delete, 'pre_delete'), (post_delete, 'post_delete')): sig.connect(on(nm), sender=Item, weak=False)\ndef trace(fn):\n    LOG.clear()\n    from django.db import connection as c\n    orig = c.execute_wrapper\n    def wrapper(execute, sql, params, many, context): LOG.append('SQL: ' + re.sub(r'\\\\s+', ' ', sql)[:52]); return execute(sql, params, many, context)\n    with c.execute_wrapper(wrapper): fn()\n    return list(LOG)\n" + code); return out.rstrip()
print('== 一:新建对象 save():信号与 SQL 的交错顺序')
o = run("""
for l in trace(lambda: Item(name='a').save()): print('  ', l)
""")
print(o); R['create'] = o
print()
print('== 二:更新已有对象 save() / save(update_fields=[...]):created=False;update_fields 传给信号')
o = run("""
it = Item.objects.create(name='b')
print('save():'); [print('  ', l) for l in trace(lambda: it.save())]
print('save(update_fields=["n"]):'); [print('  ', l) for l in trace(lambda: it.save(update_fields=['n']))]
""")
print(o); R['update'] = o
print()
print('== 三:atomic 里保存:post_save 在 COMMIT 之前触发')
o = run("""
def f():
    with transaction.atomic(): Item(name='c').save(); LOG.append('(atomic 块内最后一行)')
for l in trace(f): print('  ', l)
""")
print(o); R['atomic'] = o
print()
print('== 四:删除:pre_delete / post_delete;queryset.update() 不发信号;get_or_create、update_or_create 里的信号')
o = run("""
it = Item.objects.create(name='d')
print('instance.delete():'); [print('  ', l) for l in trace(lambda: it.delete())]
Item.objects.create(name='e')
print('queryset.update(n=1):', trace(lambda: Item.objects.filter(name='e').update(n=1)))
print('get_or_create(不存在):'); [print('  ', l) for l in trace(lambda: Item.objects.get_or_create(name='f'))]
""")
print(o); R['delete'] = o
print()
print('== 五:pre_save 里能看到什么:新对象 pk 为 None;可以在 pre_save 里改字段,会被写进数据库;post_save 里改字段不会写入')
o = run("""
def touch(sender, instance, **kw): instance.name = instance.name.upper()
pre_save.connect(touch, sender=Item, weak=False, dispatch_uid='upper')
it = Item(name='lower'); it.save(); print('pre_save 里把 name 改成大写 → 库里:', Item.objects.get(pk=it.pk).name)
pre_save.disconnect(sender=Item, dispatch_uid='upper')
def late(sender, instance, **kw): instance.name = 'changed-after'
post_save.connect(late, sender=Item, weak=False, dispatch_uid='late')
it = Item(name='orig'); it.save(); print('post_save 里改 instance.name → 内存里:', it.name, ' 库里:', Item.objects.get(pk=it.pk).name)
""")
print(o); R['mutate'] = o
save('d104', R)
