import sys, os, struct, socket, uuid; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from bson.binary import Binary, UuidRepresentation
from pymongo import monitoring
from pymongo.errors import AutoReconnect, NetworkTimeout, OperationFailure, PyMongoError
tee('m55'); reset()
rs = ReplSet('m55', 1, args=['--setParameter', 'enableTestCommands=1']).start(); rs.wait_primary()
pn = rs.nodes[0]; uri = rs.uri()
class Spy(monitoring.CommandListener):
    def __init__(self): self.log = []
    def started(self, e):
        if e.command_name in ('update', 'insert', 'delete'): self.log.append((e.command_name, e.command.get('txnNumber'), 'lsid' in e.command))
    def succeeded(self, e): pass
    def failed(self, e): pass
spy = Spy()
c = MongoClient(uri, replicaSet=rs.rs, event_listeners=[spy], retryWrites=True); db = c.test
db.ctr.insert_one({'_id': 1, 'n': 0})
adm = MongoClient(pn.uri, directConnection=True)
def fail_once(cmds, **kw): adm.admin.command('configureFailPoint', 'failCommand', mode={'times': 1}, data={'failCommands': cmds, **kw})
def fp_off(): adm.admin.command('configureFailPoint', 'failCommand', mode='off')
print('== 一:retryWrites=True(默认):服务端在 update 上先关掉连接(failCommand closeConnection),驱动自动重试一次,计数器只加了 1')
spy.log.clear(); fail_once(['update'], closeConnection=True)
r = db.ctr.update_one({'_id': 1}, {'$inc': {'n': 1}}); fp_off()
print(f'  update_one 的结果:matched {r.matched_count} modified {r.modified_count};n = {db.ctr.find_one({"_id": 1})["n"]};驱动发出的 update 命令(命令名, txnNumber, 带 lsid): {spy.log}')
print('  (两次 update 的 txnNumber 相同——重试带着同一个事务号,服务端据此判断是不是重复请求)')
print('== 二:retryWrites=False:同样的故障直接抛 NetworkError(AutoReconnect)')
c2 = MongoClient(uri, replicaSet=rs.rs, retryWrites=False); fail_once(['update'], closeConnection=True)
try: c2.test.ctr.update_one({'_id': 1}, {'$inc': {'n': 1}}); print('  没有报错?')
except AutoReconnect as e: print(f'  AutoReconnect: {str(e)[:80]}')
fp_off(); print(f'  n = {db.ctr.find_one({"_id": 1})["n"]}(这次故障发生在执行之前,没有加)')
print('== 三:服务端的去重:用手写的 OP_MSG 把同一个 update(同一个 lsid + txnNumber)发两次,再换一个 txnNumber 发一次')
class Raw:
    def __init__(self, port): self.s = socket.create_connection(('127.0.0.1', port)); self.rid = 1
    def cmd(self, doc):
        body = bson.encode(doc); msg = struct.pack('<I', 0) + b'\x00' + body; self.s.sendall(struct.pack('<iiii', 16 + len(msg), self.rid, 0, 2013) + msg); self.rid += 1
        h = b''
        while len(h) < 16: h += self.s.recv(16 - len(h))
        ln = struct.unpack('<i', h[:4])[0]; d = b''
        while len(d) < ln - 16: d += self.s.recv(ln - 16 - len(d))
        return bson.decode(d[5:])
rw = Raw(pn.port); lsid = {'id': Binary(uuid.uuid4().bytes, 4)}
db.ctr.update_one({'_id': 1}, {'$set': {'n': 0}})
def send(txn): return rw.cmd({'update': 'ctr', 'updates': [{'q': {'_id': 1}, 'u': {'$inc': {'n': 1}}}], 'lsid': lsid, 'txnNumber': Int64(txn), '$db': 'test'})
for lab_, txn in [('第 1 次(txnNumber 100)', 100), ('重发同一个请求(txnNumber 100)', 100), ('新请求(txnNumber 101)', 101)]:
    r = send(txn); print(f'  {lab_:<30}→ n={r["n"]} nModified={r["nModified"]} retriedStmtIds={r.get("retriedStmtIds")};库里 n = {db.ctr.find_one({"_id": 1})["n"]}')
print('== 四:去重靠的是 oplog 条目上的 lsid / txnNumber / stmtId:第一次执行产生一条 oplog,重发不产生新条目')
ol = c.local['oplog.rs']
ents = list(ol.find({'ns': 'test.ctr', 'lsid.id': Binary(lsid['id'].__class__(lsid['id']).__bytes__() if False else lsid['id'], 4)}).sort('$natural', 1)) if False else list(ol.find({'ns': 'test.ctr', 'txnNumber': {'$in': [100, 101]}}).sort('$natural', 1))
for e in ents: print(f'  oplog: op={e["op"]} txnNumber={e["txnNumber"]} stmtId={e.get("stmtId")} o2={e.get("o2")} o={e["o"]}')
rec = c.config.transactions.find_one({'_id.id': lsid['id']}); print(f'  config.transactions 里该会话的记录: txnNum={rec["txnNum"]},lastWriteOpTime={rec["lastWriteOpTime"]["ts"]}')
print('== 五:insert_many 的每条语句有 stmtId;整批重发只会插入一次')
lsid2 = {'id': Binary(uuid.uuid4().bytes, 4)}
def send_ins(txn): return rw.cmd({'insert': 'ins', 'documents': [{'_id': i} for i in range(3)], 'ordered': True, 'lsid': lsid2, 'txnNumber': Int64(txn), '$db': 'test'})
r1 = send_ins(1); r2 = send_ins(1)
print(f'  第 1 次:n={r1["n"]};重发:n={r2["n"]} retriedStmtIds={r2.get("retriedStmtIds")};集合里文档数 {db.ins.count_documents({})}(只有 3 个,没有重复键错误)')
print('== 六:哪些写操作可以重试:insert / update(单文档)/ delete(limit 1)/ findAndModify;multi:true 的 update_many、delete_many 不行')
spy.log.clear(); fail_once(['update'], closeConnection=True)
try: db.ctr.update_many({}, {'$inc': {'n': 1}}); print('  update_many 被重试了?')
except AutoReconnect as e: print(f'  update_many 遇到同样的连接断开:不重试,直接抛 AutoReconnect;发出的 update 命令 {spy.log}')
fp_off()
spy.log.clear(); fail_once(['delete'], closeConnection=True)
try: db.ctr.delete_one({'_id': 999}); print(f'  delete_one:被重试后成功;发出的 delete 命令 {spy.log}')
except AutoReconnect: print('  delete_one 没重试')
fp_off()
standalone = Node('m55s'); standalone.start()
try: MongoClient(standalone.uri, directConnection=True, retryWrites=True).test.t.insert_one({'x': 1}); print('  独立实例(非副本集)上 retryWrites=True 的 insert:成功(驱动检测到不支持就自动不用)')
except PyMongoError as e: print(f'  独立实例:{type(e).__name__}: {str(e)[:100]}')
msh(standalone, 'try { db.runCommand({insert: "t", documents: [{x: 2}], lsid: {id: UUID()}, txnNumber: Long(1)}) } catch (e) { e.message }', note='直接带 txnNumber 的命令在独立实例上被拒绝')
standalone.stop(); rs.stop()
