import sys, os, struct, gzip as _gz, binascii; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e12')
P = products(); S1 = jl(P)[:1 << 20]
LB = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]; LE = [0] * 8 + [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [0]
DB = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]; DE = [0, 0, 0, 0] + [k // 2 - 1 for k in range(4, 30)]
CLORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]
class BR:
    def __init__(s, data): s.d = data; s.p = 0
    def bits(s, n):
        v = 0
        for i in range(n): v |= ((s.d[s.p >> 3] >> (s.p & 7)) & 1) << i; s.p += 1
        return v
def canon(lengths):
    code = 0; res = {}; mx = max(lengths) if lengths else 0
    for L in range(1, mx + 1):
        for s, l in enumerate(lengths):
            if l == L: res[(L, code)] = s; code += 1
        code <<= 1
    return res
def hdec(br, table):
    code = 0; L = 0
    while True:
        code = (code << 1) | br.bits(1); L += 1
        if (L, code) in table: return table[(L, code)]
        if L > 15: raise ValueError('bad huffman code')
def inflate(raw, info=None):
    """解码 raw deflate 流;info 里记录每个块的统计"""
    br = BR(raw); out = bytearray(); blocks = []
    while True:
        b0 = br.p; final = br.bits(1); typ = br.bits(2); rec = dict(type=typ, start_bit=b0, lit=0, match=0, matchbytes=0, out_start=len(out))
        if typ == 0:
            br.p = (br.p + 7) & ~7; ln = br.bits(16); nl = br.bits(16); assert ln == (~nl & 0xffff)
            for _ in range(ln): out.append(br.bits(8))
            rec['hdr_bits'] = br.p - b0 - ln * 8; rec['lit'] = ln
        else:
            if typ == 1:
                ll = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8; dl = [5] * 30; rec['hdr_bits'] = 3
            else:
                hlit = br.bits(5) + 257; hdist = br.bits(5) + 1; hclen = br.bits(4) + 4; cl = [0] * 19
                for i in range(hclen): cl[CLORDER[i]] = br.bits(3)
                ct = canon(cl); lens = []
                while len(lens) < hlit + hdist:
                    s = hdec(br, ct)
                    if s < 16: lens.append(s)
                    elif s == 16: lens += [lens[-1]] * (3 + br.bits(2))
                    elif s == 17: lens += [0] * (3 + br.bits(3))
                    else: lens += [0] * (11 + br.bits(7))
                ll, dl = lens[:hlit], lens[hlit:]; rec.update(hlit=hlit, hdist=hdist, hclen=hclen, hdr_bits=br.p - b0, used_lit=sum(1 for x in ll if x), used_dist=sum(1 for x in dl if x), maxlen=max(ll))
            lt = canon(ll); dt = canon(dl)
            while True:
                s = hdec(br, lt)
                if s < 256: out.append(s); rec['lit'] += 1
                elif s == 256: break
                else:
                    k = s - 257; L = LB[k] + br.bits(LE[k]); dk = hdec(br, dt); D = DB[dk] + br.bits(DE[dk])
                    for _ in range(L): out.append(out[-D])
                    rec['match'] += 1; rec['matchbytes'] += L
        rec['end_bit'] = br.p; rec['out_end'] = len(out); blocks.append(rec)
        if final: break
    if info is not None: info.extend(blocks)
    return bytes(out)
def raw_deflate(data, lv=9): c = zlib.compressobj(lv, zlib.DEFLATED, -15); return c.compress(data) + c.flush()
print('== 一:gzip 文件的结构:10 字节头 + deflate 数据 + 8 字节尾(CRC32 与原始长度),拆开一个真实的 gzip 文件')
data = S1[:200000]; g = _gz.compress(data, 9, mtime=1760000000)
mt = struct.unpack('<I', g[4:8])[0]; crc, isz = struct.unpack('<II', g[-8:])
print(f'  总长 {len(g)} 字节 = 头 10 + deflate {len(g) - 18} + 尾 8;头:魔数 {g[0:2].hex()}、方法 {g[2]}(8 = deflate)、标志 {g[3]:#x}、mtime {mt}、xfl {g[8]}、操作系统 {g[9]}')
print(f'  尾:CRC32 {crc:#010x}(我自己用 binascii.crc32 算 {binascii.crc32(data):#010x}:{"一致" if crc == binascii.crc32(data) else "不一致"})、原始长度 {isz}({"等于输入长度" if isz == len(data) else "不等"} {len(data)})')
print(f'  同样数据,zlib 格式(2 字节头 + 4 字节 Adler-32 尾):{len(zlib.compress(data, 9))} 字节;raw deflate:{len(raw_deflate(data))} 字节;三种封装差 {len(g) - len(raw_deflate(data))} / {len(zlib.compress(data, 9)) - len(raw_deflate(data))} 字节')
print('== 二:deflate 流由若干个块组成;我写的解码器解 products 1 MiB 的 zlib 级别 9 输出,逐块统计')
raw = raw_deflate(S1); info = []; t0 = time.perf_counter(); got = inflate(raw, info); el = time.perf_counter() - t0
print(f'  压缩后 {len(raw)} 字节,解出 {len(got)} 字节,与原文{"一致" if got == S1 else "不一致"}(纯 Python 解码用时 {el:.1f} 秒);共 {len(info)} 个块')
print(f'  {"块":>3s} {"类型":6s} {"输出字节":>8s} {"块占压缩字节":>10s} {"字面量":>7s} {"匹配":>6s} {"匹配覆盖":>8s} {"块头位数":>6s}')
for i, b in enumerate(info): print(f'  {i:3d} {["存储", "固定", "动态"][b["type"]]:6s} {b["out_end"] - b["out_start"]:8d} {(b["end_bit"] - b["start_bit"]) / 8:10.0f} {b["lit"]:7d} {b["match"]:6d} {b["matchbytes"] * 100 / max(1, b["out_end"] - b["out_start"]):7.1f}% {b["hdr_bits"]:6d}')
print(f'  总计:字面量 {sum(b["lit"] for b in info)} 个,匹配 {sum(b["match"] for b in info)} 个,匹配覆盖 {sum(b["matchbytes"] for b in info) * 100 / len(S1):.1f}% 的输出')
print('== 三:动态 Huffman 块的块头:先存"码长的码长",再用它存字面量/长度和距离两棵树的码长(第一个块)')
b = [x for x in info if x['type'] == 2][0]
print(f'  HLIT = {b["hlit"]}(字面量/长度码 {b["hlit"]} 个,257 起)、HDIST = {b["hdist"]}、HCLEN = {b["hclen"]}(码长码的 19 个中存了前 {b["hclen"]} 个,顺序 {CLORDER})')
print(f'  块头共 {b["hdr_bits"]} 位 = {b["hdr_bits"] / 8:.0f} 字节,占这个块压缩后 {(b["end_bit"] - b["start_bit"]) / 8:.0f} 字节的 {b["hdr_bits"] / (b["end_bit"] - b["start_bit"]) * 100:.1f}%;用到 {b["used_lit"]} 个字面量/长度符号、{b["used_dist"]} 个距离符号;字面量/长度码最长 {b["maxlen"]} 位')
print(f'  所有动态块的块头合计 {sum(x["hdr_bits"] for x in info if x["type"] == 2) / 8:.0f} 字节,占全部压缩数据的 {sum(x["hdr_bits"] for x in info if x["type"] == 2) / 8 * 100 / len(raw):.1f}%')
print('== 四:同一份数据的 token:我自己的 LZ77(第 11 篇的方法)与 zlib 实际选的匹配比较(前 128 KiB)')
info2 = []; r2 = raw_deflate(S1[:128 * 1024]); inflate(r2, info2)
zl_lit = sum(x['lit'] for x in info2); zl_m = sum(x['match'] for x in info2); zl_mb = sum(x['matchbytes'] for x in info2)
print(f'  zlib 级别 9:{len(info2)} 个块,字面量 {zl_lit} 个,匹配 {zl_m} 个,匹配覆盖 {zl_mb * 100 / (128 * 1024):.1f}%,平均匹配长度 {zl_mb / zl_m:.1f} 字节,压缩后 {len(r2)} 字节')
print('  (第 11 篇我的懒匹配 chain 64 是 14994 个 token:字面量 5351 个,匹配 9643 个,平均长度 13.0 字节,估算 28234 字节)')
print('== 五:压缩器怎么选块类型:不同内容各压一次,看每个块用了存储(0)/固定(1)/动态(2)')
cases = [('空输入', b''), ('1 个字节', b'a'), ('"hello world"', b'hello world'), ('50 字节的短文本', S1[:50]), ('300 字节的 JSON', S1[:300]), ('2000 字节的 JSON', S1[:2000]), ('随机 5000 字节', random.Random(1).randbytes(5000)), ('随机 1 MiB', random.Random(2).randbytes(1 << 20)), ('全零 1 MiB', bytes(1 << 20))]
print(f'  {"输入":20s} {"原字节":>8s} {"deflate 后":>10s} 块类型序列(0 存储 / 1 固定 / 2 动态)')
for lab, d in cases:
    r_ = raw_deflate(d); inf = []; inflate(r_, inf); assert inflate(r_) == d
    seq = ''.join(str(x['type']) for x in inf); print(f'  {lab:20s} {len(d):8d} {len(r_):10d} {seq[:30]}{"…" if len(seq) > 30 else ""}(共 {len(inf)} 块)')
print('== 六:gzip 的一个细节:头里带时间戳,同样的数据每次压缩的字节可能不一样')
import io
g1 = _gz.compress(S1[:1000]); time.sleep(1.1); g2 = _gz.compress(S1[:1000])
def gzf(mt=None):
    bio = io.BytesIO()
    with _gz.GzipFile(fileobj=bio, mode='wb', mtime=mt) as f: f.write(S1[:1000])
    return bio.getvalue()
f1 = gzf(); time.sleep(1.1); f2 = gzf(); f3 = gzf(0); f4 = gzf(0)
diff = lambda a, b: [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
print(f'  gzip.compress 默认参数,间隔 1.1 秒压缩两次:{"字节完全相同" if g1 == g2 else "字节不同"}(头里的 mtime 是 {g1[4:8].hex()} 和 {g2[4:8].hex()})')
print(f'  gzip.GzipFile 默认 mtime,间隔 1.1 秒写两次:{"字节完全相同" if f1 == f2 else "字节不同"},不同的位置 {diff(f1, f2)}(都在头里 4–7 字节的 mtime:{f1[4:8].hex()} 对 {f2[4:8].hex()});mtime=0 写两次:{"字节完全相同" if f3 == f4 else "字节不同"}')
cat = _gz.compress(b'first ', mtime=0) + _gz.compress(b'second', mtime=0); print(f'  两个 gzip 文件直接拼在一起仍是合法的 gzip:gzip.decompress 得到 {_gz.decompress(cat)!r}(共 {len(cat)} 字节,每个成员各有 10 字节头 + 8 字节尾)')
purge()
