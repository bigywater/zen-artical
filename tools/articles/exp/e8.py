import sys, os, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e8')
P = products(); N = len(P)
zc = lambda lv=3: zstandard.ZstdCompressor(level=lv)
zs = lambda b, lv=3: len(zc(lv).compress(b)); gz = lambda b: len(zlib.compress(b, 6)); lz = lambda b: len(lz4.frame.compress(b))
COLS = ['id', 'url', 'title', 'price', 'currency', 'stock', 'rating', 'tags', 'category', 'updated_at', 'seller_id', 'seller_name']
def colvals(rows):
    return {'id': [x['id'] for x in rows], 'url': [x['url'] for x in rows], 'title': [x['title'] for x in rows], 'price': [x['price'] for x in rows], 'currency': [x['currency'] for x in rows], 'stock': [x['stock'] for x in rows],
            'rating': [x['rating'] for x in rows], 'tags': [x['tags'] for x in rows], 'category': [x['category'] for x in rows], 'updated_at': [x['updated_at'] for x in rows], 'seller_id': [x['seller']['id'] for x in rows], 'seller_name': [x['seller']['name'] for x in rows]}
def colbytes(rows): return {k: j(v) for k, v in colvals(rows).items()}
rowb = jl(P); cb = colbytes(P); colall = b''.join(cb.values())
print('== 一:同样的 2 万条 products,行式(JSON Lines)与列式(每个字段一个 JSON 数组,按列拼接)')
print(f'  {"布局":22s} {"原始字节":>9s} {"gzip-6":>9s} {"lz4":>9s} {"zstd-3":>9s} {"zstd-19":>9s}')
for lab, b in (('行式 JSON Lines', rowb), ('列式(JSON 数组)', colall)): print(f'  {lab:22s} {len(b):9d} {gz(b):9d} {lz(b):9d} {zs(b):9d} {zs(b, 19):9d}')
print(f'  列式 zstd-3 比行式小 {100 - zs(colall) * 100 / zs(rowb):.1f}%;列式 gzip 比行式小 {100 - gz(colall) * 100 / gz(rowb):.1f}%;列式 lz4 比行式小 {100 - lz(colall) * 100 / lz(rowb):.1f}%')
print('== 二:每一列单独压缩(zstd-3),看哪些列压得动、哪些压不动')
print(f'  {"列":12s} {"原始字节":>9s} {"zstd-3":>8s} {"压缩比":>7s} {"占行式压缩后总量":>16s}')
tot = zs(rowb)
for k in COLS:
    b = cb[k]; z = zs(b); print(f'  {k:12s} {len(b):9d} {z:8d} {len(b) / z:6.2f}× {z * 100 / tot:15.1f}%')
print(f'  各列压缩后相加 {sum(zs(cb[k]) for k in COLS)} 字节;整个列式拼起来一起压缩 {zs(colall)};行式 {tot}')
print('== 三:记录的排列顺序影响压缩(行式 JSON Lines,zstd-3):原顺序、按 category 排序、按 seller 排序、按 url 排序、随机打乱')
def key_seller(x): return (x['seller']['id'], x['id'])
orders = [('原顺序(按 id)', P), ('按 category 排序', sorted(P, key=lambda x: (x['category'], x['id']))), ('按 seller.id 排序', sorted(P, key=key_seller)), ('按 title 排序', sorted(P, key=lambda x: x['title'])), ('随机打乱', random.Random(1).sample(P, N))]
for lab, rows in orders:
    b = jl(rows); c = colall2 = b''.join(colbytes(rows).values()); print(f'  {lab:18s} 行式 zstd-3 {zs(b):8d};列式 zstd-3 {zs(c):8d}')
print('== 四:列式 + 针对每一列的编码(手工做一个简化的列存):字典编码低基数的字符串、差分编码 id、价格存整数分、时间戳存整数')
import datetime
def dict_enc(vals):
    d = {}; ids = [d.setdefault(v, len(d)) for v in vals]; return d, ids
def varint(n):
    o = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: o.append(b | 0x80)
        else: o.append(b); return bytes(o)
def zz(n): return (n << 1) ^ (n >> 63)
parts = {}
parts['id(差分 + varint)'] = b''.join(varint(zz(b - a)) for a, b in zip([0] + [x['id'] for x in P], [x['id'] for x in P]))
parts['url(去掉公共前缀,只存 id 以外的部分)'] = b'\n'.join(x['url'].split('?', 1)[1].encode() for x in P)
parts['title(换行分隔的文本)'] = '\n'.join(x['title'] for x in P).encode()
parts['price(整数分 varint)'] = b''.join(varint(int(round(x['price'] * 100))) for x in P)
for k in ('currency', 'category', 'seller_name'):
    src = [x[k] if k != 'seller_name' else x['seller']['name'] for x in P]; dd, ids = dict_enc(src); parts[f'{k}(字典 {len(dd)} 项)'] = b'\n'.join(v.encode() for v in dd) + b'\x00' + b''.join(varint(i) for i in ids)
parts['stock(varint)'] = b''.join(varint(x['stock']) for x in P); parts['rating(整数 ×10)'] = bytes(int(round(x['rating'] * 10)) for x in P)
dd, ids = dict_enc([tuple(x['tags']) for x in P]); allt = {}; tg = []
for x in P:
    for t in x['tags']: tg.append(allt.setdefault(t, len(allt)))
parts[f'tags(字典 {len(allt)} 项)'] = b'\n'.join(t.encode() for t in allt) + b'\x00' + b''.join(varint(i) for i in tg)
def ts_int(s): return int(datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp())
parts['updated_at(Unix 秒 varint)'] = b''.join(varint(ts_int(x['updated_at'])) for x in P); parts['seller_id(varint)'] = b''.join(varint(x['seller']['id']) for x in P)
print(f'  {"列(编码方式)":38s} {"编码后字节":>10s} {"再 zstd-3":>9s}')
tb = tz = 0
for k, b in parts.items(): print(f'  {k:38s} {len(b):10d} {zs(b):9d}'); tb += len(b); tz += zs(b)
print(f'  合计 编码后 {tb} 字节,逐列再 zstd-3 共 {tz} 字节;对比:行式 JSON Lines zstd-3 {tot}、Protobuf 拼接 zstd-3 约 1378051(第 6 篇)、列式 JSON zstd-3 {zs(colall)}')
print('== 五:分块:每块 N 条,行式与列式各自压缩(zstd-3),总字节与压缩比')
print(f'  {"每块条数":>8s} {"行式总字节":>11s} {"列式总字节":>11s} {"列式比行式小":>11s}')
for bs in (100, 1000, 5000, 20000):
    r_ = c_ = 0
    for s in range(0, N, bs): blk = P[s:s + bs]; r_ += zs(jl(blk)); c_ += zs(b''.join(colbytes(blk).values()))
    print(f'  {bs:8d} {r_:11d} {c_:11d} {100 - c_ * 100 / r_:10.1f}%')
print('== 六:只读 price 一列的代价(2 万条,各 7 次中位数):行式要解压整个文件再逐行解析,列式只解压 price 那一列')
zdec = zstandard.ZstdDecompressor(); rz = zc().compress(rowb); pz = zc().compress(cb['price'])
f1 = lambda: sum(json.loads(l)['price'] for l in zdec.decompress(rz).split(b'\n')); f2 = lambda: sum(json.loads(zdec.decompress(pz)))
for lab, f, inb in (('行式:解压全部 + 逐行 json.loads', f1, len(rz)), ('列式:只解压 price 列 + json.loads', f2, len(pz))):
    m, lo, hi = timeit(f, 7); print(f'  {lab:34s} 读入压缩数据 {inb:8d} 字节,中位 {m * 1000:7.1f} ms({lo * 1000:.1f}–{hi * 1000:.1f}),和 {f():.2f}')
purge()
