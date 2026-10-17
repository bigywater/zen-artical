import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m42'); reset()
n = Node('m42'); n.start(); c = n.client(); db = c.test
def show(js, **kw): return msh(n, js, **kw)
print('== 一:$push 与它的修饰符 $each、$position、$slice、$sort')
show('db.a.insertOne({_id: 1, v: [3, 1]}); db.a.updateOne({_id: 1}, {$push: {v: 2}}); db.a.findOne().v', label='$push: {v: 2}')
show('db.a.updateOne({_id: 1}, {$push: {v: {$each: [9, 8], $position: 0}}}); db.a.findOne().v', label='$push: {v: {$each: [9, 8], $position: 0}}')
show('db.a.updateOne({_id: 1}, {$push: {v: {$each: [7, 6], $sort: -1, $slice: 4}}}); db.a.findOne().v', label='$push: {v: {$each: [7, 6], $sort: -1, $slice: 4}}    // 追加后降序排序,只保留前 4 个')
show('db.a.updateOne({_id: 1}, {$push: {v: {$each: [], $slice: -2}}}); db.a.findOne().v', label='$push: {v: {$each: [], $slice: -2}}    // 只保留最后 2 个')
print('== 二:$addToSet(集合语义,已有就不加)、$pull(按条件删)、$pullAll(按值删)、$pop(删头或尾)')
show('db.b.insertOne({_id: 1, s: ["x", "y"]}); db.b.updateOne({_id: 1}, {$addToSet: {s: "x"}}).modifiedCount + " / " + JSON.stringify(db.b.findOne().s)', label='$addToSet: {s: "x"}    // 已存在')
show('db.b.updateOne({_id: 1}, {$addToSet: {s: {$each: ["y", "z", "w"]}}}); db.b.findOne().s', label='$addToSet: {s: {$each: ["y","z","w"]}}')
show('db.b.insertOne({_id: 2, n: [1, 5, 8, 12, 3]}); db.b.updateOne({_id: 2}, {$pull: {n: {$gt: 7}}}); db.b.findOne({_id: 2}).n', label='$pull: {n: {$gt: 7}}')
show('db.b.updateOne({_id: 2}, {$pullAll: {n: [1, 3]}}); db.b.findOne({_id: 2}).n', label='$pullAll: {n: [1, 3]}')
show('db.b.insertOne({_id: 3, n: [1, 2, 3, 4]}); db.b.updateOne({_id: 3}, {$pop: {n: 1}}); db.b.updateOne({_id: 3}, {$pop: {n: -1}}); db.b.findOne({_id: 3}).n', label='$pop: {n: 1} 然后 $pop: {n: -1}    // 先删最后一个,再删第一个')
print('== 三:位置操作符:$ 只改第一个匹配的元素;$[] 改所有元素;$[<id>] 加 arrayFilters 改满足条件的元素')
show('db.c.insertOne({_id: 1, g: [{k: "a", v: 1}, {k: "b", v: 1}, {k: "a", v: 1}]}); db.c.updateOne({_id: 1, "g.k": "a"}, {$set: {"g.$.v": 99}}); db.c.findOne().g.map(x => x.k + ":" + x.v)', label='{"g.k": "a"} + $set: {"g.$.v": 99}    // 只改第一个 k=a')
show('db.c.updateOne({_id: 1}, {$inc: {"g.$[].v": 10}}); db.c.findOne().g.map(x => x.k + ":" + x.v)', label='$inc: {"g.$[].v": 10}    // 所有元素')
show('db.c.updateOne({_id: 1}, {$set: {"g.$[e].v": 0}}, {arrayFilters: [{"e.k": "a"}]}); db.c.findOne().g.map(x => x.k + ":" + x.v)', label='$set: {"g.$[e].v": 0}, arrayFilters: [{"e.k": "a"}]    // 所有 k=a 的元素')
show('try { db.c.updateOne({_id: 1}, {$set: {"g.$.v": 5}}) } catch (e) { e.message }', label='$ 但查询条件里没有数组字段')
print('== 四:出错的情形:对不是数组的字段做 $push;字段不存在时 $push 会创建数组;$pull 一个不存在的值不报错')
show('db.d.insertOne({_id: 1, s: "text"}); try { db.d.updateOne({_id: 1}, {$push: {s: 1}}) } catch (e) { e.message }', label='$push 到字符串字段')
show('db.d.insertOne({_id: 2}); db.d.updateOne({_id: 2}, {$push: {s: 1}}); db.d.findOne({_id: 2}).s', label='$push 到缺失的字段')
show('db.d.updateOne({_id: 2}, {$pull: {s: 999}}).modifiedCount', label='$pull 不存在的值')
print('== 五:$addToSet 比较子文档要求字段顺序一致(与 BSON 字段顺序一篇呼应)')
show('db.e.insertOne({_id: 1, s: [{a: 1, b: 2}]}); db.e.updateOne({_id: 1}, {$addToSet: {s: {b: 2, a: 1}}}); db.e.findOne().s.length + " 个元素"', label='$addToSet: {s: {b: 2, a: 1}}    // 内容相同,字段顺序不同')
show('db.e.updateOne({_id: 1}, {$addToSet: {s: {a: 1, b: 2}}}); db.e.findOne().s.length + " 个元素"', label='$addToSet: {s: {a: 1, b: 2}}    // 顺序相同')
print('== 六:原子性:8 个线程各向同一个文档的数组 $push 100 次——一个都不会丢;对照“先读出来、改了再写回去”的做法')
db.f.insert_many([{'_id': 'atomic', 'v': []}, {'_id': 'rmw', 'v': []}])
def push_atomic():
    cc = n.client().test.f
    for i in range(100): cc.update_one({'_id': 'atomic'}, {'$push': {'v': i}})
def push_rmw():
    cc = n.client().test.f
    for i in range(100):
        d = cc.find_one({'_id': 'rmw'}); v = d['v'] + [i]; cc.update_one({'_id': 'rmw'}, {'$set': {'v': v}})
for fn in (push_atomic, push_rmw):
    ths = [threading.Thread(target=fn) for _ in range(8)]; [t.start() for t in ths]; [t.join() for t in ths]
print(f'  原子的 $push:数组长度 {len(db.f.find_one({"_id": "atomic"})["v"])}(应为 800)')
print(f'  读-改-写:数组长度 {len(db.f.find_one({"_id": "rmw"})["v"])}(应为 800,丢掉的是并发时被覆盖的)')
n.stop()
