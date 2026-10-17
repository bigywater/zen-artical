import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m34'); reset()
n = Node('m34'); n.start(); c = n.client(); db = c.test
N = 100000; r = random.Random(34); KEYS = [f'k{j}' for j in range(50)]
def mk(i):
    ks = r.sample(KEYS, 3); return {'_id': i, 'name': f'item{i}', 'attrs': {k: f'v{r.randrange(20)}' for k in ks}}
docs = [mk(i) for i in range(N)]
t0 = time.perf_counter()
for i in range(0, N, 10000): db.plain.insert_many(docs[i:i + 10000], ordered=False)
t_plain = (time.perf_counter() - t0) * 1000
db.wc.create_index([('attrs.$**', 1)])
t0 = time.perf_counter()
for i in range(0, N, 10000): db.wc.insert_many(docs[i:i + 10000], ordered=False)
t_wc = (time.perf_counter() - t0) * 1000
print(f'== 一:{N:,} 个文档,attrs 是一个子文档,每个文档随机带 50 个可能键名里的 3 个(k0 ~ k49),值是 v0 ~ v19。建通配符索引 attrs.$**')
msh(n, 'db.wc.getIndexes().filter(i => i.name != "_id_")')
print(f'  索引条目数: {db.command("validate", "wc", full=True)["keysPerIndex"]}(= {N:,} 个文档 × 3 个键)')
print('== 二:查询 attrs 下任意一个子字段都能走这个索引——不需要为 50 个键名各建一个索引')
msh(n, EXJS + 'ex(db.wc.find({"attrs.k17": "v5"}).explain("executionStats"))', label='db.wc.find({"attrs.k17": "v5"})', n=12)
msh(n, 'var e = db.wc.find({"attrs.k17": "v5"}).explain(); var s = e.queryPlanner.winningPlan; while (s.inputStage) s = s.inputStage; ({indexName: s.indexName, indexBounds: s.indexBounds})', note='索引键是 (字段路径, 值),所以边界是 [路径, 值]')
msh(n, EXJS + 'ex(db.wc.find({"attrs.k17": {$in: ["v5", "v6"]}}).explain("executionStats"))', label='db.wc.find({"attrs.k17": {$in: [v5, v6]}})', n=12)
msh(n, EXJS + 'ex(db.plain.find({"attrs.k17": "v5"}).explain("executionStats"))', label='对照:没有索引的 plain 集合', n=12)
d0 = docs[0]; (ka, va), (kb, vb) = list(d0['attrs'].items())[:2]
print('== 三:两个条件同时出现时只会用一个字段的范围,另一个在 FETCH 后过滤;复合索引才能同时收窄')
Q2 = '{"attrs.%s": "%s", "attrs.%s": "%s"}' % (ka, va, kb, vb)
msh(n, EXJS + f'ex(db.wc.find({Q2}).explain("executionStats"))', label=f'db.wc.find({Q2})', n=12)
db.cmp.insert_many(docs); db.cmp.create_index([(f'attrs.{ka}', 1), (f'attrs.{kb}', 1)])
msh(n, EXJS + f'ex(db.cmp.find({Q2}).explain("executionStats"))', label=f'对照:cmp 集合上 attrs.{ka} + attrs.{kb} 的复合索引', n=12)
print('== 四:通配符索引能做与不能做的:同一字段上的范围加排序、$exists: true 可以;否定条件和索引范围之外的字段不行')
msh(n, EXJS + 'ex(db.wc.find({"attrs.k17": {$gte: "v1"}}).sort({"attrs.k17": 1}).explain("executionStats"))', label='find({attrs.k17: {$gte: v1}}).sort({attrs.k17: 1})', n=12)
msh(n, EXJS + 'ex(db.wc.find({"attrs.k17": {$ne: "v5"}}).explain("executionStats"))', label='find({attrs.k17: {$ne: v5}})', n=12)
msh(n, EXJS + 'ex(db.wc.find({"attrs.k17": {$exists: true}}).explain("executionStats"))', label='find({attrs.k17: {$exists: true}})', n=12)
msh(n, EXJS + 'ex(db.wc.find({"name": "item5"}).explain("executionStats"))', label='find({name: "item5"})    // name 不在通配符索引覆盖的 attrs.* 下', n=12)
print('== 五:代价:索引条目数、大小和写入耗时(10 万个文档分 10 批插入)')
c.admin.command('fsync'); time.sleep(1.2)
szw = db.command('collStats', 'wc')['indexSizes']['attrs.$**_1']; db.plain.create_index('attrs.k17'); c.admin.command('fsync'); time.sleep(1.2); szp = db.command('collStats', 'plain')['indexSizes']['attrs.k17_1']
print(f'  通配符索引({N * 3:,} 条)大小 {szw:,} 字节;单字段索引 attrs.k17(约 {N * 3 // 50:,} 条)大小 {szp:,} 字节')
print(f'  批量插入 {N:,} 个文档:无二级索引 {t_plain:.0f} ms;带通配符索引 {t_wc:.0f} ms({t_wc / t_plain:.1f} 倍)')
print('== 六:限制:不能 unique;wildcardProjection 控制收录的字段;全文档 $** 会把所有字段都建进去;复合通配符索引的要求')
msh(n, 'try { db.x1.createIndex({"attrs.$**": 1}, {unique: true}) } catch (e) { e.message.replace(/^.*caused by :: /, "").slice(0, 150) }', label='createIndex({"attrs.$**": 1}, {unique: true})')
msh(n, 'db.x2.createIndex({"$**": 1}, {wildcardProjection: {"attrs.k1": 0, "name": 0}})', label='createIndex({"$**": 1}, {wildcardProjection: {"attrs.k1": 0, "name": 0}})    // 排除某些路径')
db.x3.create_index([('$**', 1)]); db.x3.insert_many(docs[:20000])
print(f'  整个文档 $** 的集合(2 万个文档,每个 name + 3 个 attrs + _id):索引条目数 {db.command("validate", "x3", full=True)["keysPerIndex"]}')
msh(n, 'try { db.x4.createIndex({"$**": 1, name: 1}) } catch (e) { e.message.replace(/^.*caused by :: /, "").slice(0, 150) }', label='createIndex({"$**": 1, name: 1})')
msh(n, 'try { db.x5.createIndex({"attrs.$**": 1, name: 1}) } catch (e) { e.message.replace(/^.*caused by :: /, "").slice(0, 150) }', label='createIndex({"attrs.$**": 1, name: 1})    // 通配符路径加普通字段的复合索引')
msh(n, 'db.x5.getIndexes().filter(i => i.name != "_id_")')
n.stop()
