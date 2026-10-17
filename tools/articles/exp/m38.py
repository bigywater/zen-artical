import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m38'); reset()
n = Node('m38', cache=0.5); n.start(); c = n.client(); db = c.test
N = 500000; r = random.Random(38)
fill(db.t, N, lambda i: {'_id': i, 'k': i * 3, 'u': i * 3 + 1, 'pad': 'x' * 50}, batch=25000)
db.t.create_index('k')
print(f'== 一:{N:,} 个文档,k = 3i 有索引,u = 3i+1 没有索引。查询 {{k: {{$in: [S 个存在的值]}}}},S 从 1 增大到 100,000:耗时、检查的键数')
SIZES = [1, 10, 100, 1000, 10000, 100000]
vals = {s: [3 * r.randrange(N) for _ in range(s)] for s in SIZES}
for s in SIZES: vals[s] = sorted(set(vals[s]))[:s]
print(f'  {"S":>8}{"实际去重后":>10}{"耗时":>10}{"每个值":>12}{"返回":>9}{"检查的键":>10}')
rows = {}
for s in SIZES:
    v = vals[s]; t = bench(lambda: list(db.t.find({'k': {'$in': v}}, {'pad': 0})), 5 if s <= 10000 else 3)
    ex = db.command('explain', {'find': 't', 'filter': {'k': {'$in': v}}, 'projection': {'pad': 0}}, verbosity='executionStats')
    rows[s] = (t, ex['executionStats']['nReturned'], ex['executionStats']['totalKeysExamined'])
    print(f'  {s:>8,}{len(v):>10,}{fm(t):>10}{t / len(v) * 1000:>9.1f} μs{rows[s][1]:>9,}{rows[s][2]:>10,}')
print('== 二:规划(选计划)本身的耗时:explain queryPlanner 里的 optimizationTimeMicros 随 $in 大小的变化')
for s in (1, 100, 10000, 100000):
    ex = db.command('explain', {'find': 't', 'filter': {'k': {'$in': vals[s]}}}, verbosity='queryPlanner')
    print(f'  S={s:>7,}:optimizationTimeMicros = {ex["queryPlanner"].get("optimizationTimeMicros")}')
print('== 三:结果按索引键顺序返回,不是 $in 列表的顺序;重复的值只匹配一次')
msh(n, 'db.t.find({k: {$in: [300, 3, 150, 3]}}, {_id: 0, k: 1}).toArray().map(d => d.k)', label='db.t.find({k: {$in: [300, 3, 150, 3]}})    // 列表顺序 300, 3, 150, 3')
msh(n, 'var e = db.t.find({k: {$in: [300, 3, 150, 3]}}).explain(); var s = e.queryPlanner.winningPlan; while (s.inputStage) s = s.inputStage; JSON.stringify(s.indexBounds)', note='indexBounds:排序、去重后的单点区间')
print('== 四:没有索引的字段:$in 的元素越多,全表扫描里每个文档的匹配越慢吗?(S = 10 / 1000 / 100000,各 3 次中位数)')
for s in (10, 1000, 100000):
    v = [3 * x + 1 for x in r.sample(range(N), s)]
    t = bench(lambda: list(db.t.find({'u': {'$in': v}}, {'pad': 0})), 3)
    print(f'  S={s:>7,}:{fm(t):>8}(COLLSCAN 500,000 个文档)')
print('== 五:$in 与同一条件写成 $or 的耗时对比(S=1000)')
v = vals[1000]
t_in = bench(lambda: list(db.t.find({'k': {'$in': v}}, {'pad': 0})), 5)
t_or = bench(lambda: list(db.t.find({'$or': [{'k': x} for x in v]}, {'pad': 0})), 5)
print(f'  $in {fm(t_in)};$or 1000 个分支 {fm(t_or)}')
print('== 六:上限:整条命令不能超过 16 MB(+16 KB);一个很大的 $in 数组会在客户端就被拒绝')
big = list(range(1_500_000))
try:
    list(db.t.find({'k': {'$in': big}}).limit(1))
    print('  150 万个整数的 $in 成功')
except Exception as e: print(f'  150 万个整数(BSON 数组 {len(bson.encode({"a": big})):,} 字节)的 $in: {type(e).__name__}: {str(e)[:130]}')
big = list(range(1_000_000)); sz = len(bson.encode({'a': big})); t0 = time.perf_counter(); k = len(list(db.t.find({'k': {'$in': big}}, {'pad': 0}))); dt = (time.perf_counter() - t0) * 1000
print(f'  100 万个整数(BSON 数组 {sz:,} 字节)的 $in:成功,返回 {k:,} 个,耗时 {dt:.0f} ms')
n.stop()
