import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m67'); reset()
cl = Cluster('m67', shards=2, chunk_mb=1).start(); c = cl.client(); adm = c.admin; cfg = c.config
adm.command('balancerStop'); adm.command('enableSharding', 'test')
def chunks(ns):
    uuid = cfg.collections.find_one({'_id': ns})['uuid']; return list(cfg.chunks.find({'uuid': uuid}).sort('min', 1))
def dist(ns): 
    d = {}
    for x in chunks(ns): d[x['shard']] = d.get(x['shard'], 0) + 1
    return dict(sorted(d.items()))
def owned(ns):
    sd = [x for x in adm.aggregate([{'$shardedDataDistribution': {}}]) if x['ns'] == ns]
    return {s['shardName']: s['numOwnedDocuments'] for s in sd[0]['shards']} if sd else {}
def show_ranges(ns, n=8):
    for x in chunks(ns)[:n]: print(f'    {x["shard"]}  [{x["min"]}, {x["max"]})')
print('== 一:哈希分片键在 shardCollection 时就预先建好 chunk:默认每个分片 1 个(这里 2 个分片 2 个 chunk),范围是 64 位哈希空间的切片')
c.test.command('create', 'h2'); adm.command('shardCollection', 'test.h2', key={'k': 'hashed'})
print(f'  chunk 分布 {dist("test.h2")};范围:'); show_ranges('test.h2')
print('== 二:numInitialChunks=8:想预先把哈希空间切成 8 份——在这个版本上实测结果如下')
adm.command('shardCollection', 'test.h8', key={'k': 'hashed'}, numInitialChunks=8)
print(f'  chunk 分布 {dist("test.h8")};全部范围:'); show_ranges('test.h8', 8)
print('== 三:写入 60,000 个连续整数键(0..59999),比较两种分片键下文档在两个分片上的分布(balancer 关着)')
N = 60000
adm.command('shardCollection', 'test.seq_h', key={'k': 'hashed'}, numInitialChunks=8)
c.test.command('create', 'seq_r'); adm.command('shardCollection', 'test.seq_r', key={'k': 1})
for coll in ('seq_h', 'seq_r'):
    for i in range(0, N, 2000): c.test[coll].insert_many([{'k': i + j, 'p': 'x' * 100} for j in range(2000)], ordered=False)
time.sleep(2)
print(f'  hashed:各分片拥有的文档数 {owned("test.seq_h")}')
print(f'  ranged:各分片拥有的文档数 {owned("test.seq_r")};chunk 分布 {dist("test.seq_r")}')
print('== 四:随机键(均匀分布的整数)写进 ranged 集合:先全进一个 chunk,打开 balancer 后被拆分并搬到两个分片')
c.test.command('create', 'rnd_r'); adm.command('shardCollection', 'test.rnd_r', key={'k': 1})
import random; r = random.Random(67)
for i in range(0, N, 2000): c.test.rnd_r.insert_many([{'k': r.randrange(10 ** 9), 'p': 'x' * 100} for _ in range(2000)], ordered=False)
print(f'  写完后(balancer 关着):chunk 分布 {dist("test.rnd_r")};拥有文档 {owned("test.rnd_r")}')
adm.command('balancerStart'); t0 = time.time()
while time.time() - t0 < 120:
    time.sleep(5); o = owned('test.rnd_r')
    if len(o) == 2 and min(o.values()) > 0.35 * sum(o.values()): break
print(f'  balancer 开了 {time.time() - t0:.0f} 秒后:chunk 分布 {dist("test.rnd_r")};拥有文档 {owned("test.rnd_r")}')
adm.command('balancerStop'); time.sleep(3)
print('== 五:热点键:哈希也救不了“一个键值占大头”——70% 的文档 k = 42,其余均匀。看每个 chunk 各有多少文档')
adm.command('shardCollection', 'test.hot', key={'k': 'hashed'}, numInitialChunks=8)
for i in range(0, N, 2000): c.test.hot.insert_many([{'k': 42 if r.random() < 0.7 else r.randrange(10 ** 9), 'p': 'x' * 100} for _ in range(2000)], ordered=False)
time.sleep(2); print(f'  各分片拥有的文档数 {owned("test.hot")}')
sizes = []
for x in chunks('test.hot'):
    lo = x['min']['k']; hi = x['max']['k']
    conds = []
    cond = {'$expr': {'$and': [{'$gte': [{'$toHashedIndexKey': '$k'}, lo]}, {'$lt': [{'$toHashedIndexKey': '$k'}, hi]}]}} if hi != 9223372036854775807 and lo != -9223372036854775808 else None
    if hi == 9223372036854775807: cond = {'$expr': {'$gte': [{'$toHashedIndexKey': '$k'}, lo]}}
    if lo == -9223372036854775808: cond = {'$expr': {'$lt': [{'$toHashedIndexKey': '$k'}, hi]}}
    sizes.append((x['shard'], c.test.hot.count_documents(cond)))
print(f'  每个 chunk 的文档数 (分片, 数量): {sizes}')
big = max(sizes, key=lambda t: t[1]); print(f'  最大的一个 chunk 有 {big[1]:,} 个文档({big[1] / N:.0%}),在 {big[0]} 上;哈希把 k = 42 的所有文档映射到同一个哈希值,只能落在同一个 chunk 里')
print('== 六:用 explain 看一个键落在哪个分片;以及哈希键的等值查询 targeted、范围查询 scatter-gather')
def hit(coll, q):
    e = c.test.command('explain', {'find': coll, 'filter': q}, verbosity='queryPlanner'); return sorted(s['shardName'] for s in e['queryPlanner']['winningPlan'].get('shards', []))
print(f'  hot 集合 k = 42 → {hit("hot", {"k": 42})};k = 43 → {hit("hot", {"k": 43})};k ∈ [40, 50) → {hit("hot", {"k": {"$gte": 40, "$lt": 50}})};k $in [1, 2, 3, 4] → {hit("hot", {"k": {"$in": [1, 2, 3, 4]}})}')
cl.stop()
