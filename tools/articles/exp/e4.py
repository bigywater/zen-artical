import sys, os, subprocess, struct, importlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e4')
T = timeseries(); P = products()
d = pdir('e4')
(d / 'v.proto').write_text('syntax = "proto3"; message V { int32 i32 = 1; sint32 s32 = 2; int64 i64 = 3; sint64 s64 = 4; fixed32 f32 = 5; fixed64 f64 = 6; uint32 u32 = 7; }')
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}', str(d / 'v.proto')], check=True)
sys.path.insert(0, str(d)); import v_pb2
def enc1(field, val):
    m = v_pb2.V(); setattr(m, field, val); b = m.SerializeToString()
    return b[1:]            # 去掉 1 字节字段头(字段号 1–7 都只占 1 字节)
def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: out.append(b | 0x80)
        else: out.append(b); return bytes(out)
def zz(n, bits=64): return ((n << 1) ^ (n >> (bits - 1))) & ((1 << bits) - 1)
def unzz(u): return (u >> 1) ^ -(u & 1)
print('== 一:varint 的规则:每字节低 7 位存数据,最高位 1 表示后面还有字节;手写的编码与 protobuf 库编码逐值对照')
print(f'  {"值":>12s} {"二进制(低位在后)":28s} {"手写 varint":24s} {"protobuf(uint32)":24s} 一致')
for n in (0, 1, 127, 128, 300, 16383, 16384, 2 ** 21, 2 ** 28 - 1, 2 ** 28, 2 ** 32 - 1):
    mine = varint(n); lib = enc1('u32', n); print(f'  {n:12d} {bin(n)[2:]:28s} {mine.hex(" "):24s} {lib.hex(" ") if lib else "(空:proto3 不写默认值 0)":24s} {"是" if mine == lib else ("否(库把默认值 0 整个省略了)" if n == 0 else "否")}')
print(f'  每个字节装 7 位有效数据:1 字节存 0–127,2 字节存到 {2 ** 14 - 1},3 字节到 {2 ** 21 - 1},4 字节到 {2 ** 28 - 1},5 字节到 uint32 上限')
print('== 二:负数:int32 把 -1 当成 64 位补码,占 10 个字节;sint32/sint64 用 ZigZag 把小负数映射成小正数')
print(f'  {"值":>8s} {"int32":>6s} {"int64":>6s} {"sint32":>7s} {"sint64":>7s}  ZigZag 映射 {"(手写)":6s}')
for n in (0, 1, -1, 2, -2, 63, -64, 64, -65, 1000, -1000, 2 ** 31 - 1, -2 ** 31):
    a = len(enc1('i32', n)); b = len(enc1('i64', n)); c = len(enc1('s32', n)); e = len(enc1('s64', n))
    print(f'  {n:8d} {a:6d} {b:6d} {c:7d} {e:7d}  {n} → {zz(n, 64)}  (还原 {unzz(zz(n, 64))}, 手写与库一致:{varint(zz(n, 64)) == enc1("s64", n) if n else "(0 被库省略)"})')
print(f'  int32 -1 的字节:{enc1("i32", -1).hex(" ")}(10 字节,前 9 个是 ff,最后 01);sint32 -1 的字节:{enc1("s32", -1).hex(" ")}')
print('== 三:数据分布决定大小(各 10 万个整数):varint、定长 4/8 字节、JSON 文本、MessagePack')
r = random.Random(11); n = 100000
dists = [('小值 0–100', [r.randint(0, 100) for _ in range(n)]), ('0–10000 的均匀值', [r.randint(0, 10000) for _ in range(n)]), ('任意 32 位整数', [r.randint(0, 2 ** 32 - 1) for _ in range(n)]),
         ('Unix 时间戳(2025–2026,秒)', [1735689600 + r.randint(0, 31536000) for _ in range(n)]), ('有序递增的时间戳', [1760000000 + i * 3 + r.randint(0, 2) for i in range(n)]), ('幂律(很多小值、少数大值)', [int(r.paretovariate(1.2)) for _ in range(n)])]
print(f'  {"分布":28s} {"varint":>8s} {"定长4":>8s} {"定长8":>8s} {"JSON 数组":>9s} {"MsgPack 数组":>11s}   平均每个数 varint 字节')
for lab, v in dists:
    vb = sum(len(varint(x)) for x in v); js = len(json.dumps(v, separators=(',', ':'))); mp = len(msgpack.packb(v))
    print(f'  {lab:28s} {vb:8d} {4 * n:8d} {8 * n:8d} {js:9d} {mp:11d}   {vb / n:5.2f}')
print('  (varint 和定长两列只算数字本身;JSON、MsgPack 两列是整个数组,含逗号、括号或数组头)')
print('== 四:差分(delta)编码:先存相邻两项的差,再 varint(5 万条 timeseries 的 ts 列)')
ts = [x['ts'] for x in T]; dl = [ts[0]] + [b - a for a, b in zip(ts, ts[1:])]; dd = [dl[0], dl[1]] + [b - a for a, b in zip(dl[1:], dl[2:])]
def vzz(v): return b''.join(varint(zz(x)) for x in v)
rows = [('原始值 varint', b''.join(varint(x) for x in ts)), ('原始值定长 8 字节', b''.join(struct.pack('<q', x) for x in ts)), ('差分 + ZigZag varint', vzz(dl)), ('差分的差分 + ZigZag varint', vzz(dd))]
print(f'  {"表示":26s} {"字节":>8s} {"zstd-3":>8s} {"gzip-6":>8s}')
for lab, b in rows: print(f'  {lab:26s} {len(b):8d} {len(zstandard.ZstdCompressor(level=3).compress(b)):8d} {len(zlib.compress(b, 6)):8d}')
print(f'  ts 列的差值只有 {sorted(set(dl[1:]))} 这几种(值的个数 {len(set(dl[1:]))});JSON 文本 {len(j(ts))} 字节')
print('== 五:浮点:float64、float32、按固定小数位放大成整数再 varint(price 两位小数,2 万条)')
pr = [x['price'] for x in P]
f64 = b''.join(struct.pack('<d', x) for x in pr); f32 = b''.join(struct.pack('<f', x) for x in pr); cents = b''.join(varint(int(round(x * 100))) for x in pr); txt = ','.join(repr(x) for x in pr).encode()
errs = [abs(struct.unpack('<f', struct.pack('<f', x))[0] - x) for x in pr]; bad = sum(1 for x in pr if round(struct.unpack('<f', struct.pack('<f', x))[0], 2) != x)
print(f'  {"表示":28s} {"字节":>8s} {"zstd-3":>8s}')
for lab, b in (('float64 定长', f64), ('float32 定长', f32), ('乘 100 取整后 varint', cents), ('十进制文本(逗号分隔)', txt)): print(f'  {lab:28s} {len(b):8d} {len(zstandard.ZstdCompressor(level=3).compress(b)):8d}')
print(f'  float32 的误差:最大 {max(errs):.3g};{bad} 个值(占 {bad * 100 / len(pr):.1f}%)转成 float32 再 round 到 2 位小数后与原值不同;例:{pr[0]} → {struct.unpack("<f", struct.pack("<f", pr[0]))[0]!r}')
print(f'  乘 100 取整再还原(/100)与原值完全一致:{all(int(round(x * 100)) / 100 == x for x in pr)}')
print('== 六:varint 之后再压缩——定长整数前面有大量零字节,也会被压缩器去掉(zstd-3)')
print(f'  {"分布":28s} {"varint":>8s} {"→zstd":>8s} {"定长4":>8s} {"→zstd":>8s} {"JSON":>8s} {"→zstd":>8s}')
zz3 = lambda b: len(zstandard.ZstdCompressor(level=3).compress(b))
for lab, v in dists:
    vb = b''.join(varint(x) for x in v); fb = b''.join(struct.pack('<I', x & 0xffffffff) for x in v); jb = json.dumps(v, separators=(',', ':')).encode()
    print(f'  {lab:28s} {len(vb):8d} {zz3(vb):8d} {len(fb):8d} {zz3(fb):8d} {len(jb):8d} {zz3(jb):8d}')
purge()
