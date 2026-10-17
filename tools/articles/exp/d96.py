import sys, os, time, json, re, threading, random, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d96'); R = {}
d = proj('d96', apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nCACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'OPTIONS': {'MAX_ENTRIES': 100000}}}\n")
pre = """
import logging, time, threading, random, collections; logging.disable(logging.CRITICAL)
from django.core.cache import cache
DB = {'calls': 0, 'stamps': []}
LOCK = threading.Lock()
def db_load(key):
    with LOCK: DB['calls'] += 1; DB['stamps'].append(time.perf_counter())
    time.sleep(0.05)
    return None if key.startswith('missing') else 'value-of-' + key
def run_threads(fn, n):
    ts = [threading.Thread(target=fn, args=(i,)) for i in range(n)]; t0 = time.perf_counter(); [t.start() for t in ts]; [t.join() for t in ts]; return time.perf_counter() - t0
cache.clear()
"""
def run(code): rc, out = pyscript(d, pre + code); return out.rstrip()
print('== 一:缓存穿透:请求的数据本来就不存在,每次都穿过缓存打到数据库')
o = run("""
def get_naive(key):
    v = cache.get(key)
    if v is None:
        v = db_load(key)
        if v is not None: cache.set(key, v, 60)
    return v
def get_negative(key):
    v = cache.get(key)
    if v is None:
        v = db_load(key); cache.set(key, v if v is not None else '__NONE__', 60 if v is not None else 10)
    return None if v == '__NONE__' else v
for label, fn in (('不缓存空结果', get_naive), ('缓存空结果(短 TTL)', get_negative)):
    cache.clear(); DB['calls'] = 0
    for i in range(100): fn('missing:1')
    print(f'  {label:<18} 对同一个不存在的 key 请求 100 次 → 数据库调用 {DB["calls"]} 次')
cache.clear(); DB['calls'] = 0
for i in range(100): get_negative('missing:%d' % i)
print(f'  缓存空结果,但每次请求的 key 都不同(随机 key 攻击)→ 数据库调用 {DB["calls"]} 次(空值缓存挡不住,需要布隆过滤器或参数校验,本文没有测)')
""")
print(o); R['penetration'] = o
print()
print('== 二:缓存击穿:一个热点 key 过期的瞬间,50 个并发请求同时回源')
o = run("""
def get_plain(key):
    v = cache.get(key)
    if v is None: v = db_load(key); cache.set(key, v, 60)
    return v
def get_locked(key):
    v = cache.get(key)
    if v is not None: return v
    lock = 'lock:' + key
    if cache.add(lock, 1, 5):
        try:
            v = db_load(key); cache.set(key, v, 60)
        finally: cache.delete(lock)
        return v
    for _ in range(100):
        time.sleep(0.01); v = cache.get(key)
        if v is not None: return v
    return db_load(key)
for label, fn in (('无保护', get_plain), ('互斥锁(cache.add)', get_locked)):
    cache.clear(); DB['calls'] = 0; lat = []
    def w(i):
        t0 = time.perf_counter(); fn('hot'); lat.append((time.perf_counter() - t0) * 1000)
    dt = run_threads(w, 50); print(f'  {label:<18} 热点 key 已过期,50 个并发请求 → 数据库调用 {DB["calls"]:>2} 次;最慢一次 {max(lat):.0f} ms;总耗时 {dt * 1000:.0f} ms')
""")
print(o); R['breakdown'] = o
print()
print('== 三:缓存雪崩:大量 key 同一时刻过期 → 数据库瞬间被打;TTL 加随机抖动可以摊开')
o = run("""
N = 300
def experiment(label, jitter):
    cache.clear(); DB['calls'] = 0; DB['stamps'].clear()
    for i in range(N): cache.set('k%d' % i, 'v', 1.5 + (random.uniform(-1.0, 1.0) if jitter else 0))
    stop = time.perf_counter() + 4.0; t_start = time.perf_counter()
    def w(_):
        rnd = random.Random()
        while time.perf_counter() < stop:
            k = 'k%d' % rnd.randrange(N)
            if cache.get(k) is None: v = db_load(k); cache.set(k, v, 1.5 + (rnd.uniform(-1.0, 1.0) if jitter else 0))
            time.sleep(0.002)
    run_threads(w, 40)
    buckets = collections.Counter(int((s - t_start) / 0.25) for s in DB['stamps'])
    peak = max(buckets.values()); print(f'  {label:<12} 4 秒内数据库调用共 {DB["calls"]} 次;每 250 ms 窗口的最高调用数 {peak}(窗口序列前 16 个:{[buckets.get(i, 0) for i in range(16)]})')
    return DB['calls'], peak
r1 = experiment('相同 TTL', False); r2 = experiment('TTL 抖动 ±1s', True)
""")
print(o); R['avalanche'] = o
save('d96', R)
