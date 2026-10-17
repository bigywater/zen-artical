import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d92'); R = {}
d = proj('d92', apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}\n")
def run(code): rc, out = pyscript(d, "import logging, time; logging.disable(logging.CRITICAL)\nfrom django.core.cache import cache\ncache.clear()\n" + code); return out.rstrip()
print('== 一:基本 API:set / get / add / delete / get_or_set / incr / get_many / set_many / touch')
o = run("""
cache.set('a', 1); print("set('a', 1) → get('a') =", cache.get('a'), ' get("nope") =', cache.get('nope'), ' get("nope", "默认") =', cache.get('nope', '默认'))
print("add('a', 2)(已存在)返回", cache.add('a', 2), ' 值仍是', cache.get('a'), '; add("b", 2)(不存在)返回', cache.add('b', 2))
print("get_or_set('c', lambda: 计算) 第一次:", cache.get_or_set('c', lambda: 'computed'), ' 第二次:', cache.get_or_set('c', lambda: 'again'))
print("incr('a') =", cache.incr('a'), ' incr("a", 10) =', cache.incr('a', 10), ' decr =', cache.decr('a'))
try: cache.incr('missing')
except ValueError as e: print("incr('missing') → ValueError:", e)
cache.set_many({'x': 1, 'y': 2}); print("get_many(['x','y','z']) =", cache.get_many(['x', 'y', 'z']))
print("delete('x') 返回", cache.delete('x'), ' 再 delete 返回', cache.delete('x'))
print("has_key('y') =", cache.has_key('y'), "; touch('y', 1) =", cache.touch('y', 1), '; touch 不存在的 =', cache.touch('zzz', 1))
""")
print(o); R['api'] = o
print()
print('== 二:timeout 的语义:默认 300 秒;None 永不过期;0 不缓存;负数立即过期')
o = run("""
from django.conf import settings
print('默认 TIMEOUT =', settings.CACHES['default'].get('TIMEOUT', 300), '秒(未配置时)')
cache.set('t1', 'v', 1); time.sleep(1.1); print('timeout=1 秒,1.1 秒后 get =', cache.get('t1'))
cache.set('t0', 'v', 0); print('timeout=0 之后立刻 get =', cache.get('t0'), '(等于没缓存)')
cache.set('tn', 'v', None); print('timeout=None get =', cache.get('tn'), '(永不过期)')
cache.set('tneg', 'v', -1); print('timeout=-1 立刻 get =', cache.get('tneg'))
cache.set('tshort', 'v', 2); time.sleep(1); cache.touch('tshort', 5); time.sleep(1.5); print('timeout=2 秒,1 秒后 touch(5),又过 1.5 秒(总共 2.5 秒)get =', cache.get('tshort'), '(touch 重置了过期时间)')
""")
print(o); R['timeout'] = o
print()
print('== 三:falsy 值与 None:get 无法区分「没有」和「值就是 None」;哨兵对象')
o = run("""
cache.set('zero', 0); cache.set('empty', ''); cache.set('none', None); cache.set('false', False)
for k in ('zero', 'empty', 'none', 'false', 'absent'): print(f'  get({k!r}) = {cache.get(k)!r}', ' 有这个 key 吗(has_key):', cache.has_key(k))
sentinel = object(); print('  用哨兵区分:', cache.get('none', sentinel) is sentinel, '(存了 None 时仍然返回 None,不是哨兵)', cache.get('absent', sentinel) is sentinel)
""")
print(o); R['falsy'] = o
print()
print('== 四:值是被序列化(pickle)后存的:取出的是副本,改它不会影响缓存里的;在本进程内也一样')
o = run("""
data = {'items': [1, 2]}; cache.set('d', data); data['items'].append(3)
print('set 之后又修改原对象,缓存里的仍是:', cache.get('d'))
got = cache.get('d'); got['items'].append(99); print('取出后修改,再次取:', cache.get('d'))
class NoPickle:
    def __reduce__(self): raise TypeError('cannot pickle NoPickle')
try: cache.set('bad', NoPickle())
except Exception as e: print('不能 pickle 的对象 →', type(e).__name__ + ':', e)
""")
print(o); R['pickle'] = o
save('d92', R)
