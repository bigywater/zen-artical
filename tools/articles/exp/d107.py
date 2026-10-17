import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d107'); R = {}
models = "from django.db import models\nclass Order(models.Model):\n    name = models.CharField(max_length=20)\n    status = models.CharField(max_length=10, default='new')\n    tries = models.IntegerField(default=0)\nclass Log(models.Model):\n    msg = models.CharField(max_length=50)\nclass Stock(models.Model):\n    qty = models.IntegerField(default=10)\n"
d = proj('d107', files={'lab/models.py': models}, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = "import logging, re; logging.disable(logging.CRITICAL)\nfrom django.db import connection, transaction\nfrom django.db.models.signals import post_save\nfrom django.test.utils import CaptureQueriesContext\nfrom lab.models import *\n"
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:看 Order.save() 的调用处,你能知道它会多做什么吗?挂上三个 receiver 后,一次 save() 的查询数')
o = run("""
def n_queries(): 
    with CaptureQueriesContext(connection) as c: Order.objects.create(name='x')
    return len(c)
print('没有 receiver:一次 create() 的查询数', n_queries())
def write_log(sender, instance, created, **kw): Log.objects.create(msg=f'order {instance.pk}')
def dec_stock(sender, instance, created, **kw):
    if created: s = Stock.objects.first() or Stock.objects.create(); s.qty -= 1; s.save()
def audit(sender, instance, created, **kw): Log.objects.create(msg='audit'); Log.objects.create(msg='audit2')
for f in (write_log, dec_stock, audit): post_save.connect(f, sender=Order, weak=False, dispatch_uid=f.__name__)
print('挂上 3 个 receiver 后同一行 create() 的查询数', n_queries(), ' (调用处代码完全没变)')
""")
print(o); R['hidden'] = o
print()
print('== 二:receiver 抛异常 → 调用 save() 的地方拿到异常;没有事务时前面已经写入的部分保留')
o = run("""
def bad(sender, instance, created, **kw): raise RuntimeError('库存服务不可用')
post_save.connect(bad, sender=Order, weak=False, dispatch_uid='bad')
try: Order.objects.create(name='p1')
except RuntimeError as e: print('create() 抛出:', e)
print('没有 atomic:订单已经写入了吗?', Order.objects.filter(name='p1').exists())
try:
    with transaction.atomic(): Order.objects.create(name='p2')
except RuntimeError: pass
print('外面包了 atomic:订单还在吗?', Order.objects.filter(name='p2').exists())
""")
print(o); R['fail'] = o
print()
print('== 三:receiver 里再 save() 同一个对象 → 无限递归')
o = run("""
import sys
def again(sender, instance, created, **kw): instance.tries += 1; instance.save()
post_save.connect(again, sender=Order, weak=False, dispatch_uid='again')
try: Order.objects.create(name='loop')
except RecursionError as e: print('RecursionError:', str(e)[:60], '(递归上限', sys.getrecursionlimit(), ')')
post_save.disconnect(sender=Order, dispatch_uid='again')
def safe(sender, instance, created, **kw):
    if created: Order.objects.filter(pk=instance.pk).update(status='paid')
post_save.connect(safe, sender=Order, weak=False, dispatch_uid='safe')
o = Order.objects.create(name='ok'); print('改用 queryset.update()(不发信号):库里 status =', Order.objects.get(pk=o.pk).status)
""")
print(o); R['loop'] = o
print()
print('== 四:receiver 的执行顺序取决于谁先 connect(也就是导入顺序)')
o = run("""
LOG = []
def a(sender, **kw): LOG.append('a')
def b(sender, **kw): LOG.append('b')
sig = __import__('django.dispatch', fromlist=['Signal']).Signal()
for order in ((a, b), (b, a)):
    sig2 = __import__('django.dispatch', fromlist=['Signal']).Signal()
    for f in order: sig2.connect(f)
    LOG.clear(); sig2.send(sender=None); print('connect 顺序', [f.__name__ for f in order], '→ 执行顺序', LOG)
""")
print(o); R['order'] = o
print()
print('== 五:同样的业务逻辑写成显式的服务函数:调用处一眼可见,测试时不用触发信号')
o = run("""
for dn in ('write_log', 'dec_stock', 'audit', 'bad', 'safe'): post_save.disconnect(sender=Order, dispatch_uid=dn)
def place_order(name):
    with transaction.atomic():
        o = Order.objects.create(name=name); Log.objects.create(msg=f'order {o.pk}'); s = Stock.objects.first() or Stock.objects.create(); s.qty -= 1; s.save()
    return o
with CaptureQueriesContext(connection) as c: place_order('svc')
print('place_order() 查询数:', len(c), '(同样的写入,全部写在一个函数里,调用处能看到)')
""")
print(o); R['service'] = o
save('d107', R)
