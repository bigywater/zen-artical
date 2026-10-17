import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m49'); reset()
rs = ReplSet('m49', 1).start(); rs.wait_primary()
c = rs.client(); db = c.test; ol = c.local['oplog.rs']
db.a.insert_many([{'_id': 1, 'v': 1}, {'_id': 2, 'v': 2}, {'_id': 3, 'v': 3}])
def last_ts(): return ol.find_one(sort=[('$natural', -1)])['ts']
def brief(e):
    keys = {k: v for k, v in e.items() if k in ('op', 'ns', 'o', 'o2', 'lsid', 'txnNumber', 'prevOpTime', 'multiOpType', 'stmtId', 'prevWriteOpTimeInTransaction', 'ts')}
    return keys
print('== 一:一个事务里做 3 个操作(insert、update、delete),提交后看 oplog 里新增的条目:只有 1 条,是一个 applyOps 命令,3 个操作都装在里面')
t0 = last_ts()
with c.start_session() as s:
    with s.start_transaction():
        db.a.insert_one({'_id': 10, 'v': 10}, session=s); db.a.update_one({'_id': 1}, {'$set': {'v': 100}}, session=s); db.a.delete_one({'_id': 2}, session=s)
ents = list(ol.find({'ts': {'$gt': t0}}).sort('$natural', 1))
print(f'  新增了 {len(ents)} 条 oplog 条目')
e = ents[0]; print(f'  条目的顶层字段: {sorted(k for k in e)}')
print(f'  op={e["op"]!r} ns={e["ns"]!r};o 里的键 {sorted(e["o"])};applyOps 里有 {len(e["o"]["applyOps"])} 个操作:')
for o in e['o']['applyOps']: print(f'    op={o["op"]} ns={o["ns"]}  o={o["o"]}  o2={o.get("o2")}')
print(f'  lsid 的键 {sorted(e["lsid"])};txnNumber = {e["txnNumber"]};prevOpTime.ts = {e["prevOpTime"]["ts"]}(事务的第一条,没有前驱)')
print('== 二:对照:同样的 3 个操作不放进事务(用 retryWrites=False 的客户端),每个操作各自一条 oplog,没有 lsid / txnNumber')
c2 = MongoClient(rs.uri(), replicaSet=rs.rs, retryWrites=False); d2 = c2.test
t0 = last_ts()
d2.a.insert_one({'_id': 20, 'v': 20}); d2.a.update_one({'_id': 3}, {'$set': {'v': 300}}); d2.a.delete_one({'_id': 10})
ents2 = list(ol.find({'ts': {'$gt': t0}}).sort('$natural', 1))
print(f'  新增了 {len(ents2)} 条:')
for e2 in ents2: print(f'    op={e2["op"]} ns={e2["ns"]}  o={e2["o"] if len(str(e2["o"])) < 80 else str(e2["o"])[:70]}  o2={e2.get("o2")}  lsid={"有" if "lsid" in e2 else "无"}')
print('== 三:oplog 里的 update 不再存整个新文档,存的是“diff”:事务里的 $set 在 applyOps 里长什么样(与 $set 一篇呼应)')
for o in ents[0]['o']['applyOps']:
    if o['op'] == 'u': print(f'    update 的 o = {o["o"]}')
print('== 四:提交的标记在哪里:config.transactions 里这个会话的记录(lastWriteOpTime 指向上面那一条 applyOps)')
rec = c.config.transactions.find_one({'_id': ents[0]['lsid']})
print(f'  config.transactions 记录: ' + str({k: v for k, v in rec.items() if k != "_id"}))
print(f'  与 applyOps 条目的 ts 相同: {rec["lastWriteOpTime"]["ts"] == ents[0]["ts"]}')
print('== 五:中止的事务:不在 oplog 里留下任何与业务相关的条目')
t0 = last_ts()
with c.start_session() as s:
    s.start_transaction(); db.a.insert_one({'_id': 30}, session=s); db.a.update_one({'_id': 1}, {'$inc': {'v': 1}}, session=s); s.abort_transaction()
n_new = ol.count_documents({'ts': {'$gt': t0}, 'ns': {'$ne': 'config.system.sessions'}})
print(f'  insert + update 之后 abortTransaction:oplog 里新增了 {n_new} 条;文档 _id 30 存在: {db.a.count_documents({"_id": 30}) > 0}')
print('== 六:大事务会拆成多条 applyOps(每条有大小上限):事务里插入 20 个 1 MiB 的文档')
t0 = last_ts()
with c.start_session() as s:
    with s.start_transaction():
        for i in range(20): db.big.insert_one({'_id': i, 'p': 'z' * (1024 * 1024)}, session=s)
ents3 = list(ol.find({'ts': {'$gt': t0}, 'o.applyOps': {'$exists': True}}).sort('$natural', 1))
print(f'  oplog 里新增 {len(ents3)} 条 applyOps 条目:')
for i, e3 in enumerate(ents3): print(f'    条目 {i + 1}: applyOps 里 {len(e3["o"]["applyOps"])} 个操作;partialTxn={e3["o"].get("partialTxn")};count={e3["o"].get("count")};prevOpTime.ts={"(0,0)" if e3["prevOpTime"]["ts"].time == 0 else e3["prevOpTime"]["ts"]}')
rs.stop()
