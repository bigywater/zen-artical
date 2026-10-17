import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m25'); reset()
n = Node('m25'); n.start(); c = n.client(); db = c.test
N = 200000
fill(db.t, N, lambda i: {'_id': i, 'a': i % 5, 'b': i % 1000, 'c': (i * 7919) % 100003, 'pad': 'x' * 50})
db.t.create_index('a'); db.t.create_index('b'); db.t.create_index('c')
APX = 'function plans(e) { var all = e.executionStats.allPlansExecution; var win = e.queryPlanner.winningPlan; return all.map(function(p) { var s = p.executionStages; var chain = []; while (s) { chain.push(s.stage + (s.indexName ? "(" + s.indexName + ")" : "")); s = s.inputStage }; return {plan: chain.reverse().join(" > "), nReturned: p.nReturned, works: p.executionStages.works, keys: p.totalKeysExamined, docs: p.totalDocsExamined} }) }; '
print('== 一:一条查询有多个候选索引时,优化器让每个候选计划“试跑”一小段,看谁在相同的 works 里返回得多。查询 {a: 3, b: 8}:a 有 5 个取值(不挑),b 有 1000 个取值(很挑)')
msh(n, EXJS + APX + 'var e = db.t.find({a: 3, b: 8}).explain("allPlansExecution"); ({winner: chain(e.queryPlanner.winningPlan), rejected: e.queryPlanner.rejectedPlans.map(p => chain(p)), trial: plans(e)})', n=60)
print('== 二:试跑的上限是服务端参数:每个候选最多取 101 条结果、最多 works 次数,或不超过集合文档数的一定比例')
msh(n, 'db.adminCommand({getParameter: 1, internalQueryPlanEvaluationMaxResults: 1, internalQueryPlanEvaluationWorks: 1, internalQueryPlanEvaluationCollFraction: 1, internalQueryCacheEvictionRatio: 1, internalQueryCacheWorksGrowthCoefficient: 1})')
print('== 三:把 MaxResults 调成 10,试跑就在返回 10 条时结束(同一条查询,allPlansExecution 里的 nReturned 与 works)')
msh(n, 'db.adminCommand({setParameter: 1, internalQueryPlanEvaluationMaxResults: 10})')
msh(n, EXJS + APX + 'var e = db.t.find({a: 3, b: 8}).explain("allPlansExecution"); plans(e)', label='db.t.find({a: 3, b: 8}).explain("allPlansExecution")    // MaxResults = 10', n=40)
msh(n, 'db.adminCommand({setParameter: 1, internalQueryPlanEvaluationMaxResults: 101})')
print('== 四:没有阻塞排序的计划更受青睐:{a: 3} 按 c 排序,候选一是 a_1 索引加内存 SORT,候选二是按 c_1 索引顺序扫、边扫边过滤 a')
msh(n, EXJS + APX + 'var e = db.t.find({a: 3}).sort({c: 1}).explain("allPlansExecution"); ({winner: chain(e.queryPlanner.winningPlan), trial: plans(e)})', n=60)
msh(n, EXJS + 'ex(db.t.find({a: 3}).sort({c: 1}).limit(10).explain("executionStats"))', label='加 limit(10) 之后', n=12)
print('== 五:一个计划在试跑期间就把所有结果返回完(到达 EOF),直接获胜:查询一个只有 2 条结果的值')
msh(n, EXJS + APX + 'var e = db.t.find({c: 5000, a: {$gte: 0}}).explain("allPlansExecution"); ({winner: chain(e.queryPlanner.winningPlan), trial: plans(e)})', n=60)
print('== 六:试跑选出来的计划在完整执行里的表现:对 {a: 3, b: 8} 逐个 hint 每个索引,看真实耗时(9 次中位数)')
def t(h): return bench(lambda: list(db.t.find({'a': 3, 'b': 8}).hint(h)), 9)
rows = [(h, t(h)) for h in ('a_1', 'b_1', 'c_1')]
for h, ms_ in rows: print(f'  hint({h}): {fm(ms_)}')
print(f'  不 hint(优化器选): {fm(bench(lambda: list(db.t.find({"a": 3, "b": 7})), 9))}')
n.stop()
