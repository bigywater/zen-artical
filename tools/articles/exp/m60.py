import sys, os, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.write_concern import WriteConcern
tee('m60'); reset()
rs = ReplSet('m60', 3, args=['--setParameter', 'enableTestCommands=1']).start(); rs.wait_secondaries()
pi = rs.wait_primary(); old = rs.nodes[pi]; secs = [nd for nd in rs.nodes if nd is not old]
c = rs.client(); db = c.test
wm = db.get_collection('t', write_concern=WriteConcern(w='majority'))
wm.insert_many([{'_id': i, 'src': 'base'} for i in range(10)])
print(f'== 一:基线:3 节点,primary 是 {old.port};写入 10 个文档(w:majority)。然后让两个 secondary 停止拉取 oplog,再在旧 primary 上用 w:1 写 5 个文档')
for nd in secs: nd.client().admin.command('configureFailPoint', 'stopReplProducer', mode='alwaysOn')
oc = old.client(); w1 = oc.test.get_collection('t', write_concern=WriteConcern(w=1))
w1.insert_many([{'_id': 100 + i, 'src': 'old-primary-only'} for i in range(5)]); time.sleep(0.5)
for nd in rs.nodes: print(f'  节点 {nd.port}:{nd.client().test.t.count_documents({})} 个文档,_id>=100 的有 {nd.client().test.t.count_documents({"_id": {"$gte": 100}})} 个')
print('== 二:旧 primary 突然崩溃(kill -9),两个 secondary 选出新 primary(此时放开 failpoint),新 primary 上写入新文档')
old.stop(kill=True)
for nd in secs: nd.client().admin.command('configureFailPoint', 'stopReplProducer', mode='off')
t0 = time.time(); newi = None
while time.time() - t0 < 60:
    for i, nd in enumerate(rs.nodes):
        if nd is old: continue
        try:
            if nd.client(serverSelectionTimeoutMS=300).admin.command('hello')['isWritablePrimary']: newi = i; break
        except Exception: pass
    if newi is not None: break
    time.sleep(0.3)
new = rs.nodes[newi]; print(f'  {time.time() - t0:.1f} s 后选出新 primary {new.port}(原来的 primary 是 {old.port})')
nc = new.client(); nc.test.get_collection('t', write_concern=WriteConcern(w='majority')).insert_many([{'_id': 200 + i, 'src': 'new-primary'} for i in range(3)])
print(f'  新 primary 上写入 3 个文档(_id 200~202,w:majority)后,文档数 {nc.test.t.count_documents({})},_id>=100 的 {sorted(d["_id"] for d in nc.test.t.find({"_id": {"$gte": 100}}))}')
print('== 三:重启旧 primary:它的数据里有新 primary 没有的 5 个文档(_id 100~104)——加入时必须回滚。记录它的状态变化')
t0 = time.time(); old.start(wait=False); states = []
while time.time() - t0 < 90:
    try:
        oc = MongoClient(old.uri, directConnection=True, serverSelectionTimeoutMS=300); s = oc.admin.command('replSetGetStatus')['myState']
        nm = {0: 'STARTUP', 1: 'PRIMARY', 2: 'SECONDARY', 3: 'RECOVERING', 5: 'STARTUP2', 6: 'UNKNOWN', 7: 'ARBITER', 8: 'DOWN', 9: 'ROLLBACK', 10: 'REMOVED'}.get(s, s)
        if not states or states[-1][1] != nm: states.append((round(time.time() - t0, 2), nm))
        if nm == 'SECONDARY': break
    except Exception: pass
    time.sleep(0.1)
print(f'  旧 primary 的状态(距重启秒数): {states}')
time.sleep(2)
print('== 四:旧 primary 日志里的状态转换与回滚记录(重启后)')
tr = [j for j in old.logs(msg='Replica set state transition')]
print('  状态转换(日志时间 → 新状态):' + ';'.join(f'{j["t"]["$date"][11:23]} {j["attr"].get("oldState")}→{j["attr"].get("newState")}' for j in tr[-6:]))
lg = old.logs(r'(?i)rollback')
seen = []
for j in lg:
    m = j.get('msg', '')
    if m not in seen and m not in ('WiredTiger message', 'State transition ops metrics for intent registry', 'State transition ops metrics'): seen.append(m); print(f'  {j["t"]["$date"][11:23]}  {m[:100]}')
    if len(seen) >= 12: break
print('== 五:被回滚的数据没有丢:保存在旧 primary 的 dbpath/rollback/ 目录下的 BSON 文件里')
files = sorted(glob.glob(str(old.db / 'rollback' / '**' / '*.bson'), recursive=True))
print(f'  rollback 目录里的文件: {[os.path.relpath(f, old.db) for f in files]}')
for f in files[:1]:
    docs = list(bson.decode_all(open(f, 'rb').read())); print(f'  {os.path.basename(f)} 里的文档: {docs}')
print('== 六:回滚之后三个节点的数据一致;w:1 写入的 5 个文档永远消失在集合里(只在 rollback 文件里)')
time.sleep(3)
for nd in rs.nodes:
    d = nd.client(); ids = sorted(x['_id'] for x in d.test.t.find({}, {'_id': 1})); print(f'  节点 {nd.port}:{len(ids)} 个文档,_id>=100 的 {[i for i in ids if i >= 100]}')
rs.stop()
