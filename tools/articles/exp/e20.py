import sys, os, subprocess, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e20')
d = pdir('e20'); sys.path.insert(0, str(d))
(d / 'x.proto').write_text('''syntax = "proto3"; package x;
message Seller { int32 id = 1; string name = 2; }
message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; double rating = 7; repeated string tags = 8; string category = 9; string updated_at = 10; Seller seller = 11; }
message Batch { repeated Product items = 1; }
message Product2 { int64 id = 1; int32 page = 2; string title = 3; int32 price_cents = 4; int32 currency = 5; int32 stock = 6; int32 rating10 = 7; repeated int32 tags = 8; int32 category = 9; int64 updated = 10; int32 seller_id = 11; string seller_name = 12; }
message Batch2 { repeated Product2 items = 1; }
message Cols { repeated int64 id = 1; repeated string url = 2; repeated string title = 3; repeated double price = 4; repeated string currency = 5; repeated int32 stock = 6; repeated double rating = 7; repeated string tags = 8; repeated string category = 9; repeated string updated_at = 10; repeated int32 seller_id = 11; repeated string seller_name = 12; }''')
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}', str(d / 'x.proto')], check=True)
import x_pb2
P = products(); N = len(P)
zs = lambda b, lv=3: len(zstandard.ZstdCompressor(level=lv).compress(b))
TAGIDX = {t: i for i, t in enumerate(TAGS)}; CATIDX = {c: i for i, c in enumerate(CATS)}
def ts_int(s): return int(datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp())
def to2(x):
    page = int(x['url'].rsplit('page=', 1)[1]); assert x['url'] == f'https://shop.example.com/item/{x["id"]}?ref=list&page={page}'
    return {'id': x['id'], 'page': page, 'title': x['title'], 'price_cents': int(round(x['price'] * 100)), 'currency': 0 if x['currency'] == 'CNY' else 1, 'stock': x['stock'], 'rating10': int(round(x['rating'] * 10)),
            'tags': [TAGIDX[t] for t in x['tags']], 'category': CATIDX[x['category']], 'updated': ts_int(x['updated_at']), 'seller_id': x['seller']['id'], 'seller_name': x['seller']['name']}
P2 = [to2(x) for x in P]
def pb1(x): return x_pb2.Product(id=x['id'], url=x['url'], title=x['title'], price=x['price'], currency=x['currency'], stock=x['stock'], rating=x['rating'], tags=x['tags'], category=x['category'], updated_at=x['updated_at'], seller=x_pb2.Seller(id=x['seller']['id'], name=x['seller']['name']))
def pb2(x): return x_pb2.Product2(**x)
B1 = x_pb2.Batch(); B1.items.extend(pb1(x) for x in P); B2 = x_pb2.Batch2(); B2.items.extend(pb2(x) for x in P2)
print('== 一:逐字段拆开:每个字段的 2 万个值单独放成一列,用 JSON 数组 / MessagePack 数组 / Protobuf(repeated 字段)各编码一次,再 zstd-3 压缩')
fields = [('id', [x['id'] for x in P]), ('url', [x['url'] for x in P]), ('title', [x['title'] for x in P]), ('price', [x['price'] for x in P]), ('currency', [x['currency'] for x in P]), ('stock', [x['stock'] for x in P]), ('rating', [x['rating'] for x in P]),
          ('tags', [t for x in P for t in x['tags']]), ('category', [x['category'] for x in P]), ('updated_at', [x['updated_at'] for x in P]), ('seller_id', [x['seller']['id'] for x in P]), ('seller_name', [x['seller']['name'] for x in P])]
print(f'  {"字段":12s} {"JSON 原":>9s} {"→zstd":>8s} {"MsgPack 原":>10s} {"→zstd":>8s} {"Protobuf 原":>11s} {"→zstd":>8s}   谁压缩后最小')
tot = collections.Counter()
for nm, vals in fields:
    c = x_pb2.Cols(); getattr(c, nm if nm != 'tags' else 'tags').extend(vals); pbb = c.SerializeToString(); jb = j(vals); mb = msgpack.packb(vals)
    sizes = {'JSON': zs(jb), 'MsgPack': zs(mb), 'Protobuf': zs(pbb)}; best = min(sizes, key=sizes.get); tot['JSON'] += sizes['JSON']; tot['MsgPack'] += sizes['MsgPack']; tot['Protobuf'] += sizes['Protobuf']
    print(f'  {nm:12s} {len(jb):9d} {sizes["JSON"]:8d} {len(mb):10d} {sizes["MsgPack"]:8d} {len(pbb):11d} {sizes["Protobuf"]:8d}   {best}')
print(f'  各列压缩后合计:JSON {tot["JSON"]}、MessagePack {tot["MsgPack"]}、Protobuf {tot["Protobuf"]}')
print('== 二:改数据模型,不换格式:price 存整数分、rating 存整数(×10)、currency 存 0/1、category 和 tags 存编号、updated_at 存 Unix 秒、url 只存 page(其余可由 id 推出,已逐条校验)')
print(f'  一条记录:原模型 JSON {len(j(P[0]))} 字节、新模型 JSON {len(j(P2[0]))} 字节;原模型 Protobuf {len(pb1(P[0]).SerializeToString())} 字节、新模型 Protobuf {len(pb2(P2[0]).SerializeToString())} 字节')
print(f'  新模型示例:{j(P2[0]).decode()}')
print('== 三:数据模型 × 格式——2 万条整批:原始字节 / zstd-3 / zstd-19 / gzip-6')
rows = [('原模型 JSON Lines', jl(P)), ('原模型 Protobuf', B1.SerializeToString()), ('新模型 JSON Lines', jl(P2)), ('新模型 Protobuf', B2.SerializeToString())]
print(f'  {"组合":22s} {"原始":>9s} {"zstd-3":>9s} {"zstd-19":>9s} {"gzip-6":>9s}')
res = {}
for lab, b in rows: res[lab] = (len(b), zs(b), zs(b, 19), len(zlib.compress(b, 6))); print(f'  {lab:22s} {res[lab][0]:9d} {res[lab][1]:9d} {res[lab][2]:9d} {res[lab][3]:9d}')
a, b2 = res['原模型 JSON Lines'][1], res['新模型 JSON Lines'][1]; c, d2 = res['原模型 Protobuf'][1], res['新模型 Protobuf'][1]
print(f'  换数据模型的收益(zstd-3):JSON {100 - b2 * 100 / a:.1f}%、Protobuf {100 - d2 * 100 / c:.1f}%;换格式的收益(新模型,JSON → Protobuf):原始 {100 - res["新模型 Protobuf"][0] * 100 / res["新模型 JSON Lines"][0]:.1f}%、zstd-3 {100 - d2 * 100 / b2:+.1f}%')
print('== 四:没有办法再省的部分——只剩 title 字符串时的下限(title 是随机拼的词)')
tt = '\n'.join(x['title'] for x in P).encode(); print(f'  2 万个 title 用换行拼起来 {len(tt)} 字节,zstd-3 {zs(tt)}、zstd-19 {zs(tt, 19)};占新模型 JSON zstd-3 总量 {res["新模型 JSON Lines"][1]} 的 {zs(tt) * 100 / res["新模型 JSON Lines"][1]:.1f}%')
non_title = [{k: v for k, v in x.items() if k != 'title'} for x in P2]; print(f'  去掉 title 以后:新模型 JSON {zs(jl(non_title))}、新模型 Protobuf {zs(x_pb2.Batch2(items=[pb2(dict(x, title="")) for x in P2]).SerializeToString())}(zstd-3 字节),title 单独压缩 {zs(tt)}')
print('== 五:每条记录单独压缩(不能攒批):平均每条字节;zstd 用 16 KiB 字典(5000 条训练,2000 条测试)')
tr1, te1 = P[:5000], P[5000:7000]; tr2, te2 = P2[:5000], P2[5000:7000]
combos = [('原模型 JSON', j, tr1, te1), ('原模型 Protobuf', lambda x: pb1(x).SerializeToString(), tr1, te1), ('新模型 JSON', j, tr2, te2), ('新模型 Protobuf', lambda x: pb2(x).SerializeToString(), tr2, te2)]
print(f'  {"组合":18s} {"不压缩":>8s} {"zstd-3":>8s} {"zstd-3+字典":>11s}')
for lab, f, tr, te in combos:
    dd = zstandard.train_dictionary(16384, [f(x) for x in tr]); zd = zstandard.ZstdCompressor(level=3, dict_data=dd); z0 = zstandard.ZstdCompressor(level=3); items = [f(x) for x in te]; n = len(items)
    print(f'  {lab:18s} {sum(map(len, items)) / n:8.1f} {sum(len(z0.compress(b)) for b in items) / n:8.1f} {sum(len(zd.compress(b)) for b in items) / n:11.1f}')
print('== 六:汇总排序:所有变体按 zstd-19 压缩后大小从小到大(2 万条整批)')
allv = list(res.items()) + [('原模型 列式 JSON(每列一个数组)', None)]
colj = b''.join(j(v) for _, v in fields); res['原模型 列式 JSON'] = (len(colj), zs(colj), zs(colj, 19), len(zlib.compress(colj, 6)))
cols2 = b''.join(j([x[k] for x in P2]) for k in ('id', 'page', 'title', 'price_cents', 'currency', 'stock', 'rating10', 'tags', 'category', 'updated', 'seller_id', 'seller_name')); res['新模型 列式 JSON'] = (len(cols2), zs(cols2), zs(cols2, 19), len(zlib.compress(cols2, 6)))
for lab, v in sorted(res.items(), key=lambda t: t[1][2]): print(f'  {lab:22s} 原始 {v[0]:9d}  zstd-3 {v[1]:9d}  zstd-19 {v[2]:9d}  gzip-6 {v[3]:9d}')
purge()
