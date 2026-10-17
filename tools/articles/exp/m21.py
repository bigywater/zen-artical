import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m21'); reset()
n = Node('m21'); n.start(); c = n.client(); db = c.test
def keys(coll, idx): return c.test.command('validate', coll, full=True)['keysPerIndex'][idx]
print('== 一:数组字段上建索引会为每个元素生成一条索引条目(multikey);对每种取值单独建一个一文档的集合,用 validate 看索引里的条目数')
cases = [("['x','y','z']", ['x', 'y', 'z']), ("['x']", ['x']), ('[]', []), ('字段缺失', None), ("标量 'x'", 'x'), ("['x','x','x']", ['x', 'x', 'x']), ("[['x','y'],'z']", [['x', 'y'], 'z']), ("[null, 'x']", [None, 'x'])]
tot = 0
for i, (nm, v) in enumerate(cases):
    coll = db[f'one{i}']; coll.insert_one({'_id': 1} if v is None else {'_id': 1, 't': v}); coll.create_index('t'); k = keys(f'one{i}', 't_1'); tot += k
    print(f'  t = {nm:<18}索引条目 {k}')
db.a.insert_many([{'_id': i + 1, **({} if v is None else {'t': v})} for i, (nm, v) in enumerate(cases)])
db.a.create_index('t')
print(f'  把这 {len(cases)} 个文档放进同一个集合建索引 t_1,条目数 = {keys("a", "t_1")}(上面逐个相加 = {tot})')
msh(n, EXJS + 'var e = db.a.find({t: "x"}).explain("executionStats"); var s = e.queryPlanner.winningPlan; while (s.inputStage) s = s.inputStage; ({isMultiKey: s.isMultiKey, multiKeyPaths: s.multiKeyPaths, keysExamined: e.executionStats.totalKeysExamined, nReturned: e.executionStats.nReturned})', label='db.a.find({t: "x"}).explain("executionStats")')
print('== 二:条目数随数组长度线性增长:每个文档带 N 个元素的数组,10,000 个文档,索引大小和条目数')
print(f'  {"每个数组元素数":<14}{"索引条目":>12}{"索引大小(字节)":>18}{"每个文档平均":>14}')
for k in (1, 5, 20, 100):
    coll = db[f'g{k}']; coll.insert_many([{'_id': i, 't': [f'v{(i * 31 + j) % 5000}' for j in range(k)]} for i in range(10000)]); coll.create_index('t')
    c.admin.command('fsync'); time.sleep(1.2)
    ks = keys(f'g{k}', 't_1'); sz = db.command('collStats', f'g{k}')['indexSizes']['t_1']
    print(f'  {k:<14}{ks:>12,}{sz:>18,}{sz / 10000:>12.0f} B')
print('== 三:数组里的重复值:同一个文档里重复的元素只会生成一条索引条目')
db.d.insert_many([{'_id': 1, 't': ['a', 'a', 'a', 'b']}]); db.d.create_index('t')
print(f'  [a,a,a,b] 一个文档,索引条目数 = {keys("d", "t_1")}(元素 4 个,不同值 2 个)')
print('== 四:查询怎么用 multikey 索引:$all 取交集边界,$elemMatch 在子文档数组上,以及数组整体匹配')
db.p.insert_many([{'_id': i, 'tags': [f'a{i % 10}', f'b{i % 7}', f'c{i % 3}'], 'items': [{'k': f'a{i % 10}', 'v': (i // 10) % 5}, {'k': f'b{i % 7}', 'v': (i // 7) % 5}]} for i in range(50000)])
db.p.create_index('tags'); db.p.create_index([('items.k', 1), ('items.v', 1)])
msh(n, EXJS + 'ex(db.p.find({tags: "a3"}).explain("executionStats"))', label='db.p.find({tags: "a3"})')
msh(n, EXJS + 'ex(db.p.find({tags: {$all: ["a3", "b2"]}}).explain("executionStats"))', label='db.p.find({tags: {$all: ["a3", "b2"]}})')
msh(n, EXJS + 'ex(db.p.find({tags: ["a3", "b2", "c0"]}).explain("executionStats"))', label='db.p.find({tags: ["a3", "b2", "c0"]})    // 整个数组相等')
print('== 五:$elemMatch 与普通条件的区别:同一个子文档里同时满足,还是分别由不同元素满足')
msh(n, 'db.p.countDocuments({"items.k": "a3", "items.v": 1})', label='db.p.countDocuments({"items.k": "a3", "items.v": 1})    // 可以由不同元素各满足一个')
msh(n, 'db.p.countDocuments({items: {$elemMatch: {k: "a3", v: 1}}})', label='db.p.countDocuments({items: {$elemMatch: {k: "a3", v: 1}}})    // 同一个元素同时满足')
msh(n, EXJS + 'ex(db.p.find({"items.k": "a3", "items.v": 1}).explain("executionStats"))', label='db.p.find({"items.k": "a3", "items.v": 1}) 的计划')
msh(n, EXJS + 'ex(db.p.find({items: {$elemMatch: {k: "a3", v: 1}}}).explain("executionStats"))', label='db.p.find({items: {$elemMatch: {k: "a3", v: 1}}}) 的计划')
print('== 六:multikey 的代价:写入时每个元素都要插一条索引条目;对比 1 个元素与 100 个元素时 10,000 个文档的批量写入耗时')
for k in (1, 100):
    coll = db[f'w{k}']; coll.create_index('t'); docs = [{'_id': i, 't': [f'v{(i * 31 + j) % 5000}' for j in range(k)]} for i in range(10000)]
    t0 = time.perf_counter(); coll.insert_many(docs, ordered=False); dt = (time.perf_counter() - t0) * 1000
    print(f'  每个文档 {k:>3} 个元素:插入 10,000 个文档(带 t 上的索引)耗时 {dt:.0f} ms')
n.stop()
