import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import datetime as dt, re as _re
tee('m2'); reset()
n = Node('m2'); n.start(); c = n.client(); db = c.test
VALS = [('MaxKey', bson.max_key.MaxKey()), ('regex', bson.regex.Regex('a', 'i')), ('Timestamp', Timestamp(1, 1)), ('Date', dt.datetime(2026, 1, 1)), ('true', True), ('false', False),
        ('ObjectId', ObjectId('65a000000000000000000001')), ('BinData', b'abc'), ('object {a:1}', {'a': 1}), ('string "b"', 'b'), ('string "a"', 'a'),
        ('number 5', 5), ('number 5.5 (double)', 5.5), ('number -1 (long)', Int64(-1)), ('null', None), ('MinKey', bson.min_key.MinKey())]
random.Random(2).shuffle(VALS)
for i, (nm, v) in enumerate(VALS): db.t.insert_one({'_id': i, 'name': nm, 'v': v})
db.t.insert_one({'_id': 100, 'name': '(字段缺失)'})
print('== 一:同一个字段 v 里放 16 种不同类型的值(再加一个没有 v 的文档),按 v 升序排序,看跨类型的顺序')
msh(n, 'db.t.find({}, {_id: 0, name: 1}).sort({v: 1}).toArray().map(d => d.name)')
print('== 二:比较运算只在同一“类型括号”内匹配:{v: {$gt: 5}} 只返回数字,{v: {$lt: "b"}} 只返回字符串')
msh(n, 'db.t.find({v: {$gt: 5}}, {_id: 0, name: 1}).toArray().map(d => d.name)')
msh(n, 'db.t.find({v: {$lt: "b"}}, {_id: 0, name: 1}).toArray().map(d => d.name)')
msh(n, 'db.t.countDocuments({v: {$gte: MinKey()}}) + " / " + db.t.countDocuments()')
msh(n, 'db.t.countDocuments({v: {$lte: MaxKey()}}) + " / " + db.t.countDocuments()')
print('== 三:null 与字段缺失:升序排序里缺失的字段和 null 并列;{v: null} 两种都匹配,{v: {$exists: false}} 只匹配缺失')
msh(n, 'db.t.find({v: null}, {_id: 0, name: 1}).toArray().map(d => d.name)')
msh(n, 'db.t.find({v: {$exists: false}}, {_id: 0, name: 1}).toArray().map(d => d.name)')
msh(n, 'db.t.find({v: {$type: "null"}}, {_id: 0, name: 1}).toArray().map(d => d.name)')
msh(n, 'db.t.find({v: {$in: [null]}}, {_id: 0, name: 1}).sort({_id: 1}).toArray().map(d => d.name)')
print('== 四:数组参与排序:升序用数组里最小的元素,降序用最大的元素(比较的是元素本身,不是整个数组)')
db.a.insert_many([{'_id': 1, 'v': [5, 1]}, {'_id': 2, 'v': [3]}, {'_id': 3, 'v': [9, 0]}, {'_id': 4, 'v': 2}])
msh(n, 'db.a.find().sort({v: 1}).toArray().map(d => JSON.stringify(d.v))')
msh(n, 'db.a.find().sort({v: -1}).toArray().map(d => JSON.stringify(d.v))')
print('== 五:子文档按“字段类型、字段名、值”逐个字段比较,字段顺序不同就是不同的文档')
db.o.insert_many([{'_id': 1, 'v': {'a': 2}}, {'_id': 2, 'v': {'a': 1, 'b': 1}}, {'_id': 3, 'v': {'b': 1}}, {'_id': 4, 'v': {'a': 1}}, {'_id': 5, 'v': {'b': 1, 'a': 1}}, {'_id': 6, 'v': {}}])
msh(n, 'db.o.find().sort({v: 1}).toArray().map(d => JSON.stringify(d.v))')
print('== 六:$cmp 在聚合里按同一套顺序比较任意两个值')
msh(n, 'db.t.aggregate([{$limit: 1}, {$project: {_id: 0, number_vs_string: {$cmp: [1, "a"]}, string_vs_object: {$cmp: ["a", {}]}, object_vs_array: {$cmp: [{}, []]}, array_vs_bool: {$cmp: [[], true]}, null_vs_number: {$cmp: [null, 0]}, int_vs_double: {$cmp: [NumberInt(1), 1.5]}, long_vs_double: {$cmp: [NumberLong("2"), 1.5]}}}])')
n.stop()
