import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d103'); R = {}
d = proj('d103', apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging, time, statistics; logging.disable(logging.CRITICAL)\nfrom django.dispatch import Signal, receiver\n" + code); return out.rstrip()
print('== 一:send():按连接顺序依次调用,返回 [(receiver, response), …];receiver 必须接受 **kwargs')
o = run("""
sig = Signal(); LOG = []
def r1(sender, **kw): LOG.append('r1'); return 'from r1'
def r2(sender, x=None, **kw): LOG.append(f'r2(x={x})'); return 'from r2'
sig.connect(r1); sig.connect(r2)
res = sig.send(sender='S', x=42)
print('调用顺序:', LOG); print('send() 返回:', [(f.__name__, v) for f, v in res])
def bad(sender): pass
try: sig.connect(bad)
except ValueError as e: print('connect 一个没有 **kwargs 的函数 →', type(e).__name__ + ':', str(e)[:80])
""")
print(o); R['basic'] = o
print()
print('== 二:sender 过滤:只对指定的发送者生效')
o = run("""
class A: pass
class B: pass
sig = Signal(); LOG = []
def only_a(sender, **kw): LOG.append('only_a')
def any_sender(sender, **kw): LOG.append('any')
sig.connect(only_a, sender=A); sig.connect(any_sender)
sig.send(sender=A); print('sender=A:', LOG); LOG.clear(); sig.send(sender=B); print('sender=B:', LOG)
""")
print(o); R['sender'] = o
print()
print('== 三:receiver 抛异常:send() 直接抛出、后面的 receiver 不再执行;send_robust() 捕获并返回异常')
o = run("""
sig = Signal(); LOG = []
def ok1(sender, **kw): LOG.append('ok1'); return 1
def boom(sender, **kw): LOG.append('boom'); raise ValueError('receiver failed')
def ok2(sender, **kw): LOG.append('ok2'); return 2
for f in (ok1, boom, ok2): sig.connect(f)
try: sig.send(sender=None)
except ValueError as e: print('send() 抛出:', e, ' 已执行:', LOG)
LOG.clear(); res = sig.send_robust(sender=None); print('send_robust() 已执行:', LOG); print('  返回:', [(f.__name__, repr(v)) for f, v in res])
""")
print(o); R['errors'] = o
print()
print('== 四:dispatch_uid 防止重复连接;disconnect;@receiver 装饰器;同一个函数连接两次')
o = run("""
sig = Signal(); LOG = []
def f(sender, **kw): LOG.append('f')
sig.connect(f); sig.connect(f); sig.send(None); print('同一个函数 connect 两次,send 一次调用', len(LOG), '次')
LOG.clear(); sig2 = Signal()
sig2.connect(f, dispatch_uid='x'); sig2.connect(f, dispatch_uid='x'); sig2.connect(f, dispatch_uid='y'); sig2.send(None); print('用了 dispatch_uid: x, x, y → 调用', len(LOG), '次(x 只算一个)')
LOG.clear(); print('disconnect(dispatch_uid="x") 返回', sig2.disconnect(dispatch_uid='x')); sig2.send(None); print('之后调用', len(LOG), '次')
@receiver(sig)
def deco(sender, **kw): LOG.append('deco')
LOG.clear(); sig.send(None); print('@receiver 装饰器连接后调用:', LOG)
""")
print(o); R['uid'] = o
print()
print('== 五:开销:一次 send() 的耗时随 receiver 数量(10 万次取平均)')
o = run("""
def bench(n_recv, n=100000):
    sig = Signal(); 
    for i in range(n_recv):
        def r(sender, **kw): pass
        sig.connect(r, weak=False)
    t0 = time.perf_counter()
    for _ in range(n): sig.send(sender=None)
    return (time.perf_counter() - t0) / n * 1e6
for k in (0, 1, 5, 20): print(f'  {k:>2} 个 receiver:每次 send {bench(k):6.2f} µs')
""")
print(o); R['cost'] = o
save('d103', R)
