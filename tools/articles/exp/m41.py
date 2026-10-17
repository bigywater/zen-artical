import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m41'); reset()
n = Node('m41', cache=0.5); n.start(); c = n.client(); db = c.test
NO, NC = 200000, 20000; r = random.Random(41)
fill(db.customers, NC, lambda i: {'_id': i, 'cid': f'c{i}', 'name': f'name{i}', 'region': i % 10}, batch=20000)
fill(db.orders, NO, lambda i: {'_id': i, 'cust': r.randrange(NC), 'ccid': f'c{r.randrange(NC)}', 'amount': r.randrange(1000)}, batch=20000)
print(f'== 一:{NO:,} 个订单、{NC:,} 个客户。orders.cust 对应 customers._id(有默认的 _id 索引);orders.ccid 对应 customers.cid(没有索引)')
LK = lambda local, foreign, lim: f'[{{$limit: {lim}}}, {{$lookup: {{from: "customers", localField: "{local}", foreignField: "{foreign}", as: "c"}}}}]'
SJS = ('function strat(e) { var st = JSON.stringify(e); var m = st.match(/"strategy":"([A-Za-z]+)"/); var ix = st.match(/"indexName":"([A-Za-z0-9_]+)"/); var fc = st.match(/"foreignCollection":"([a-z.]+)"/); '
       'return {strategy: m && m[1], foreignCollection: fc && fc[1], foreignIndex: ix && ix[1]} }; ')
msh(n, SJS + 'strat(db.orders.explain("executionStats").aggregate(' + LK('cust', '_id', 1000) + '))', label='$lookup {localField: "cust", foreignField: "_id"}  // foreign 有 _id 索引', n=12)
msh(n, SJS + 'strat(db.orders.explain("executionStats").aggregate(' + LK('ccid', 'cid', 1000) + '))', label='$lookup {localField: "ccid", foreignField: "cid"}  // foreign 没有索引', n=12)
print('== 二:同样 1,000 条订单 $lookup 到客户:有索引与没有索引的耗时(各 5 次中位数,3 次)')
def tl_(local, foreign, lim, k=5): return bench(lambda: list(db.orders.aggregate(json.loads(LK(local, foreign, lim).replace('$limit: ', '"$limit": ').replace('{$lookup', '{"$lookup').replace('from:', '"from":').replace('localField:', '"localField":').replace('foreignField:', '"foreignField":').replace('as:', '"as":').replace('[{', '[{').replace('{$limit', '{"$limit')))), k) if False else None
def pipe(local, foreign, lim): return [{'$limit': lim}, {'$lookup': {'from': 'customers', 'localField': local, 'foreignField': foreign, 'as': 'c'}}]
def tm(local, foreign, lim, k=5): return bench(lambda: list(db.orders.aggregate(pipe(local, foreign, lim))), k)
for lim in (100, 1000):
    print(f'  {lim:>5} 条订单:有索引({"cust → _id"}) {fm(tm("cust", "_id", lim))};没有索引(ccid → cid) {fm(tm("ccid", "cid", lim, 3))}')
print('== 三:给 customers.cid 建索引之后,同一个 $lookup')
db.customers.create_index('cid')
msh(n, SJS + 'strat(db.orders.explain("executionStats").aggregate(' + LK('ccid', 'cid', 1000) + '))', label='$lookup {localField: "ccid", foreignField: "cid"}  // 建了 cid 索引', n=12)
for lim in (100, 1000):
    print(f'  {lim:>5} 条订单:有索引(ccid → cid) {fm(tm("ccid", "cid", lim))}')
print('== 四:订单数增加时的耗时:有索引随输入线性增长;没有索引呢?(没有索引的 cid 先删掉再测)')
db.customers.drop_index('cid_1')
print(f'  {"订单数":>8}{"有索引":>12}{"无索引":>12}')
for lim in (100, 1000, 10000):
    a = tm('cust', '_id', lim, 3); b = tm('ccid', 'cid', lim, 1 if lim >= 10000 else 3)
    print(f'  {lim:>8,}{fm(a):>12}{fm(b):>12}')
print('== 五:$lookup 的 let / pipeline 形式:相当于子查询,条件写在 $expr 里,能用索引吗?')
PL = '[{$limit: 1000}, {$lookup: {from: "customers", let: {c: "$cust"}, pipeline: [{$match: {$expr: {$eq: ["$_id", "$$c"]}}}], as: "c"}}]'
msh(n, SJS + f'strat(db.orders.explain("executionStats").aggregate({PL}))', label='let / pipeline 形式({$match: {$expr: {$eq: ["$_id", "$$c"]}}})', n=12)
def tp(k=5): return bench(lambda: list(db.orders.aggregate([{'$limit': 1000}, {'$lookup': {'from': 'customers', 'let': {'c': '$cust'}, 'pipeline': [{'$match': {'$expr': {'$eq': ['$_id', '$$c']}}}], 'as': 'c'}}])), k)
print(f'  1000 条订单:let/pipeline 形式 {fm(tp())};普通 localField/foreignField 形式 {fm(tm("cust", "_id", 1000))}')
print('== 六:$lookup 把匹配到的所有文档放进一个数组字段;结果文档可以大于 16 MiB 返回给客户端,但写不进集合')
db.big.insert_many([{'_id': i, 'g': 1, 'pad': 'y' * (1024 * 1024)} for i in range(20)]); db.one.insert_one({'_id': 1, 'g': 1})
msh(n, 'var r = db.one.aggregate([{$lookup: {from: "big", localField: "g", foreignField: "g", as: "m"}}, {$project: {n: {$size: "$m"}, bytes: {$bsonSize: "$$ROOT"}}}]).toArray()[0]; r', label='$lookup 匹配 20 个 1 MiB 的文档,看结果文档有多大', n=12)
msh(n, 'try { db.one.aggregate([{$lookup: {from: "big", localField: "g", foreignField: "g", as: "m"}}, {$out: "joined"}]).toArray(); "ok" } catch (e) { e.message.slice(0, 200) }', label='同样的结果 $out 写进集合')
msh(n, 'db.one.aggregate([{$lookup: {from: "big", localField: "g", foreignField: "g", as: "m"}}, {$unwind: "$m"}, {$project: {"m.pad": 0}}, {$count: "n"}])', label='先 $unwind 展开再 $project 去掉大字段')
n.stop()
