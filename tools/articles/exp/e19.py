import sys, os, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
import brotli
tee('e19')
d = pdir('e19'); sys.path.insert(0, str(d))
(d / 'm.proto').write_text('''syntax = "proto3"; package m;
message Seller { int32 id = 1; string name = 2; }
message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; double rating = 7; repeated string tags = 8; string category = 9; string updated_at = 10; Seller seller = 11; }
message ProductBatch { repeated Product items = 1; }
message Row { int64 ts = 1; int32 sensor = 2; double value = 3; int32 status = 4; }
message RowBatch { repeated Row items = 1; }
message Opt { int32 retries = 1; int32 timeout_ms = 2; }
message Node { string name = 1; repeated Node children = 2; Opt options = 3; bool enabled = 4; int32 threshold = 5; string label = 6; }
message NodeBatch { repeated Node items = 1; }''')
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}', str(d / 'm.proto')], check=True)
import m_pb2
P = products(); T = timeseries(); N = nested()
def pb_products(rows):
    b = m_pb2.ProductBatch()
    for x in rows:
        m = b.items.add(id=x['id'], url=x['url'], title=x['title'], price=x['price'], currency=x['currency'], stock=x['stock'], rating=x['rating'], category=x['category'], updated_at=x['updated_at']); m.tags.extend(x['tags']); m.seller.id = x['seller']['id']; m.seller.name = x['seller']['name']
    return b.SerializeToString()
def pb_rows(rows):
    b = m_pb2.RowBatch(); [b.items.add(ts=x['ts'], sensor=x['sensor'], value=x['value'], status=x['status']) for x in rows]; return b.SerializeToString()
def fill(m, o):
    if 'children' in o:
        m.name = o['name']; m.options.retries = o['options']['retries']; m.options.timeout_ms = o['options']['timeout_ms']
        for c in o['children']: fill(m.children.add(), c)
    else: m.enabled = o['enabled']; m.threshold = o['threshold']; m.label = o['label']
def pb_nodes(rows):
    b = m_pb2.NodeBatch(); [fill(b.items.add(), x) for x in rows]; return b.SerializeToString()
FMT = {'JSON': lambda rows: j(rows), 'MessagePack': lambda rows: msgpack.packb(rows)}
COMP = [('不压缩', lambda b: b), ('snappy', snappy.compress), ('lz4', lz4.frame.compress), ('gzip-6', lambda b: zlib.compress(b, 6)), ('zstd-3', lambda b: zstandard.ZstdCompressor(level=3).compress(b)), ('zstd-19', lambda b: zstandard.ZstdCompressor(level=19).compress(b)), ('brotli q5', lambda b: brotli.compress(b, quality=5)), ('brotli q11', lambda b: brotli.compress(b, quality=11))]
def matrix(name, rows, pbf, title):
    fm = dict(FMT); fm['Protobuf'] = pbf; enc = {k: f(rows) for k, f in fm.items()}
    print(f'  --- {title} ---'); print(f'  {"编码":12s}' + ''.join(f'{c[0]:>12s}' for c in COMP))
    out = {}
    for k, b in enc.items():
        row = [len(c[1](b)) for c in COMP]; out[k] = row; print(f'  {k:12s}' + ''.join(f'{x:12d}' for x in row))
    base = out['JSON'][0]; best = min((v, k, COMP[i][0]) for k, r in out.items() for i, v in enumerate(r) if i > 0)
    print(f'  最小的组合:{best[1]} + {best[2]} = {best[0]} 字节(JSON 不压缩的 {base} 字节的 {best[0] * 100 / base:.1f}%);JSON + zstd-3 = {out["JSON"][4]};Protobuf 不压缩 = {out["Protobuf"][0]}')
    return enc, out
print('== 一:体积矩阵——products 2 万条(整批编码后再压缩),字节数')
encP, outP = matrix('products', P, pb_products, 'products 2 万条')
print('== 二:耗时矩阵——products 2 万条:编码 + 压缩 的耗时(ms,各 5 次中位数),以及 解压 + 解码')
pbm = m_pb2.ProductBatch
DEC = {'JSON': lambda b: json.loads(b), 'MessagePack': lambda b: msgpack.unpackb(b, raw=False), 'Protobuf': lambda b: [m.title for m in pbm.FromString(b).items]}
DCOMP = {'不压缩': lambda c: c, 'snappy': snappy.decompress, 'lz4': lz4.frame.decompress, 'gzip-6': zlib.decompress, 'zstd-3': zstandard.ZstdDecompressor().decompress, 'zstd-19': zstandard.ZstdDecompressor().decompress, 'brotli q5': brotli.decompress, 'brotli q11': brotli.decompress}
ENC = {'JSON': lambda: orjson.dumps(P), 'MessagePack': lambda: msgpack.packb(P), 'Protobuf': lambda: pb_products(P)}
print(f'  编码耗时:JSON(orjson)' + f' {timeit(ENC["JSON"], 5)[0] * 1000:.1f} ms、MessagePack {timeit(ENC["MessagePack"], 5)[0] * 1000:.1f} ms、Protobuf(从 dict 构造)' + f' {timeit(ENC["Protobuf"], 5)[0] * 1000:.1f} ms')
print(f'  {"编码+压缩":16s}' + ''.join(f'{c[0]:>11s}' for c in COMP[1:]) + '   |  ' + ''.join(f'{c[0]:>9s}' for c in COMP[1:]) + '  ← 右边是 解压+解码(并完整访问 title 字段)')
for k in ('JSON', 'MessagePack', 'Protobuf'):
    b = encP[k]; row = []; row2 = []
    for lab, cf in COMP[1:]:
        row.append(timeit(lambda: cf(b), 3 if lab in ('zstd-19', 'brotli q11') else 5)[0] * 1000); c = cf(b); row2.append(timeit(lambda: DEC[k](DCOMP[lab](c)), 5)[0] * 1000)
    et = timeit(ENC[k], 5)[0] * 1000
    print(f'  {k:16s}' + ''.join(f'{et + t:11.1f}' for t in row) + '   |  ' + ''.join(f'{t:9.1f}' for t in row2))
print('  (左边 = 编码 + 压缩 毫秒,JSON 用 orjson 编码;右边 = 解压 + 解码毫秒,JSON 用标准库 json.loads)')
print('== 三:同样体积下谁更快:把"体积 vs 编码+压缩耗时"画成一条前沿(products 2 万条,所有 21 个组合,只列出前沿上的点)')
pts = []
for k in ('JSON', 'MessagePack', 'Protobuf'):
    b = encP[k]; et = timeit(ENC[k], 3)[0] * 1000
    for lab, cf in COMP[1:]: pts.append((len(cf(b)), et + timeit(lambda: cf(b), 3)[0] * 1000, f'{k} + {lab}'))
front = sorted(pts); best_t = 1e18; fr = []
for sz, t, nm in front:
    if t < best_t: fr.append((sz, t, nm)); best_t = t
for sz, t, nm in fr: print(f'  前沿:{nm:26s} {sz:9d} 字节  {t:8.1f} ms')
print(f'  (不在前沿上的组合,同样大或更大的体积至少有另一个组合比它更快;共 {len(pts)} 个组合,前沿上 {len(fr)} 个)')
print('== 四:数值密集的数据——timeseries 5 万行(整批),字节数')
encT, outT = matrix('timeseries', T, pb_rows, 'timeseries 5 万行')
print('== 五:嵌套较深的数据——nested 3000 个文档(整批),字节数')
encN, outN = matrix('nested', N, pb_nodes, 'nested 3000 个文档')
print('== 六:逐条编码/压缩(每条记录独立,不能攒批):products 单条的平均字节;zstd 用 16 KiB 字典(5000 条训练,2000 条测试)')
tr, te = P[:5000], P[5000:7000]
pb1 = lambda x: m_pb2.Product(id=x['id'], url=x['url'], title=x['title'], price=x['price'], currency=x['currency'], stock=x['stock'], rating=x['rating'], tags=x['tags'], category=x['category'], updated_at=x['updated_at'], seller=m_pb2.Seller(id=x['seller']['id'], name=x['seller']['name'])).SerializeToString()
E1 = {'JSON': j, 'MessagePack': msgpack.packb, 'Protobuf': pb1}
print(f'  {"编码":12s} {"不压缩":>8s} {"snappy":>8s} {"lz4":>8s} {"gzip-6":>8s} {"zstd-3":>8s} {"zstd-3+字典":>11s}   (平均每条字节)')
for k, f in E1.items():
    dd = zstandard.train_dictionary(16384, [f(x) for x in tr]); zd = zstandard.ZstdCompressor(level=3, dict_data=dd); items = [f(x) for x in te]; n = len(items)
    print(f'  {k:12s} {sum(map(len, items)) / n:8.1f} {sum(len(snappy.compress(b)) for b in items) / n:8.1f} {sum(len(lz4.frame.compress(b)) for b in items) / n:8.1f} {sum(len(zlib.compress(b, 6)) for b in items) / n:8.1f} {sum(len(zstandard.ZstdCompressor(level=3).compress(b)) for b in items) / n:8.1f} {sum(len(zd.compress(b)) for b in items) / n:11.1f}')
purge()
