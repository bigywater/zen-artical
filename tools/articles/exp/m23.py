import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m23'); reset()
n = Node('m23'); n.start(); c = n.client(); db = c.test
def keys(coll, idx): return c.test.command('validate', coll, full=True)['keysPerIndex'][idx]
N = 30000
docs = [{'_id': i, 'status': ['active', 'inactive'][i % 20 == 0], 'email': f'u{i}@x.com' if i % 3 else None, 'deleted_at': None if i % 10 else 1700000000 + i, 'score': i % 100} for i in range(N)]
for d in docs:
    if d['email'] is None and d['_id'] % 2: del d['email']
db.t.insert_many(docs)
print(f'== 一:数据:{N:,} 个文档;email 有三种情况(有值、显式 null、字段缺失),约 2/3 有值;5% 的 status 是 inactive')
msh(n, 'var c = db.t; ({total: c.countDocuments({}), hasEmail: c.countDocuments({email: {$type: "string"}}), nullEmail: c.countDocuments({email: {$type: "null"}}), missing: c.countDocuments({email: {$exists: false}}), inactive: c.countDocuments({status: "inactive"})})')
print('== 二:稀疏索引:只收录“有这个字段”的文档(字段存在,即使值是 null 也收录);缺失的文档不进索引')
db.t.create_index('email', name='email_full'); db.t.create_index('email', name='email_sparse', sparse=True)
print(f'  普通索引条目数 {keys("t", "email_full"):,};稀疏索引条目数 {keys("t", "email_sparse"):,}(= 有值 + 显式 null)')
sz = db.command('collStats', 't')['indexSizes']
c.admin.command('fsync'); time.sleep(1.2); sz = db.command('collStats', 't')['indexSizes']
print(f'  索引大小:普通 {sz["email_full"]:,} 字节,稀疏 {sz["email_sparse"]:,} 字节')
print('== 三:稀疏索引的陷阱:查询需要“缺失”的文档时,优化器不会用它(会漏数据);用 hint 强制则真的漏了')
msh(n, EXJS + 'ex(db.t.find({email: null}).explain("executionStats"))', label='db.t.find({email: null})    // 两个索引都在,优化器怎么选')
msh(n, 'db.t.find({email: null}).hint("email_sparse").toArray().length + " vs 实际 " + db.t.countDocuments({email: null})', label='db.t.find({email: null}).hint("email_sparse") 与实际数量')
msh(n, 'db.t.find({}).sort({email: 1}).hint("email_sparse").toArray().length + " vs 实际 " + db.t.countDocuments({})', label='db.t.find().sort({email: 1}).hint("email_sparse")    // 排序用稀疏索引也会漏')
print('== 四:部分索引:只收录满足 partialFilterExpression 的文档;查询条件必须“蕴含”这个过滤条件才能用它')
db.t.create_index('score', name='score_inactive', partialFilterExpression={'status': 'inactive'})
db.t.create_index('score', name='score_all')
print(f'  部分索引 score_inactive 条目数 {keys("t", "score_inactive"):,}(只有 inactive 的),普通索引 score_all 条目数 {keys("t", "score_all"):,}')
sz = db.command('collStats', 't')['indexSizes']; print(f'  索引大小: score_inactive {sz["score_inactive"]:,} 字节,score_all {sz["score_all"]:,} 字节')
db.t.drop_index('score_all')
msh(n, EXJS + 'ex(db.t.find({status: "inactive", score: 5}).explain("executionStats"))', label='db.t.find({status: "inactive", score: 5})    // 条件蕴含过滤条件')
msh(n, EXJS + 'ex(db.t.find({score: 5}).explain("executionStats"))', label='db.t.find({score: 5})    // 没有 status 条件,部分索引不能用')
msh(n, EXJS + 'ex(db.t.find({status: {$in: ["inactive", "active"]}, score: 5}).explain("executionStats"))', label='db.t.find({status: {$in: [inactive, active]}, score: 5})')
print('== 五:部分索引的常见用法:软删除。只给“未删除”的文档建唯一索引,已删除的可以重复')
db.u.create_index('email', unique=True, partialFilterExpression={'deleted_at': None})
db.u.insert_one({'_id': 1, 'email': 'a@x.com', 'deleted_at': None}); 
msh(n, 'try { db.u.insertOne({_id: 2, email: "a@x.com", deleted_at: null}) } catch (e) { e.message.slice(0, 110) }', label='再插入一个未删除、同 email 的文档')
msh(n, 'db.u.updateOne({_id: 1}, {$set: {deleted_at: 1700000000}}); db.u.insertOne({_id: 3, email: "a@x.com", deleted_at: null}).acknowledged', label='把 _id 1 软删除之后,同 email 的新文档可以插入')
msh(n, 'db.u.insertOne({_id: 4, email: "a@x.com", deleted_at: 1700000001}).acknowledged', label='再插一个同 email 且已删除的文档')
print('== 六:部分索引的限制:partialFilterExpression 里能用的操作符有限;稀疏 + 部分不能同时指定')
for lab_, js in [('$exists: true 过滤', 'db.p1.createIndex({a: 1}, {partialFilterExpression: {a: {$exists: true}}})'), ('$or 过滤', 'db.p2.createIndex({a: 1}, {partialFilterExpression: {$or: [{a: 1}, {b: 2}]}})'), ('$ne 过滤', 'db.p3.createIndex({a: 1}, {partialFilterExpression: {a: {$ne: 1}}})'), ('sparse + partial', 'db.p4.createIndex({a: 1}, {sparse: true, partialFilterExpression: {a: {$gt: 1}}})')]:
    msh(n, f'try {{ {js} }} catch (e) {{ e.message.replace(/ *Error in specification.*? :: caused by :: /, "").slice(0, 150) }}', label=js)
n.stop()
