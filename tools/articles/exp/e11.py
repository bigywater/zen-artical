import sys, os, math, heapq; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e11')
P = products(); PG = pages()
S1 = jl(P)[:128 * 1024]
def lz77(data, window=32768, chain=32, lazy=False, minlen=3, maxlen=258):
    n = len(data); table = {}; toks = []; i = 0
    def find(i):
        if i + minlen > n: return 0, 0
        lst = table.get(data[i:i + 3]); best = 0; bd = 0
        if not lst: return 0, 0
        lim = min(maxlen, n - i); k = 0
        for c in reversed(lst):
            k += 1
            if k > chain or i - c > window: break
            L = 0
            while L < lim and data[c + L] == data[i + L]: L += 1
            if L > best: best, bd = L, i - c
            if best == lim: break
        return best, bd
    def ins(p):
        if p + 3 <= n: table.setdefault(data[p:p + 3], []).append(p)
    while i < n:
        L, d = find(i)
        if L >= minlen and lazy and i + 1 < n:
            ins(i); L2, d2 = find(i + 1)
            if L2 > L: toks.append((0, data[i])); i += 1; continue
            toks.append((d, L)); 
            for p in range(i + 1, i + L): ins(p)
            i += L; continue
        if L >= minlen:
            toks.append((d, L))
            for p in range(i, i + L): ins(p)
            i += L
        else: toks.append((0, data[i])); ins(i); i += 1
    return toks
def unlz(toks):
    out = bytearray()
    for d, x in toks:
        if d == 0: out.append(x)
        else:
            for _ in range(x): out.append(out[-d])          # 逐字节复制,允许 距离 < 长度(重叠)
    return bytes(out)
LB = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]; LE = [0] * 8 + [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [0]
DB = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]; DE = [0, 0, 0, 0] + [k // 2 - 1 for k in range(4, 30)]
def lcode(L):
    for k in range(len(LB) - 1, -1, -1):
        if L >= LB[k]: return k
def dcode(D):
    for k in range(len(DB) - 1, -1, -1):
        if D >= DB[k]: return k
ok = all(LB[k] + 2 ** LE[k] - 1 == LB[k + 1] - 1 for k in range(len(LB) - 2)) and all(DB[k] + 2 ** DE[k] == DB[k + 1] for k in range(len(DB) - 1)) and DB[-1] + 2 ** DE[-1] == 32769
def estimate(toks):
    lit = collections.Counter(); dst = collections.Counter(); extra = 0
    for d, x in toks:
        if d == 0: lit[x] += 1
        else: lit[257 + lcode(x)] += 1; dst[dcode(d)] += 1; extra += LE[lcode(x)] + DE[dcode(d)]
    lit[256] += 1
    def cost(fr):
        if len(fr) == 1: return sum(fr.values())
        h = [(c, i, (s,)) for i, (s, c) in enumerate(sorted(fr.items()))]; heapq.heapify(h); dep = collections.Counter(); tk = len(h)
        while len(h) > 1:
            c1, _, a = heapq.heappop(h); c2, _, b = heapq.heappop(h)
            for s in a + b: dep[s] += 1
            heapq.heappush(h, (c1 + c2, tk, a + b)); tk += 1
        return sum(fr[s] * dep[s] for s in fr)
    return cost(lit), cost(dst), extra
def est_bytes(tk): a, b, e = estimate(tk); return (a + b + e) / 8
print('== 一:LZ77 的输出:字面量,或者(往回看多远,复制多长);先看一个小例子')
for sample in (b'abracadabra abracadabra', b'{"id":1,"id":2,"id":3}', b'aaaaaaaaaa'):
    t = lz77(sample, chain=64); print(f'  {sample!r}: ' + ' '.join(f'"{chr(x)}"' if d == 0 else f'({d},{x})' for d, x in t) + f'  → 解回原文{"一致" if unlz(t) == sample else "不一致"}({len(sample)} 字节 → {sum(1 for d, _ in t if d == 0)} 个字面量 + {sum(1 for d, _ in t if d)} 个匹配)')
t = lz77(S1[:300], chain=64); print('  products JSON Lines 的前 300 字节:' + ' '.join(f'"{chr(x)}"' if d == 0 else f'({d},{x})' for d, x in t)[:360] + ' …')
print('== 二:对 products JSON Lines 的前 128 KiB 做 LZ77(窗口 32 KiB,每个位置最多查 64 个候选,懒匹配),看 token 的统计')
t0 = time.perf_counter(); toks = lz77(S1, 32768, 64, True); el = time.perf_counter() - t0
nl = sum(1 for d, _ in toks if d == 0); nm = len(toks) - nl; mb = sum(x for d, x in toks if d); assert unlz(toks) == S1
print(f'  输入 {len(S1)} 字节 → {len(toks)} 个 token:字面量 {nl} 个(占输入 {nl * 100 / len(S1):.1f}%),匹配 {nm} 个(覆盖输入的 {mb * 100 / len(S1):.1f}%,平均长度 {mb / nm:.1f} 字节);用时 {el:.1f} 秒;解回原文一致')
lens = collections.Counter(); dists = collections.Counter()
for d, x in toks:
    if d: lens['3' if x == 3 else '4' if x == 4 else '5–8' if x <= 8 else '9–16' if x <= 16 else '17–32' if x <= 32 else '33–258'] += 1; dists['≤16' if d <= 16 else '≤256' if d <= 256 else '≤4096' if d <= 4096 else '≤32768'] += 1
print('  匹配长度分布:' + '、'.join(f'{k}:{lens[k]}' for k in ('3', '4', '5–8', '9–16', '17–32', '33–258')))
print('  匹配距离分布:' + '、'.join(f'{k}:{dists[k]}' for k in ('≤16', '≤256', '≤4096', '≤32768')))
print('== 三:往回看多远(窗口大小):我的 LZ77 在不同窗口下覆盖多少字节;再看真实压缩器(zlib 的 windowBits、zstd 的 windowLog)')
print(f'  {"窗口":>8s} {"匹配覆盖输入":>10s} {"字面量个数":>8s} {"匹配个数":>8s} {"估算压缩后字节":>12s}')
for w in (256, 1024, 4096, 16384, 65536, 131072):
    tk = lz77(S1, w, 16, False); mbw = sum(x for d, x in tk if d); print(f'  {w:8d} {mbw * 100 / len(S1):9.1f}% {sum(1 for d, _ in tk if d == 0):8d} {sum(1 for d, _ in tk if d):8d} {est_bytes(tk):12.0f}')
big = b''.join(PG)[:4 << 20]
print(f'  真实压缩器,pages 数据 {len(big) / 1048576:.0f} MiB(每页约 13 KiB,不同页之间有相同的模板):')
row = []
for wb in (9, 11, 13, 15):
    c = zlib.compressobj(6, zlib.DEFLATED, -wb, 9); row.append(f'windowBits {wb}(窗口 {2 ** wb // 1024 if wb >= 10 else 2 ** wb} {"KiB" if wb >= 10 else "B"}):{len(c.compress(big) + c.flush())}')
print('    zlib 级别 6:' + ';'.join(row))
row = []
for wl in (10, 12, 14, 17, 20, 22):
    cc = zstandard.ZstdCompressor(compression_params=zstandard.ZstdCompressionParameters.from_level(3, window_log=wl)); row.append(f'windowLog {wl}({2 ** wl // 1024} KiB):{len(cc.compress(big))}')
print('    zstd 级别 3:' + ';'.join(row))
print('== 四:匹配搜索的努力程度:每个位置最多查多少个候选(chain)、是否懒匹配,以及 zlib 的级别')
print(f'  {"chain":>6s} {"懒匹配":>6s} {"匹配覆盖输入":>10s} {"token 数":>8s} {"估算压缩后字节":>12s} {"用时(秒)":>8s}')
for ch, lz in ((1, False), (4, False), (16, False), (64, False), (256, False), (64, True), (256, True)):
    t0 = time.perf_counter(); tk = lz77(S1, 32768, ch, lz); el = time.perf_counter() - t0; mbw = sum(x for d, x in tk if d); print(f'  {ch:6d} {"是" if lz else "否":>6s} {mbw * 100 / len(S1):9.1f}% {len(tk):8d} {est_bytes(tk):12.0f} {el:8.2f}')
print(f'  zlib 各级别(raw deflate,同样 128 KiB 输入):' + ';'.join(f'级别 {lv}:{len(zlib.compressobj(lv, zlib.DEFLATED, -15).compress(S1) + (lambda c: c.flush())(zlib.compressobj(lv, zlib.DEFLATED, -15))) if False else (lambda c: len(c.compress(S1) + c.flush()))(zlib.compressobj(lv, zlib.DEFLATED, -15))}({timeit(lambda: zlib.compress(S1, lv), 5)[0] * 1000:.1f} ms)' for lv in (1, 3, 6, 9)))
print('== 五:重叠匹配:距离小于长度时的复制(游程)——全零数据的压缩比随输入长度怎么变')
print(f'  {"输入":>10s} {"zlib-9":>9s} {"压缩比":>9s} {"zstd-3":>9s} {"压缩比":>9s} {"zstd-19":>9s} {"压缩比":>9s} {"lz4":>9s} {"压缩比":>9s}')
for n in (1 << 10, 1 << 14, 1 << 20, 1 << 24, 1 << 26):
    z0 = bytes(n); a = len(zlib.compress(z0, 9)); b = len(zstandard.ZstdCompressor(level=3).compress(z0)); c = len(zstandard.ZstdCompressor(level=19).compress(z0)); d = len(lz4.frame.compress(z0))
    print(f'  {n / 1048576 if n >= 1 << 20 else n / 1024:8.2f}{"MiB" if n >= 1 << 20 else "KiB":>3s} {a:9d} {n / a:8.1f}× {b:9d} {n / b:8.1f}× {c:9d} {n / c:8.1f}× {d:9d} {n / d:8.1f}×')
print('  deflate 的最大匹配长度是 258 字节,所以压缩比有上限(约 1000×);zstd 的匹配长度没有这个限制')
print('== 六:LZ77 token + Huffman = deflate?用 RFC 1951 的长度/距离编码表估算 token 流的位数,和真实 zlib 对照(同样 128 KiB 输入)')
print(f'  表自检:长度码(3…258)与距离码(1…32768)的范围首尾相接、没有缺口:{ok}')
for lab, tk in (('贪心 chain 16', lz77(S1, 32768, 16, False)), ('懒匹配 chain 64', toks)):
    a, b, e = estimate(tk); tot = (a + b + e) / 8; real = (lambda c: len(c.compress(S1) + c.flush()))(zlib.compressobj(9, zlib.DEFLATED, -15))
    print(f'  {lab}:字面量/长度码 {a} 位 + 距离码 {b} 位 + 额外位 {e} 位 = {tot:.0f} 字节(估算,不含码表);zlib 级别 9 实际 {real} 字节;估算是实际的 {tot * 100 / real:.0f}%')
purge()
