import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m15'); reset()
n = Node('m15'); n.start(); c = n.client(); db = c.test
db.orders.insert_many([{'_id': i, 'user': f'u{i % 20}', 'status': ['new', 'paid', 'shipped'][i % 3], 'amount': 10 + i % 50, 'secret': 'x'} for i in range(3000)])
db.orders.create_index('status'); db.orders.create_index('user')
print('== 一:视图就是存下来的 pipeline:createView 之后 listCollections 里 type 是 view,options 里有 viewOn 和 pipeline;内部集合 system.views 里存着它')
msh(n, 'db.createView("paid_orders", "orders", [{$match: {status: "paid"}}, {$project: {secret: 0}}])')
msh(n, 'db.getCollectionInfos({name: "paid_orders"})')
msh(n, 'db.system.views.find()')
msh(n, 'db.getCollectionInfos().map(c => c.name + ":" + c.type)')
print('== 二:查询视图时,服务端把视图的 pipeline 放在你的查询前面:底层数据一改,视图立刻跟着变,没有物化')
msh(n, 'db.paid_orders.countDocuments({})')
msh(n, 'db.orders.updateMany({_id: {$lt: 6}}, {$set: {status: "paid"}}).modifiedCount')
msh(n, 'db.paid_orders.countDocuments({})')
msh(n, 'db.paid_orders.findOne({_id: 3})')
print('== 三:视图自己没有索引,用的是底层集合的索引:优化器把对视图的过滤条件尽量前移到视图 pipeline 里,条件在分组键上能前移到 $group 之前,在聚合结果上则不能')
msh(n, 'db.createView("by_user", "orders", [{$group: {_id: "$user", total: {$sum: "$amount"}}}])')
CH = 'function chain(p) { var s = []; while (p) { s.push(p.stage + (p.indexName ? "(" + p.indexName + ")" : "")); p = p.inputStage; } return s.join(" > ") }; '
CH2 = 'function chain(p) { var s = []; while (p) { s.push(p.stage + (p.indexName ? "(" + p.indexName + ")" : "")); p = p.inputStage; } return s.join(" > ") }; function show(e) { return {plan: chain(e.queryPlanner.winningPlan.queryPlan || e.queryPlanner.winningPlan), optimizedPipeline: e.queryPlanner.optimizedPipeline, totalKeysExamined: e.executionStats.totalKeysExamined, totalDocsExamined: e.executionStats.totalDocsExamined, nReturned: e.executionStats.nReturned} }; '
print('  视图 paid_orders = orders 上 [{$match: {status: "paid"}}, {$project: {secret: 0}}]:')
msh(n, CH2 + 'show(db.paid_orders.find({user: "u3"}).explain("executionStats"))', label='db.paid_orders.find({user: "u3"}).explain("executionStats")')
print('  对照:直接在 orders 上查同样的条件')
msh(n, CH2 + 'show(db.orders.find({status: "paid", user: "u3"}).explain("executionStats"))', label='db.orders.find({status: "paid", user: "u3"}).explain("executionStats")')
print('  视图 by_user = orders 上 [{$group: {_id: "$user", total: {$sum: "$amount"}}}]:')
msh(n, CH2 + 'show(db.by_user.explain("executionStats").aggregate([{$match: {_id: "u3"}}]))', label='db.by_user.explain("executionStats").aggregate([{$match: {_id: "u3"}}])    // 条件在分组键 _id 上')
msh(n, CH2 + 'show(db.by_user.explain("executionStats").aggregate([{$match: {total: {$gt: 1000}}}]))', label='db.by_user.explain("executionStats").aggregate([{$match: {total: {$gt: 1000}}}])    // 条件在聚合结果 total 上')
print('== 四:对视图的限制:写入、建索引、更新、rename 都不行;$natural 排序是可以的')
for lab_, js in [('insertOne', 'db.paid_orders.insertOne({a: 1})'), ('createIndex', 'db.paid_orders.createIndex({user: 1})'), ('updateOne', 'db.paid_orders.updateOne({_id: 3}, {$set: {a: 1}})'), ('find().sort({$natural: 1})', 'db.paid_orders.find().sort({$natural: 1}).toArray().length'), ('renameCollection', 'db.paid_orders.renameCollection("x")')]:
    msh(n, f'try {{ ({js}) }} catch (e) {{ e.message.slice(0, 150) }}', label=js)
print('== 五:视图套视图的层数上限')
db.create_collection('lv0')
msh(n, 'db.adminCommand({getParameter: 1, internalMaxViewDepth: 1})') if False else None
depth = 0
try:
    for i in range(1, 30):
        db.command('create', f'lv{i}', viewOn=f'lv{i-1}', pipeline=[]); depth = i
except Exception as e: err = str(e)[:140]
print(f'  连续把 lv(i-1) 作为 lv(i) 的 viewOn 创建视图:成功到 lv{depth},下一个报错: {err}')
print('== 六:删掉底层集合之后视图还在,但查询返回空;collMod 可以改视图的 pipeline')
db.orders.drop()
msh(n, 'db.paid_orders.find().toArray().length')
msh(n, 'db.getCollectionInfos({name: "paid_orders"})[0].options.viewOn')
db.create_collection('src2'); db.src2.insert_many([{'_id': i, 'k': i} for i in range(10)])
db.command('create', 'v2', viewOn='src2', pipeline=[{'$match': {'k': {'$lt': 3}}}])
msh(n, 'db.v2.countDocuments({})')
msh(n, 'db.runCommand({collMod: "v2", viewOn: "src2", pipeline: [{$match: {k: {$gte: 3}}}]})')
msh(n, 'db.v2.countDocuments({})')
n.stop()
