import sys, os, struct, binascii; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.errors import OperationFailure, PyMongoError
tee('m50'); reset()
rs = ReplSet('m50', 1, oplog=128).start(); rs.wait_primary()
c = rs.client(); db = c.test
db.create_collection('t')
def drain(cs, n, timeout=5):
    out = []; t0 = time.time()
    while len(out) < n and time.time() - t0 < timeout:
        e = cs.try_next()
        if e: out.append(e)
    return out
print('== 一:打开 change stream,插入 3 个文档,每个事件里有什么')
cs = db.t.watch(); db.t.insert_many([{'_id': 1, 'v': 'a'}, {'_id': 2, 'v': 'b'}]); db.t.update_one({'_id': 1}, {'$set': {'v': 'A'}})
evs = drain(cs, 3)
for e in evs: print(f'  {e["operationType"]:<8}ns={e["ns"]}  documentKey={e["documentKey"]}  clusterTime={e["clusterTime"]}  _id._data={e["_id"]["_data"][:28]}…')
print(f'  事件的键: {sorted(evs[0])}')
print('== 二:resume token 的 _data 是一个十六进制串,里面编码了 oplog 位置:第 1 个字节是类型,后 8 字节就是 clusterTime(秒 4 字节 + 序号 4 字节)')
for e in evs[:3]:
    raw = binascii.unhexlify(e['_id']['_data']); t, i = struct.unpack('>II', raw[1:9])
    print(f'  token {e["_id"]["_data"][:40]}…  首字节 0x{raw[0]:02x};后 8 字节解码为 Timestamp({t}, {i});事件的 clusterTime = {e["clusterTime"]};相等: {e["clusterTime"] == Timestamp(t, i)}')
print(f'  token 总长 {len(evs[0]["_id"]["_data"]) // 2} 字节')
print('== 三:resumeAfter:读完前 2 个事件后“崩溃”,用第 2 个事件的 token 重新打开,从第 3 个事件继续,不丢不重')
tok = evs[1]['_id']; cs.close()
cs2 = db.t.watch(resume_after=tok); rest = drain(cs2, 5, timeout=3)
print(f'  从第 2 个事件的 token 继续:收到 {len(rest)} 个事件: ' + ', '.join(f'{e["operationType"]} {e["documentKey"]["_id"]}' for e in rest) + '(正是原来的第 3 个事件)')
db.t.insert_one({'_id': 3}); more = drain(cs2, 1); print(f'  之后新写入也能收到: {[e["operationType"] + " " + str(e["documentKey"]["_id"]) for e in more]}')
cs2.close()
print('== 四:startAtOperationTime:从某个时间点开始,而不是某个 token')
tt = c.admin.command('hello')['operationTime']; time.sleep(0.2)
db.t.insert_one({'_id': 100}); db.t.insert_one({'_id': 101})
cs3 = db.t.watch(start_at_operation_time=tt); got = drain(cs3, 3)
print(f'  从 operationTime={tt}(它是当时最后一次写入的时间)开始,收到: {[e["documentKey"]["_id"] for e in got]}(含该时间点的那次写入 _id=3,以及之后的写入)'); cs3.close()
print('== 五:空闲的 stream 的 resume token 也会前进(postBatchResumeToken):没有匹配事件时,token 跟着 oplog 往前走,所以用它恢复不会回到很久以前')
cs4 = db.t.watch(); tok0 = cs4.resume_token
db.other.insert_many([{'x': i} for i in range(1000)])      # 其它集合的写入,与 db.t 的 stream 无关
for _ in range(5): cs4.try_next()
tok1 = cs4.resume_token
print(f'  token 前: {tok0["_data"][:30] if tok0 else None}…;其它集合写了 1000 条后(本 stream 没有事件): {tok1["_data"][:30]}…;token 前进了: {tok0 != tok1}')
cs4.close()
print('== 六:token 对应的位置不在某个节点的 oplog 窗口里,恢复就失败(ChangeStreamHistoryLost,code 286)。这里用“新加入的成员”来构造:它做完 initial sync 后,oplog 只从同步点开始')
from pymongo import ReadPreference
old_tok = evs[0]['_id']
for i in range(5): db.t.insert_one({'_id': 200 + i})
sec = Node('m50/n1', args=['--replSet', rs.rs, '--oplogSize', '128'], cache=0.25, root=mdir('m50/n1')); sec.start()
cfg = c.admin.command('replSetGetConfig')['config']; cfg['version'] += 1; cfg['members'].append({'_id': 1, 'host': sec.addr, 'priority': 0, 'votes': 0})
c.admin.command('replSetReconfig', cfg)
t0 = time.time()
while time.time() - t0 < 90:
    m = [x for x in c.admin.command('replSetGetStatus')['members'] if x['_id'] == 1][0]
    if m['stateStr'] == 'SECONDARY': break
    time.sleep(1)
sc = MongoClient(sec.uri, directConnection=True)
f_p = c.local['oplog.rs'].find_one(sort=[('$natural', 1)])['ts']; f_s = sc.local['oplog.rs'].find_one(sort=[('$natural', 1)])['ts']
print(f'  新成员状态 {m["stateStr"]}(initial sync 用了 {time.time() - t0:.0f} s)')
print(f'  primary 的 oplog 最早一条 ts = {f_p};新成员的 oplog 最早一条 ts = {f_s}(比 primary 晚);最旧事件 token 的 clusterTime = {evs[0]["clusterTime"]}')
c2 = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=ReadPreference.SECONDARY)
try:
    cs5 = c2.test.t.watch(resume_after=old_tok); print(f'  在新成员上恢复:{cs5.try_next()}')
except OperationFailure as e: print(f'  在新成员(secondary 读偏好)上用旧 token 恢复:code={e.code}({e.details.get("codeName")});{str(e)[:150]}')
cs6 = db.t.watch(resume_after=old_tok); first = cs6.try_next()
print(f'  在 primary 上用同一个旧 token 恢复:成功,收到的第一个事件 {first["operationType"]} {first["documentKey"]}')
sec.stop(); rs.stop()
