import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d109'); R = {}
d = proj('d109', apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging, gc; logging.disable(logging.CRITICAL)\nfrom django.dispatch import Signal\n" + code); return out.rstrip()
print('== 一:默认 weak=True:局部函数 receiver 在函数返回、gc.collect() 之后,信号还能不能调到它?')
o = run("""
sig = Signal(); LOG = []
def setup():
    def local(sender, **kw): LOG.append('local called')
    sig.connect(local)
setup(); gc.collect()
sig.send(sender=None); print('setup() 返回并 gc.collect() 之后 send:LOG =', LOG)
""")
print(o); R['local'] = o
print()
print('== 二:为什么没被回收?Django 在 connect 时用 functools.lru_cache(maxsize=512) 缓存函数签名,缓存把函数强引用住了;把这个缓存冲掉之后才会被回收')
o = run("""
from django.utils.inspect import _get_func_parameters as cache
sig = Signal(); LOG = []
def setup():
    def local(sender, **kw): LOG.append('local called')
    sig.connect(local)
setup(); gc.collect()
print('缓存现状:', cache.cache_info())
other = Signal()
for i in range(600):
    def f(sender, i=i, **kw): pass
    other.connect(f, weak=False)
gc.collect()
print('再 connect 600 个别的函数后:', cache.cache_info())
print('send:', sig.send(sender=None), ' LOG =', LOG, ' receivers =', len(sig.receivers))
""")
print(o); R['cache'] = o
print()
print('== 三:lambda、functools.partial、模块级函数:gc.collect() 之后是否都还能被调到')
o = run("""
import functools
sig = Signal(); LOG = []
sig.connect(lambda sender, **kw: LOG.append('lambda'))
def h(sender, tag=None, **kw): LOG.append(tag)
sig.connect(functools.partial(h, tag='partial'))
def mod_level(sender, **kw): LOG.append('module-level')
sig.connect(mod_level)
gc.collect(); sig.send(sender=None); print('被调用的:', LOG)
""")
print(o); R['lambda'] = o
print()
print('== 四:绑定方法:弱引用的是对象本身——对象销毁后 receiver 自动消失(不需要 disconnect)')
o = run("""
class Handler:
    def __init__(self): self.n = 0
    def on(self, sender, **kw): self.n += 1
sig = Signal(); hnd = Handler(); sig.connect(hnd.on)
sig.send(sender=None); print('对象存在:n =', hnd.n, ' receivers =', len(sig.receivers))
del hnd; gc.collect()
print('对象 del 之后 send() 返回:', sig.send(sender=None), ' receivers =', len(sig.receivers))
""")
print(o); R['method'] = o
print()
print('== 五:弱引用的 receiver 如果被对象持有,会阻止那个对象被回收吗?(strong=False 时不会)')
o = run("""
import weakref
class Handler:
    def on(self, sender, **kw): pass
for weak in (True, False):
    sig = Signal(); h = Handler(); w = weakref.ref(h); sig.connect(h.on, weak=weak); del h; gc.collect()
    print(f'weak={weak}: 删除对象引用后对象是否已被回收:', w() is None)
""")
print(o); R['leak'] = o
save('d109', R)
