import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import zlib, struct, datetime as dt
tee('m80'); reset()
nd = Node('m80').start(); c = nd.client(); DD = nd.db / 'diagnostic.data'
def listing():
    return sorted((f, (DD / f).stat().st_size) for f in os.listdir(DD))
print('== 一:FTDC(full-time diagnostic data capture)默认就开着:diagnostic.data 目录、采样间隔、文件与目录大小上限')
p = {k: v for k, v in c.admin.command('getParameter', '*').items() if k.startswith('diagnosticDataCollection') and k in ('diagnosticDataCollectionEnabled', 'diagnosticDataCollectionPeriodMillis', 'diagnosticDataCollectionFileSizeMB', 'diagnosticDataCollectionDirectorySizeMB', 'diagnosticDataCollectionSamplesPerChunk', 'diagnosticDataCollectionSamplesPerInterimUpdate')}
print('  参数: ' + str(p))
time.sleep(3)
print('  刚启动约 3 秒后目录里的文件: ' + str(listing()))
time.sleep(2)
c.test.t.insert_many([{'_id': i, 'p': 'x' * 100} for i in range(2000)], ordered=False)
time.sleep(5)
BEFORE_INS = c.admin.command('serverStatus')['opcounters']['insert']
for i in range(5): c.test.u.insert_many([{'_id': j + i * 1000, 'p': 'y' * 100} for j in range(1000)], ordered=False); time.sleep(0.4)
AFTER_INS = c.admin.command('serverStatus')['opcounters']['insert']
print(f'  在运行期间精确插入了 5,000 个文档(serverStatus 的 opcounters.insert 从 {BEFORE_INS} 涨到 {AFTER_INS})')
time.sleep(25)
print('  运行约 36 秒后(mongod 还在运行)目录里的文件: ' + str(listing()))
nd.stop(); time.sleep(1)
print('  mongod 正常关闭之后: ' + str(listing()))
print('== 二:文件格式:顺序排列的 BSON 文档,每个有 _id(时间)、type 和 doc 或 data。type 0 = 元数据,1 = 压缩的指标块,2 = 周期性元数据')
fn = [f for f in os.listdir(DD) if f.startswith('metrics.2')][0]; raw = (DD / fn).read_bytes()
docs = []; off = 0
while off < len(raw):
    ln = struct.unpack('<i', raw[off:off + 4])[0]; docs.append(bson.decode(raw[off:off + ln])); off += ln
from collections import Counter
print(f'  {fn}:{len(raw):,} 字节,共 {len(docs)} 个 BSON 文档,type 的计数 = {dict(Counter(d["type"] for d in docs))}')
for d in docs:
    if d['type'] == 0: print('  type 0 文档的字段: ' + str(list(d.keys())) + ',doc 里的顶层字段: ' + str(list(d['doc'].keys())))
    if d['type'] == 1: print(f'  type 1 文档:_id = {d["_id"]},data 是 BinData {len(d["data"]):,} 字节,前 4 字节 = 解压后长度 {struct.unpack("<I", bytes(d["data"])[:4])[0]:,}')
chunks = [d for d in docs if d['type'] == 1]
print('== 三:解压一个 type 1 块:zlib 压缩;里面是一个参考文档(第一次采样的完整 serverStatus 等),然后是指标个数、采样个数,再是 varint 编码的差值')
def varint(buf, pos):
    r = 0; sh = 0
    while True:
        b = buf[pos]; pos += 1; r |= (b & 0x7f) << sh; sh += 7
        if not b & 0x80: return r, pos
def flat(o, pre, out):
    if isinstance(o, dict):
        for k, v in o.items(): flat(v, pre + [k], out)
    elif isinstance(o, list):
        for i, v in enumerate(o): flat(v, pre + [str(i)], out)
    elif isinstance(o, bool): out.append(('.'.join(pre), int(o)))
    elif isinstance(o, (int, float)) and not isinstance(o, bool): out.append(('.'.join(pre), int(o)))
    elif isinstance(o, dt.datetime): out.append(('.'.join(pre), int(o.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)))
    elif isinstance(o, bson.Timestamp): out.append(('.'.join(pre) + '.t', o.time)); out.append(('.'.join(pre) + '.i', o.inc))
def decode_chunk(d):
    b = bytes(d['data']); un = struct.unpack('<I', b[:4])[0]; z = zlib.decompress(b[4:]); assert len(z) == un
    rl = struct.unpack('<i', z[:4])[0]; ref = bson.decode(z[:rl]); nm, nd_ = struct.unpack('<II', z[rl:rl + 8]); pos = rl + 8
    names = []; flat(ref, [], names)
    assert len(names) == nm, (len(names), nm)
    flatv = []; total = nm * nd_
    while len(flatv) < total:
        v, pos = varint(z, pos)
        if v == 0:
            n, pos = varint(z, pos); flatv.extend([0] * (n + 1))
        else:
            if v >= 1 << 63: v -= 1 << 64
            flatv.append(v)
    assert len(flatv) == total
    series = []
    for i in range(nm):
        vals = [names[i][1]]
        for x in flatv[i * nd_:(i + 1) * nd_]: vals.append(vals[-1] + x)
        series.append(vals)
    assert pos == len(z), (pos, len(z))
    return ref, [n for n, _ in names], series, len(b), un, nd_ + 1
dec = [decode_chunk(d) for d in chunks]
for i, (r_, n_, s_, zc_, un_, ns_) in enumerate(dec): print(f'  块 {i}:{ns_} 个采样,{len(n_):,} 个指标,压缩后 {zc_:,} 字节,解压后 {un_:,} 字节')
k = max(range(len(dec)), key=lambda i: dec[i][5]); ref, names, series, zc, un, ns = dec[k]
print(f'  取采样最多的块 {k}:压缩后 {zc:,} 字节 → 解压后 {un:,} 字节(压缩比 {un / zc:.1f}×)')
print(f'  参考文档的顶层字段: {list(ref.keys())}')
print(f'  指标个数(数值型叶子字段)= {len(names):,},采样个数 = {ns}')
print('== 四:各组指标的个数(按路径前缀统计)')
grp = Counter('.'.join(n.split('.')[:2]) if n.startswith('serverStatus.') else n.split('.')[0] for n in names)
print('  ' + str(dict(grp.most_common(10))))
print('== 五:用已知负载验证解码:运行期间精确插入了 5,000 个文档(之前还有 2,000 个),解码出的 serverStatus.opcounters.insert 序列应当同步增加')
same = all(d[1] == dec[0][1] for d in dec)
print(f'  所有块的指标名完全相同: {same}(每个块的指标集若变了就要开新块)')
S_ = [x for d in dec for x in d[2][d[1].index('serverStatus.opcounters.insert')]]; T_ = [x for d in dec for x in d[2][d[1].index('start')]]
gaps = Counter(b - a for a, b in zip(T_, T_[1:]))
print(f'  共 {len(S_)} 个采样;start 时间戳相邻差(毫秒)最常见的取值: {gaps.most_common(4)}')
print(f'  opcounters.insert 序列首尾: {S_[0]} → {S_[-1]}')
inc = [(i, b - a) for i, (a, b) in enumerate(zip(S_, S_[1:])) if b != a]
print('  insert 计数有变化的采样 (第几个采样, 增量): ' + str(inc))
print(f'  增量之和 = {sum(x for _, x in inc)};其中 2,000 来自先插入的那批,后面 5 次 insert_many(各 1,000 个)分落在三个采样里;serverStatus 自己读到的 {BEFORE_INS} → {AFTER_INS},增量 {AFTER_INS - BEFORE_INS}')
C_ = [x for d in dec for x in d[2][d[1].index('serverStatus.connections.current')]]; print(f'  serverStatus.connections.current 序列的取值: {sorted(set(C_))}')
print('== 六:占多少空间、能保留多久:每增加一个采样的边际代价,以及每个块都带一份参考文档的固定代价')
bz = zlib.decompress(bytes(chunks[k]['data'])[4:]); rl = struct.unpack('<i', bz[:4])[0]
ref_c = len(zlib.compress(bz[:rl], 6)); del_c = len(zlib.compress(bz[rl:], 6))
print(f'  取采样最多的块({ns} 个采样)分开压缩:参考文档(完整的第一个采样,{rl:,} 字节)压缩后 {ref_c:,} 字节;其余 {ns - 1} 个采样的差值流({len(bz) - rl:,} 字节)压缩后 {del_c:,} 字节 → 每个采样的差值约 {del_c / (ns - 1):.0f} 字节')
chunk300 = ref_c + del_c / (ns - 1) * 299; per_day = chunk300 * 288
print(f'  按每块 300 个采样估算:每块约 {chunk300 / 1000:.0f} KB,每天 288 块约 {per_day / 1e6:.1f} MB;500 MB 的目录上限约够 {500e6 / per_day:.0f} 天(这是空闲实例的外推,不是实测)')
