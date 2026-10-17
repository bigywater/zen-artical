import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import ReadPreference, monitoring
from pymongo.write_concern import WriteConcern
tee('m53'); reset()
rs = ReplSet('m53', 3, args=['--setParameter', 'enableTestCommands=1']).start(); rs.wait_secondaries()
pri = rs.nodes[rs.wait_primary()]; secs = [nd for nd in rs.nodes if nd is not pri]
cp = MongoClient(rs.uri(), replicaSet=rs.rs, w=1)
class Spy(monitoring.CommandListener):
    def __init__(self): self.last = {}
    def started(self, e):
        if e.command_name == 'find': self.last = {'readConcern': e.command.get('readConcern'), 'host': e.connection_id}
    def succeeded(self, e): pass
    def failed(self, e): pass
spy = Spy()
cs = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=ReadPreference.SECONDARY, event_listeners=[spy])
db_p = cp.test; db_s = cs.test
db_p.t.insert_one({'_id': 0, 'i': -1}); time.sleep(1)
print('== 一:写 primary(w:1)后立刻读 secondary,连续 3000 轮:不带会话的读有多少次读到旧数据?因果一致性会话的读呢?')
stale_plain = 0; N = 3000
for i in range(N):
    db_p.t.update_one({'_id': 0}, {'$set': {'i': i}})
    if db_s.t.find_one({'_id': 0})['i'] != i: stale_plain += 1
stale_causal = 0
with cs.start_session(causal_consistency=True) as s:
    for i in range(N, 2 * N):
        r = db_p.t.update_one({'_id': 0}, {'$set': {'i': i}})
        s.advance_operation_time(cp.test.command('ping')['operationTime']) if False else None
        s.advance_cluster_time(db_p.command('ping')['$clusterTime']); s.advance_operation_time(db_p.command('ping')['operationTime'])
        if db_s.t.find_one({'_id': 0}, session=s)['i'] != i: stale_causal += 1
print(f'  不带会话:{stale_plain} / {N} 次读到旧值;因果一致性会话(把写入的 operationTime 传给会话):{stale_causal} / {N} 次')
print('== 二:确定性地制造落后:用 failpoint stopReplProducer 让一个 secondary 停止拉取 oplog,再写 primary')
time.sleep(3)   # 让 secondary 先追上第一节留下的积压
sec0 = secs[0]; sc0 = MongoClient(sec0.uri, directConnection=True, read_preference=ReadPreference.SECONDARY_PREFERRED)
sc0.admin.command('configureFailPoint', 'stopReplProducer', mode='alwaysOn')
db_p.t.update_one({'_id': 0}, {'$set': {'i': 'FRESH'}}); wt = db_p.command('ping')['operationTime']
r_stale = sc0.test.t.find_one({'_id': 0}); print(f'  secondary(已停止拉取)上不带会话的读:i = {r_stale["i"]!r}(旧值)')
res = {}
def release(): time.sleep(2.0); sc0.admin.command('configureFailPoint', 'stopReplProducer', mode='off')
threading.Thread(target=release).start()
with sc0.start_session(causal_consistency=True) as s:
    s.advance_operation_time(wt)
    t0 = time.perf_counter(); r = sc0.test.t.find_one({'_id': 0}, session=s); dt = (time.perf_counter() - t0) * 1000
print(f'  同一个 secondary 上,带因果一致性会话(operationTime={wt})的读:等了 {dt:.0f} ms 后返回 i = {r["i"]!r}(等到 failpoint 关闭、secondary 追上)')
print('== 三:机制:会话的读命令里多了 readConcern.afterClusterTime')
spy.last = {}
with cs.start_session(causal_consistency=True) as s:
    s.advance_operation_time(wt); db_s.t.find_one({'_id': 0}, session=s)
print(f'  带因果会话的 find 命令里的 readConcern: {spy.last.get("readConcern")}')
spy.last = {}; db_s.t.find_one({'_id': 0})
print(f'  不带会话的 find 命令里的 readConcern: {spy.last.get("readConcern")}')
print('== 四:会话怎么知道“要等到哪个时间点”:每次响应里的 operationTime 被会话记下,下一次读带上它;可以手工在客户端之间传递')
with cp.start_session() as s1:
    db_p.t.update_one({'_id': 0}, {'$set': {'i': 'A'}}, session=s1); ot = s1.operation_time; print(f'  写入后 s1.operation_time = {ot}')
with cs.start_session(causal_consistency=True) as s2:
    print(f'  新会话 s2 一开始 operation_time = {s2.operation_time}');
    s2.advance_operation_time(ot); print(f'  把 s1 的 operationTime 传给 s2 之后: {s2.operation_time};读 → {db_s.t.find_one({"_id": 0}, session=s2)["i"]!r}')
print('== 五:因果一致性只保证“同一条因果链”:不同会话没有传递时间戳,就没有保证(这里同样 failpoint 让 secondary 落后)')
sc0.admin.command('configureFailPoint', 'stopReplProducer', mode='alwaysOn')
db_p.t.update_one({'_id': 0}, {'$set': {'i': 'B'}})
with sc0.start_session(causal_consistency=True) as s3:
    r = sc0.test.t.find_one({'_id': 0}, session=s3); print(f'  新会话没有传递 operationTime:读到 i = {r["i"]!r}(旧值;因果一致性会话自己没有写过,也没有被告知要等谁)')
sc0.admin.command('configureFailPoint', 'stopReplProducer', mode='off')
print('== 六:隐含的要求:因果一致性要和 majority 读关注 + majority 写关注配合才保证“写后读 + 单调读”这些全部性质;w:1 时 primary 回滚会撤销写入')
msh(rs.primary(), 'db.runCommand({find: "t", filter: {_id: 0}, readConcern: {level: "local", afterClusterTime: Timestamp(0, 1)}}).ok', note='afterClusterTime 是 readConcern 的一个参数,可以和 local / majority / snapshot 任意搭配')
rs.stop()
