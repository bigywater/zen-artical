import sys, os, subprocess, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
import brotli
tee('e23')
d = pdir('e23'); sys.path.insert(0, str(d))
(d / 'x.proto').write_text('''syntax = "proto3"; package x;
message Seller { int32 id = 1; string name = 2; }
message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; double rating = 7; repeated string tags = 8; string category = 9; string updated_at = 10; Seller seller = 11; }
message Batch { repeated Product items = 1; }''')
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}', str(d / 'x.proto')], check=True)
import x_pb2
P = products(); PG = pages(); N = len(P)
def pb1(x): return x_pb2.Product(id=x['id'], url=x['url'], title=x['title'], price=x['price'], currency=x['currency'], stock=x['stock'], rating=x['rating'], tags=x['tags'], category=x['category'], updated_at=x['updated_at'], seller=x_pb2.Seller(id=x['seller']['id'], name=x['seller']['name']))
def pbd(b): m = x_pb2.Product.FromString(b); return (m.id, m.url, m.title, m.price, m.currency, m.stock, m.rating, list(m.tags), m.category, m.updated_at, m.seller.id, m.seller.name)
zc3 = zstandard.ZstdCompressor(level=3); zd = zstandard.ZstdDecompressor()
print('== 一:场景"单条小消息"(RPC 或队列里的一条商品记录,约 360 字节):平均字节与"编码+解码"耗时(微秒/条,完整访问全部字段)')
tr, te = P[:5000], P[5000:7000]; n = len(te)
ENC = {'JSON(orjson)': (orjson.dumps, orjson.loads), 'MessagePack': (msgpack.packb, lambda b: msgpack.unpackb(b, raw=False)), 'Protobuf': (lambda x: pb1(x).SerializeToString(), pbd)}
print(f'  {"编码":14s} {"不压缩":>8s} {"zstd-3":>8s} {"+字典":>8s}   {"编码+解码 µs":>12s}  {"+zstd 字典 µs":>13s}')
res1 = {}
for k, (e, dcd) in ENC.items():
    items = [e(x) for x in te]; dd = zstandard.train_dictionary(16384, [e(x) for x in tr]); zcd = zstandard.ZstdCompressor(level=3, dict_data=dd); zdd = zstandard.ZstdDecompressor(dict_data=dd)
    t1 = timeit(lambda: [dcd(e(x)) for x in te], 3)[0] / n * 1e6; t2 = timeit(lambda: [dcd(zdd.decompress(zcd.compress(e(x)))) for x in te], 3)[0] / n * 1e6
    a = sum(map(len, items)) / n; b = sum(len(zc3.compress(x)) for x in items) / n; c = sum(len(zcd.compress(x)) for x in items) / n; res1[k] = (a, b, c, t1, t2)
    print(f'  {k:14s} {a:8.1f} {b:8.1f} {c:8.1f}   {t1:12.1f}  {t2:13.1f}')
print(f'  体积最小:{min(res1, key=lambda k: res1[k][2])} + 字典({min(v[2] for v in res1.values()):.1f} 字节);不压缩时体积最小:{min(res1, key=lambda k: res1[k][0])}({min(v[0] for v in res1.values()):.1f});编码+解码最快(不压缩):{min(res1, key=lambda k: res1[k][3])}({min(v[3] for v in res1.values()):.1f} 微秒)')
print('== 二:场景"批量归档"(2 万条,写一次、很少读,要最小):体积与压缩耗时')
jb = jl(P); pbb = x_pb2.Batch(items=[pb1(x) for x in P]).SerializeToString()
cands = [('JSON Lines + gzip-9', jb, lambda b: zlib.compress(b, 9)), ('JSON Lines + zstd-19', jb, lambda b: zstandard.ZstdCompressor(level=19).compress(b)), ('JSON Lines + brotli q11', jb, lambda b: brotli.compress(b, quality=11)), ('Protobuf 整批 + zstd-19', pbb, lambda b: zstandard.ZstdCompressor(level=19).compress(b)), ('JSON Lines + xz-9', jb, lambda b: __import__('lzma').compress(b, preset=9))]
print(f'  {"组合":28s} {"字节":>9s} {"占 JSON Lines":>12s} {"压缩耗时":>9s}')
res2 = []
for lab, b, f in cands:
    t0 = time.perf_counter(); c = f(b); el = time.perf_counter() - t0; res2.append((len(c), lab, el)); print(f'  {lab:28s} {len(c):9d} {len(c) * 100 / len(jb):11.1f}% {el * 1000:7.0f}ms')
print(f'  体积最小:{min(res2)[1]}({min(res2)[0]} 字节)')
print('== 三:场景"批量热数据"(2 万条,写一次读很多次,要读得快):体积与"解压 + 解析并访问 title"的耗时')
cands3 = [('JSON Lines + lz4', jb, lz4.frame.compress, lz4.frame.decompress, lambda b: [json.loads(l)['title'] for l in b.split(b'\n')]), ('JSON Lines + zstd-3', jb, zc3.compress, zd.decompress, lambda b: [json.loads(l)['title'] for l in b.split(b'\n')]),
          ('Protobuf 整批 + lz4', pbb, lz4.frame.compress, lz4.frame.decompress, lambda b: [m.title for m in x_pb2.Batch.FromString(b).items]), ('Protobuf 整批 + zstd-3', pbb, zc3.compress, zd.decompress, lambda b: [m.title for m in x_pb2.Batch.FromString(b).items]),
          ('JSON Lines + zstd-3(orjson 解析)', jb, zc3.compress, zd.decompress, lambda b: [orjson.loads(l)['title'] for l in b.split(b'\n')])]
print(f'  {"组合":30s} {"字节":>9s} {"解压+解析":>10s}')
res3 = []
for lab, b, cf, df, parse in cands3:
    c = cf(b); t = timeit(lambda: parse(df(c)), 5)[0]; res3.append((t, lab, len(c))); print(f'  {lab:30s} {len(c):9d} {t * 1000:8.1f}ms')
print(f'  读得最快:{min(res3)[1]}({min(res3)[0] * 1000:.1f} ms);体积最小:{min(res3, key=lambda r: r[2])[1]}({min(r[2] for r in res3)} 字节)')
print('== 四:场景"HTTP 动态响应"(一页 13 KiB HTML,现场压缩):体积与压缩耗时')
page = PG[0]; print(f'  {"编码":14s} {"字节":>6s} {"压缩 µs":>8s} {"解压 µs":>8s}')
res4 = []
for lab, cf, df in (('gzip-6', lambda: zlib.compress(page, 6), zlib.decompress), ('zstd-3', lambda: zc3.compress(page), zd.decompress), ('brotli q5', lambda: brotli.compress(page, quality=5), brotli.decompress), ('brotli q11', lambda: brotli.compress(page, quality=11), brotli.decompress)):
    c = cf(); tc = timeit(cf, 30 if 'q11' in lab else 200)[0] * 1e6; td = timeit(lambda: df(c), 200)[0] * 1e6; res4.append((len(c), tc, lab)); print(f'  {lab:14s} {len(c):6d} {tc:8.0f} {td:8.0f}')
print(f'  现压缩里"体积 × 耗时"(越小越好)的第一名:{min(res4, key=lambda r: r[0] * r[1])[2]};体积最小:{min(res4)[2]}')
print('== 五:场景"缓存 / 队列的内存"(5000 页缓存):每页平均字节与读取一页的解压耗时(微秒)')
pgs = pages(5500); train, cache = pgs[:500], pgs[500:]; dpg = zstandard.train_dictionary(65536, train); zcp = zstandard.ZstdCompressor(level=3, dict_data=dpg); zdp = zstandard.ZstdDecompressor(dict_data=dpg)
print(f'  {"方式":14s} {"平均字节":>8s} {"解压 µs/页":>10s}')
res5 = []
for lab, cf, df in (('原样', lambda b: b, lambda b: b), ('lz4', lz4.frame.compress, lz4.frame.decompress), ('zstd-3', zc3.compress, zd.decompress), ('zstd-3 + 字典', zcp.compress, zdp.decompress)):
    cs = [cf(b) for b in cache[:1000]]; t = timeit(lambda: [df(c) for c in cs], 5)[0] / 1000 * 1e6; res5.append((sum(map(len, cs)) / 1000, lab, t)); print(f'  {lab:14s} {sum(map(len, cs)) / 1000:8.0f} {t:10.1f}')
print(f'  内存最省:{min(res5)[1]};解压最快(不含原样):{min(r for r in res5 if r[1] != "原样" )[1] if False else min((r for r in res5 if r[1] != "原样"), key=lambda r: r[2])[1]}')
print('== 六:不值得压缩的情况(zstd-3):随机/已压缩的数据、54 字节的短行、50 字节的随机短串')
rb = random.Random(6).randbytes(1 << 20); gzd = zlib.compress(jb[:1 << 20], 6); row = j(timeseries(1)[0])
for lab, b in (('随机 1 MiB', rb), ('已经 gzip 过的 1 MiB 文本', gzd), ('timeseries 的一行(54 字节)', row), ('50 字节随机串', rb[:50]), ('products 一条(360 字节)', j(P[0]))):
    z = len(zc3.compress(b)); print(f'  {lab:28s} 原 {len(b):8d} → zstd-3 {z:8d}({z * 100 / len(b):6.1f}%){"  ← 比原文还大" if z > len(b) else ""}')
purge()
