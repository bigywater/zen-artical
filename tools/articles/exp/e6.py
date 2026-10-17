import sys, os, subprocess, struct, textwrap; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e6')
d = pdir('e6'); sys.path.insert(0, str(d))
(d / 'prod.proto').write_text('syntax = "proto3"; package pr; message Seller { int32 id = 1; string name = 2; } message Product { int64 id = 1; string url = 2; string title = 3; double price = 4; string currency = 5; int32 stock = 6; double rating = 7; repeated string tags = 8; string category = 9; string updated_at = 10; Seller seller = 11; } message Batch { repeated Product items = 1; }')
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}', str(d / 'prod.proto')], check=True)
import prod_pb2
from google.protobuf.json_format import MessageToDict
P = products()
def to_pb(x):
    m = prod_pb2.Product()
    for k in ('id', 'url', 'title', 'price', 'currency', 'stock', 'rating', 'category', 'updated_at'): setattr(m, k, x[k])
    m.tags.extend(x['tags']); m.seller.id = x['seller']['id']; m.seller.name = x['seller']['name']; return m
batch = prod_pb2.Batch(); batch.items.extend(to_pb(x) for x in P)
jb = j(P); mb = msgpack.packb(P); pb = batch.SerializeToString()
print(f'== 一:2 万条 products 整批编码/解码的耗时(各 7 次中位数);三者的字节数:JSON {len(jb)}、MessagePack {len(mb)}、Protobuf {len(pb)}')
def pb_touch(b):
    bt = prod_pb2.Batch(); bt.ParseFromString(b); s = 0
    for m in bt.items: s += m.id + len(m.url) + len(m.title) + int(m.price) + m.stock + len(m.tags) + m.seller.id + len(m.seller.name) + len(m.category) + len(m.updated_at) + len(m.currency)
    return s
def pb_build():
    bt = prod_pb2.Batch(); bt.items.extend(to_pb(x) for x in P); return bt.SerializeToString()
rows = [('JSON(标准库)', lambda: json.dumps(P, separators=(',', ':'), ensure_ascii=False), lambda: json.loads(jb)), ('JSON(orjson)', lambda: orjson.dumps(P), lambda: orjson.loads(jb)), ('MessagePack', lambda: msgpack.packb(P), lambda: msgpack.unpackb(mb, raw=False)),
        ('Protobuf(从 dict 构造消息再序列化)', pb_build, None), ('Protobuf(仅解析,不访问字段)', None, lambda: prod_pb2.Batch.FromString(pb)), ('Protobuf(解析并访问全部字段)', None, lambda: pb_touch(pb))]
for lab, e, dcd in rows:
    te = f'编码 {timeit(e, 7)[0] * 1000:7.1f} ms' if e else '编码   -      '; td = f'解码 {timeit(dcd, 7)[0] * 1000:7.1f} ms' if dcd else ''
    print(f'  {lab:34s} {te}  {td}')
mp = lambda: [MessageToDict(m, preserving_proto_field_name=True) for m in prod_pb2.Batch.FromString(pb).items]
print(f'  Protobuf 解析后转成 dict(MessageToDict)  {"":14s} 解码 {timeit(mp, 3)[0] * 1000:7.1f} ms(转成 Python 字典的代价)')
print('== 二:数据不合 schema 时各格式的反应(同一条记录,故意改坏)')
x = dict(P[0])
def tryit(lab, fn):
    try: r_ = fn(); print(f'  {lab:40s} {r_}')
    except Exception as e: print(f'  {lab:40s} 抛出 {type(e).__name__}: {str(e)[:60]}')
bad_cases = [('price 写成字符串 "abc"', dict(x, price='abc')), ('缺少 url 字段', {k: v for k, v in x.items() if k != 'url'}), ('多了一个未知字段 extra', dict(x, extra=1)), ('stock 写成 1.5', dict(x, stock=1.5)), ('id 写成 2**70', dict(x, id=2 ** 70))]
for lab, o in bad_cases:
    jr = 'JSON 接受' ; mr = 'MsgPack ' + ('接受' if not isinstance(o.get('id'), int) or o['id'] < 2 ** 64 else '抛出 OverflowError')
    def pbf(o=o):
        m = prod_pb2.Product()
        for k, v in o.items():
            if k in ('tags', 'seller'): continue
            setattr(m, k, v)
        return 'Protobuf 接受,序列化 %d 字节' % len(m.SerializeToString())
    try: pr_ = pbf()
    except Exception as e: pr_ = f'Protobuf 抛出 {type(e).__name__}({str(e)[:40]})'
    print(f'  {lab:28s} {jr}、{mr}、{pr_}')
print('== 三:没有 schema 时能读出什么:同一条记录拿到字节后')
print(f'  JSON 前 80 字节:{j(P[0])[:80]!r}')
print(f'  MessagePack 解成通用结构(不知道任何 schema):{str(msgpack.unpackb(msgpack.packb(P[0]), raw=False))[:120]}…')
r = subprocess.run(['protoc', '--decode_raw'], input=to_pb(P[0]).SerializeToString(), capture_output=True); lines = r.stdout.decode().splitlines()
print('  Protobuf 用 protoc --decode_raw 看到的前 8 行:' + ' | '.join(lines[:8]))
amb = prod_pb2.Seller(id=1, name='x').SerializeToString(); r2 = subprocess.run(['protoc', '--decode_raw'], input=prod_pb2.Product(title=amb.decode('latin1')).SerializeToString(), capture_output=True)
print(f'  歧义:把恰好是合法消息的字节({amb.hex(" ")})存进 title 字符串字段,decode_raw 显示为:{r2.stdout.decode().strip().replace(chr(10), " ")}(没有 schema 分不清它是字符串还是嵌套消息)')
print(f'  浮点 price 在 decode_raw 里显示为 {lines[3].strip()}(只知道是 64 位,不知道是 double 还是 fixed64 还是别的)')
print('== 四:schema 的收益有多少来自 schema 本身:JSON 数组 + 一次表头 / MessagePack 数组 + 表头 / Protobuf,体积(2 万条,字段顺序固定)')
keys_ = ['id', 'url', 'title', 'price', 'currency', 'stock', 'rating', 'tags', 'category', 'updated_at']
rows_ = [[x[k] for k in keys_] + [x['seller']['id'], x['seller']['name']] for x in P]
cands = [('JSON 对象(每条带键名)', jl(P)), ('JSON 数组 + 表头', j({'cols': keys_ + ['seller_id', 'seller_name'], 'rows': rows_})), ('MessagePack 对象', b''.join(msgpack.packb(x) for x in P)), ('MessagePack 数组 + 表头', msgpack.packb({'cols': keys_ + ['seller_id', 'seller_name'], 'rows': rows_})), ('Protobuf', pb)]
zs = lambda b: len(zstandard.ZstdCompressor(level=3).compress(b))
print(f'  {"表示":28s} {"字节":>9s} {"zstd-3":>9s}')
for lab, b in cands: print(f'  {lab:28s} {len(b):9d} {zs(b):9d}')
print('== 五:数据损坏时各格式的反应:对一条记录随机翻转 1 个字节,各试 3000 次——解码抛异常 / 解出和原来一样的值 / 静默解出不同的值')
one = P[0]; raws = {'JSON': j(one), 'MessagePack': msgpack.packb(one), 'Protobuf': to_pb(one).SerializeToString()}
orig = {'JSON': one, 'MessagePack': one, 'Protobuf': to_pb(one)}
def dec(fmt, b):
    if fmt == 'JSON': return json.loads(b)
    if fmt == 'MessagePack': return msgpack.unpackb(b, raw=False, strict_map_key=False)
    m = prod_pb2.Product(); m.ParseFromString(b); return m
rr = random.Random(5)
for fmt, b in raws.items():
    c = collections.Counter()
    for _ in range(3000):
        i = rr.randrange(len(b)); bb = bytearray(b); bb[i] ^= 1 << rr.randrange(8); bb = bytes(bb)
        try: v = dec(fmt, bb); c['解出相同' if v == orig[fmt] else '静默解出不同的值'] += 1
        except Exception: c['抛异常'] += 1
    print(f'  {fmt:12s} {len(b)} 字节:抛异常 {c["抛异常"]}、解出相同 {c["解出相同"]}、静默解出不同的值 {c["静默解出不同的值"]}(共 3000 次)')
print('== 六:解码到内存里要多少(在独立子进程里测 ru_maxrss 的增量;2 万条 products)')
CH = textwrap.dedent(f'''
    import sys, resource, json; sys.path.insert(0, {str(d)!r}); sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__)) + '/..'!r}); import ec, msgpack, orjson, prod_pb2
    fmt = sys.argv[1]; b = open(sys.argv[2], 'rb').read()
    r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if fmt == 'json': o = json.loads(b)
    elif fmt == 'orjson': o = orjson.loads(b)
    elif fmt == 'msgpack': o = msgpack.unpackb(b, raw=False)
    else: o = prod_pb2.Batch.FromString(b); sum(len(m.url) for m in o.items)
    print((resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - r0) / 1048576)
''')
(d / 'jb').write_bytes(jb); (d / 'mb').write_bytes(mb); (d / 'pb').write_bytes(pb); (d / 'c.py').write_text(CH)
for fmt, f, sz in (('json', 'jb', len(jb)), ('orjson', 'jb', len(jb)), ('msgpack', 'mb', len(mb)), ('protobuf', 'pb', len(pb))):
    vals = [float(subprocess.run([sys.executable, str(d / 'c.py'), fmt, str(d / f)], capture_output=True, text=True, env=dict(os.environ)).stdout.strip() or 'nan') for _ in range(3)]
    print(f'  {fmt:9s} 输入 {sz / 1048576:.1f} MiB,解码后峰值内存增量 {statistics.median(vals):.0f} MiB(3 次:{[round(v) for v in vals]},macOS 的 ru_maxrss 单位是字节)')
purge()
