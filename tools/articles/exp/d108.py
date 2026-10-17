import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d108'); R = {}
d = proj('d108', apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging, asyncio; logging.disable(logging.CRITICAL)\nfrom django.dispatch import Signal, receiver\n" + code); return out.rstrip()
print('== 一:定义与发送(Django 6.1.1):Signal() 不带参数;providing_args 在 4.0 已移除')
o = run("""
order_paid = Signal()
LOG = []
@receiver(order_paid)
def send_email(sender, order_id, amount, **kw): LOG.append(f'email 订单 {order_id} 金额 {amount}'); return 'ok'
res = order_paid.send(sender='shop', order_id=7, amount=99)
print(LOG, [(f.__name__, v) for f, v in res])
try: Signal(providing_args=['order_id'])
except TypeError as e: print('Signal(providing_args=[...]) → TypeError:', e)
""")
print(o); R['define'] = o
print()
print('== 二:sender 传类还是传字符串:receiver 用 sender=... 做匹配时按「相等」比较')
o = run("""
class Shop: pass
sig = Signal(); LOG = []
sig.connect(lambda sender, **kw: LOG.append('for Shop'), sender=Shop, weak=False)
sig.connect(lambda sender, **kw: LOG.append("for 'shop'"), sender='shop', weak=False)
sig.send(sender=Shop); print('sender=Shop 类:', LOG); LOG.clear(); sig.send(sender='shop'); print("sender='shop' 字符串:", LOG); LOG.clear(); sig.send(sender=Shop()); print('sender=Shop() 实例:', LOG)
""")
print(o); R['sender'] = o
print()
print('== 三:async receiver:send() 会同步调用 async receiver(内部在事件循环里跑);asend() 在协程里并发执行 async receiver')
o = run("""
import time
sig = Signal(); LOG = []
async def slow_async(sender, **kw): await asyncio.sleep(0.2); LOG.append('async done'); return 'a'
def slow_sync(sender, **kw): time.sleep(0.2); LOG.append('sync done'); return 's'
sig.connect(slow_async); sig.connect(slow_sync)
t0 = time.perf_counter(); res = sig.send(sender=None); print(f'send()  同步调用 → {time.perf_counter() - t0:.2f} s,返回', [(f.__name__, v) for f, v in res])
LOG.clear()
async def main():
    t0 = time.perf_counter(); res = await sig.asend(sender=None); print(f'asend() 协程里调用 → {time.perf_counter() - t0:.2f} s,返回', [(f.__name__, v) for f, v in res])
asyncio.run(main())
""")
print(o); R['async'] = o
print()
print('== 四:send_robust 对自定义信号:一个 receiver 失败不影响其余;响应里带异常对象,可以记日志')
o = run("""
sig = Signal()
def ok(sender, **kw): return 'fine'
def bad(sender, **kw): raise KeyError('missing')
sig.connect(ok); sig.connect(bad)
for f, v in sig.send_robust(sender=None): print(' ', f.__name__, '→', repr(v), '(是异常对象)' if isinstance(v, Exception) else '')
""")
print(o); R['robust'] = o
save('d108', R)
