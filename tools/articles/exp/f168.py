import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f168'); R = {}
import random, bisect, itertools, redis as redis_lib
from cachelib import SimpleCache
random.seed(7)
KEYS = 5000; REQ = 20000
w = [1 / (i + 1) for i in range(KEYS)]; cum = list(itertools.accumulate(w)); tot = cum[-1]
zipf = [bisect.bisect(cum, random.random() * tot) for _ in range(REQ)]; uni = [random.randrange(KEYS) for _ in range(REQ)]
top = collections = None
import collections
cnt = collections.Counter(zipf); print(f'  Zipf 访问序列:{REQ} 个请求落在 {KEYS} 个 key 上,最热的 key 占 {cnt.most_common(1)[0][1] / REQ * 100:.1f}%,前 100 个 key 占 {sum(c for _, c in cnt.most_common(100)) / REQ * 100:.1f}%,前 500 个占 {sum(c for _, c in cnt.most_common(500)) / REQ * 100:.1f}%')
R['zipf'] = [cnt.most_common(1)[0][1] / REQ, sum(c for _, c in cnt.most_common(100)) / REQ, sum(c for _, c in cnt.most_common(500)) / REQ]
MISS_MS, HIT_MS = 5.0, 0.05
def run(seq, threshold, timeout=0, clock_step=0.0):
    import cachelib.simple as cs_; now = [1000.0]; real = cs_.time; cs_.time = lambda: now[0]
    try:
        c = SimpleCache(threshold=threshold, default_timeout=timeout or 0); hits = misses = 0
        for k in seq:
            now[0] += clock_step
            if c.get(f'k{k}') is not None: hits += 1
            else: misses += 1; c.set(f'k{k}', 1, timeout=timeout or 0)
    finally: cs_.time = real
    return hits / len(seq), hits, misses
print()
print('== 一:缓存容量(SimpleCache 的 threshold,超过就清理)对命中率的影响:Zipf 访问,不过期')
print(f'  {"容量":>6} {"命中率":>7} {"平均耗时(未命中 5 ms,命中 0.05 ms)":>36}')
R['cap'] = {}
for cap in (100, 500, 2000, 5000):
    hr, h, m = run(zipf, cap); avg = hr * HIT_MS + (1 - hr) * MISS_MS; print(f'  {cap:>6} {hr * 100:>6.1f}% {avg:>30.2f} ms'); R['cap'][cap] = [hr, avg]
print()
print('== 二:访问分布:同样容量 500,Zipf(有热点)vs 均匀随机')
R['dist'] = {}
for label, seq in (('Zipf(有热点)', zipf), ('均匀随机', uni)):
    hr, h, m = run(seq, 500); print(f'  {label:<14} 命中率 {hr * 100:.1f}%'); R['dist'][label] = hr
print()
print('== 三:过期时间 TTL:Zipf 访问,容量足够(5000),模拟时钟每个请求前进 1 ms(20000 个请求 = 20 秒);注意:SimpleCache 用 int(time()) + TTL 算到期时间(源码如此),亚秒级的 TTL 没有意义')
R['ttl'] = {}
for ttl in (0.05, 0.5, 1, 2, 5, 10, 0):
    hr, h, m = run(zipf, 5000, timeout=ttl, clock_step=0.001); lab = '不过期' if ttl == 0 else f'{ttl} 秒'; print(f'  TTL {lab:<8} 命中率 {hr * 100:.1f}%'); R['ttl'][lab] = hr
print()
print('== 四:同一个访问序列放到真实的 redis(自己起,maxmemory 很小 + allkeys-lru),对照 redis 自己统计的 keyspace_hits / misses')
RP = 9655; rdir = FT / 'f168_redis'; shutil.rmtree(rdir, ignore_errors=True); rdir.mkdir(parents=True)
rproc = subprocess.Popen(['/opt/homebrew/bin/redis-server', '--port', str(RP), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(rdir), '--maxmemory', '1300kb', '--maxmemory-policy', 'allkeys-lru'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try: redis_lib.Redis(port=RP).ping(); break
    except Exception: time.sleep(0.1)
try:
    r = redis_lib.Redis(port=RP); r.flushall(); r.config_resetstat(); hits = 0; payload = b'x' * 100
    for k in zipf:
        if r.get(f'k{k}') is not None: hits += 1
        else: r.set(f'k{k}', payload)
    info = r.info(); st = r.info('stats'); mem = r.info('memory'); print(f'  应用侧统计命中率 {hits / REQ * 100:.1f}% | redis 的 keyspace_hits {st["keyspace_hits"]}、keyspace_misses {st["keyspace_misses"]} → {st["keyspace_hits"] / (st["keyspace_hits"] + st["keyspace_misses"]) * 100:.1f}% | evicted_keys {st["evicted_keys"]} | 当前 key 数 {r.dbsize()},已用内存 {mem["used_memory_human"]}')
    R['redis'] = [hits / REQ, st['keyspace_hits'], st['keyspace_misses'], st['evicted_keys'], r.dbsize()]
finally: rproc.terminate(); rproc.wait(5)
save('f168', R)
