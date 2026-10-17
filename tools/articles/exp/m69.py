import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from bson.min_key import MinKey
from bson.max_key import MaxKey
tee('m69'); reset()
cl = Cluster('m69', shards=3, chunk_mb=1).start(); c = cl.client(); adm = c.admin; cfg = c.config
adm.command('balancerStop'); adm.command('enableSharding', 'test')
S = [nd.client() for nd in cl.shards]
c.test.command('create', 'users'); adm.command('shardCollection', 'test.users', key={'region': 1, 'uid': 1})
REG = ['eu', 'us', 'apac']
def by_region(owned=True):
    out = {}
    for i, s in enumerate(S):
        for reg in REG:
            out[(f'sh{i}', reg)] = s.test.users.count_documents({'region': reg})
    return out
def owned():
    sd = [x for x in adm.aggregate([{'$shardedDataDistribution': {}}]) if x['ns'] == 'test.users'][0]['shards']; return {s['shardName']: s['numOwnedDocuments'] for s in sd}
print('== 一:三个分片,分片键 {region, uid}。把 sh0 标成区域 EU、sh1 标成区域 US(sh2 不加区域),再声明键范围:region = "eu" 的数据属于 EU,region = "us" 的属于 US')
adm.command('addShardToZone', 'sh0', zone='EU'); adm.command('addShardToZone', 'sh1', zone='US')
adm.command('updateZoneKeyRange', 'test.users', min={'region': 'eu', 'uid': MinKey()}, max={'region': 'eu', 'uid': MaxKey()}, zone='EU')
adm.command('updateZoneKeyRange', 'test.users', min={'region': 'us', 'uid': MinKey()}, max={'region': 'us', 'uid': MaxKey()}, zone='US')
print('  分片的 zone: ' + str([(s['_id'], s.get('tags')) for s in cfg.shards.find()]))
print('  zone 的键范围(config.tags): ' + str([(t['tag'], t['min'], t['max']) for t in cfg.tags.find()]))
print('== 二:写入 3 个区域各 8,000 个文档(共 24,000,每个约 1 KB)。balancer 关着时它们全在 primary 分片上')
import random; r = random.Random(69)
for reg in REG:
    for i in range(0, 8000, 2000): c.test.users.insert_many([{'region': reg, 'uid': r.randrange(10 ** 9), 'p': 'x' * 1000} for _ in range(2000)], ordered=False)
b = by_region(); print('  各分片上各区域的文档数 (分片, 区域): ' + str({k: v for k, v in b.items() if v}))
print('== 三:打开 balancer:数据按 zone 迁移——eu 的去 sh0,us 的去 sh1,没有 zone 的 apac 由 balancer 自己平均')
adm.command('balancerStart'); t0 = time.time()
while time.time() - t0 < 150:
    time.sleep(5); b = by_region(); ok = b[('sh0', 'eu')] >= 7900 and b[('sh1', 'us')] >= 7900 and b[('sh0', 'us')] + b[('sh2', 'us')] < 100 and b[('sh1', 'eu')] + b[('sh2', 'eu')] < 100
    if ok and time.time() - t0 > 20: break
print(f'  balancer 开了 {time.time() - t0:.0f} 秒后各分片上各区域的文档数(含尚未清理的孤儿): ' + str({k: v for k, v in b.items() if v}))
print(f'  各分片拥有的文档数(不含孤儿): {owned()}')
print('== 四:chunk 的范围在 zone 边界上被切开,每个 chunk 都完全落在一个 zone 里')
uuid = cfg.collections.find_one({'_id': 'test.users'})['uuid']; cs = list(cfg.chunks.find({'uuid': uuid}).sort('min', 1))
def desc(x): return f'{x["shard"]}  [{x["min"]["region"]!s}/{x["min"]["uid"]!s}, {x["max"]["region"]!s}/{x["max"]["uid"]!s})'
print(f'  共 {len(cs)} 个 chunk;各分片 chunk 数 {dict((s, sum(1 for x in cs if x["shard"] == s)) for s in ("sh0", "sh1", "sh2"))}')
for x in cs: 
    if x['min']['region'] != x['max']['region'] or True: pass
shown = [x for x in cs if str(x['min']['region']) in ('MinKey()', 'eu') and str(x['max']['region']) in ('eu', 'us', 'apac') or x['min']['region'] == 'us'][:5]
b_ = [desc(x) for x in cs if x['min']['region'] != x['max']['region']]; print(f'  跨 region 边界的 chunk(它们的 min/max 的 region 不同): {b_}')
print('== 五:改 zone:把 US 区域的键范围移到 sh2 上(sh2 加入 US,sh1 退出 US),数据会跟着搬')
adm.command('addShardToZone', 'sh2', zone='US'); adm.command('removeShardFromZone', 'sh1', zone='US')
t0 = time.time()
while time.time() - t0 < 150:
    time.sleep(5); b = by_region()
    if b[('sh2', 'us')] >= 7900 and time.time() - t0 > 10: break
print(f'  改 zone 后 {time.time() - t0:.0f} 秒:各分片拥有的文档数 {owned()};sh2 上 us 区域的文档 {b[("sh2", "us")]}')
print('== 六:不属于任何 zone 范围的键(region = "apac")——balancer 当作普通数据,在没有 zone 的分片(也可以是任意分片)之间平均')
sd = {s: S[i].test.users.count_documents({'region': 'apac'}) for i, s in enumerate(['sh0', 'sh1', 'sh2'])}
print(f'  apac 的 8,000 个文档在各分片上(直连计数,含孤儿): {sd};各分片拥有的文档数总计 {owned()}')
cl.stop()
