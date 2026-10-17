import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m37'); reset()
n = Node('m37', cache=0.5); n.start(); c = n.client(); db = c.test
N = 500000; r = random.Random(37)
fill(db.t, N, lambda i: {'_id': i, 'ts': i // 10, 'user': r.randrange(1000), 'pad': 'x' * 100}, batch=25000)
db.t.create_index([('ts', 1), ('_id', 1)])
print(f'== 一:{N:,} 个文档,按 ts 排序(ts 有索引,每 10 个文档同一个 ts)取一页 20 条:skip 越大越慢——被跳过的索引键都要扫一遍')
rows = []
for sk in (0, 1000, 10000, 100000, 400000):
    t = bench(lambda: list(db.t.find({}, {'pad': 0}).sort([('ts', 1), ('_id', 1)]).skip(sk).limit(20)), 5)
    ex = jv(n, f'(function(){{ var e = db.t.find({{}}, {{pad: 0}}).sort({{ts: 1, _id: 1}}).skip({sk}).limit(20).explain("executionStats"); return {{keys: e.executionStats.totalKeysExamined, docs: e.executionStats.totalDocsExamined, nReturned: e.executionStats.nReturned}} }})()')
    rows.append((sk, t, ex))
print(f'  {"skip":>8}{"耗时":>10}{"检查的键":>12}{"读取的文档":>12}{"返回":>6}')
for sk, t, ex in rows: print(f'  {sk:>8,}{fm(t):>10}{ex["keys"]:>12,}{ex["docs"]:>12,}{ex["nReturned"]:>6}')
print('== 二:范围分页:记住上一页最后一条的 (ts, _id),下一页从它后面开始——不管翻到多深,每页的代价一样')
rows2 = []
for last in (0, 1000, 10000, 100000, 400000):
    lt, lid = last // 10, last
    q = {'$or': [{'ts': {'$gt': lt}}, {'ts': lt, '_id': {'$gt': lid}}]}
    t = bench(lambda: list(db.t.find(q, {'pad': 0}).sort([('ts', 1), ('_id', 1)]).limit(20)), 5)
    ex = jv(n, f'(function(){{ var e = db.t.find({json.dumps(q)}, {{pad: 0}}).sort({{ts: 1, _id: 1}}).limit(20).explain("executionStats"); return {{keys: e.executionStats.totalKeysExamined, docs: e.executionStats.totalDocsExamined, nReturned: e.executionStats.nReturned}} }})()')
    rows2.append((last, t, ex))
print(f'  {"上一页最后一条的 _id":>20}{"耗时":>10}{"检查的键":>12}{"读取的文档":>12}{"返回":>6}')
for last, t, ex in rows2: print(f'  {last:>20,}{fm(t):>10}{ex["keys"]:>12,}{ex["docs"]:>12,}{ex["nReturned"]:>6}')
print('== 三:用 explain 看 skip 的真面目:SKIP 阶段在 FETCH 之下,被跳过的只读索引键、不读文档;但键数是 skip + limit')
msh(n, EXJS.replace('return {plan: chain(root)', 'return {plan: (function f(s){ return s.stage + (s.inputStage ? " > " + f(s.inputStage) : "") })(root)') + 'ex(db.t.find({}).sort({ts: 1, _id: 1}).skip(100000).limit(20).explain("executionStats"))', label='db.t.find().sort({ts: 1, _id: 1}).skip(100000).limit(20)', n=12)
msh(n, 'var e = db.t.find({}, {_id: 1, ts: 1}).sort({ts: 1, _id: 1}).skip(100000).limit(20).explain("executionStats"); ({keys: e.executionStats.totalKeysExamined, docs: e.executionStats.totalDocsExamined})', label='只要索引里的字段(覆盖查询){_id: 1, ts: 1} 同样 skip 100000:')
print('== 四:排序键不唯一时必须带一个唯一的“平局打破”字段,否则范围分页会漏数据')
ts_last = 49999  # 最后一个 ts 值所在的行组: ts = 49999 对应 _id 499990~499999
page1 = list(db.t.find({'ts': {'$gte': 100}}, {'_id': 1, 'ts': 1}).sort('ts', 1).limit(15))
print(f'  按 ts 排序取一页 15 条:最后一条 _id={page1[-1]["_id"]}, ts={page1[-1]["ts"]};这个 ts 值共有 10 个文档')
wrong = list(db.t.find({'ts': {'$gt': page1[-1]['ts']}}, {'_id': 1, 'ts': 1}).sort('ts', 1).limit(5))
seen = {d['_id'] for d in page1}; allts = {d['_id'] for d in db.t.find({'ts': {'$in': [d['ts'] for d in page1]}}, {'_id': 1})}
print(f'  只用 ts > 上一页最后的 ts 作为条件:下一页第一条 _id={wrong[0]["_id"]};这两页之间丢掉了 {len(allts - seen - {d["_id"] for d in wrong})} 个 ts 相同的文档')
right = list(db.t.find({'$or': [{'ts': {'$gt': page1[-1]['ts']}}, {'ts': page1[-1]['ts'], '_id': {'$gt': page1[-1]['_id']}}]}, {'_id': 1, 'ts': 1}).sort([('ts', 1), ('_id', 1)]).limit(5))
print(f'  用 (ts, _id) 作为条件:下一页第一条 _id={right[0]["_id"]}(紧接着上一页的最后一条,不丢)')
print('== 五:翻页过程中有新数据写入:skip 分页会重复,范围分页不会。数据按 _id 倒序(最新的在前)展示,翻第 1 页、有 10 条新数据插入、再翻第 2 页')
db.feed.insert_many([{'_id': i, 'v': i} for i in range(1, 1001)])
p1 = [d['_id'] for d in db.feed.find({}, {'_id': 1}).sort('_id', -1).skip(0).limit(20)]
db.feed.insert_many([{'_id': i, 'v': i} for i in range(1001, 1011)])
p2_skip = [d['_id'] for d in db.feed.find({}, {'_id': 1}).sort('_id', -1).skip(20).limit(20)]
p2_range = [d['_id'] for d in db.feed.find({'_id': {'$lt': p1[-1]}}, {'_id': 1}).sort('_id', -1).limit(20)]
print(f'  第 1 页(最新 20 条): {p1[0]} … {p1[-1]}')
print(f'  skip 方式的第 2 页:{p2_skip[0]} … {p2_skip[-1]};与第 1 页重复的条数 {len(set(p1) & set(p2_skip))}')
print(f'  范围方式的第 2 页:{p2_range[0]} … {p2_range[-1]};与第 1 页重复的条数 {len(set(p1) & set(p2_range))}')
print('== 六:“总页数”要的总数:countDocuments 要数,estimatedDocumentCount 读元数据')
t_c = bench(lambda: db.t.count_documents({}), 5); t_e = bench(lambda: db.t.estimated_document_count(), 5)
t_f = bench(lambda: db.t.count_documents({'user': 5}), 3)
print(f'  countDocuments({{}}) {fm(t_c)};estimatedDocumentCount() {fm(t_e)};countDocuments({{user: 5}})(无索引的过滤条件){fm(t_f)}')
n.stop()
