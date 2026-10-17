import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m65'); reset()
cl = Cluster('m65', shards=2, chunk_mb=1).start(); c = cl.client(); adm = c.admin; cfg = c.config
print('== 一:两个分片 sh0、sh1(各是一个单节点副本集)+ 一个 config server + 一个 mongos;为了在小数据上观察,把 chunk 大小设成 1 MB(默认 128 MB)')
msh(cl.mongos, 'db.getSiblingDB("config").settings.find()', db='test', note='config.settings')
print('  ' + str([(s['_id'], s['host']) for s in adm.command('listShards')['shards']]))
adm.command('enableSharding', 'test'); adm.command('shardCollection', 'test.t', key={'k': 1})
def dist(coll='test.t'):
    uuid = cfg.collections.find_one({'_id': coll})['uuid']
    r = list(cfg.chunks.aggregate([{'$match': {'uuid': uuid}}, {'$group': {'_id': '$shard', 'chunks': {'$sum': 1}}}, {'$sort': {'_id': 1}}]))
    return {x['_id']: x['chunks'] for x in r}
print(f'== 二:刚分片的空集合只有一个覆盖 [MinKey, MaxKey) 的 chunk,在 primary 分片上:{dist()}')
msh(cl.mongos, 'db.getSiblingDB("config").chunks.find({}, {_id: 0, min: 1, max: 1, shard: 1})', note='config.chunks')
import random
r = random.Random(65)
print('== 三:balancer 开着的情况下写入 60 MB 数据(每个文档约 1 KB,k 随机):写入的同时,chunk 被拆分、迁移。写入期间每 2 秒看一次 chunk 分布')
N = 60000; hist = []; box = {'done': False}
def writer():
    for i in range(0, N, 1000): c.test.t.insert_many([{'k': r.randrange(10 ** 9), 'p': 'x' * 1000} for _ in range(1000)], ordered=False); time.sleep(0.15)
    box['done'] = True
t0 = time.time(); wt = threading.Thread(target=writer); wt.start()
while not box['done']:
    hist.append((round(time.time() - t0), dist())); time.sleep(2)
wt.join(); print('  写入期间 chunk 分布: ' + ' → '.join(f'{t}s:{d}' for t, d in hist[::max(1, len(hist) // 5)]))
print(f'  写完时(耗时 {time.time() - t0:.0f} s):{dist()}')
print('== 四:写入停止后 balancer 继续迁移,直到两个分片的数据量接近(最后 chunk 个数差很多,数据量却接近)。每 5 秒看一次 chunk 分布')
t1 = time.time(); h2 = []
while time.time() - t1 < 120:
    d = dist(); h2.append((round(time.time() - t1), d))
    if time.time() - t1 > 45 and h2[-1][1] == h2[-2][1] == h2[-3][1] if len(h2) >= 3 else False: break
    time.sleep(5)
print('  写完之后: ' + ' → '.join(f'{t}s:{d}' for t, d in h2[::max(1, len(h2) // 5)] + [h2[-1]]))
d_final = dist(); print(f'  最终 chunk 分布 {d_final}(chunk 个数差很多,但看数据量)')
sd = list(adm.aggregate([{'$shardedDataDistribution': {}}, {'$match': {'ns': 'test.t'}}]))[0]
for s in sd['shards']: print(f'    {s["shardName"]}:拥有 {s["numOwnedDocuments"]:,} 个文档 / {s["ownedSizeBytes"] / 1048576:.1f} MB;孤儿文档 {s["numOrphanedDocs"]:,} 个 / {s["orphanedSizeBytes"] / 1048576:.1f} MB')
print(f'    经 mongos 总数 {c.test.t.count_documents({}):,};直连分片的文档数 sh0={cl.shards[0].client().test.t.count_documents({}):,}、sh1={cl.shards[1].client().test.t.count_documents({}):,}(含孤儿文档,所以之和大于总数;mongos 会过滤孤儿)')
msh(cl.shards[0], 'db.adminCommand({getParameter: 1, orphanCleanupDelaySecs: 1}).orphanCleanupDelaySecs', note='孤儿文档的清理延迟(秒)')
print('== 五:config.changelog 里记录了每次迁移的步骤和耗时(moveChunk.from):看其中一次')
ev = list(cfg.changelog.find({'what': 'moveChunk.from'}).sort('time', 1))
print(f'  moveChunk.from 事件共 {len(ev)} 条')
if ev:
    e = ev[len(ev) // 2]; d = e['details']
    print(f'  其中一条:from {d.get("from")} → to {d.get("to")};min={d.get("min")} max={d.get("max")}')
    print('    各步骤耗时(毫秒): ' + ', '.join(f'{k}: {v}' for k, v in d.items() if k.startswith('step')))
    print(f'    其它字段: {sorted(k for k in d if not k.startswith("step"))}')
print('== 六:jumbo chunk:所有文档的分片键相同,chunk 太大却没法拆(没有可用的分割点)')
c.test.command('create', 'j'); adm.command('shardCollection', 'test.j', key={'k': 1})
for i in range(0, 4000, 1000): c.test.j.insert_many([{'k': 7, 'p': 'y' * 1000} for _ in range(1000)])
time.sleep(12)
jc = list(cfg.chunks.find({'uuid': cfg.collections.find_one({'_id': 'test.j'})['uuid']}))
print(f'  test.j:4000 个文档(约 4 MB)全部 k = 7;chunk 数 {len(jc)};其中带 jumbo 标记的 {sum(1 for x in jc if x.get("jumbo"))}')
print(f'  chunk 范围: {[(x["min"], x["max"], x["shard"]) for x in jc]}')
cl.stop()
