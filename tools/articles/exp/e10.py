import sys, os, math, heapq; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e10')
P = products(); S1 = jl(P)[:1 << 20]
def H(freq):
    n = sum(freq.values()); return -sum(c / n * math.log2(c / n) for c in freq.values() if c)
def huff_lengths(freq):
    """返回 {符号: 码长};freq 只有一个符号时码长记 1"""
    if len(freq) == 1: return {s: 1 for s in freq}
    h = [(c, i, (s,)) for i, (s, c) in enumerate(sorted(freq.items()))]; heapq.heapify(h); depth = collections.Counter(); tick = len(h)
    while len(h) > 1:
        c1, _, s1 = heapq.heappop(h); c2, _, s2 = heapq.heappop(h)
        for s in s1 + s2: depth[s] += 1
        heapq.heappush(h, (c1 + c2, tick, s1 + s2)); tick += 1
    return dict(depth)
def canonical(lengths):
    """规范 Huffman:按 (码长, 符号) 排序后依次分配码"""
    code = 0; prev = 0; out = {}
    for s, L in sorted(lengths.items(), key=lambda t: (t[1], t[0])):
        code <<= (L - prev); out[s] = (code, L); code += 1; prev = L
    return out
def avg_len(freq, lengths): n = sum(freq.values()); return sum(freq[s] * lengths[s] for s in freq) / n
print('== 一:Huffman 树怎么建:每次取出现次数最少的两个合并(例:abracadabra)')
txt = b'abracadabra'; fr = collections.Counter(txt); print(f'  出现次数 { {chr(k): v for k, v in sorted(fr.items())} };0 阶熵 {H(fr):.4f} bit/符号,共 {len(txt)} 个符号 → 理论下限 {H(fr) * len(txt):.2f} 位')
h = [(c, i, chr(s)) for i, (s, c) in enumerate(sorted(fr.items()))]; heapq.heapify(h); tick = len(h); step_ = 0
while len(h) > 1:
    c1, _, s1 = heapq.heappop(h); c2, _, s2 = heapq.heappop(h); step_ += 1; print(f'  第 {step_} 步:合并 "{s1}"({c1})+ "{s2}"({c2})→ "{s1 + s2}"({c1 + c2})'); heapq.heappush(h, (c1 + c2, tick, s1 + s2)); tick += 1
L = huff_lengths(fr); cd = canonical(L); bits = ''.join(format(cd[b][0], f'0{cd[b][1]}b') for b in txt)
print(f'  码长 { {chr(k): v for k, v in sorted(L.items())} };规范码 { {chr(k): format(v[0], f"0{v[1]}b") for k, v in sorted(cd.items())} }')
print(f'  编码后 {len(bits)} 位 = {len(bits) / 8:.2f} 字节(定长 8 位是 {len(txt) * 8} 位;平均码长 {avg_len(fr, L):.4f} bit,熵 {H(fr):.4f} bit);编码结果 {bits}')
print('== 二:真实数据(products JSON Lines 的 1 MiB):Huffman 的平均码长与熵')
fr = collections.Counter(S1); L = huff_lengths(fr); al = avg_len(fr, L)
print(f'  不同的字节值 {len(fr)} 种;熵 {H(fr):.4f} bit/字节;Huffman 平均码长 {al:.4f} bit/字节(差 {al - H(fr):.4f},约 {100 * (al - H(fr)) / H(fr):.2f}%);最短码 {min(L.values())} 位,最长码 {max(L.values())} 位')
print(f'  编码后 {math.ceil(al * len(S1) / 8)} 字节(熵下限 {int(H(fr) * len(S1) / 8)} 字节,原 {len(S1)} 字节,压缩比 {len(S1) * 8 / (al * len(S1)):.3f}×)')
top = sorted(fr.items(), key=lambda t: -t[1])[:6]; print('  最常出现的 6 个字节及其码长:' + '、'.join(f'{chr(s)!r}({c / len(S1) * 100:.1f}%)→{L[s]} 位' for s, c in top))
print('== 三:分布很偏时 Huffman 的浪费:平均码长与熵(每个符号至少 1 位)')
print(f'  {"分布":30s} {"熵":>8s} {"Huffman 平均码长":>14s} {"多出":>7s}   合并 2 个符号 {"":8s} 合并 4 个符号')
def block(probs, k):
    sy = list(range(len(probs))); f = {}
    for t in __import__('itertools').product(sy, repeat=k): p = 1.0; [p := p * probs[i] for i in t]; f[t] = p
    return f
for lab, pr in (('0.5 / 0.5', [0.5, 0.5]), ('0.9 / 0.1', [0.9, 0.1]), ('0.99 / 0.01', [0.99, 0.01]), ('0.999 / 0.001', [0.999, 0.001]), ('0.7 / 0.2 / 0.1', [0.7, 0.2, 0.1])):
    f1 = {i: p for i, p in enumerate(pr)}; Hh = H(f1); row = []
    for k in (1, 2, 4):
        fk = block(pr, k) if k > 1 else f1; ls = huff_lengths({t: p for t, p in fk.items()}); row.append(avg_len(fk, ls) / k)
    print(f'  {lab:30s} {Hh:8.4f} {row[0]:14.4f} {100 * (row[0] - Hh) / Hh:6.1f}%   平均每符号 {row[1]:.4f}({100 * (row[1] - Hh) / Hh:5.1f}%)   平均每符号 {row[2]:.4f}({100 * (row[2] - Hh) / Hh:5.1f}%)')
print('  (把多个符号合成一个大符号再 Huffman,每个符号的平均码长逼近熵,代价是码表按符号个数的幂次增长)')
print('== 四:规范 Huffman:码表里只存每个符号的码长,解码端按规则重建同一套码;验证编码解码往返,并算码表本身的大小')
cd = canonical(L); enc = collections.defaultdict(str)
bits = ''.join(format(cd[b][0], f'0{cd[b][1]}b') for b in S1[:100000])
dec = {(c, l): s for s, (c, l) in cd.items()}; out = bytearray(); cur = 0; ln = 0
for ch in bits:
    cur = (cur << 1) | (ch == '1'); ln += 1
    if (cur, ln) in dec: out.append(dec[(cur, ln)]); cur = 0; ln = 0
print(f'  编码解码往返(前 100000 字节):{"一致" if bytes(out) == S1[:100000] else "不一致"};编码后 {len(bits)} 位 = {math.ceil(len(bits) / 8)} 字节')
tree_bytes = len(fr) * 2 + (len(fr) - 1) * 2
print(f'  码表只存码长:{len(fr)} 个符号用到的码长(每个 4 位,没出现的符号码长 0,共 256 个位置)= {256 * 4 // 8} 字节;若把整棵树存下来(每个符号 1 字节符号值 + 1 字节码长)约 {len(fr) * 2} 字节')
cl = [L.get(i, 0) for i in range(256)]; rl = len(zlib.compress(bytes(cl), 9)); print(f'  把 256 个码长当作字节数组,再用 deflate 压一下:{rl} 字节(deflate 对码长序列自己也用了游程 + Huffman 来存)')
print('== 五:限制最大码长(deflate 最长 15 位,zstd 的 Huffman 最长 11 位):码长受限后平均码长的变化')
def limited(freq, maxlen):
    f = dict(freq)
    while True:
        l = huff_lengths(f)
        if max(l.values()) <= maxlen: return l
        f = {s: max(1, c >> 1) for s, c in f.items()}
print(f'  {"最大码长限制":>10s} {"实际最长码":>8s} {"平均码长 bit/字节":>16s} {"比不限制多":>10s}')
base = avg_len(fr, huff_lengths(fr))
for mx in (99, 15, 11, 9, 8):
    ll = limited(fr, mx); a_ = avg_len(fr, ll); print(f'  {mx:10d} {max(ll.values()):8d} {a_:16.4f} {100 * (a_ - base) / base:9.3f}%')
print('  (这里用"反复把次数减半直到最长码不超过限制"的简单办法,deflate 和 zstd 用的是更精细的算法,结果会略好一些)')
print('== 六:只做 Huffman、不做 LZ 匹配:zlib 的几种策略对 products 的 1 MiB(deflate 级别 9)')
for lab, st in (('Z_DEFAULT_STRATEGY(LZ77 + Huffman)', zlib.Z_DEFAULT_STRATEGY), ('Z_FILTERED', zlib.Z_FILTERED), ('Z_HUFFMAN_ONLY(只做 Huffman)', zlib.Z_HUFFMAN_ONLY), ('Z_RLE', zlib.Z_RLE)):
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9, st); n = len(c.compress(S1) + c.flush()); print(f'  {lab:36s} {n:8d} 字节  压缩比 {len(S1) / n:5.2f}×')
print(f'  我算的 Huffman 理论大小 {math.ceil(avg_len(fr, huff_lengths(fr)) * len(S1) / 8)} 字节(不含码表);Z_HUFFMAN_ONLY 多出的部分是 deflate 的块头和码表')
purge()
