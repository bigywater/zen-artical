import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d120'); R = {}
models = "from django.db import models\nclass Order(models.Model):\n    name = models.CharField(max_length=20)\n"
tests = '''
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from lab.models import Order
class T(TestCase):
    def test_plain(self):
        ran = []
        with transaction.atomic():
            Order.objects.create(name='t'); transaction.on_commit(lambda: ran.append('cb'))
        print('  [TestCase]                   atomic 块结束后回调是否执行:', ran)
    def test_capture(self):
        ran = []
        with self.captureOnCommitCallbacks(execute=True) as cbs:
            with transaction.atomic():
                Order.objects.create(name='t'); transaction.on_commit(lambda: ran.append('cb'))
        print('  [captureOnCommitCallbacks]   捕获到', len(cbs), '个回调,execute=True 后 ran =', ran)
class TT(TransactionTestCase):
    def test_tt(self):
        ran = []
        with transaction.atomic():
            Order.objects.create(name='t'); transaction.on_commit(lambda: ran.append('cb'))
        print('  [TransactionTestCase]        atomic 块结束后回调是否执行:', ran)
'''
d = proj('d120', files={'lab/models.py': models, 'lab/tests.py': tests}, apps=['django.contrib.contenttypes', 'lab'], middleware=[])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging\nREC = []\nclass H(logging.Handler):\n    def emit(self, r): REC.append(r.getMessage())\nlg = logging.getLogger('django.db.backends.base'); lg.addHandler(H()); lg.propagate = False\nfrom django.db import transaction, connection\nfrom lab.models import Order\nLOG = []\n" + code); return out.rstrip()
print('== 一:多个回调:按注册顺序、提交之后执行;autocommit(没有 atomic)时立刻执行')
o = run("""
with transaction.atomic():
    transaction.on_commit(lambda: LOG.append('A')); transaction.on_commit(lambda: LOG.append('B')); LOG.append('块内最后一行')
print('  atomic 里注册 A、B:', LOG)
LOG.clear(); transaction.on_commit(lambda: LOG.append('C')); LOG.append('注册之后的下一行'); print('  没有 atomic 时注册 C:', LOG)
""")
print(o); R['order'] = o
print()
print('== 二:回调抛异常:默认的后果 vs robust=True;数据已经提交')
o = run("""
def bad(): raise RuntimeError('通知服务挂了')
LOG.clear()
try:
    with transaction.atomic():
        Order.objects.create(name='o1'); transaction.on_commit(lambda: LOG.append('first')); transaction.on_commit(bad); transaction.on_commit(lambda: LOG.append('third'))
except RuntimeError as e: print('  atomic 退出时抛出:', e)
print('  已执行的回调:', LOG, '(third 没有执行)  订单已提交:', Order.objects.filter(name='o1').exists())
LOG.clear()
with transaction.atomic():
    Order.objects.create(name='o2'); transaction.on_commit(lambda: LOG.append('first')); transaction.on_commit(bad, robust=True); transaction.on_commit(lambda: LOG.append('third'))
print('  robust=True:atomic 正常退出,已执行的回调:', LOG)
print('  django.db.backends.base 的错误日志:', REC)
""")
print(o); R['robust'] = o
print()
print('== 三:savepoint(嵌套 atomic)回滚:里面注册的回调被丢弃;外层提交时执行其余的')
o = run("""
with transaction.atomic():
    transaction.on_commit(lambda: LOG.append('outer'))
    try:
        with transaction.atomic():
            transaction.on_commit(lambda: LOG.append('inner(将回滚)')); raise ValueError('inner fails')
    except ValueError: pass
    with transaction.atomic(): transaction.on_commit(lambda: LOG.append('inner2(成功)'))
print('  执行了:', LOG)
LOG.clear()
try:
    with transaction.atomic(): transaction.on_commit(lambda: LOG.append('x')); raise ValueError
except ValueError: pass
print('  外层整体回滚:执行了', LOG)
""")
print(o); R['savepoint'] = o
print()
print('== 四:测试里的 on_commit(manage.py test)')
rc, out = manage(d, 'test', 'lab', '-v', '0')
o = '\n'.join(l for l in out.splitlines() if l.startswith('  [')); print(o); R['tests'] = o
save('d120', R)
