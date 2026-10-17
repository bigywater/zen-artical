import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d105'); R = {}
models = "from django.db import models\nclass Item(models.Model):\n    name = models.CharField(max_length=20)\n"
files = {
    'lab/models.py': models,
    'lab/handlers.py': "from django.db.models.signals import post_save\nfrom django.dispatch import receiver\nfrom lab.models import Item\nCOUNT = {'n': 0}\n@receiver(post_save, sender=Item)\ndef on_saved(sender, instance, created, **kw): COUNT['n'] += 1\n",
}
d = proj('d105', files=files, apps=['django.contrib.contenttypes', 'lab'])
manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.db.models.signals import post_save\nfrom django.dispatch import receiver\nfrom lab.models import Item\n" + code); return out.rstrip()
print('== 一:同一个函数对象连接两次 → 只算一次;不同的函数对象(即使代码相同)→ 各算一次')
o = run("""
n = {'c': 0}
def h(sender, **kw): n['c'] += 1
post_save.connect(h, sender=Item, weak=False); post_save.connect(h, sender=Item, weak=False)
Item.objects.create(name='a'); print('同一个 h 连接两次,save 一次触发:', n['c'])
n['c'] = 0
def make():
    def h2(sender, **kw): n['c'] += 1
    return h2
post_save.connect(make(), sender=Item, weak=False); post_save.connect(make(), sender=Item, weak=False)
Item.objects.create(name='b'); print('再连接两个「工厂造出来的相同代码」的函数,共 3 个 receiver 里有效的:', n['c'], '次触发(1 个 h + 2 个新函数)')
""")
print(o); R['identity'] = o
print()
print('== 二:同一个模块被两个不同的名字导入 → 模块代码执行两次,@receiver 装饰的函数是两个对象,信号触发两次')
o = run("""
import sys, importlib
import lab.handlers as h1
print('第一次(lab.handlers)导入后 receiver 数:', len(post_save.receivers))
spec = importlib.util.spec_from_file_location('handlers_again', h1.__file__); h2 = importlib.util.module_from_spec(spec); sys.modules['handlers_again'] = h2; spec.loader.exec_module(h2)
print('用另一个名字(handlers_again)再导入同一个文件后 receiver 数:', len(post_save.receivers))
Item.objects.create(name='dup'); print('保存一次:lab.handlers.COUNT =', h1.COUNT['n'], ' handlers_again.COUNT =', h2.COUNT['n'])
""")
print(o); R['twice'] = o
print()
print('== 三:dispatch_uid 让「不管导入几次」都只连接一次')
o = run("""
import sys, importlib
n = {'c': 0}
src = "from django.db.models.signals import post_save\\nfrom django.dispatch import receiver\\nfrom lab.models import Item\\n@receiver(post_save, sender=Item, dispatch_uid='my-unique-handler')\\ndef on_saved(sender, **kw): N['c'] += 1\\n"
for i in range(3):
    mod = type(sys)('m%d' % i); mod.N = n; exec(src, mod.__dict__)
Item.objects.create(name='u'); print('同一段代码执行 3 次(模拟重复导入),dispatch_uid 相同 → 保存一次触发:', n['c'])
""")
print(o); R['uid'] = o
print()
print('== 四:AppConfig.ready() 被调用多次的情形:runserver 的两个进程各有各的 receivers,不重复;同一进程里 ready() 里 connect 不带 dispatch_uid 的 lambda / 局部函数会累加')
o = run("""
before = len(post_save.receivers)
for i in range(3):
    post_save.connect(lambda sender, **kw: None, sender=Item, weak=False)
print('在「ready()」里 connect 一个 lambda,连续执行 3 次 → receiver 增加了', len(post_save.receivers) - before, '个(每个 lambda 都是新对象)')
""")
print(o); R['ready'] = o
save('d105', R)
