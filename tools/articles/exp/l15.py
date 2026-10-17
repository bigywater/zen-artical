import sys, os, random, bisect, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l15')
d = lab('l15')
files = {f'd{i // 100:02d}/f{i:04d}.txt': f'文件 {i} 的内容\n' for i in range(3000)}
W(d, files); ci(d, '3000 个小文件', t=0)
run(d, 'git gc -q')
pk = next((d / '.git' / 'objects' / 'pack').glob('*.pack')); ix = pk.with_suffix('.idx'); data = ix.read_bytes()
print('== 一:.idx 文件的结构:魔数、版本、256 项 fanout 表、hash 表、crc 表、offset 表、两个校验和')
magic = data[:4]; ver = struct.unpack('>I', data[4:8])[0]
fan = list(struct.unpack('>256I', data[8:8 + 1024])); N = fan[255]
print(f'  魔数 {magic!r}  版本 {ver}  对象数(fanout[255]) = {N:,}  文件大小 {len(data):,} 字节')
hexdump(data, 32)
off_hash = 8 + 1024; off_crc = off_hash + 20 * N; off_off = off_crc + 4 * N
print(f'  各段字节范围: fanout [8,{8 + 1024})  hash 表 [{off_hash},{off_crc})  crc 表 [{off_crc},{off_off})  offset 表 [{off_off},{off_off + 4 * N})  再加 20+20 字节校验和')
print(f'  4 + 4 + 1024 + {N}×(20+4+4) + 40 = {8 + 1024 + N * 28 + 40:,}(与文件大小一致: {8 + 1024 + N * 28 + 40 == len(data)})')
print('== 二:fanout[i] = 第一个字节 ≤ i 的对象个数(累计值),所以每一档的个数是相邻两项之差')
hashes = [data[off_hash + 20 * i: off_hash + 20 * i + 20] for i in range(N)]
print('  hash 表是按 hash 升序排列的:', hashes == sorted(hashes))
cnt = [0] * 256
for h in hashes: cnt[h[0]] += 1
acc = 0; ok = True
for i in range(256):
    acc += cnt[i]; ok &= (acc == fan[i])
print('  用 hash 表重新数出来的累计值与 fanout 全部一致:', ok)
print('  部分条目:'); [print(f'    fanout[0x{i:02x}] = {fan[i]:>5}   该档对象数 = {fan[i] - (fan[i - 1] if i else 0)}') for i in (0, 1, 0x7f, 0xfe, 0xff)]
sizes = [fan[i] - (fan[i - 1] if i else 0) for i in range(256)]
print(f'  256 档的对象数:最少 {min(sizes)},最多 {max(sizes)},平均 {N / 256:.1f}')
print('== 三:查一个对象:先用第一个字节在 fanout 里圈出范围,再在范围内二分查找')
def _bs(l, h, t):
    n = 0
    while l < h:
        m = (l + h) // 2; n += 1
        if hashes[m] == t: return n
        if hashes[m] < t: l = m + 1
        else: h = m
    return n
target = next(x.hex() for x in hashes if x[0] > 0x40 and _bs(fan[x[0] - 1] if x[0] else 0, fan[x[0]], x) == 4 and out1(d, f'git cat-file -t {x.hex()}') == 'blob')
tb = bytes.fromhex(target); b0 = tb[0]
lo = fan[b0 - 1] if b0 else 0; hi = fan[b0]
print(f'  目标 {target}\n  第一个字节 0x{b0:02x} → fanout[0x{b0 - 1:02x}]={lo}, fanout[0x{b0:02x}]={hi},候选范围 [{lo}, {hi}) 共 {hi - lo} 个')
steps = 0
l, h = lo, hi
while l < h:
    m = (l + h) // 2; steps += 1; c = hashes[m]
    print(f'    第 {steps} 次比较:下标 {m}  hash {c.hex()[:12]}…  {"<" if c < tb else (">" if c > tb else "==")} 目标')
    if c == tb: idx = m; break
    if c < tb: l = m + 1
    else: h = m
off = struct.unpack('>I', data[off_off + 4 * idx: off_off + 4 * idx + 4])[0]
vp = out1(d, f'git verify-pack -v {pk} | grep ^{target}').split()
print(f'  下标 {idx} → offset 表里的值 {off};git verify-pack 给出的偏移 {vp[4]}  一致: {off == int(vp[4])}')
print('== 四:fanout 省了多少次比较:对全部对象各查一次,统计二分比较次数')
def bs(l, h, t):
    n = 0
    while l < h:
        m = (l + h) // 2; n += 1
        if hashes[m] == t: return n
        if hashes[m] < t: l = m + 1
        else: h = m
    return n
with_f = []; without = []
for hh in hashes:
    b = hh[0]; with_f.append(bs(fan[b - 1] if b else 0, fan[b], hh)); without.append(bs(0, N, hh))
print(f'  对象数 N={N}')
print(f'  不用 fanout(整表二分):平均 {sum(without) / N:.2f} 次,最多 {max(without)} 次;log2(N) = {math.log2(N):.2f}')
print(f'  用 fanout 圈范围再二分:平均 {sum(with_f) / N:.2f} 次,最多 {max(with_f)} 次')
print('== 五:尾部:pack 的校验和 + idx 自己的校验和;crc 表用来在复用 pack 数据时检查坏数据')
print('  idx 倒数第 40~21 字节(pack 的 SHA-1):', data[-40:-20].hex()); print('  pack 文件最后 20 字节               :', pk.read_bytes()[-20:].hex())
print('  idx 最后 20 字节(idx 自己的 SHA-1)  :', data[-20:].hex()); print('  重新算 idx 前面全部内容的 SHA-1        :', hashlib.sha1(data[:-20]).hexdigest())
e = parse_pack(pk.read_bytes())[2]; pkd = pk.read_bytes()
i0 = 5; ent = e[i0]; nxt = e[i0 + 1]['off'] if i0 + 1 < len(e) else len(pkd) - 20
crc = zlib.crc32(pkd[ent['off']:nxt]); order = {int.from_bytes(data[off_off + 4 * k: off_off + 4 * k + 4], 'big'): k for k in range(N)}
k = order[ent['off']]; icrc = struct.unpack('>I', data[off_crc + 4 * k: off_crc + 4 * k + 4])[0]
print(f'  取 pack 里偏移 {ent["off"]} 的条目原始字节算 CRC32 = {crc:08x};idx 的 crc 表里这一项 = {icrc:08x}  一致: {crc == icrc}')
