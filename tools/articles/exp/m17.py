import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m17'); reset()
n = Node('m17'); n.start(); c = n.client(); db = c.test
db.names.insert_many([{'_id': i, 'n': v} for i, v in enumerate(['alice', 'Alice', 'ALICE', 'bob', 'Bob', 'Ärger', 'arger', 'Zoe', 'zoe', 'élan', 'Elan', 'a10', 'a2', 'a1'])])
print('== 一:默认的比较是二进制(逐字节)的:大小写不同就是不同的值,排序是大写字母在小写前面')
msh(n, 'db.names.find({n: "alice"}).toArray().map(d => d.n)')
msh(n, 'db.names.find({}, {_id: 0}).sort({n: 1}).toArray().map(d => d.n)')
print('== 二:查询时指定 collation:strength 2 忽略大小写,strength 1 连重音符号也忽略;locale 决定排序规则')
msh(n, 'db.names.find({n: "alice"}).collation({locale: "en", strength: 2}).toArray().map(d => d.n)')
msh(n, 'db.names.find({n: "arger"}).collation({locale: "en", strength: 2}).toArray().map(d => d.n)')
msh(n, 'db.names.find({n: "arger"}).collation({locale: "en", strength: 1}).toArray().map(d => d.n)')
msh(n, 'db.names.find({}, {_id: 0}).sort({n: 1}).collation({locale: "en"}).toArray().map(d => d.n)')
print('== 三:numericOrdering 让数字字符串按数值比较(a2 < a10),其它 locale 有自己的排序')
msh(n, 'db.names.find({n: /^a\\d/}, {_id: 0}).sort({n: 1}).collation({locale: "en", numericOrdering: true}).toArray().map(d => d.n)')
db.cn.insert_many([{'n': x} for x in ['张', '李', '王', '赵', '陈', '刘', '杨']])
msh(n, 'db.cn.find({}, {_id: 0}).sort({n: 1}).toArray().map(d => d.n)', label='db.cn.find().sort({n: 1})    // 默认:按 UTF-8 字节')
msh(n, 'db.cn.find({}, {_id: 0}).sort({n: 1}).collation({locale: "zh"}).toArray().map(d => d.n)', label='db.cn.find().sort({n: 1}).collation({locale: "zh"})    // 拼音顺序')
print('== 四:索引与 collation:没有指定 collation 的索引,用 collation 查询时不能用它(explain 里变成 COLLSCAN);要建同 collation 的索引')
N = 200000; r = random.Random(17)
base = ['alice', 'bob', 'carol', 'dave', 'erin', 'frank', 'grace', 'heidi', 'ivan', 'judy']
docs = [{'_id': i, 'n': r.choice(base) + str(r.randrange(20000)) if r.random() < 0.5 else r.choice(base).capitalize() + str(r.randrange(20000))} for i in range(N)]
for i in range(0, N, 20000): db.big.insert_many(docs[i:i + 20000], ordered=False)
db.big.create_index('n')
CH = 'function chain(p) { var s = []; while (p) { s.push(p.stage + (p.indexName ? "(" + p.indexName + ")" : "")); p = p.inputStage; } return s.join(" > ") }; '
msh(n, CH + 'var e = db.big.find({n: "alice77"}).collation({locale: "en", strength: 2}).explain("executionStats"); ({plan: chain(e.queryPlanner.winningPlan), nReturned: e.executionStats.nReturned, totalKeysExamined: e.executionStats.totalKeysExamined, totalDocsExamined: e.executionStats.totalDocsExamined})', label='db.big.find({n: "alice77"}).collation({locale: "en", strength: 2}).explain()    // 索引 n_1 是二进制比较')
db.big.create_index('n', name='n_ci', collation={'locale': 'en', 'strength': 2})
msh(n, CH + 'var e = db.big.find({n: "alice77"}).collation({locale: "en", strength: 2}).explain("executionStats"); ({plan: chain(e.queryPlanner.winningPlan), nReturned: e.executionStats.nReturned, totalKeysExamined: e.executionStats.totalKeysExamined, totalDocsExamined: e.executionStats.totalDocsExamined})', label='同样的查询,建了 {n: 1} + collation {locale: "en", strength: 2} 的索引 n_ci 之后')
msh(n, CH + 'var e = db.big.find({n: "alice77"}).explain("executionStats"); ({plan: chain(e.queryPlanner.winningPlan), nReturned: e.executionStats.nReturned, totalKeysExamined: e.executionStats.totalKeysExamined})', label='不带 collation 的查询仍然用 n_1 索引')
print('== 五:耗时(各 9 次中位数):不区分大小写的等值查询,四种写法')
def t(fn, k=9):
    fn(); ts = []
    for _ in range(k):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
from pymongo.collation import Collation
CI = Collation('en', strength=2)
coll = db.big
t_idx = t(lambda: list(coll.find({'n': 'alice77'}, collation=CI)))
coll.drop_index('n_ci'); t_scan = t(lambda: list(coll.find({'n': 'alice77'}, collation=CI)), 5)
t_regex = t(lambda: list(coll.find({'n': {'$regex': '^alice77$', '$options': 'i'}})), 5)
t_exact = t(lambda: list(coll.find({'n': 'alice77'})))
print(f'  精确等值(二进制索引 n_1)             {t_exact:>8.1f} ms')
print(f'  collation strength 2 + 同 collation 索引 {t_idx:>8.1f} ms')
print(f'  collation strength 2 但索引 collation 不匹配(全表) {t_scan:>8.1f} ms')
print(f'  正则 /^alice77$/i                    {t_regex:>8.1f} ms')
print('== 六:集合级默认 collation:创建集合时指定后,查询和索引默认继承它;索引变大')
db.create_collection('ci', collation={'locale': 'en', 'strength': 2})
db.ci.insert_many([{'_id': i, 'n': d['n']} for i, d in enumerate(docs[:100000])]); db.bin.insert_many([{'_id': i, 'n': d['n']} for i, d in enumerate(docs[:100000])])
db.ci.create_index('n'); db.bin.create_index('n')
msh(n, 'db.getCollectionInfos({name: "ci"})[0].options')
Q = docs[0]['n'].swapcase()
print(f'  集合里存着 {docs[0]["n"]!r},现在用大小写相反的 {Q!r} 去查(查询里没有写 collation):')
msh(n, f'db.ci.find({{n: "{Q}"}}).toArray().length + " 个(ci 集合)," + db.bin.find({{n: "{Q}"}}).toArray().length + " 个(普通二进制集合)"', label=f'db.ci.find({{n: "{Q}"}}) 与 db.bin.find({{n: "{Q}"}})')
msh(n, 'db.ci.getIndexes()')
c.admin.command('fsync'); time.sleep(1)
si = db.command('collStats', 'ci')['indexSizes']['n_1']; sb = db.command('collStats', 'bin')['indexSizes']['n_1']
print(f'  同样 100,000 个文档上的 n_1 索引大小:二进制 {sb:,} 字节,collation(en, strength 2) {si:,} 字节({si / sb:.2f} 倍)')
n.stop()
