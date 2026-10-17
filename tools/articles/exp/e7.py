import sys, os, subprocess, re, bisect; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e7')
d = pdir('e7'); sys.path.insert(0, str(d))
FULL = 'message Seller { int32 id = 1; string name = 2; } message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; double rating = 7; repeated string tags = 8; string category = 9; string updated_at = 10; Seller seller = 11; } message Batch { repeated Product items = 1; }'
PROJ = {1: 'message Product { double price = 4; } message Batch { repeated Product items = 1; }', 3: 'message Product { int64 id = 1; double price = 4; int32 stock = 6; } message Batch { repeated Product items = 1; }',
        6: 'message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; } message Batch { repeated Product items = 1; }'}
(d / 'full.proto').write_text('syntax = "proto3"; package full; ' + FULL)
for k, v in PROJ.items(): (d / f'proj{k}.proto').write_text(f'syntax = "proto3"; package proj{k}; ' + v)
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}'] + [str(d / f) for f in ['full.proto'] + [f'proj{k}.proto' for k in PROJ]], check=True)
import full_pb2, proj1_pb2, proj3_pb2, proj6_pb2
P = products(); N = len(P)
def to_pb(x):
    m = full_pb2.Product()
    for k in ('id', 'url', 'title', 'price', 'currency', 'stock', 'rating', 'category', 'updated_at'): setattr(m, k, x[k])
    m.tags.extend(x['tags']); m.seller.id = x['seller']['id']; m.seller.name = x['seller']['name']; return m
pbs = [to_pb(x).SerializeToString() for x in P]; batch = full_pb2.Batch(); batch.items.extend(to_pb(x) for x in P); pbb = batch.SerializeToString()
jl_lines = [j(x) for x in P]; jl_b = b'\n'.join(jl_lines); jl_off = [0]
for l in jl_lines: jl_off.append(jl_off[-1] + len(l) + 1)
jarr = j(P); mp_recs = [msgpack.packb(x) for x in P]; mp_b = b''.join(mp_recs); mp_off = [0]
for r_ in mp_recs: mp_off.append(mp_off[-1] + len(r_))
mp_arr = msgpack.packb(P); pb_b = b''.join(pbs); pb_off = [0]
for s in pbs: pb_off.append(pb_off[-1] + len(s))
rr = random.Random(7); picks = [rr.randrange(N) for _ in range(300)]
def per(fn, reps):
    ts = []
    for k in picks[:reps]:
        t0 = time.perf_counter(); v = fn(k); ts.append(time.perf_counter() - t0); assert v == P[k]['title'], (k, v)
    ts.sort(); return ts[len(ts) // 2] * 1000
print(f'== 一:按序号取第 k 条记录的 title(2 万条,随机 k,每次查询的中位耗时;"整批"一栏表示每次都要解整个数组)')
rows = [('JSON 数组(整批 json.loads)', lambda k: json.loads(jarr)[k]['title'], 5, len(jarr)), ('JSON 数组(整批 orjson.loads)', lambda k: orjson.loads(jarr)[k]['title'], 5, len(jarr)), ('JSON Lines + 行偏移索引', lambda k: json.loads(jl_b[jl_off[k]:jl_off[k + 1]])['title'], 300, jl_off[k0 := 1] - jl_off[0]),
        ('MessagePack 数组(整批 unpackb)', lambda k: msgpack.unpackb(mp_arr, raw=False)[k]['title'], 5, len(mp_arr)), ('MessagePack 逐条 + 偏移索引', lambda k: msgpack.unpackb(mp_b[mp_off[k]:mp_off[k + 1]], raw=False)['title'], 300, mp_off[1]),
        ('Protobuf Batch(整批解析)', lambda k: full_pb2.Batch.FromString(pbb).items[k].title, 300, len(pbb)), ('Protobuf 逐条 + 偏移索引', lambda k: full_pb2.Product.FromString(pb_b[pb_off[k]:pb_off[k + 1]]).title, 300, pb_off[1])]
for lab, f, reps, nbytes in rows:
    t = per(f, reps); print(f'  {lab:34s} 每次查询 {t:9.4f} ms(每次要处理约 {nbytes / 1024:8.1f} KiB 的输入)')
print('== 二:扫一整列——对全部 2 万条求 price 的和(各 7 次中位数)')
true_sum = sum(x['price'] for x in P)
def pb_sum(mod, b): return sum(m.price for m in mod.Batch.FromString(b).items)
rx = re.compile(rb'"price":([0-9.]+)')
res = [('json.loads 后求和', lambda: sum(x['price'] for x in json.loads(jarr))), ('orjson.loads 后求和', lambda: sum(x['price'] for x in orjson.loads(jarr))), ('msgpack.unpackb 后求和', lambda: sum(x['price'] for x in msgpack.unpackb(mp_arr, raw=False))),
       ('Protobuf 完整 schema(11 个字段)', lambda: pb_sum(full_pb2, pbb)), ('Protobuf 只声明 price 一个字段的 schema', lambda: pb_sum(proj1_pb2, pbb)), ('JSON Lines 上用正则直接扫 "price":', lambda: sum(float(m) for m in rx.findall(jl_b)))]
for lab, f in res:
    m, lo, hi = timeit(f, 7); v = f(); print(f'  {lab:40s} 中位 {m * 1000:7.1f} ms({lo * 1000:.1f}–{hi * 1000:.1f}),求和 {v:.2f} {"✓" if abs(v - true_sum) < 1e-6 else "✗"}')
print(f'  正确的和是 {true_sum:.2f}')
print('== 三:字节级扫描 JSON 的两个陷阱:空白格式不同、同名的键出现在嵌套对象里')
true1 = sum(x['price'] for x in P)
sp = b'\n'.join(json.dumps(x, ensure_ascii=False).encode() for x in P)          # 默认分隔符:冒号后有空格
print(f'  同样的数据用 json.dumps 默认写法(冒号后面有空格):正则 "price":([0-9.]+) 扫出 {len(rx.findall(sp))} 个,和 {sum(float(m) for m in rx.findall(sp)):.2f}(真实和 {true1:.2f},共 {N} 条)')
P2 = [dict(x, seller=dict(x['seller'], price=1.0)) if i % 100 == 0 else x for i, x in enumerate(P)]
jl2 = jl(P2); got = sum(float(m) for m in rx.findall(jl2)); true2 = sum(x['price'] for x in P2)
print(f'  每 100 条里有 1 条的 seller 对象里也有一个 price 键(值 1.0,共 {sum(1 for i in range(N) if i % 100 == 0)} 条):正则的和 {got:.2f},顶层 price 的真实和 {true2:.2f},多算 {got - true2:.2f}(正好是嵌套的 price 之和)')
tq = jl(P[:1] ); P3 = dict(P[0], title='say \\"price\\":999 now'); t3 = j(P3)
print(f'  title 里含有 "price":999 这样的文本时,json.dumps 会把引号转义成 \\",所以正则 {"没有" if len(rx.findall(t3)) == 1 else "仍然"}被骗:找到 {len(rx.findall(t3))} 个 price(正确是 1 个)')
print('== 四:Protobuf 只声明用得上的字段(投影 schema)——解析并对全部 2 万条取 price 求和,各 7 次中位数')
for k, mod in ((1, proj1_pb2), (3, proj3_pb2), (6, proj6_pb2), (11, full_pb2)):
    m, lo, hi = timeit(lambda: sum(x.price for x in mod.Batch.FromString(pbb).items), 7); print(f'  schema 里声明 {k:2d} 个字段:中位 {m * 1000:6.1f} ms({lo * 1000:.1f}–{hi * 1000:.1f})')
rb = proj1_pb2.Batch.FromString(pbb); rt = rb.SerializeToString()
print(f'  投影 schema 解析后再序列化:{len(rt)} 字节(原 {len(pbb)} 字节){"——未声明的字段作为未知字段全部保留" if len(rt) == len(pbb) else "——未知字段被丢弃了"}')
print('== 五:压缩之后还能随机访问吗:把记录分块,每块单独 zstd-3 压缩(JSON Lines,2 万条),取第 k 条要解压它所在的整块')
zc = zstandard.ZstdCompressor(level=3); zd = zstandard.ZstdDecompressor()
print(f'  {"每块条数":>8s} {"压缩后总字节":>12s} {"压缩比":>7s} {"点查中位耗时":>12s}')
for bs in (1, 10, 100, 1000, 20000):
    blocks = [zc.compress(b'\n'.join(jl_lines[s:s + bs])) for s in range(0, N, bs)]; tot = sum(map(len, blocks))
    def look(k):
        blk = zd.decompress(blocks[k // bs]); lines = blk.split(b'\n'); return json.loads(lines[k % bs])['title']
    ts = []
    for k in picks[:200]:
        t0 = time.perf_counter(); v = look(k); ts.append(time.perf_counter() - t0); assert v == P[k]['title']
    ts.sort(); print(f'  {bs:8d} {tot:12d} {len(jl_b) / tot:6.2f}× {ts[len(ts) // 2] * 1000:10.4f} ms')
purge()
