import sys, os, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e3')
P = products(); T = timeseries(); N = nested(); B = blobby()
zs = lambda b, lv=3: len(zstandard.ZstdCompressor(level=lv).compress(b))
pk = lambda o: msgpack.packb(o, use_bin_type=True)
print('== 一:MessagePack 的编码规则:几个值编码成多少字节(十六进制)')
def show(lab, o): b = pk(o); print(f'  {lab:28s} {len(b):4d} 字节  {b[:12].hex(" ")}{" …" if len(b) > 12 else ""}')
for lab, o in (('整数 0', 0), ('整数 127', 127), ('整数 128', 128), ('整数 255', 255), ('整数 256', 256), ('整数 65535', 65535), ('整数 65536', 65536), ('整数 -1', -1), ('整数 -32', -32), ('整数 -33', -33), ('整数 2**32', 2 ** 32), ('浮点 1.5', 1.5), ('浮点 0.1', 0.1), ('True / None', [True, None]), ('字符串 "a"', 'a'), ('字符串 31 字节', 'x' * 31), ('字符串 32 字节', 'x' * 32), ('字符串 255 字节', 'x' * 255), ('字符串 256 字节', 'x' * 256), ('bytes 3 字节', b'abc'), ('{"a":1}', {'a': 1}), ('[1,2,3]', [1, 2, 3])):
    show(lab, o)
print(f'  JSON 对照:127 → {len(json.dumps(127))} 字节、65536 → {len(json.dumps(65536))} 字节、"x"*31 → {len(json.dumps("x" * 31))} 字节、{{"a":1}} → {len(json.dumps({"a": 1}, separators=(",", ":")))} 字节、0.1 → {len(json.dumps(0.1))} 字节')
print('== 二:四个数据集的体积:JSON(紧凑)与 MessagePack,以及压缩之后(每个数据集整批作为一个数组)')
def blobj(o):   # JSON 里没有 bytes:thumb 用 base64
    return [dict(x, thumb=base64.b64encode(x['thumb']).decode()) for x in o]
print(f'  {"数据集":12s} {"JSON":>9s} {"MsgPack":>9s} {"省下":>6s}   压缩后 zstd-3: {"JSON":>9s} {"MsgPack":>9s} {"差":>6s}   gzip-6: {"JSON":>9s} {"MsgPack":>9s}   lz4: {"JSON":>9s} {"MsgPack":>9s}')
sizes = {}
for nm, d, dj in (('products', P, P), ('timeseries', T, T), ('nested', N, N), ('blobby', B, blobj(B))):
    a = j(dj); b = pk(d); sizes[nm] = (len(a), len(b), zs(a), zs(b))
    print(f'  {nm:12s} {len(a):9d} {len(b):9d} {100 - len(b) * 100 / len(a):5.1f}%   {"":14s} {zs(a):9d} {zs(b):9d} {100 - zs(b) * 100 / zs(a):5.1f}%   {"":8s} {len(zlib.compress(a, 6)):9d} {len(zlib.compress(b, 6)):9d}   {"":4s} {len(lz4.frame.compress(a)):9d} {len(lz4.frame.compress(b)):9d}')
print('== 三:为什么有的数据变小很多、有的几乎没变——把 MessagePack 的字节按类型拆开(products 与 timeseries,2 万条与 5 万条)')
def mp_stats(o, acc):
    if isinstance(o, dict):
        acc['容器头'] += len(pk({})) if len(o) < 16 else 3
        for k, v in o.items(): acc['键名'] += len(pk(k)); mp_stats(v, acc)
    elif isinstance(o, list):
        acc['容器头'] += 1 if len(o) < 16 else 3
        for v in o: mp_stats(v, acc)
    elif isinstance(o, str): acc['字符串'] += len(pk(o))
    elif isinstance(o, bytes): acc['bytes'] += len(pk(o))
    elif isinstance(o, float): acc['浮点'] += len(pk(o))
    elif isinstance(o, bool) or o is None: acc['布尔/空'] += 1
    else: acc['整数'] += len(pk(o))
for nm, d in (('products', P), ('timeseries', T)):
    acc = collections.Counter()
    for x in d: mp_stats(x, acc)
    tot = sum(acc.values()); print(f'  {nm}:MessagePack 逐值统计合计 {tot} 字节(整批打包 {len(pk(d))} 字节,差在数组头);' + ';'.join(f'{k} {v * 100 / tot:.1f}%' for k, v in acc.most_common()))
    accj = collections.Counter()
print(f'  products:JSON {sizes["products"][0]} → MsgPack {sizes["products"][1]},省下 {100 - sizes["products"][1] * 100 / sizes["products"][0]:.1f}%;timeseries:{sizes["timeseries"][0]} → {sizes["timeseries"][1]},省下 {100 - sizes["timeseries"][1] * 100 / sizes["timeseries"][0]:.1f}%')
print('== 四:速度(各取 7 次中位数,整批作为一个对象)')
bj = {nm: (j(d), pk(d)) for nm, d in (('products', P), ('timeseries', T))}
for nm, d in (('products', P), ('timeseries', T)):
    jb, mb = bj[nm]; row = []
    for lab, f, sz in (('json.dumps', lambda: json.dumps(d, separators=(',', ':'), ensure_ascii=False), len(jb)), ('orjson.dumps', lambda: orjson.dumps(d), len(jb)), ('msgpack.packb', lambda: pk(d), len(mb)),
                       ('json.loads', lambda: json.loads(jb), len(jb)), ('orjson.loads', lambda: orjson.loads(jb), len(jb)), ('msgpack.unpackb', lambda: msgpack.unpackb(mb, raw=False), len(mb))):
        m, lo, hi = timeit(f, 7); row.append(f'{lab} {m * 1000:.1f} ms')
    print(f'  {nm}:' + ';'.join(row))
print('== 五:类型保真:Python 对象 → MessagePack → Python 对象,哪些会变')
import datetime
for lab, o, kw in (('tuple (1, 2)', (1, 2), {}), ('整数键 {1: "a"}', {1: 'a'}, {}), ('bytes b"ab"', b'ab', {}), ('str "ab"', 'ab', {}), ('2**63', 2 ** 63, {}), ('2**64', 2 ** 64, {}), ('float nan', float('nan'), {}), ('datetime', datetime.datetime(2026, 10, 12), {}), ('set {1,2}', {1, 2}, {})):
    try:
        b = pk(o); r_ = msgpack.unpackb(b, raw=False, strict_map_key=False); res = f'{len(b)} 字节 → {r_!r}'
    except Exception as e: res = f'打包抛出 {type(e).__name__}'
    print(f'  {lab:20s} {res}')
b = msgpack.packb({'a': b'ab', 'b': 'ab'}, use_bin_type=False)
print(f'  use_bin_type=False(旧格式):bytes 和 str 打包成同一类型 → {msgpack.unpackb(b, raw=False)!r}')
try: msgpack.unpackb(pk({1: 'a'}), raw=False)
except Exception as e: print(f'  默认 strict_map_key=True 解包整数键:{type(e).__name__}')
print('== 六:流式:多条记录拼在一起,分块喂给 Unpacker(每块 1000 字节)——取得到几条、遇到被截断的尾巴怎么办')
recs = P[:2000]; stream = b''.join(pk(x) for x in recs); jls = jl(recs)
up = msgpack.Unpacker(raw=False); got = 0; chunks = 0
for s in range(0, len(stream), 1000): up.feed(stream[s:s + 1000]); chunks += 1; got += sum(1 for _ in up)
print(f'  MessagePack 流 {len(stream)} 字节(没有分隔符),按 1000 字节切成 {chunks} 块喂 Unpacker:取出 {got}/{len(recs)} 条;JSON Lines {len(jls)} 字节(靠换行分隔)')
cut = stream[:len(stream) // 2 + 137]; up = msgpack.Unpacker(raw=False); up.feed(cut); n = sum(1 for _ in up)
print(f'  把流截断在中间(多出半条):Unpacker 取出 {n} 条完整记录,最后半条不会报错,只是留在缓冲里(再喂剩下的字节就能取出)')
print(f'  JSON Lines 截断在同样位置:按行解析,', end='')
lines = jls[:len(jls) // 2 + 137].split(b'\n'); ok = 0
for ln in lines:
    try: json.loads(ln); ok += 1
    except Exception: pass
print(f'{ok}/{len(lines)} 行可解析(最后一行是半行,json.loads 抛出 JSONDecodeError)')
print('== 七:products 上 MessagePack 压缩后反而比 JSON 大——检验两个猜想(猜想 1:浮点数的 8 字节二进制接近随机、压不动;猜想 2:长度前缀和类型字节打断了重复)')
def variant(o, mode):
    o = dict(o)
    if mode in ('int', 'nofloat'): o['price'] = int(round(o['price'] * 100)); o['rating'] = int(round(o['rating'] * 10))
    if mode == 'nofloat': o.pop('price'); o.pop('rating')
    return o
print(f'  {"版本":34s} {"JSON":>9s} {"MsgPack":>9s} {"zstd JSON":>10s} {"zstd Msg":>10s} {"MsgPack 比 JSON(压缩后)":>22s}')
for lab, mode in (('原样(price/rating 是浮点)', 'orig'), ('price→整数分、rating→整数', 'int'), ('去掉 price 和 rating', 'nofloat')):
    d = [variant(x, mode) for x in P]; a = j(d); b = pk(d); za, zb = zs(a), zs(b)
    print(f'  {lab:34s} {len(a):9d} {len(b):9d} {za:10d} {zb:10d} {100 * (zb - za) / za:+21.1f}%')
fl = [x['price'] for x in P[:1000]]; print(f'  参考:1000 个 price 的 8 字节 float64 二进制(拼接)zstd-3 后 {zs(b"".join(struct.pack(">d", v) for v in fl))} 字节(原 8000 字节);同样 1000 个 price 的文本(逗号分隔)zstd-3 后 {zs(",".join(map(str, fl)).encode())} 字节(原 {len(",".join(map(str, fl)))} 字节)')
print('  只看字符串字段(把某个字段的 2 万个值单独拿出来):')
for fld in ('title', 'url', 'updated_at', 'category'):
    vals_ = [x[fld] for x in P]; a = j(vals_); b = pk(vals_); c = '\n'.join(vals_).encode()
    print(f'    {fld:10s} JSON 数组 {len(a):8d} → zstd {zs(a):7d};MsgPack 数组 {len(b):8d} → zstd {zs(b):7d};换行分隔的纯文本 {len(c):8d} → zstd {zs(c):7d}')
purge()
