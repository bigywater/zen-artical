import gc, os, sys, time, tracemalloc, subprocess, collections, json

def rss_mb():
    return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(os.getpid())], capture_output=True, text=True).stdout.strip()) / 1024

class Blob:
    def __init__(self, i): self.i = i; self.payload = bytearray(1000); self.me = None

print("== 一、「泄漏」不是环: 全局容器持有引用, gc.collect() 一个都收不走 ==")
cache = {}
def handle(i): cache[i] = Blob(i)
tracemalloc.start()
for i in range(20000): handle(i)
cur0 = tracemalloc.get_traced_memory()[0] / 1e6
n = gc.collect()
cur1 = tracemalloc.get_traced_memory()[0] / 1e6
print(f"  往全局 cache 里放了 20000 个对象后, Python 占用 {cur0:.1f} MB; gc.collect() 回收了 {n} 个对象, 之后仍占用 {cur1:.1f} MB")
victim = cache[123]
ref = [type(r).__name__ + (f" (长度 {len(r)})" if hasattr(r, '__len__') else '') for r in gc.get_referrers(victim) if r is not globals() and not isinstance(r, type(sys._getframe()))]
print("  gc.get_referrers(cache[123]) 找到的持有者:", ref)
del cache, victim
n = gc.collect(); cur2 = tracemalloc.get_traced_memory()[0] / 1e6
print(f"  del cache 之后 gc.collect() 回收 {n} 个, 占用 {cur2:.1f} MB (释放的是引用, 不是靠 gc)")
tracemalloc.stop()

print("\n== 二、找出「谁在占内存」: 用 gc.get_objects() 做类型直方图 ==")
gc.collect(); before = collections.Counter(type(o).__name__ for o in gc.get_objects())
keep = [Blob(i) for i in range(5000)]
for b in keep: b.me = b            # 每个还自引用
after = collections.Counter(type(o).__name__ for o in gc.get_objects())
diff = {k: after[k] - before.get(k, 0) for k in after if after[k] - before.get(k, 0) > 100}
print("  创建 5000 个自引用 Blob 之后, 数量增加最多的类型:", dict(sorted(diff.items(), key=lambda kv: -kv[1])))
del keep

print("\n== 三、回收了 Python 对象, 进程内存(RSS)不一定还给系统 ==")
gc.collect(); r0 = rss_mb()
objs = [Blob(i) for i in range(200000)]
for o in objs: o.me = o
r1 = rss_mb()
del objs; freed = gc.collect(); r2 = rss_mb()
print(f"  基线 RSS {r0:7.1f} MB → 创建 20 万个 (各带 1000 字节 payload, 自引用) {r1:7.1f} MB → gc.collect() 回收 {freed} 个对象后 {r2:7.1f} MB")
big = bytearray(300 * 1024 * 1024); big[::4096] = b'x' * len(big[::4096]); r3 = rss_mb()
del big; r4 = rss_mb()
print(f"  对照: 申请一块 300 MB 的 bytearray 并写满 {r3:7.1f} MB → del 之后 {r4:7.1f} MB")

print("\n== 四、gc.collect() 本身有多贵: 取决于活着的被追踪对象数量 ==")
res = []
for n in (10_000, 100_000, 1_000_000):
    keep = [[] for _ in range(n)]
    gc.collect(); t = time.perf_counter(); gc.collect(); ms = (time.perf_counter() - t) * 1000
    res.append((n, ms)); print(f"  活着 {n:>9,} 个被追踪对象时, 一次完整 gc.collect() 用时 {ms:8.2f} ms")
    del keep
print("\n== 五、gc.freeze() ==")
keep = [[] for _ in range(1_000_000)]; gc.collect()
t = time.perf_counter(); gc.collect(); before_ms = (time.perf_counter() - t) * 1000
gc.freeze(); t = time.perf_counter(); gc.collect(); after_ms = (time.perf_counter() - t) * 1000
print(f"  100 万个存活对象: freeze 前 gc.collect() {before_ms:.2f} ms → gc.freeze() 之后 {after_ms:.3f} ms;  gc.get_freeze_count() = {gc.get_freeze_count():,}")
gc.unfreeze(); print("  gc.unfreeze() 之后 gc.get_freeze_count() =", gc.get_freeze_count())
json.dump({'res': res, 'freeze': [before_ms, after_ms], 'rss': [r0, r1, r2, r3, r4]}, open('out/85.json', 'w'))
