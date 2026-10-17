import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m27'); reset()
n = Node('m27'); n.start(); c = n.client(); db = c.test
N = 300000
fill(db.t, N, lambda i: {'_id': i, 'status': ['A', 'B', 'C', 'D'][i % 4], 'ts': i, 'user': i % 10000, 'v': (i * 7919) % 1000})
db.t.create_index('status'); db.t.create_index('ts'); db.t.create_index('user'); db.t.create_index([('status', 1), ('ts', 1)])
Q = '{status: "A", ts: {$gte: 290000}, user: 1234}'
print(f'== 一:查询 {Q}:三个条件各有索引,复合索引 status_1_ts_1 也在。让优化器自己选,和逐个 hint 的耗时对比(9 次中位数)')
from pymongo import ASCENDING
def tq(h=None):
    def f():
        cur = db.t.find({'status': 'A', 'ts': {'$gte': 290000}, 'user': 1234})
        if h: cur = cur.hint(h)
        list(cur)
    return bench(f, 9)
rows = [('(优化器自己选)', None), ('status_1', 'status_1'), ('ts_1', 'ts_1'), ('user_1', 'user_1'), ('status_1_ts_1', 'status_1_ts_1'), ('$natural: 1(全表)', [('$natural', 1)])]
for nm, h in rows:
    print(f'  hint {nm:<20}{fm(tq(h)):>10}')
msh(n, EXJS + f'ex(db.t.find({Q}).explain("executionStats"))', label='不 hint 时优化器的选择', n=12)
print('== 二:hint 逐个强制后的计划和检查量')
for h in ('status_1', 'ts_1', 'user_1', 'status_1_ts_1'):
    msh(n, EXJS + f'ex(db.t.find({Q}).hint("{h}").explain("executionStats"))', label=f'hint("{h}")', n=12)
print('== 三:hint 写法:索引名、键模式都可以;不存在的索引报错;{$natural: 1} / -1 强制全表正向 / 反向')
msh(n, EXJS + f'ex(db.t.find({Q}).hint({{status: 1, ts: 1}}).explain("executionStats"))', label='hint({status: 1, ts: 1})    // 键模式', n=12)
msh(n, f'try {{ db.t.find({Q}).hint("nope_1").toArray() }} catch (e) {{ ({{code: e.code, message: e.message}}) }}', label='hint("nope_1")    // 不存在的索引')
msh(n, f'try {{ db.t.find({Q}).hint({{status: -1}}).toArray() }} catch (e) {{ ({{code: e.code, message: e.message}}) }}', label='hint({status: -1})    // 存在 status_1,但键模式方向不同')
msh(n, EXJS + f'ex(db.t.find({Q}).hint({{$natural: -1}}).explain("executionStats"))', label='hint({$natural: -1})    // 反向全表', n=12)
print('== 四:hint 的计划不进计划缓存:不 hint 的同形状查询会建缓存条目,hint 的不会')
msh(n, 'db.t.getPlanCache().clear(); for (var i = 0; i < 3; i++) db.t.find({status: "A", ts: {$gte: 290000}, user: 1000 + i}).hint("ts_1").toArray(); db.t.aggregate([{$planCacheStats: {}}]).toArray().length', label='连续 3 次带 hint("ts_1") 的查询之后缓存条目数')
msh(n, 'for (var i = 0; i < 3; i++) db.t.find({status: "A", ts: {$gte: 290000}, user: 1000 + i}).toArray(); db.t.aggregate([{$planCacheStats: {}}]).toArray().length', label='连续 3 次不带 hint 的同形状查询之后缓存条目数')
print('== 五:hint 用错的代价:一条本来很快的按 user 查询,被迫走了 status_1(只有 4 个取值)')
t_good = bench(lambda: list(db.t.find({'user': 777})), 9); t_bad = bench(lambda: list(db.t.find({'user': 777}).hint('status_1')), 5); t_nat = bench(lambda: list(db.t.find({'user': 777}).hint([('$natural', 1)])), 3)
print(f'  find({{user: 777}}):不 hint {fm(t_good)};hint status_1 {fm(t_bad)}({t_bad / t_good:.0f} 倍);hint $natural {fm(t_nat)}({t_nat / t_good:.0f} 倍)')
msh(n, EXJS + 'ex(db.t.find({user: 777}).hint("status_1").explain("executionStats"))', label='db.t.find({user: 777}).hint("status_1")', n=12)
print('== 六:hint 也能用在 aggregate、count、update / delete 上')
msh(n, EXJS + 'var e = db.t.explain("executionStats").aggregate([{$match: {user: 777}}], {hint: "status_1"}); ex(e)', label='aggregate([{$match: {user: 777}}], {hint: "status_1"})', n=12)
msh(n, 'db.t.countDocuments({user: 777}, {hint: "user_1"})', label='db.t.countDocuments({user: 777}, {hint: "user_1"})')
msh(n, 'var e = db.runCommand({explain: {update: "t", updates: [{q: {user: 777}, u: {$set: {x: 1}}, multi: true, hint: "status_1"}]}, verbosity: "executionStats"}); ({stage: e.executionStats.executionStages.stage, docsExamined: e.executionStats.totalDocsExamined, keysExamined: e.executionStats.totalKeysExamined})', label='update 带 hint: "status_1" 的 explain')
n.stop()
