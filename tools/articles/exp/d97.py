import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d97'); R = {}
d = proj('d97', apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}\n")
pre = """
import logging, time, threading, statistics; logging.disable(logging.CRITICAL)
from django.core.cache import cache
COMPUTES = {'n': 0}; CL = threading.Lock()
def compute(delay=0.1):
    with CL: COMPUTES['n'] += 1; n = COMPUTES['n']
    time.sleep(delay); return 'result-%d' % n
def run_threads(fn, n):
    ts = [threading.Thread(target=fn, args=(i,)) for i in range(n)]; t0 = time.perf_counter(); [t.start() for t in ts]; [t.join() for t in ts]; return time.perf_counter() - t0
cache.clear()
"""
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:get_or_set 不是并发安全的「只算一次」:20 个线程同时对一个不存在的 key 调用')
o = run("""
res = []
def w(i): res.append(cache.get_or_set('k', lambda: compute(0.1), 60))
dt = run_threads(w, 20)
print('compute 被执行了', COMPUTES['n'], '次;返回了', len(set(res)), '个不同的值:', sorted(set(res))[:5], ' 缓存里最终留下:', cache.get('k'))
""")
print(o); R['get_or_set'] = o
print()
print('== 二:用 add 做互斥,只让一个线程计算;其它线程等它算完')
o = run("""
COMPUTES['n'] = 0; cache.clear()
def get_once(i):
    v = cache.get('k2')
    if v is not None: return v
    if cache.add('lock:k2', 1, 5):
        try: v = compute(0.1); cache.set('k2', v, 60)
        finally: cache.delete('lock:k2')
        return v
    for _ in range(100):
        time.sleep(0.01); v = cache.get('k2')
        if v is not None: return v
res = []
def w(i): res.append(get_once(i))
dt = run_threads(w, 20)
print('compute 被执行了', COMPUTES['n'], '次;所有线程拿到同一个值:', len(set(res)) == 1, ';总耗时 %.0f ms' % (dt * 1000))
""")
print(o); R['lock'] = o
print()
print('== 三:过期瞬间的等待:计算耗时 200 ms 的值,TTL 1 秒。持续请求 4 秒,阻塞式回源 vs 「过期后先返回旧值、后台刷新」(stale-while-revalidate)')
o = run("""
def blocking():
    cache.clear(); COMPUTES['n'] = 0; lat = []; stop = time.perf_counter() + 4
    def get():
        v = cache.get('b')
        if v is None: v = compute(0.2); cache.set('b', v, 1)
        return v
    def w(i):
        while time.perf_counter() < stop:
            t0 = time.perf_counter(); get(); lat.append((time.perf_counter() - t0) * 1000); time.sleep(0.02)
    run_threads(w, 4); return lat, COMPUTES['n']
def swr():
    cache.clear(); COMPUTES['n'] = 0; lat = []; stop = time.perf_counter() + 4; state = {'refreshing': False}
    def refresh():
        v = compute(0.2); cache.set('s', (v, time.time() + 1), 60); state['refreshing'] = False
    def get():
        item = cache.get('s')
        if item is None: v = compute(0.2); cache.set('s', (v, time.time() + 1), 60); return v
        v, soft = item
        if time.time() > soft and not state['refreshing']:
            state['refreshing'] = True; threading.Thread(target=refresh).start()
        return v
    def w(i):
        while time.perf_counter() < stop:
            t0 = time.perf_counter(); get(); lat.append((time.perf_counter() - t0) * 1000); time.sleep(0.02)
    run_threads(w, 4); time.sleep(0.3); return lat, COMPUTES['n']
for label, fn in (('阻塞式回源', blocking), ('stale-while-revalidate', swr)):
    lat, n = fn(); lat.sort(); print(f'  {label:<24} 请求 {len(lat)} 次;计算 {n} 次;p50 {statistics.median(lat):.2f} ms;p99 {lat[int(len(lat) * .99)]:.1f} ms;最慢 {lat[-1]:.0f} ms')
""")
print(o); R['swr'] = o
print()
print('== 四:set 会重置过期时间(滑动过期需要自己 touch);缓存值比 TTL 更早被替换时的「旧值写回」竞态')
o = run("""
cache.set('s1', 'a', 2); time.sleep(1.2); cache.set('s1', 'a2', 2); time.sleep(1.2); print('set 后 1.2s 再 set(2s),再过 1.2s(距第一次 2.4s):', cache.get('s1'), '(第二次 set 重置了 TTL)')
cache.set('lost', 'v0', 60)
def slow_writer():
    v = cache.get('lost'); time.sleep(0.3); cache.set('lost', v + '+writer', 60)
t = threading.Thread(target=slow_writer); t.start(); time.sleep(0.05); cache.set('lost', 'v1-from-other', 60); t.join()
print('读-改-写竞态:另一个线程在中间写入了 v1-from-other,最终 =', cache.get('lost'), ' ← 覆盖了对方的写入(lost update)')
""")
print(o); R['ttl'] = o
save('d97', R)
