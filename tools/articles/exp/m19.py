import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m19'); reset()
n = Node('m19'); n.start(); c = n.client(); db = c.test
N = 300000; ST = ['open', 'closed', 'pending', 'done', 'hold']
fill(db.t, N, lambda i: {'_id': i, 'status': ST[i % 5], 'ts': i, 'score': (i * 7919) % 1000})
print(f'== 一:数据:{N:,} 个文档,status 5 个取值(等值)、ts 单调递增(排序)、score 0~999 随机(范围);查询 {{status: "open", score: {{$gte: 900}}}},按 ts 倒序,取前 20')
IDX = [('E-S-R', {'status': 1, 'ts': 1, 'score': 1}), ('E-R-S', {'status': 1, 'score': 1, 'ts': 1}), ('R-E-S', {'score': 1, 'status': 1, 'ts': 1}), ('S-E-R', {'ts': 1, 'status': 1, 'score': 1})]
for nm, k in IDX: db.t.create_index(list(k.items()), name=nm)
msh(n, 'db.t.countDocuments({status: "open", score: {$gte: 900}})')
def run_q(js_hint, limit, label):
    lim = f'.limit({limit})' if limit else ''
    return msh(n, EXJS + f'var e = db.t.find({{status: "open", score: {{$gte: 900}}}}).sort({{ts: -1}}){lim}.hint({js_hint}).explain("executionStats"); ex(e)', label=label, n=12)
print('== 二:带 limit(20):四个顺序不同的复合索引,用 hint 强制各用一次,看计划里有没有 SORT、检查了多少键和文档')
for nm, k in IDX: run_q(json.dumps(nm), 20, f'hint("{nm}")  // 字段顺序 {" , ".join(k)}')
print('== 三:不带 limit(6,000 个结果全部按 ts 排序)')
for nm, k in IDX: run_q(json.dumps(nm), 0, f'hint("{nm}")  // 字段顺序 {" , ".join(k)},无 limit')
print('== 四:耗时(各 7 次中位数,pymongo):同样的查询,limit 20 / 不 limit')
from pymongo import ASCENDING
def t(name, lim):
    def f():
        cur = db.t.find({'status': 'open', 'score': {'$gte': 900}}).sort('ts', -1).hint(name)
        if lim: cur = cur.limit(lim)
        list(cur)
    return bench(f, 7)
print(f'  {"索引":<8}{"limit 20":>12}{"无 limit":>12}')
for nm, k in IDX: print(f'  {nm:<8}{fm(t(nm, 20)):>12}{fm(t(nm, 0)):>12}')
print('== 五:不 hint,让优化器自己选(有四个候选)')
run_q('undefined', 20, '不加 hint,limit 20') if False else None
msh(n, EXJS + 'var e = db.t.find({status: "open", score: {$gte: 900}}).sort({ts: -1}).limit(20).explain("executionStats"); ex(e)', label='不加 hint,limit 20', n=12)
msh(n, EXJS + 'var e = db.t.find({status: "open", score: {$gte: 900}}).sort({ts: -1}).explain("executionStats"); ex(e)', label='不加 hint,无 limit', n=12)
print('== 六:把范围条件改成等值 {status: "open", score: 950} 再按 ts 排序:这时两个等值字段放在前面、排序字段放最后(E-R-S)就是最好的顺序')
msh(n, EXJS + 'var e = db.t.find({status: "open", score: 950}).sort({ts: -1}).hint("E-S-R").explain("executionStats"); ex(e)', label='hint("E-S-R")', n=12)
msh(n, EXJS + 'var e = db.t.find({status: "open", score: 950}).sort({ts: -1}).hint("E-R-S").explain("executionStats"); ex(e)', label='hint("E-R-S")', n=12)
n.stop()
