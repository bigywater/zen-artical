import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.errors import DuplicateKeyError, BulkWriteError
tee('m56'); reset()
n = Node('m56'); n.start(); c = n.client(); db = c.test
print('== 一:插入重复的 _id:mongosh 里的 e.message、code、keyPattern、keyValue')
msh(n, 'db.a.insertOne({_id: 1, email: "a@x.com"})')
msh(n, 'try { db.a.insertOne({_id: 1}) } catch (e) { ({name: e.name, code: e.code, message: e.message, keyPattern: e.keyPattern, keyValue: e.keyValue}) }', n=14)
print('  pymongo 里同一个错误:')
try: db.a.insert_one({'_id': 1})
except DuplicateKeyError as e: print(f'  DuplicateKeyError.code = {e.code};str(e) = {str(e)[:110]}…;e.details 的键 = {sorted(e.details)};keyPattern = {e.details.get("keyPattern")};keyValue = {e.details.get("keyValue")}')
print('== 二:二级唯一索引、复合索引、嵌套字段上的 E11000:message 里的 index 名与 dup key 的形状')
db.u.create_index('email', unique=True); db.u.create_index([('org', 1), ('seq', 1)], unique=True, name='org_seq'); db.u.create_index('profile.phone', unique=True)
db.u.insert_one({'_id': 1, 'email': 'a@x.com', 'org': 'o1', 'seq': 1, 'profile': {'phone': '111'}})
for lab_, doc in [('email 重复', {'_id': 2, 'email': 'a@x.com', 'org': 'o2', 'seq': 2, 'profile': {'phone': '222'}}), ('复合 (org, seq) 重复', {'_id': 3, 'email': 'c@x.com', 'org': 'o1', 'seq': 1, 'profile': {'phone': '333'}}), ('嵌套 profile.phone 重复', {'_id': 4, 'email': 'd@x.com', 'org': 'o4', 'seq': 4, 'profile': {'phone': '111'}})]:
    try: db.u.insert_one(doc)
    except DuplicateKeyError as e: m = e.details['errmsg']; print(f'  {lab_:<22}index={m.split("index: ")[1].split(" dup key")[0]:<14} errmsg 的 dup key 部分: {m.split("dup key: ")[1]}  keyPattern={e.details.get("keyPattern")}  keyValue={e.details.get("keyValue")}')
print('== 三:一个文档同时违反两个唯一索引时,一次只会报其中一个;修好这个再试会报另一个')
doc = {'_id': 6, 'email': 'a@x.com', 'org': 'o1', 'seq': 1, 'profile': {'phone': '444'}}
for k in range(2):
    try: db.u.insert_one(doc); print('  成功'); break
    except DuplicateKeyError as e:
        print(f'  第 {k + 1} 次报的是: {e.details["keyPattern"]}'); doc['email'] = 'e@x.com'
print('== 四:很长的字符串键:E11000 里的 dup key 会被截断吗?(5000 个字符的唯一字符串)')
db.big.create_index('s', unique=True); long_s = 'x' * 5000; db.big.insert_one({'s': long_s})
try: db.big.insert_one({'s': long_s})
except DuplicateKeyError as e: print(f'  errmsg 长度 {len(e.details["errmsg"])} 字符;dup key 部分: {e.details["errmsg"].split("dup key: ")[1][:60]}…(共 {len(e.details["errmsg"].split("dup key: ")[1])} 字符);keyValue.s 长度 {len(e.details["keyValue"]["s"])}')
print('== 五:应用里的“插入或取回已存在的”:捕获 E11000,用 keyValue 去查已有的那个文档')
def get_or_create(email):
    try: return 'created', db.u.insert_one({'email': email, 'org': 'oX' + email, 'seq': 1, 'profile': {'phone': 'p' + email}}).inserted_id
    except DuplicateKeyError as e:
        existing = db.u.find_one(e.details['keyValue']); return 'existing', existing['_id']
print('  第一次(新 email):', get_or_create('new@x.com')); print('  第二次(同一个 email):', get_or_create('new@x.com'))
print('== 六:批量与更新里的 E11000:insertMany(unordered)的 writeErrors;update 把唯一字段改成已有的值')
try: db.b.create_index('k', unique=True); db.b.insert_many([{'k': 1}, {'k': 2}]); db.b.insert_many([{'k': 3}, {'k': 1}, {'k': 4}, {'k': 2}], ordered=False)
except BulkWriteError as e: print(f'  writeErrors: {[(w["index"], w["code"], w["keyValue"]) for w in e.details["writeErrors"]]};nInserted={e.details["nInserted"]}')
try: db.b.update_one({'k': 3}, {'$set': {'k': 1}})
except DuplicateKeyError as e: print(f'  update 把 k=3 改成 1:code={e.code},details.errmsg={e.details["errmsg"][:100]}…')
msh(n, 'try { db.b.findOneAndUpdate({k: 3}, {$set: {k: 2}}) } catch (e) { ({code: e.code, keyValue: e.keyValue}) }', note='findOneAndUpdate 同样')
n.stop()
