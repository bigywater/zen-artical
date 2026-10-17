import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import InsertOne, UpdateOne, DeleteOne, monitoring
from pymongo.errors import BulkWriteError
tee('m45'); reset()
n = Node('m45'); n.start(); c0 = n.client(); db0 = c0.test
class Counter(monitoring.CommandListener):
    def __init__(self): self.cmds = []
    def started(self, e):
        if e.command_name in ('insert', 'update', 'delete'): self.cmds.append((e.command_name, len(e.command.get(e.command_name + 's', e.command.get('documents', [])))))
    def succeeded(self, e): pass
    def failed(self, e): pass
lst = Counter(); c = MongoClient(n.uri, directConnection=True, event_listeners=[lst]); db = c.test
def docs(): return [{'_id': i, 'v': i} for i in range(10)]
print('== 一:ordered(默认):按顺序执行,遇到第一个错误就停下,后面的不再执行。第 5 个文档的 _id 与第 2 个重复')
d = docs(); d[4] = {'_id': 1, 'v': 'dup'}
try: db.o.insert_many(d)
except BulkWriteError as e:
    det = e.details; print(f'  nInserted = {det["nInserted"]};writeErrors: {[(w["index"], w["code"], w["errmsg"][:60]) for w in det["writeErrors"]]}')
print(f'  集合里的 _id: {sorted(x["_id"] for x in db.o.find())}(第 5 个出错,后面 5 个没插)')
print('== 二:unordered(ordered=False):出错的跳过,其余照常执行;所有错误一起返回')
d = docs(); d[4] = {'_id': 1, 'v': 'dup'}; d[7] = {'_id': 2, 'v': 'dup'}
try: db.u.insert_many([{'_id': i, 'v': i} for i in (1, 2)]); db.u.insert_many(d, ordered=False)
except BulkWriteError as e:
    det = e.details; print(f'  nInserted = {det["nInserted"]};writeErrors 的 index: {[w["index"] for w in det["writeErrors"]]}(全部 {len(det["writeErrors"])} 个错误都返回了)')
print(f'  集合里的 _id: {sorted(x["_id"] for x in db.u.find())}')
print('== 三:有依赖的混合操作必须用 ordered:先 insert 一个文档、再 update 它')
ops = [InsertOne({'_id': 'a', 'n': 1}), UpdateOne({'_id': 'a'}, {'$inc': {'n': 10}})]
r = db.m1.bulk_write(ops, ordered=True); print(f'  ordered   [insert a, update a]:  inserted {r.inserted_count} matched {r.matched_count} modified {r.modified_count};n = {db.m1.find_one({"_id": "a"})["n"]}')
ops_rev = [UpdateOne({'_id': 'b'}, {'$inc': {'n': 10}}), InsertOne({'_id': 'b', 'n': 1})]
r = db.m2.bulk_write(ops_rev, ordered=True); print(f'  ordered   [update b, insert b]:  inserted {r.inserted_count} matched {r.matched_count} modified {r.modified_count};n = {db.m2.find_one({"_id": "b"})["n"]}(update 先执行,什么也没匹配到)')
r = db.m3.bulk_write(ops_rev, ordered=False); print(f'  unordered [update b, insert b]:  inserted {r.inserted_count} matched {r.matched_count} modified {r.modified_count};n = {db.m3.find_one({"_id": "b"})["n"]}(顺序不再保证)')
lst.cmds.clear(); db.m4.bulk_write([UpdateOne({'_id': 'c'}, {'$inc': {'n': 10}}), InsertOne({'_id': 'c', 'n': 1}), DeleteOne({'_id': 'zzz'})], ordered=False)
print(f'  unordered 的 3 个操作实际发出的命令序列: {lst.cmds}(驱动把同类操作分组,插入组排在更新组之前)')
lst.cmds.clear(); db.m5.bulk_write([UpdateOne({'_id': 'c'}, {'$inc': {'n': 10}}), InsertOne({'_id': 'c', 'n': 1}), DeleteOne({'_id': 'zzz'})], ordered=True)
print(f'  ordered   的同样 3 个操作发出的命令序列: {lst.cmds}(按原顺序,每次类型变化就换一条命令)')
print('== 四:批次拆分:一次 bulk 里的操作数超过 maxWriteBatchSize(100,000)就拆成多条命令;ordered 与 unordered 都一样')
big = [{'_id': i, 'v': i} for i in range(250000)]
for lab_, od in (('ordered', True), ('unordered', False)):
    db.big.drop(); lst.cmds.clear(); t0 = time.perf_counter(); db.big.insert_many(big, ordered=od); dt = (time.perf_counter() - t0) * 1000
    print(f'  {lab_:<9}插入 250,000 个文档:{dt:.0f} ms;发出的 insert 命令 {[x[1] for x in lst.cmds]}')
print('== 五:耗时对比(插入 5 万个文档,各 5 次中位数)')
sm = [{'_id': i, 'v': i, 'pad': 'x' * 50} for i in range(50000)]
def ins(od):
    db.t5.drop(); db.t5.insert_many(sm, ordered=od)
a = bench(lambda: ins(True), 5, 1); b = bench(lambda: ins(False), 5, 1)
print(f'  ordered {fm(a)};unordered {fm(b)}(单节点上差别很小)')
print('== 六:BulkWriteError.details 的字段')
d = docs(); d[3] = {'_id': 1, 'v': 'dup'}
try: db.e.insert_many([{'_id': 1}]); db.e.insert_many(d, ordered=False)
except BulkWriteError as e:
    det = e.details; print(f'  details 的键: {sorted(det)}'); w = det['writeErrors'][0]; print(f'  writeErrors[0] 的键: {sorted(w)};code={w["code"]},index={w["index"]},keyValue={w.get("keyValue")}')
n.stop()
