import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m51'); reset()
rs = ReplSet('m51', 1).start(); rs.wait_primary()
c = rs.client(); db = c.test
db.create_collection('t'); db.t.insert_one({'_id': 1, 'status': 'new', 'n': 0, 'tags': [1, 2, 3]})
def drain(cs, n, timeout=3):
    out = []; t0 = time.time()
    while len(out) < n and time.time() - t0 < timeout:
        e = cs.try_next()
        if e: out.append(e)
    return out
def short(e):
    d = {k: e[k] for k in ('operationType', 'documentKey', 'updateDescription', 'fullDocument', 'fullDocumentBeforeChange') if k in e}
    return jpp({k: (v if k != 'documentKey' else v) for k, v in d.items()})
print('== 一:默认情况下各种事件带什么:insert 带完整文档;update 只带 updateDescription(改了哪些字段),没有 fullDocument;replace 带新文档;delete 只有 documentKey')
cs = db.t.watch()
db.t.insert_one({'_id': 2, 'status': 'new', 'n': 0}); db.t.update_one({'_id': 2}, {'$set': {'status': 'paid'}, '$unset': {'n': ''}}); db.t.replace_one({'_id': 2}, {'status': 'replaced'}); db.t.delete_one({'_id': 2})
for e in drain(cs, 4): print('  ' + short(e).replace('\n', ' ').replace('  ', ' '))
cs.close()
print('== 二:fullDocument: "updateLookup":update 事件里附带“查询那一刻”的当前文档——不是这次修改刚完成时的样子。连续改两次,消费者晚一点读取')
cs = db.t.watch(full_document='updateLookup')
db.t.update_one({'_id': 1}, {'$set': {'n': 1}}); db.t.update_one({'_id': 1}, {'$set': {'n': 2}}); time.sleep(0.5)
for e in drain(cs, 2): print(f'  update 事件的 updatedFields={e["updateDescription"]["updatedFields"]};updateLookup 取回的 fullDocument.n = {e["fullDocument"]["n"]}')
print('  (两个事件的 fullDocument.n 都是 2:第一个事件对应的 n=1 那个中间状态丢了)')
cs.close()
print('== 三:要精确的前后镜像,需要在集合上打开 changeStreamPreAndPostImages,然后用 fullDocument="required"、fullDocumentBeforeChange="required"')
db.command('collMod', 't', changeStreamPreAndPostImages={'enabled': True})
cs = db.t.watch(full_document='required', full_document_before_change='required')
db.t.update_one({'_id': 1}, {'$set': {'n': 10}}); db.t.update_one({'_id': 1}, {'$set': {'n': 20}}); time.sleep(0.5)
for e in drain(cs, 2): print(f'  update 事件:前镜像 n = {e["fullDocumentBeforeChange"]["n"]},后镜像 n = {e["fullDocument"]["n"]}  (updatedFields={e["updateDescription"]["updatedFields"]})')
db.t.delete_one({'_id': 1}); d = drain(cs, 1)[0]
print(f'  delete 事件:operationType={d["operationType"]},documentKey={d["documentKey"]};fullDocumentBeforeChange = {d["fullDocumentBeforeChange"]}(删除前的完整文档)')
cs.close()
print('== 四:在 watch 的 pipeline 里过滤:服务端只把匹配的事件发给客户端。10 次写入里只想要 status 变成 paid 的更新')
db.o.insert_many([{'_id': i, 'status': 'new'} for i in range(10)])
pipe = [{'$match': {'operationType': 'update', 'updateDescription.updatedFields.status': 'paid'}}]
cs = db.o.watch(pipe); cs_all = db.o.watch()
for i in range(10): db.o.update_one({'_id': i}, {'$set': {'status': 'paid' if i % 3 == 0 else 'shipped'}})
got = drain(cs, 10, timeout=2); got_all = drain(cs_all, 10, timeout=2)
print(f'  不带过滤的 stream 收到 {len(got_all)} 个事件;带 $match 的 stream 收到 {len(got)} 个,documentKey: {[e["documentKey"]["_id"] for e in got]}(i % 3 == 0 的 4 个)')
cs.close(); cs_all.close()
print('== 五:insert 事件自带 fullDocument,可以直接 $match;$project 能裁剪字段,但不能去掉 _id(那是 resume token)')
cs = db.o.watch([{'$match': {'operationType': 'insert', 'fullDocument.kind': 'vip'}}, {'$project': {'fullDocument.kind': 1, 'fullDocument.name': 1, 'operationType': 1}}])
db.o.insert_many([{'_id': 100, 'kind': 'vip', 'name': 'a', 'big': 'x' * 1000}, {'_id': 101, 'kind': 'normal', 'name': 'b'}, {'_id': 102, 'kind': 'vip', 'name': 'c', 'big': 'y' * 1000}])
got = drain(cs, 3, timeout=2)
print(f'  收到 {len(got)} 个事件(只有 vip 的):{[ {k: v for k, v in e.items() if k != "_id"} for e in got]}')
cs.close()
cs = db.o.watch([{'$project': {'_id': 0}}])
db.o.insert_one({'_id': 103, 'kind': 'x'})
try: drain(cs, 1); print('  去掉 _id 的 $project:成功?')
except Exception as e: print(f'  去掉 _id 的 $project:{type(e).__name__}: {str(e)[:130]}')
print('== 六:drop 与 invalidate:删集合时 stream 收到 drop 然后 invalidate,stream 关闭;要继续得用 startAfter')
cs = db.t2.watch() if False else None
db.create_collection('t6'); cs = db.t6.watch(); tok_alive = None
db.t6.insert_one({'_id': 1}); e1 = drain(cs, 1)[0]; db.t6.drop()
evs = drain(cs, 2, timeout=2); print(f'  drop 之后收到: {[e["operationType"] for e in evs]};stream.alive = {cs.alive}')
rs.stop()
