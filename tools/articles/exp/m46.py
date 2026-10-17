import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.write_concern import WriteConcern
from pymongo.errors import WriteConcernError, DuplicateKeyError
tee('m46'); reset()
rs = ReplSet('m46', 3).start(); st = rs.wait_secondaries()
c = rs.client(); db = c.test
print('== 一:三节点副本集:一个 primary、两个 secondary')
print('  成员状态:' + ', '.join(f'{m["name"].split(":")[1]}={m["stateStr"]}' for m in st['members']))
msh(rs.primary(), 'db.adminCommand({getDefaultRWConcern: 1}).defaultWriteConcern', note='集群的默认写关注(没有显式设置时)')
msh(rs.primary(), 'var h = db.hello(); ({setName: h.setName, isWritablePrimary: h.isWritablePrimary, members: h.hosts.length, majority: Math.floor(h.hosts.length / 2) + 1})')
def lat(wc, n=300, coll='t'):
    col = db.get_collection(coll, write_concern=wc); ts = []
    for i in range(n):
        t0 = time.perf_counter(); col.insert_one({'i': i, 'pad': 'x' * 100}); ts.append((time.perf_counter() - t0) * 1000)
    ts.sort(); return median(ts), ts[int(len(ts) * .99)]
print('== 二:单条 insert_one 的延迟(各 300 次):w:0 不等确认,w:1 等 primary 写入,j:true 等 primary 的 journal 落盘,w:2 / w:majority / w:3 等副本复制')
print(f'  {"写关注":<26}{"中位数":>10}{"p99":>10}')
res = {}
for nm, wc in [('w:0', WriteConcern(w=0)), ('w:1', WriteConcern(w=1)), ('w:1, j:true', WriteConcern(w=1, j=True)), ('w:2', WriteConcern(w=2)), ('w:majority', WriteConcern(w='majority')), ('w:3', WriteConcern(w=3)), ('w:majority, j:true', WriteConcern(w='majority', j=True))]:
    m, p = lat(wc); res[nm] = (m, p); print(f'  {nm:<26}{fm(m):>10}{fm(p):>10}')
print('== 三:关掉一个 secondary(kill -9):w:majority 仍然能满足(2/3),w:3 要等不存在的第三个确认,到 wtimeout 才返回错误')
rs.nodes[2].stop(kill=True); time.sleep(2)
col = db.get_collection('t3', write_concern=WriteConcern(w='majority', wtimeout=2000)); t0 = time.perf_counter(); col.insert_one({'k': 'maj'}); print(f'  w:majority(只剩 2 个节点在线):成功,耗时 {(time.perf_counter() - t0) * 1000:.1f} ms')
col = db.get_collection('t3', write_concern=WriteConcern(w=3, wtimeout=1000)); t0 = time.perf_counter()
try: col.insert_one({'k': 'w3'}); print('  w:3 成功?')
except WriteConcernError as e: print(f'  w:3 wtimeout=1000:{(time.perf_counter() - t0) * 1000:.0f} ms 后返回 WriteConcernError code={e.code}: {str(e.details.get("errmsg"))[:90]}')
print(f'  但 w:3 那条文档已经写进了 primary:count({{k: "w3"}}) = {db.t3.with_options(read_preference=__import__("pymongo").ReadPreference.PRIMARY).count_documents({"k": "w3"})}')
print('== 四:再关掉另一个 secondary,只剩 primary:primary 会因为看不到多数而降级为 secondary;w:majority 的写入还写得进去吗?')
rs.nodes[1].stop(kill=True); time.sleep(12)
pr_ = [i for i, nd in enumerate(rs.nodes) if nd.p.poll() is None]
cc = rs.nodes[pr_[0]].client(); h = cc.admin.command('hello')
print(f'  只剩 1 个节点在线:isWritablePrimary = {h["isWritablePrimary"]},secondary = {h.get("secondary")}')
try: cc.test.t3.insert_one({'k': 'alone'}); print('  insert 成功?')
except Exception as e: print(f'  向它写入:{type(e).__name__}: {str(e)[:90]}')
for i in (1, 2): rs.nodes[i].start()
rs.wait_primary(60); rs.wait_secondaries(60); time.sleep(1)
c = rs.client(); db = c.test
print('== 五:w:0(不确认):错误不会告诉你')
col0 = db.get_collection('t5', write_concern=WriteConcern(w=0)); col0.insert_one({'_id': 1})
try: col0.insert_one({'_id': 1}); print('  w:0 重复插入 _id:1:没有抛异常(服务端没把错误告诉客户端)')
except DuplicateKeyError as e: print('  w:0 抛了异常')
try: db.t5.insert_one({'_id': 1}); print('  w:1 重复插入?')
except DuplicateKeyError as e: print('  w:1 重复插入 _id:1:DuplicateKeyError')
print(f'  t5 里实际文档数 {db.t5.count_documents({})}')
print('== 六:写关注可以放在连接串上、集合上、单次操作上;优先级:单次操作 > 集合 / 数据库 > 连接串 > 集群默认')
c2 = MongoClient(rs.uri(), replicaSet=rs.rs, w=2); print(f'  连接串 w=2:client.write_concern = {c2.write_concern.document}')
print(f'  集合上 with_options(write_concern=WriteConcern(w=1)):{c2.test.t.with_options(write_concern=WriteConcern(w=1)).write_concern.document}')
msh(rs.primary(), 'db.t.insertOne({x: 1}, {writeConcern: {w: "majority", wtimeout: 5000}}).acknowledged', note='mongosh:单次操作指定')
rs.stop()
