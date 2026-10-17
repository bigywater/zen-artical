import sys, os, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e13')
P = products(); S1 = jl(P)[:1 << 18]
def normalize(counts, M):
    """把次数缩放成总和恰好为 M、每个出现过的符号至少为 1 的频率(先按比例取整,再逐个调整)"""
    syms = [s for s, c in enumerate(counts) if c]; tot = sum(counts)
    if len(syms) > M: raise ValueError('M 太小')
    f = {s: max(1, int(counts[s] * M / tot)) for s in syms}
    while sum(f.values()) > M: f[max((s for s in syms if f[s] > 1), key=lambda s: f[s])] -= 1
    while sum(f.values()) < M: f[max(syms, key=lambda s: counts[s] / f[s])] += 1
    return f
def rans_encode(data, f, scale_bits):
    M = 1 << scale_bits; cum = {}; c = 0
    for s in sorted(f): cum[s] = c; c += f[s]
    x = 1 << 16; out = []; L = 1 << 16
    for s in reversed(data):
        fs = f[s]; xmax = ((L >> scale_bits) << 16) * fs
        while x >= xmax: out.append(x & 0xffff); x >>= 16
        x = ((x // fs) << scale_bits) + (x % fs) + cum[s]
    return x, out[::-1]
def rans_decode(x, words, f, scale_bits, n):
    M = 1 << scale_bits; cum = {}; c = 0; slot = [0] * M
    for s in sorted(f):
        cum[s] = c
        for k in range(f[s]): slot[c + k] = s
        c += f[s]
    res = bytearray(); it = iter(words); L = 1 << 16
    for _ in range(n):
        low = x & (M - 1); s = slot[low]; res.append(s); x = f[s] * (x >> scale_bits) + low - cum[s]
        while x < L: x = (x << 16) | next(it)
    return bytes(res)
def rans_size(data, scale_bits=12):
    cnt = [0] * 256
    for b in data: cnt[b] += 1
    f = normalize(cnt, 1 << scale_bits); x, w = rans_encode(data, f, scale_bits); return f, x, w, 4 + 2 * len(w)
print('== 一:ANS 的思想:状态 x 里"存"了已经编码的符号;编码一个符号 s 让 x 变大,变大的倍数约等于 1/概率。小例子——符号 a、b、c 频率 3、3、2(总和 M = 8),编码序列 abcabcaa')
f = {97: 3, 98: 3, 99: 2}; cum = {97: 0, 98: 3, 99: 6}; seq = b'abcabcaa'; x = 16
print(f'  初始状态 x = {x};从最后一个符号开始往前编码(ANS 先进后出):x\' = (x // f) × M + (x % f) + 累积频率')
for s in reversed(seq):
    nx = (x // f[s]) * 8 + (x % f[s]) + cum[s]; print(f'    编码 "{chr(s)}"(f={f[s]},累积={cum[s]}):x = {x} → ({x} // {f[s]}) × 8 + {x} % {f[s]} + {cum[s]} = {nx}  (x 变大 {nx / x:.2f} 倍,-log2 概率 = {-math.log2(f[s] / 8):.2f} 位,log2(变大倍数) = {math.log2(nx / x):.2f})'); x = nx
print(f'  最终 x = {x}({x.bit_length()} 位);解码时 x % 8 落在哪个符号的区间就是哪个符号:', end='')
slot = {r: s for s in f for r in range(cum[s], cum[s] + f[s])}; out = []
for _ in range(len(seq)): r = x % 8; s = slot[r]; out.append(s); x = f[s] * (x // 8) + r - cum[s]
print(f'{bytes(out).decode()}(还原 x = {x},与初始状态 16 {"相同" if x == 16 else "不同"})')
print('== 二:rANS 编码(12 位频率精度,32 位状态,每次输出 16 位)对比 Huffman 和熵,每份 256 KiB')
r = random.Random(4)
def src(probs, n=1 << 18): return bytes(r.choices(range(len(probs)), weights=probs, k=n))
print(f'  {"数据":24s} {"熵下限":>9s} {"Huffman":>9s} {"rANS":>9s} {"Huffman 多出":>10s} {"rANS 多出":>9s}   解码')
for lab, data in (('0.5 / 0.5', src([0.5, 0.5])), ('0.9 / 0.1', src([0.9, 0.1])), ('0.99 / 0.01', src([0.99, 0.01])), ('0.999 / 0.001', src([0.999, 0.001])), ('16 个符号 均匀', src([1 / 16] * 16)), ('指数衰减的 20 个符号', src([0.5 ** (i + 1) for i in range(20)])), ('products 文本(256 KiB)', S1)):
    cnt = collections.Counter(data); h = H0(cnt) * len(data) / 8; hf = huff_cost(cnt) / 8; fq, x, w, sz = rans_size(data)
    ok = rans_decode(x, w, fq, 12, len(data)) == data
    print(f'  {lab:24s} {h:9.0f} {hf:9.0f} {sz:9d} {100 * (hf - h) / h:9.1f}% {100 * (sz - h) / h:8.2f}%   {"往返一致" if ok else "往返失败"}')
print('== 三:频率的量化精度(表的大小 M = 2^k)对 rANS 压缩率的影响——精度太低,小概率被"舍入"成别的值')
print(f'  {"数据":22s}' + ''.join(f'{"M=2^" + str(k):>11s}' for k in (6, 8, 10, 12, 14)) + f'{"熵下限":>11s}')
for lab, data in (('0.99 / 0.01', src([0.99, 0.01])), ('0.999 / 0.001', src([0.999, 0.001])), ('指数衰减的 20 个符号', src([0.5 ** (i + 1) for i in range(20)])), ('products 文本', S1)):
    cnt = collections.Counter(data); h = H0(cnt) * len(data) / 8; row = ''
    for k in (6, 8, 10, 12, 14):
        try: fq, x, w, sz = rans_size(data, k); row += f'{sz:11d}'
        except ValueError: row += f'{"(M 太小)":>11s}'
    print(f'  {lab:22s}{row}{h:11.0f}')
print('== 四:tANS(FSE 的做法):把 rANS 的状态转移预先算成一张表,编码/解码只查表、移位,不做除法。表大小 L = 2^R;我按 zstd FSE 的方式把符号"散布"到表里')
def build_tans(counts, R):
    L = 1 << R; f = normalize(counts, L); step = (L >> 1) + (L >> 3) + 3; pos = 0; table = [None] * L
    for s in sorted(f):
        for _ in range(f[s]): table[pos] = s; pos = (pos + step) & (L - 1)
    assert all(t is not None for t in table) and pos == 0
    slots = {s: [] for s in f}; 
    for X, s in enumerate(table): slots[s].append(X)
    dec = [None] * L; 
    for s in f:
        for k, X in enumerate(slots[s]):
            xs = f[s] + k; nb = R - (xs.bit_length() - 1); dec[X] = (s, nb, (xs << nb) - L)
    return f, table, slots, dec
def tans_encode(data, f, slots, R):
    L = 1 << R; chunks = []; X = slots[data[-1]][0]
    for s in reversed(data[:-1]):
        t = X + L; fs = f[s]
        nb = 0
        while (t >> nb) >= 2 * fs: nb += 1
        xs = t >> nb; chunks.append((t & ((1 << nb) - 1), nb)); X = slots[s][xs - fs]
    return X, chunks[::-1]
def tans_decode(X, chunks, dec, n):
    out = bytearray()
    for i in range(n):
        s, nb, base = dec[X]; out.append(s)
        if i < n - 1: bits, nbb = chunks[i]; assert nbb == nb; X = base + bits
    return bytes(out)
def tans_size(data, R):
    cnt = [0] * 256
    for b in data: cnt[b] += 1
    f, table, slots, dec = build_tans(cnt, R); X, ch = tans_encode(data, f, slots, R); bits = sum(nb for _, nb in ch) + R
    return math.ceil(bits / 8), tans_decode(X, ch, dec, len(data)) == data
print(f'  {"数据":22s} {"熵下限":>9s} {"Huffman":>9s} {"rANS(12)":>9s}' + ''.join(f'{"tANS R=" + str(k):>12s}' for k in (6, 8, 10, 11, 12)) + '   往返')
for lab, data in (('0.9 / 0.1', src([0.9, 0.1], 1 << 16)), ('0.99 / 0.01', src([0.99, 0.01], 1 << 16)), ('16 个符号 均匀', src([1 / 16] * 16, 1 << 16)), ('指数衰减的 20 个符号', src([0.5 ** (i + 1) for i in range(20)], 1 << 16)), ('products 文本(64 KiB)', S1[:1 << 16])):
    cnt = collections.Counter(data); h = H0(cnt) * len(data) / 8; hf = huff_cost(cnt) / 8; rs = rans_size(data)[3]; row = ''; allok = True
    for k in (6, 8, 10, 11, 12):
        sz, ok = tans_size(data, k); row += f'{sz:12d}'; allok &= ok
    print(f'  {lab:22s} {h:9.0f} {hf:9.0f} {rs:9d}{row}   {"全部一致" if allok else "有失败"}')
print('== 五:一张具体的 FSE 解码表(R = 4,表大小 16;符号 a、b、c 的频率 7、5、4):每个状态 → 符号、要读的位数、新状态基数')
cnt = [0] * 256; cnt[97], cnt[98], cnt[99] = 7, 5, 4; f, table, slots, dec = build_tans(cnt, 4)
print(f'  归一化频率 { {chr(k): v for k, v in f.items()} };散布步长 (16>>1)+(16>>3)+3 = {(16 >> 1) + (16 >> 3) + 3};表中符号序列:{"".join(chr(t) for t in table)}')
print(f'  {"状态":>4s} {"符号":>4s} {"读位数":>6s} {"新状态基数":>10s}   新状态范围')
for X, (s, nb, base) in enumerate(dec): print(f'  {X:4d} {chr(s):>4s} {nb:6d} {base:10d}   [{base}, {base + (1 << nb) - 1}]')
for sy in (97, 98, 99):
    nbs = [nb for (s_, nb, base) in dec if s_ == sy]; print(f'  符号 {chr(sy)}:频率 {f[sy]}/16,各状态读的位数 {nbs},平均 {sum(nbs) / len(nbs):.3f} 位;-log2(概率) = {-math.log2(f[sy] / 16):.3f} 位;Huffman 对 a/b/c 的码长是 {"1/2/2" if True else ""} 位')
print('  (频率高的符号 a,有的状态只读 1 位,有的读 2 位——平均读的位数接近该符号的 -log2 概率,这是 Huffman 做不到的"分数位")')
print('== 六:同一份 LZ77 token(第 11 篇的懒匹配,128 KiB products),熵编码分别用 Huffman 和 tANS,其余(额外位)完全一样')
tk = lz77(S1[:128 * 1024], 32768, 64, True); lit = collections.Counter(); dst = collections.Counter(); extra = 0; ls = []; ds = []
for d, x in tk:
    if d == 0: lit[x] += 1; ls.append(x)
    else: lit[257 + lcode(x)] += 1; ls.append(257 + lcode(x)); dst[dcode(d)] += 1; ds.append(dcode(d)); extra += LE[lcode(x)] + DE[dcode(d)]
lit[256] += 1; ls.append(256)
def ans_bytes(seq, R):
    # 字母表可能超过 256:映射到 0..n-1
    keys = sorted(set(seq)); mp = {k: i for i, k in enumerate(keys)}; cnt = [0] * len(keys)
    for v in seq: cnt[mp[v]] += 1
    L = 1 << R
    if len(keys) > L: raise ValueError
    f, table, slots, dec = build_tans(cnt, R); data = [mp[v] for v in seq]; X, ch = tans_encode(data, f, slots, R); bits = sum(nb for _, nb in ch) + R
    out = bytearray(); X2 = X; dd = [];
    # 解码验证
    o = []; Xd = X
    for i in range(len(data)):
        s, nb, base = dec[Xd]; o.append(s)
        if i < len(data) - 1: Xd = base + ch[i][0]
    return math.ceil(bits / 8), o == data
print(f'  token 流:{len(tk)} 个 token,字面量/长度符号 {len(ls)} 个(字母表 {len(lit)} 种),距离符号 {len(ds)} 个(字母表 {len(dst)} 种),额外位 {extra} 位 = {extra / 8:.0f} 字节')
hl, hd = huff_cost(lit) / 8, huff_cost(dst) / 8; el, ed = H0(lit) * len(ls) / 8, H0(dst) * len(ds) / 8
al, okl = ans_bytes(ls, 12); ad, okd = ans_bytes(ds, 10)
print(f'  字面量/长度流:熵 {el:.0f} 字节、Huffman {hl:.0f} 字节、tANS(R=12){al} 字节({"往返一致" if okl else "往返失败"});距离流:熵 {ed:.0f}、Huffman {hd:.0f}、tANS(R=10){ad}({"往返一致" if okd else "往返失败"})')
tot_h = hl + hd + extra / 8; tot_a = al + ad + extra / 8
print(f'  合计(含额外位,不含码表):Huffman {tot_h:.0f} 字节,tANS {tot_a:.0f} 字节,tANS 小 {100 * (tot_h - tot_a) / tot_h:.1f}%;对照 zlib 级别 9 实际 {len((lambda c: c.compress(S1[:128 * 1024]) + c.flush())(zlib.compressobj(9, zlib.DEFLATED, -15)))} 字节,zstd-19 实际 {len(zstandard.ZstdCompressor(level=19).compress(S1[:128 * 1024]))} 字节')
purge()
