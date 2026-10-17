import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m71'); reset()
cl = Cluster('m71', shards=3).start(); c = cl.client(); adm = c.admin
adm.command('balancerStop'); adm.command('enableSharding', 'test')
c.test.command('create', 't'); adm.command('shardCollection', 'test.t', key={'uid': 1})
adm.command('split', 'test.t', middle={'uid': 10000}); adm.command('split', 'test.t', middle={'uid': 20000})
print('== 一:3 个分片(uid 每 10000 一段),30,000 个文档。explain 里的 splitPipeline 把 pipeline 拆成 shardsPart(在分片上执行)和 mergerPart(合并);带分片键条件的只访问相关分片,没有 splitPipeline')
for f, to in ((5, 'sh0'), (15000, 'sh1'), (25000, 'sh2')):
    try: adm.command('moveChunk', 'test.t', find={'uid': f}, to=to, _waitForDelete=True)
    except Exception as ex: print('  moveChunk', f, to, 'skip:', str(ex)[:80])
print('  块分布:', [(d['min']['uid'], d['max']['uid'], d['shard']) for d in c.config.chunks.find({'uuid': c.config.collections.find_one({'_id': 'test.t'})['uuid']}).sort('min', 1)])
N = 30000
for i in range(0, N, 5000): c.test.t.insert_many([{'uid': i + j, 'city': (i + j) % 50, 'amount': (i + j) % 100, 'pad': 'x' * 100} for j in range(5000)], ordered=False)
c.test.command('create', 'cities'); c.test.cities.insert_many([{'_id': i, 'name': f'city{i}'} for i in range(50)])
def plan(pipe):
    return c.test.command('explain', {'aggregate': 't', 'pipeline': pipe, 'cursor': {}}, verbosity='queryPlanner')
def split_info(pipe):
    e = plan(pipe)
    if 'splitPipeline' in e and e['splitPipeline']:
        sp = e['splitPipeline']; stg = lambda L: [list(s.keys())[0] for s in L]
        return dict(shards=sorted(e['shards'].keys()), shardsPart=stg(sp['shardsPart']), mergerPart=stg(sp['mergerPart']))
    return dict(shards=sorted(e['shards'].keys()) if 'shards' in e else None, splitPipeline=None, keys=sorted(e.keys())[:6])
def show(label, pipe):
    print(f'  {label:<34}{json.dumps(split_info(pipe), ensure_ascii=False)[:230]}')
show('$match uid = 15000', [{'$match': {'uid': 15000}}, {'$group': {'_id': '$city', 'n': {'$sum': 1}}}])
show('$match uid 范围 [0, 5000) + $group', [{'$match': {'uid': {'$lt': 5000}}}, {'$group': {'_id': '$city', 'n': {'$sum': 1}}}])
print('== 二:没有分片键条件的 $group:每个分片先做部分分组,再合并')
show('$group by city', [{'$group': {'_id': '$city', 'n': {'$sum': 1}, 'total': {'$sum': '$amount'}}}])
show('$group by city, 然后 $sort', [{'$group': {'_id': '$city', 'n': {'$sum': 1}}}, {'$sort': {'n': -1}}])
print('== 三:partial group 减少了多少数据:分片返回给合并阶段的文档数 vs 分片上扫描的文档数(executionStats)')
e = c.test.command('explain', {'aggregate': 't', 'pipeline': [{'$group': {'_id': '$city', 'n': {'$sum': 1}}}], 'cursor': {}}, verbosity='executionStats')
for sh, v in sorted(e['shards'].items()):
    st = v['executionStats']
    print(f'  {sh}:扫描 {st["totalDocsExamined"]:,} 个文档,返回给合并阶段 {st["nReturned"]} 个文档')
print('== 四:$sort + $limit:每个分片各自排序取 limit 个,合并阶段再排一次')
show('$sort amount, uid; $limit 5', [{'$sort': {'amount': -1, 'uid': 1}}, {'$limit': 5}])
sp = plan([{'$sort': {'amount': -1, 'uid': 1}}, {'$limit': 5}])['splitPipeline']
print('  shardsPart[0] =', json.dumps(sp['shardsPart'][0], ensure_ascii=False, default=str)); mc = sp['mergerPart'][0]['$mergeCursors']; print('  mergerPart    =', [list(x.keys())[0] for x in sp['mergerPart']], ' $mergeCursors 的 sort =', json.dumps(mc.get('sort')), ' $mergeCursors 的字段 =', sorted(mc.keys()))
print('== 五:$lookup 到未分片的小集合(cities)和 $out / $merge:合并发生在哪里')
show('$group + $lookup(cities)', [{'$group': {'_id': '$city', 'n': {'$sum': 1}}}, {'$lookup': {'from': 'cities', 'localField': '_id', 'foreignField': '_id', 'as': 'c'}}])
show('$match + $out', [{'$match': {'uid': {'$lt': 5000}}}, {'$out': 'o1'}])
show('$group + $merge', [{'$group': {'_id': '$city', 'n': {'$sum': 1}}}, {'$merge': {'into': 'm1'}}])
print('== 六:真实运行的耗时:只有 $group(每个分片先做部分分组),对比 $group 前加 $sort(分片要先把全部文档按 uid 排好序再交给合并阶段)')
import time as _t
def tm(pipe, n=5): return bench(lambda: list(c.test.t.aggregate(pipe)), n)
a = tm([{'$group': {'_id': '$city', 'n': {'$sum': 1}}}]); b = tm([{'$sort': {'uid': 1}}, {'$group': {'_id': '$city', 'n': {'$sum': 1}}}])
print(f'  只有 $group:{fm(a)};$sort 在 $group 前(排序整个集合再分组):{fm(b)}')
sb = split_info([{'$sort': {'uid': 1}}, {'$group': {'_id': '$city', 'n': {'$sum': 1}}}])
print(f'  后一种的拆分: {json.dumps(sb, ensure_ascii=False)}')
cl.stop()
