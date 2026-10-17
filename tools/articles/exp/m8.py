import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m8'); reset()
n = Node('m8', cache=0.25); n.start(); c = n.client(); db = c.test
r = random.Random(8)
words = [''.join(r.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(r.randrange(3, 10))) for _ in range(300)]
def doc(i):
    return {'_id': i, 'user': r.randrange(5000), 'level': r.choice(['INFO', 'INFO', 'INFO', 'WARN', 'ERROR']), 'ts': 1_700_000_000 + i * 3, 'msg': ' '.join(r.choice(words) for _ in range(r.randrange(12, 24))), 'host': f'srv-{r.randrange(40):02d}'}
N = 100000
docs = [doc(i) for i in range(N)]
raw = sum(len(bson.encode(d)) for d in docs)
print(f'== 一:数据:{N:,} 条日志样的文档(msg 是从 300 个词里随机拼的 12~23 个词),BSON 总大小 {raw:,} 字节,平均 {raw // N} 字节')
print('  样例:', {k: (v if k != 'msg' else v[:40] + '…') for k, v in docs[0].items()})
COMP = ['none', 'snappy', 'zstd', 'zlib']
res = {}
print('== 二:同一份数据放进 4 个集合,每个集合 createCollection 时指定 block_compressor(WiredTiger 的块压缩),插入后 fsync')
for cm in COMP:
    db.create_collection(f'c_{cm}', storageEngine={'wiredTiger': {'configString': f'block_compressor={cm}'}})
    t0 = time.perf_counter()
    for i in range(0, N, 5000): db[f'c_{cm}'].insert_many(docs[i:i + 5000], ordered=False)
    ins = (time.perf_counter() - t0) * 1000
    res[cm] = {'insert': ins}
c.admin.command('fsync'); time.sleep(2); c.admin.command('fsync')
print(f'  {"压缩算法":<8}{"dataSize":>14}{"storageSize":>14}{"占 BSON 的比例":>16}{"磁盘文件大小":>14}')
for cm in COMP:
    st = db.command('collStats', f'c_{cm}'); uri = st['wiredTiger']['uri'].split(':')[-1]
    sz = (n.db / f'{uri}.wt').stat().st_size
    res[cm].update(data=st['size'], store=st['storageSize'], file=sz)
    print(f'  {cm:<8}{st["size"]:>14,}{st["storageSize"]:>14,}{st["storageSize"] / st["size"]:>15.0%}{sz:>14,}')
print('== 三:创建时的配置字符串在 collStats 里能看到;服务器级默认值来自启动参数')
for cm in ('snappy', 'zstd'):
    cs = db.command('collStats', f'c_{cm}')['wiredTiger']['creationString']
    print(f'  c_{cm}: ' + ','.join(x for x in cs.split(',') if 'block_compressor' in x))
msh(n, 'db.adminCommand({getCmdLineOpts: 1}).parsed')
db.create_collection('c_default'); db.c_default.insert_one({'x': 1})
cs = db.command('collStats', 'c_default')['wiredTiger']['creationString']
print('  没有指定压缩算法的集合 c_default: ' + ','.join(x for x in cs.split(',') if 'block_compressor' in x))
ci_ = db.command('collStats', 'c_zstd')['indexDetails']['_id_']
print('  索引的 creationString 里有 prefix_compression 吗: ' + ','.join(x for x in ci_['creationString'].split(',') if 'prefix_compression' in x or 'block_compressor' in x))
print('== 四:插入耗时(同样的 100,000 个文档,分 20 批,每个集合 1 次)')
for cm in COMP: print(f'  {cm:<8}{res[cm]["insert"]:>8.0f} ms')
print('== 五:冷缓存全表扫描:重启 mongod(清空 WiredTiger 缓存)后,每个集合扫描一次(磁盘块要先解压)。每个集合在重启后各测 1 次,顺序打乱,共 3 轮取中位数')
n.restart(); c = n.client(); db = c.test
scan = {cm: [] for cm in COMP}
for rnd in range(3):
    if rnd: n.restart(); c = n.client(); db = c.test
    order = COMP[:]; random.Random(rnd).shuffle(order)
    for cm in order:
        t0 = time.perf_counter(); k = len(list(db[f'c_{cm}'].find({'level': 'FATAL'}))); db_ = (time.perf_counter() - t0) * 1000
        scan[cm].append(db_)
        n.restart(); c = n.client(); db = c.test
for cm in COMP: print(f'  {cm:<8}{median(scan[cm]):>8.0f} ms   (3 次: {", ".join(f"{x:.0f}" for x in scan[cm])})')
print('== 六:数据本身的可压缩性决定一切:同样 100,000 个文档,payload 换成随机字节(不可压缩)')
rb = random.Random(9)
rdocs = [{'_id': i, 'p': Binary(rb.randbytes(200))} for i in range(N)]
rraw = sum(len(bson.encode(d)) for d in rdocs)
rr = {}
for cm in ('none', 'snappy', 'zstd', 'zlib'):
    db.create_collection(f'r_{cm}', storageEngine={'wiredTiger': {'configString': f'block_compressor={cm}'}})
    for i in range(0, N, 5000): db[f'r_{cm}'].insert_many(rdocs[i:i + 5000], ordered=False)
c.admin.command('fsync'); time.sleep(2); c.admin.command('fsync')
print(f'  随机字节文档的 BSON 总大小 {rraw:,};')
for cm in ('none', 'snappy', 'zstd', 'zlib'):
    st = db.command('collStats', f'r_{cm}'); print(f'  {cm:<8}storageSize {st["storageSize"]:>12,}  占 BSON 的 {st["storageSize"] / rraw:.0%}')
n.stop()
