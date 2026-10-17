import sys, os, subprocess, struct, importlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e5')
d = pdir('e5'); sys.path.insert(0, str(d))
PROTOS = {
'prod.proto': 'syntax = "proto3"; package pr; message Seller { int32 id = 1; string name = 2; } message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; double rating = 7; repeated string tags = 8; string category = 9; string updated_at = 10; Seller seller = 11; }',
'prodhi.proto': 'syntax = "proto3"; package ph; message Seller { int32 id = 16; string name = 17; } message Product { int64 id = 16; string url = 17; string title = 18; double price = 19; string currency = 20; int32 stock = 21; double rating = 22; repeated string tags = 23; string category = 24; string updated_at = 25; Seller seller = 26; }',
'v1.proto': 'syntax = "proto3"; package v1; message Item { int32 id = 1; string name = 2; }',
'v2.proto': 'syntax = "proto3"; package v2; message Item { int32 id = 1; string name = 2; double price = 3; }',
'v3.proto': 'syntax = "proto3"; package v3; message Item { int64 id = 1; string name = 2; }',
'v4.proto': 'syntax = "proto3"; package v4; message Item { string id = 1; string name = 2; }',
'v5.proto': 'syntax = "proto3"; package v5; message Item { int32 id = 1; int32 name = 2; }',
'v6.proto': 'syntax = "proto3"; package v6; message Item { int32 id = 1; string title = 2; }',
'pres.proto': 'syntax = "proto3"; package pre; message Plain { int32 a = 1; int32 b = 2; string s = 3; } message Opt { optional int32 a = 1; optional int32 b = 2; optional string s = 3; }',
}
for fn, src in PROTOS.items(): (d / fn).write_text(src)
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}'] + [str(d / f) for f in PROTOS], check=True)
import prod_pb2, prodhi_pb2, v1_pb2, v2_pb2, v3_pb2, v4_pb2, v5_pb2, v6_pb2, pres_pb2
P = products()
def to_pb(x, mod):
    m = mod.Product(); 
    for k in ('id', 'url', 'title', 'price', 'currency', 'stock', 'rating', 'category', 'updated_at'): setattr(m, k, x[k])
    m.tags.extend(x['tags']); m.seller.id = x['seller']['id']; m.seller.name = x['seller']['name']; return m
def parse_wire(b, depth=0, out=None):
    out = [] if out is None else out; i = 0
    while i < len(b):
        start = i; key = 0; sh = 0
        while True:
            c = b[i]; i += 1; key |= (c & 0x7f) << sh; sh += 7
            if not c & 0x80: break
        f, wt = key >> 3, key & 7
        if wt == 0:
            v = 0; sh = 0
            while True:
                c = b[i]; i += 1; v |= (c & 0x7f) << sh; sh += 7
                if not c & 0x80: break
            out.append((start, i - start, f, wt, v))
        elif wt == 1: out.append((start, 9, f, wt, struct.unpack('<d', b[i:i + 8])[0])); i += 8
        elif wt == 5: out.append((start, 5, f, wt, struct.unpack('<f', b[i:i + 4])[0])); i += 4
        elif wt == 2:
            ln = 0; sh = 0
            while True:
                c = b[i]; i += 1; ln |= (c & 0x7f) << sh; sh += 7
                if not c & 0x80: break
            out.append((start, i - start + ln, f, wt, b[i:i + ln])); i += ln
    return out
x0 = P[0]; m0 = to_pb(x0, prod_pb2); b0 = m0.SerializeToString()
print(f'== 一:一条 products 记录的 Protobuf 字节(第 0 条,共 {len(b0)} 字节;JSON 紧凑 {len(j(x0))} 字节,MessagePack {len(msgpack.packb(x0))} 字节),逐个字段拆解')
print(f'  {"偏移":>4s} {"字节数":>5s} {"字段号":>5s} {"类型":>12s}  内容')
WT = {0: 'varint', 1: '64 位', 2: '长度前缀', 5: '32 位'}
for off, ln, f, wt, v in parse_wire(b0):
    desc = repr(v.decode('utf-8', 'replace')) if wt == 2 and f != 11 else (f'(嵌套消息 {len(v)} 字节)' if f == 11 else repr(v))
    print(f'  {off:4d} {ln:5d} {f:5d} {WT[wt]:>12s}  {desc}')
print(f'  前 24 字节:{b0[:24].hex(" ")}  (08 = 字段 1 类型 varint;12 = 字段 2 类型 长度前缀)')
r = subprocess.run(['protoc', '--decode_raw'], input=b0, capture_output=True); print('  protoc --decode_raw 的输出前 5 行:' + ' | '.join(r.stdout.decode().splitlines()[:5]))
import re as _re
top = [l for l in r.stdout.decode().splitlines() if _re.match(r'^\d+(:| \{)', l)]
print(f'  手写解析得到 {len(parse_wire(b0))} 个顶层字段(tags 的 3 个元素各算一个,嵌套的 seller 算一个);protoc --decode_raw 输出 {len(top)} 个顶层条目:{"一致" if len(top) == len(parse_wire(b0)) else "不一致"}')
print('== 二:字段号决定字段头的长度:1–15 的字段头 1 字节,16 起 2 字节(同一份 products 数据换一套字段号)')
lo = sum(len(to_pb(x, prod_pb2).SerializeToString()) for x in P); hi = sum(len(to_pb(x, prodhi_pb2).SerializeToString()) for x in P)
print(f'  字段号 1–11:2 万条共 {lo} 字节(平均 {lo / len(P):.1f});字段号 16–26:{hi} 字节(平均 {hi / len(P):.1f}),多 {hi - lo} 字节 = 每条多 {(hi - lo) / len(P):.1f} 字节;一条记录有 {len(parse_wire(b0)) + 2} 个字段头(13 个顶层 + seller 里的 2 个),每个多 1 字节')
print(f'  字段 1 的字段头(varint):{bytes([(1 << 3) | 0]).hex()};字段 15:{bytes([(15 << 3) | 0]).hex()};字段 16(varint 类型)的字段头:{bytes([((16 << 3) | 0) & 0x7f | 0x80, ((16 << 3) | 0) >> 7]).hex()}(2 字节)')
print('== 三:2 万条 products 的体积(每条单独序列化再拼接,或者整批作为 repeated):Protobuf 对 JSON 与 MessagePack')
pbs = [to_pb(x, prod_pb2).SerializeToString() for x in P]
def vi(n):
    o = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: o.append(b | 0x80)
        else: o.append(b); return bytes(o)
framed = b''.join(vi(len(s)) + s for s in pbs); jb = jl(P); mb = b''.join(msgpack.packb(x) for x in P)
zs = lambda b: len(zstandard.ZstdCompressor(level=3).compress(b))
print(f'  {"格式":26s} {"字节":>9s} {"zstd-3":>9s} {"gzip-6":>9s}')
for lab, b in (('JSON Lines(紧凑)', jb), ('MessagePack(逐条拼接)', mb), ('Protobuf(长度前缀拼接)', framed)): print(f'  {lab:26s} {len(b):9d} {zs(b):9d} {len(zlib.compress(b, 6)):9d}')
print(f'  Protobuf 比 JSON 小 {100 - len(framed) * 100 / len(jb):.1f}%,比 MessagePack 小 {100 - len(framed) * 100 / len(mb):.1f}%;压缩后比 JSON {"小" if zs(framed) < zs(jb) else "大"} {abs(100 - zs(framed) * 100 / zs(jb)):.1f}%')
print('== 四:schema 演进:用一个版本写入、另一个版本读取,会发生什么')
def rt(w_mod, w_vals, r_mod):
    w = w_mod.Item(**w_vals); b = w.SerializeToString(); r_ = r_mod.Item(); r_.ParseFromString(b); return b, r_
cases = [('新写(v2 多了 price)→ 旧读(v1)', v2_pb2, dict(id=7, name='ab', price=9.5), v1_pb2), ('旧写(v1)→ 新读(v2)', v1_pb2, dict(id=7, name='ab'), v2_pb2),
         ('字段改名 name→title(编号不变)', v1_pb2, dict(id=7, name='ab'), v6_pb2), ('int32 → int64(同编号),值 2**40', v3_pb2, dict(id=2 ** 40, name='ab'), v1_pb2),
         ('int32 → int64,值 -5', v3_pb2, dict(id=-5, name='ab'), v1_pb2), ('int32(v1)→ string(v4)读,id=7', v1_pb2, dict(id=7, name='ab'), v4_pb2), ('string(name)→ int32(v5)读', v1_pb2, dict(id=7, name='ab'), v5_pb2)]
for lab, wm, vals, rm in cases:
    try:
        b, r_ = rt(wm, vals, rm); print(f'  {lab}:字节 {b.hex(" ")};读出 {{{", ".join(f"{f.name}={getattr(r_, f.name)!r}" for f in rm.Item.DESCRIPTOR.fields)}}}')
    except Exception as e: print(f'  {lab}:读取抛出 {type(e).__name__}: {str(e)[:60]}')
b1 = v2_pb2.Item(id=7, name='ab', price=9.5).SerializeToString(); old = v1_pb2.Item(); old.ParseFromString(b1); back = old.SerializeToString(); again = v2_pb2.Item(); again.ParseFromString(back)
print(f'  旧版本读到新字段后再写回:原字节 {len(b1)} 字节,旧版本重新序列化 {len(back)} 字节({"保留了" if again.price == 9.5 else "丢掉了"}未知字段 price),新版本再读 price={again.price}')
print('== 五:默认值与字段是否存在:proto3 普通字段等于默认值时不写出,optional 字段会写出')
pl_ = pres_pb2.Plain(a=0, b=5, s=''); op = pres_pb2.Opt(a=0, b=5, s='')
print(f'  Plain(a=0, b=5, s=""):{pl_.SerializeToString().hex(" ")}({len(pl_.SerializeToString())} 字节);Opt(a=0, b=5, s=""):{op.SerializeToString().hex(" ")}({len(op.SerializeToString())} 字节)')
try: pl_.HasField('a')
except ValueError as e: print(f'  Plain.HasField("a") → ValueError({str(e)[:50]})')
print(f'  Opt.HasField("a") = {op.HasField("a")},Opt().HasField("a") = {pres_pb2.Opt().HasField("a")};Plain 解出来的 a 是 {pres_pb2.Plain.FromString(pl_.SerializeToString()).a},无法区分"写了 0"和"没写"')
zeros = [dict(stock=0, rating=0.0) for _ in range(1000)]
pz = sum(len(prod_pb2.Product(stock=z['stock'], rating=z['rating']).SerializeToString()) for z in zeros)
print(f'  1000 条 stock=0、rating=0.0 的记录:proto3 普通字段共 {pz} 字节(全是空消息);JSON 的 "stock":0,"rating":0.0 每条至少 {len(json.dumps({"stock": 0, "rating": 0.0}, separators=(",", ":")))} 字节')
purge()
