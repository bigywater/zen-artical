import sys, os, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e15')
P = products(); T = timeseries(); PG = pages()
S1 = jl(P)[:1 << 20]; SP = b''.join(PG)[:1 << 20]; ST = jl(T)[:1 << 20]
def parse_lz4(b):
    """把一个 LZ4 block 拆成序列 [(字面量长度, 匹配长度或 None, 偏移或 None)] 并解码"""
    i = 0; out = bytearray(); seqs = []
    while i < len(b):
        tok = b[i]; i += 1; ll = tok >> 4
        if ll == 15:
            while True:
                x = b[i]; i += 1; ll += x
                if x != 255: break
        out += b[i:i + ll]; i += ll
        if i >= len(b): seqs.append((ll, None, None)); break
        off = b[i] | (b[i + 1] << 8); i += 2; ml = tok & 15
        if ml == 15:
            while True:
                x = b[i]; i += 1; ml += x
                if x != 255: break
        ml += 4
        for _ in range(ml): out.append(out[-off])
        seqs.append((ll, ml, off))
    return seqs, bytes(out)
def parse_snappy(b):
    i = 0; n = 0; sh = 0
    while True:
        c = b[i]; i += 1; n |= (c & 0x7f) << sh; sh += 7
        if not c & 0x80: break
    out = bytearray(); els = []
    while i < len(b):
        tag = b[i]; i += 1; t = tag & 3
        if t == 0:
            ln = tag >> 2
            if ln < 60: ln += 1
            else: nb = ln - 59; ln = int.from_bytes(b[i:i + nb], 'little') + 1; i += nb
            out += b[i:i + ln]; i += ln; els.append(('L', ln, 0))
        else:
            if t == 1: ln = 4 + ((tag >> 2) & 7); off = ((tag >> 5) << 8) | b[i]; i += 1
            elif t == 2: ln = (tag >> 2) + 1; off = b[i] | (b[i + 1] << 8); i += 2
            else: ln = (tag >> 2) + 1; off = int.from_bytes(b[i:i + 4], 'little'); i += 4
            for _ in range(ln): out.append(out[-off])
            els.append(('C%d' % t, ln, off))
    return n, els, bytes(out)
print('== 一:LZ4 block 的格式:每个"序列"= 1 个 token(高 4 位字面量长度、低 4 位匹配长度减 4)+ [字面量长度的扩展字节] + 字面量 + 2 字节偏移 + [匹配长度的扩展字节];最后一个序列只有字面量')
for sample in (b'abracadabra abracadabra abracadabra', b'{"id":1,"id":2,"id":3,"id":4}'):
    blk = lz4.block.compress(sample, store_size=False); seqs, out = parse_lz4(blk)
    print(f'  {sample!r}:原 {len(sample)} 字节 → block {len(blk)} 字节 {blk.hex(" ")};序列 {seqs}(字面量长度, 匹配长度, 偏移);解回{"一致" if out == sample else "不一致"}')
blk = lz4.block.compress(S1, store_size=False); seqs, out = parse_lz4(blk); assert out == S1
ll = [s[0] for s in seqs]; ml = [s[1] for s in seqs if s[1]]; of = [s[2] for s in seqs if s[2]]
print(f'  products 1 MiB:block {len(blk)} 字节(压缩比 {len(S1) / len(blk):.2f}×),{len(seqs)} 个序列;字面量共 {sum(ll)} 字节(占输入 {sum(ll) * 100 / len(S1):.1f}%),匹配共 {sum(ml)} 字节;平均每序列字面量 {statistics.mean(ll):.1f} 字节、匹配 {statistics.mean(ml):.1f} 字节;解回一致')
print(f'  匹配长度:最短 {min(ml)}、最长 {max(ml)}(LZ4 最小匹配 4 字节);偏移:最小 {min(of)}、最大 {max(of)}(偏移占 2 字节,最大 65535)')
print(f'  block 里 token 与偏移等"元数据"的字节数:{len(seqs)} 个 token + {len(of)} × 2 字节偏移 + 扩展长度字节 = {len(blk) - sum(ll)} 字节;其余 {sum(ll)} 字节是原样存放的字面量')
print('== 二:Snappy 的格式:开头是原始长度(varint),然后是一串元素,每个元素的第 1 个字节(tag)低 2 位决定类型:0 字面量、1 短复制(偏移 < 2048)、2 复制(2 字节偏移)、3 复制(4 字节偏移)')
for sample in (b'abracadabra abracadabra abracadabra', b'{"id":1,"id":2,"id":3,"id":4}'):
    c = snappy.compress(sample); n, els, out = parse_snappy(c); print(f'  {sample!r}:原 {len(sample)} 字节 → {len(c)} 字节 {c.hex(" ")};头里的原始长度 {n};元素 {els};解回{"一致" if out == sample else "不一致"}')
c = snappy.compress(S1); n, els, out = parse_snappy(c); assert out == S1 and n == len(S1)
kinds = collections.Counter(e[0] for e in els); lit = sum(e[1] for e in els if e[0] == 'L'); cp = [e for e in els if e[0] != 'L']
print(f'  products 1 MiB:{len(c)} 字节(压缩比 {len(S1) / len(c):.2f}×),{len(els)} 个元素:{dict(kinds)};字面量共 {lit} 字节({lit * 100 / len(S1):.1f}%);复制的平均长度 {statistics.mean(e[1] for e in cp):.1f}、最长 {max(e[1] for e in cp)}(单个复制元素最长 64 字节);偏移最大 {max(e[2] for e in cp)}')
print('== 三:没有熵编码,LZ4 的字面量原样存放——如果再对这些字面量做 Huffman,还有多少可省(products 1 MiB,LZ4 默认与 HC 级别)')
for name, kw in (('默认', {}), ('HC 级别 9', dict(mode='high_compression', compression=9)), ('HC 级别 12', dict(mode='high_compression', compression=12))):
    blk = lz4.block.compress(S1, store_size=False, **kw); seqs, out = parse_lz4(blk); lit_bytes = bytearray(); i = 0
    # 再解析一次取出字面量字节
    i = 0
    while i < len(blk):
        tok = blk[i]; i += 1; l_ = tok >> 4
        if l_ == 15:
            while True:
                x = blk[i]; i += 1; l_ += x
                if x != 255: break
        lit_bytes += blk[i:i + l_]; i += l_
        if i >= len(blk): break
        i += 2
        if tok & 15 == 15:
            while True:
                x = blk[i]; i += 1
                if x != 255: break
    h = huff_cost(collections.Counter(lit_bytes)) / 8
    print(f'  LZ4 {name:10s}:block {len(blk)} 字节,字面量 {len(lit_bytes)} 字节;对字面量做 Huffman 估计 {h:.0f} 字节,可省 {len(lit_bytes) - h:.0f} 字节({(len(lit_bytes) - h) * 100 / len(blk):.1f}% 的 block);对照 zstd-3 {len(zstandard.ZstdCompressor(level=3).compress(S1))} 字节')
print('== 四:各压缩器在不同数据上的压缩比(每份 1 MiB)')
rnd = random.Random(7).randbytes(1 << 20)
print(f'  {"数据":22s} {"snappy":>8s} {"lz4":>8s} {"lz4 HC-9":>9s} {"zlib-6":>8s} {"zstd-3":>8s} {"zstd-19":>8s}')
for lab, d in (('products JSON Lines', S1), ('类 HTML 页面', SP), ('timeseries JSON Lines', ST), ('随机字节', rnd)):
    f = lambda c: f'{len(d) / len(c):7.2f}×'
    print(f'  {lab:22s} {f(snappy.compress(d))} {f(lz4.block.compress(d, store_size=False))} {len(d) / len(lz4.block.compress(d, store_size=False, mode="high_compression", compression=9)):8.2f}× {f(zlib.compress(d, 6))} {f(zstandard.ZstdCompressor(level=3).compress(d))} {f(zstandard.ZstdCompressor(level=19).compress(d))}')
print('== 五:窗口与匹配长度的限制(用上面的解析器看更大的数据:pages 8 MiB 与 products 全部 6.9 MiB)')
for lab, d in (('pages 8 MiB', b''.join(PG)[:8 << 20]), ('products 全部', jl(P))):
    blk = lz4.block.compress(d, store_size=False); seqs, _ = parse_lz4(blk); of = [s[2] for s in seqs if s[2]]
    c = snappy.compress(d); n, els, _ = parse_snappy(c); cp = [e for e in els if e[0] != 'L']
    print(f'  {lab}:LZ4 最大偏移 {max(of)}(上限 65535);Snappy 最大偏移 {max(e[2] for e in cp)},复制类型 {dict(collections.Counter(e[0] for e in cp))}')
print('== 六:很短的输入:各格式的固定开销(字节)')
print(f'  {"输入":14s} {"lz4.block":>9s} {"lz4.frame":>9s} {"snappy raw":>10s} {"zlib":>6s} {"gzip":>6s} {"zstd-3":>7s}')
for lab, d in (('空', b''), ('1 字节', b'a'), ('10 字节', b'0123456789'), ('100 字节 JSON', S1[:100]), ('1000 字节 JSON', S1[:1000])):
    print(f'  {lab:14s} {len(lz4.block.compress(d, store_size=False)):9d} {len(lz4.frame.compress(d)):9d} {len(snappy.compress(d)):10d} {len(zlib.compress(d, 6)):6d} {len(gzip.compress(d, 6, mtime=0)):6d} {len(zstandard.ZstdCompressor(level=3).compress(d)):7d}')
purge()
