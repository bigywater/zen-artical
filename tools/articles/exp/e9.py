import sys, os, math, lzma, bz2, itertools, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e9')
P = products(); T = timeseries(); PG = pages()
zs = lambda b, lv=3: len(zstandard.ZstdCompressor(level=lv).compress(b)); gz = lambda b: len(zlib.compress(b, 9)); xz = lambda b: len(lzma.compress(b, preset=9)); bz = lambda b: len(bz2.compress(b, 9))
def H(counter):
    n = sum(counter.values()); return -sum(c / n * math.log2(c / n) for c in counter.values())
def h0(b): return H(collections.Counter(b))
def hk(b, k):
    """经验条件熵 H(X | 前 k 个字节)(用 (k+1)-gram 的熵减去 k-gram 的熵)"""
    if k == 0: return h0(b)
    g1 = collections.Counter(b[i:i + k + 1] for i in range(len(b) - k)); g0 = collections.Counter(b[i:i + k] for i in range(len(b) - k)); return H(g1) - H(g0)
S1 = jl(P)[:1 << 20]; SP = b''.join(PG)[:1 << 20]; r = random.Random(3)
words = ' '.join(r.choice(VOC[:1500]) for _ in range(300000)).encode()[:1 << 20]
print('== 一:0 阶熵(只看每个字节出现的频率)给出的"体积下限"与真实压缩器(每份 1 MiB)')
print(f'  {"内容":26s} {"0 阶熵 bit/字节":>14s} {"0 阶下限":>9s} {"gzip-9":>9s} {"zstd-3":>9s} {"zstd-19":>9s} {"xz-9":>9s} {"bz2-9":>9s}')
for lab, b in (('随机字节', r.randbytes(1 << 20)), ('随机小写字母', bytes(r.choice(b'abcdefghijklmnopqrstuvwxyz') for _ in range(1 << 20))), ('词表拼接', words), ('products JSON Lines', S1), ('类 HTML 页面', SP)):
    h = h0(b); print(f'  {lab:26s} {h:14.3f} {int(h * len(b) / 8):9d} {gz(b):9d} {zs(b):9d} {zs(b, 19):9d} {xz(b):9d} {bz(b):9d}')
print('  (0 阶下限 = 熵 × 字节数 / 8。能比它小,是因为压缩器还利用了"前后文"——下一节)')
print('== 二:条件熵:已知前面 k 个字节时,下一个字节还剩多少不确定(products JSON Lines 的 1 MiB,k = 0…4;另给样本只取前 64 KiB 的结果)')
print(f'  {"k":>2s} {"1 MiB 样本 bit/字节":>18s} {"对应体积下限":>12s} {"64 KiB 样本 bit/字节":>19s}')
for k in range(0, 5):
    a = hk(S1, k); b64 = hk(S1[:65536], k); print(f'  {k:2d} {a:18.3f} {int(a * len(S1) / 8):12d} {b64:19.3f}')
print(f'  对照:zstd-19 实际 {zs(S1, 19)} 字节 = {zs(S1, 19) * 8 / len(S1):.3f} bit/字节;xz-9 {xz(S1)} 字节 = {xz(S1) * 8 / len(S1):.3f} bit/字节')
print('  (阶数越高、样本越小,经验熵越低,但那是"样本太少、每种上下文只见过几次"造成的假象,不是真的可压缩那么多)')
print('== 三:不可能全部变小:枚举所有长度 0–2 的字节串,再抽样 10 万个长度 3 的字节串,看压缩后变短、相等、变长的个数')
def strings(n): return (bytes(t) for t in itertools.product(range(256), repeat=n))
for name, comp in (('zlib(gzip 的 deflate)', lambda b: zlib.compress(b, 9)), ('zstd-3', lambda b: zstandard.ZstdCompressor(level=3).compress(b)), ('lz4 frame', lambda b: lz4.frame.compress(b)), ('lz4 block', lambda b: lz4.block.compress(b, store_size=False))):
    c = collections.Counter(); 
    for n in range(0, 3):
        for s in strings(n): L = len(comp(s)); c['变短' if L < len(s) else ('相等' if L == len(s) else '变长')] += 1
    rr = random.Random(9)
    for _ in range(100000): s = rr.randbytes(3); L = len(comp(s)); c['变短' if L < len(s) else ('相等' if L == len(s) else '变长')] += 1
    tot = sum(c.values()); ex = comp(b'a'); print(f'  {name:22s} 共 {tot} 个:变短 {c["变短"]}、相等 {c["相等"]}、变长 {c["变长"]};压缩 1 字节 b"a" 得到 {len(ex)} 字节')
print('  计数论证:长度 < n 的字节串共 ' + str(sum(256 ** i for i in range(3))) + ' 个(n=3),长度为 3 的有 16777216 个,不可能每一个都映射到一个更短的字节串')
print('== 四:已知熵的信源——压缩器能压到多接近理论值(每份 1 MiB 个独立同分布的符号,按各符号概率生成)')
def source(probs, n=1 << 20):
    syms = list(range(len(probs))); return bytes(r.choices(syms, weights=probs, k=n))
print(f'  {"信源":28s} {"理论熵 bit/符号":>14s} {"理论下限":>9s} {"zstd-19":>9s} {"xz-9":>9s} {"bz2-9":>9s} {"zstd 超出":>9s}')
for lab, probs in (('两个符号 0.5/0.5', [0.5, 0.5]), ('两个符号 0.9/0.1', [0.9, 0.1]), ('两个符号 0.99/0.01', [0.99, 0.01]), ('4 个符号 均匀', [0.25] * 4), ('16 个符号 均匀', [1 / 16] * 16), ('8 个符号 0.5,0.25,…(2 的幂)', [2 ** -(i + 1) for i in range(7)] + [2 ** -7])):
    Hh = -sum(p * math.log2(p) for p in probs if p > 0); b = source(probs); lb = Hh * len(b) / 8; z = zs(b, 19)
    print(f'  {lab:28s} {Hh:14.4f} {int(lb):9d} {z:9d} {xz(b):9d} {bz(b):9d} {100 * (z - lb) / lb:8.1f}%')
print('== 五:能用很短的程序生成,不等于能被压缩:同样 1 MiB,用 random.Random(1) 生成的伪随机字节')
pr = random.Random(1).randbytes(1 << 20); print(f'  伪随机字节(种子 1):gzip-9 {gz(pr)}、zstd-19 {zs(pr, 19)}、xz-9 {xz(pr)}、bz2-9 {bz(pr)} 字节(原 {len(pr)});而 Python 里生成它只要 "random.Random(1).randbytes(1 << 20)" 这 {len("random.Random(1).randbytes(1 << 20)")} 个字符')
cnt = bytes(i & 0xff for i in range(1 << 20)); sq = bytes((i * i) & 0xff for i in range(1 << 20)); print(f'  0,1,2,…255 循环:gzip-9 {gz(cnt)}、zstd-19 {zs(cnt, 19)};i*i 取低 8 位:gzip-9 {gz(sq)}、zstd-19 {zs(sq, 19)}(周期性的规律压缩器能找到)')
print('== 六:换一种表示就改变熵:同一批时间戳和价格,不同表示的 0 阶/2 阶熵与压缩后大小')
ts = [x['ts'] for x in T]; dl = [ts[0]] + [b - a for a, b in zip(ts, ts[1:])]
pr_ = [x['price'] for x in P]
def vi(n):
    o = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: o.append(b | 0x80)
        else: o.append(b); return bytes(o)
reps = [('时间戳:十进制文本', ','.join(map(str, ts)).encode()), ('时间戳:定长 8 字节', b''.join(struct.pack('>q', x) for x in ts)), ('时间戳:差分 varint', b''.join(vi(x) for x in dl)),
        ('价格:十进制文本', ','.join(map(str, pr_)).encode()), ('价格:float64', b''.join(struct.pack('>d', x) for x in pr_)), ('价格:整数分 varint', b''.join(vi(int(round(x * 100))) for x in pr_))]
print(f'  {"表示":22s} {"字节":>8s} {"0 阶 bit/字节":>12s} {"2 阶 bit/字节":>12s} {"zstd-19":>8s} {"xz-9":>8s}')
for lab, b in reps: print(f'  {lab:22s} {len(b):8d} {h0(b):12.3f} {hk(b, 2):12.3f} {zs(b, 19):8d} {xz(b):8d}')
purge()
