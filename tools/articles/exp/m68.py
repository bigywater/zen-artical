import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.errors import PyMongoError
tee('m68'); reset()
cl = Cluster('m68', shards=3).start(); c = cl.client(); adm = c.admin; cfg = c.config
adm.command('balancerStop'); adm.command('enableSharding', 'test')
c.test.command('create', 't'); adm.command('shardCollection', 'test.t', key={'uid': 1})
adm.command('split', 'test.t', middle={'uid': 1000}); adm.command('split', 'test.t', middle={'uid': 2000})
adm.command('moveChunk', 'test.t', find={'uid': 1500}, to='sh1'); adm.command('moveChunk', 'test.t', find={'uid': 2500}, to='sh2')
c.test.t.create_index('city')
c.test.t.insert_many([{'uid': i, 'city': i % 50, 'v': i % 7, 'pad': 'x' * 100} for i in range(3000)], ordered=False)
S = [nd.client() for nd in cl.shards]
print('== 一:3 个分片,分片键 uid(ranged),手工分成三段:sh0 拥有 uid < 1000、sh1 拥有 [1000, 2000)、sh2 拥有 >= 2000。每段 1000 个文档')
uuid = cfg.collections.find_one({'_id': 'test.t'})['uuid']
for x in cfg.chunks.find({'uuid': uuid}).sort('min', 1): print(f'  {x["shard"]}  [{x["min"]["uid"]}, {x["max"]["uid"]})')
def explain_shards(q, sort=None, limit=None):
    cmd = {'find': 't', 'filter': q}
    if sort: cmd['sort'] = sort
    if limit: cmd['limit'] = limit
    e = c.test.command('explain', cmd, verbosity='queryPlanner'); wp = e['queryPlanner']['winningPlan']
    return wp['stage'], sorted(s['shardName'] for s in wp.get('shards', []))
print('== 二:explain 的 winningPlan.stage 与涉及的分片:SINGLE_SHARD = 只问一个分片(targeted);SHARD_MERGE = 问多个分片再合并')
for lab_, q, sort in [('uid = 1500', {'uid': 1500}, None), ('uid ∈ [500, 800)', {'uid': {'$gte': 500, '$lt': 800}}, None), ('uid ∈ [900, 1100)(跨 sh0、sh1)', {'uid': {'$gte': 900, '$lt': 1100}}, None), ('uid $in [10, 1100, 2100]', {'uid': {'$in': [10, 1100, 2100]}}, None), ('city = 7(不含分片键)', {'city': 7}, None), ('空条件(全表)', {}, None), ('city = 7, sort uid', {'city': 7}, {'uid': 1})]:
    st, sh = explain_shards(q, sort); print(f'  {lab_:<28}stage={st:<14}分片 {sh}')
print('== 三:实际执行:各分片的 query 计数器(opcounters.query)在 100 次查询前后的增量。看不同查询给每个分片带来多少负载')
def qc(): return [s.admin.command('serverStatus')['opcounters']['query'] for s in S]
print(f'  {"查询(各 100 次)":<30}{"sh0":>6}{"sh1":>6}{"sh2":>6}')
for lab_, q in [('uid = 1500(targeted)', lambda i: {'uid': 1000 + i}), ('uid 范围 [0, 100)', lambda i: {'uid': {'$gte': i % 50, '$lt': 100}}), ('city = 7(无分片键)', lambda i: {'city': i % 50}), ('空条件 limit 1', lambda i: {})]:
    b = qc()
    for i in range(100): list(c.test.t.find(q(i), {'_id': 1}).limit(1))
    a = qc(); print(f'  {lab_:<30}{a[0] - b[0]:>6}{a[1] - b[1]:>6}{a[2] - b[2]:>6}')
print('== 四:sort + limit:每个分片各自排序取 limit 个,mongos 合并再取前 limit 个(SHARD_MERGE_SORT)')
e = c.test.command('explain', {'find': 't', 'filter': {'city': 7}, 'sort': {'uid': -1}, 'limit': 5}, verbosity='executionStats')
wp = e['queryPlanner']['winningPlan']; print(f'  stage = {wp["stage"]};各分片返回 nReturned: {[(s["shardName"], s["nReturned"]) for s in e["executionStats"]["executionStages"]["shards"]]};最终 nReturned {e["executionStats"]["nReturned"]}')
print('== 五:update / delete 不带分片键:单文档的写要找到该文档在哪个分片')
for lab_, fn in [('update_one 带分片键 uid', lambda: c.test.t.update_one({'uid': 1500}, {'$set': {'v': 99}})), ('update_one 只带 _id 以外的字段 city', lambda: c.test.t.update_one({'city': 7}, {'$set': {'v': 98}})), ('update_many 不带分片键', lambda: c.test.t.update_many({'city': 8}, {'$set': {'v': 97}})), ('delete_one 不带分片键', lambda: c.test.t.delete_one({'city': 9}))]:
    try: r = fn(); print(f'  {lab_:<34}成功(matched={getattr(r, "matched_count", getattr(r, "deleted_count", None))})')
    except PyMongoError as ex: print(f'  {lab_:<34}失败 {type(ex).__name__}: {str(ex)[:90]}')
print('== 六:executionStats 里每个分片检查了多少文档:targeted 与 scatter-gather 对比')
for lab_, q in [('uid = 1500', {'uid': 1500}), ('city = 7', {'city': 7})]:
    e = c.test.command('explain', {'find': 't', 'filter': q}, verbosity='executionStats'); st = e['executionStats']
    per = [(s['shardName'], s['totalKeysExamined'], s['totalDocsExamined'], s['nReturned']) for s in st['executionStages']['shards']]
    print(f'  {lab_:<12}涉及 {len(per)} 个分片;每个分片(名, 检查的键, 检查的文档, 返回): {per};合计检查键 {st["totalKeysExamined"]}')
cl.stop()
