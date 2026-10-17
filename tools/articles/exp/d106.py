import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d106'); R = {}
pg = PG(9471).start()
models = "from django.db import models\nclass Order(models.Model):\n    name = models.CharField(max_length=20)\n"
d = proj('d106', files={'lab/models.py': models}, databases=pg.databases(), apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
pre = """
import logging, threading, time; logging.disable(logging.CRITICAL)
from django.db import connection, connections, transaction
from django.db.models.signals import post_save
from lab.models import Order
def visible_elsewhere(pk):
    out = []
    def w():
        out.append(Order.objects.filter(pk=pk).exists()); connections.close_all()
    t = threading.Thread(target=w); t.start(); t.join(); return out[0]
EVENTS = []
def on_saved(sender, instance, created, **kw):
    EVENTS.append(f'post_save 触发:另一个连接能看到这一行吗?{visible_elsewhere(instance.pk)}')
    transaction.on_commit(lambda: EVENTS.append(f'on_commit 回调:另一个连接能看到吗?{visible_elsewhere(instance.pk)}'))
post_save.connect(on_saved, sender=Order, weak=False)
"""
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:atomic 里保存对象:post_save 触发时数据对别的连接还不可见;on_commit 里才可见')
o = run("""
with transaction.atomic():
    o = Order.objects.create(name='a'); EVENTS.append('create() 返回')
EVENTS.append('atomic 块退出(已提交)')
for e in EVENTS: print('  ', e)
""")
print(o); R['visible'] = o
print()
print('== 二:事务回滚了,post_save 里做过的事(比如发通知)已经发生,收不回来')
o = run("""
SENT = []
def notify(sender, instance, created, **kw): SENT.append(f'已通知外部系统:订单 {instance.pk} 创建')
post_save.connect(notify, sender=Order, weak=False, dispatch_uid='notify')
EVENTS.clear()
try:
    with transaction.atomic():
        o = Order.objects.create(name='will-rollback'); raise RuntimeError('后面的步骤失败了')
except RuntimeError: pass
print('事务回滚后,库里这个订单存在吗:', Order.objects.filter(name='will-rollback').exists(), ' | 外部通知列表:', SENT)
print('on_commit 版本的回调有没有执行:', [e for e in EVENTS if 'on_commit' in e] or '没有(回滚后不会执行)')
""")
print(o); R['rollback'] = o
print()
print('== 三:把「通知」改成 on_commit:回滚时不发,提交后才发')
o = run("""
SENT = []
post_save.disconnect(on_saved, sender=Order)
def notify_commit(sender, instance, created, **kw):
    transaction.on_commit(lambda: SENT.append(f'提交后通知:订单 {instance.pk}'))
post_save.connect(notify_commit, sender=Order, weak=False, dispatch_uid='nc')
try:
    with transaction.atomic(): Order.objects.create(name='r1'); raise RuntimeError('fail')
except RuntimeError: pass
print('回滚:', SENT)
with transaction.atomic(): Order.objects.create(name='r2')
print('提交:', SENT)
""")
print(o); R['oncommit'] = o
print()
print('== 四:没有 atomic(autocommit)时:每条 save 自己提交,post_save 在提交之后(此时另一个连接能看到)')
o = run("""
EVENTS.clear(); o = Order.objects.create(name='auto')
for e in EVENTS: print('  ', e)
""")
print(o); R['auto'] = o
pg.stop(); save('d106', R)
