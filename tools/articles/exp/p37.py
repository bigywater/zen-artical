import sys, os, math, hashlib, struct, tracemalloc, zlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p37')
N = 1_000_000; Q = 200_000
def url(i): return f'http://shop.test/category/{i % 977}/item/{i}?id={i * 7919 % 1000003}&ref=list'

class Bloom:
    def __init__(self, n, p):
        self.m = int(-n * math.log(p) / (math.log(2) ** 2)); self.k = max(1, round(self.m / n * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8); self.n = 0
    def _idx(self, s):
        h = hashlib.blake2b(s.encode(), digest_size=16).digest(); a, b = struct.unpack('<QQ', h); b |= 1
        m = self.m
        return [(a + i * b) % m for i in range(self.k)]
    def add(self, s):
        bits = self.bits
        for x in self._idx(s): bits[x >> 3] |= 1 << (x & 7)
        self.n += 1
    def __contains__(self, s):
        bits = self.bits
        return all(bits[x >> 3] & (1 << (x & 7)) for x in self._idx(s))
    def theory(self, n=None):
        n = n or self.n; return (1 - math.exp(-self.k * n / self.m)) ** self.k

def build(kind):
    if kind == 'set_str': return {url(i) for i in range(N)}
    if kind == 'set_md5': return {hashlib.md5(url(i).encode()).digest() for i in range(N)}
    if kind == 'set_int64': return {int.from_bytes(hashlib.blake2b(url(i).encode(), digest_size=8).digest(), 'little') for i in range(N)}
    if kind == 'set_int32': return {zlib.crc32(url(i).encode()) for i in range(N)}

print(f'== 一:存 {N:,} 个 URL(每个约 {len(url(123456))} 个字符)的内存:只算数据结构本身(tracemalloc,URL 字符串是边生成边放进去的)')
print(f'  {"结构":<34}{"内存":>10}{"平均每个 URL":>14}')
sizes = {}
for kind, lab in (('set_str', 'set 里存完整 URL 字符串'), ('set_md5', 'set 里存 16 字节 MD5 摘要'), ('set_int64', 'set 里存 64 位整数哈希'), ('set_int32', 'set 里存 32 位整数(crc32)')):
    tracemalloc.start(); t0 = time.perf_counter(); s = build(kind); cur, _ = tracemalloc.get_traced_memory(); tracemalloc.stop()
    sizes[kind] = cur; print(f'  {lab:<30}{cur / 1048576:>8.1f} MiB{cur / N:>11.1f} 字节   (构建 {time.perf_counter() - t0:.1f} 秒,集合里 {len(s):,} 个元素)'); del s
blooms = {}
for p in (0.01, 0.001):
    t0 = time.perf_counter(); b = Bloom(N, p)
    for i in range(N): b.add(url(i))
    el = time.perf_counter() - t0; blooms[p] = b
    print(f'  Bloom 过滤器(目标误判率 {p * 100:g}%,m={b.m:,} 位,k={b.k})   {len(b.bits) / 1048576:>6.1f} MiB{len(b.bits) / N:>11.2f} 字节   (构建 {el:.1f} 秒)')

print(f'== 二:误判率实测:再用 {Q:,} 个从没放进去过的 URL 去问"见过吗"')
def fp(contains, off=10_000_000): return sum(1 for i in range(off, off + Q) if contains(url(i))) / Q
for p, b in blooms.items():
    obs = fp(b.__contains__)
    print(f'  Bloom(目标 {p * 100:g}%):实测误判 {obs * 100:.3f}%(按公式 (1-e^(-kn/m))^k 的理论值 {b.theory() * 100:.3f}%),{int(obs * Q)} / {Q:,} 个没见过的 URL 被误认为"已抓过"')
s32 = build('set_int32'); obs32 = fp(lambda u: zlib.crc32(u.encode()) in s32)
print(f'  set 里存 32 位 crc32:实测误判 {obs32 * 100:.3f}%(粗略预期 n / 2^32 = {N / 2 ** 32 * 100:.3f}%)'); del s32
s64 = build('set_int64'); obs64 = fp(lambda u: int.from_bytes(hashlib.blake2b(u.encode(), digest_size=8).digest(), 'little') in s64)
print(f'  set 里存 64 位哈希:实测误判 {obs64 * 100:.4f}%(粗略预期 n / 2^64 ≈ 0)'); del s64
sstr = build('set_str'); print(f'  set 里存完整 URL:实测误判 {fp(sstr.__contains__) * 100:.3f}%(精确集合没有误判)')

print('== 三:Bloom 过滤器装的比设计容量多时,误判率怎么涨(按 100 万、1% 设计,继续往里加)')
b = Bloom(N, 0.01)
for i in range(N): b.add(url(i))
print(f'  {"已加入":>10}{"理论误判":>10}{"实测误判":>10}')
added = N
for target in (N, 2 * N, 3 * N):
    while added < target:
        b.add(url(added)); added += 1
    print(f'  {added:>10,}{b.theory(added) * 100:>9.3f}%{fp(b.__contains__, 50_000_000) * 100:>9.3f}%')

print('== 四:速度(每秒能判断多少个 URL;各取 200000 次查询)')
t0 = time.perf_counter(); n = sum(1 for i in range(Q) if url(i) in sstr); ts = time.perf_counter() - t0
t0 = time.perf_counter(); n2 = sum(1 for i in range(Q) if url(i) in blooms[0.01]); tb = time.perf_counter() - t0
t0 = time.perf_counter(); [url(i) for i in range(Q)]; tg = time.perf_counter() - t0
print(f'  生成 URL 字符串本身:{Q / tg / 1000:.0f} 千次/秒;set 查询(含生成):{Q / ts / 1000:.0f} 千次/秒;Bloom 查询(含生成,k={blooms[0.01].k},纯 Python):{Q / tb / 1000:.0f} 千次/秒')
purge()
