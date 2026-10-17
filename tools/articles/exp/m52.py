import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.errors import OperationFailure, PyMongoError
tee('m52'); reset()
rs = ReplSet('m52', 3).start(); rs.wait_secondaries()
c = rs.client(); db = c.test
db.t.insert_one({'_id': 1, 'v': 'old'})
def rd(level): return db.get_collection('t', read_concern=ReadConcern(level))
print('== 一:健康的副本集上各读关注读到的都一样;延迟差别也很小(各 500 次读 _id 的中位数)')
for lv in ('local', 'available', 'majority', 'snapshot', 'linearizable'):
    try:
        col = rd(lv); ms_ = []
        for _ in range(500):
            t0 = time.perf_counter(); d = col.find_one({'_id': 1}); ms_.append((time.perf_counter() - t0) * 1000)
        print(f'  {lv:<14}读到 {d["v"]!r};中位数 {median(ms_):.2f} ms,p99 {sorted(ms_)[int(len(ms_) * .99)]:.2f} ms')
    except PyMongoError as e: print(f'  {lv:<14}报错: {type(e).__name__}: {str(e)[:100]}')
print('== 二:构造“已写入 primary、还没被多数确认”的窗口:同时 kill 两个 secondary,在 primary 因看不到多数而降级之前(约 10 秒),用 w:1 写入新值')
pri = rs.nodes[[i for i, nd in enumerate(rs.nodes) if rs.client().admin.command('hello')['primary'] == nd.addr][0]]
sec = [nd for nd in rs.nodes if nd is not pri]
pc = pri.client()
for nd in sec: nd.stop(kill=True)
pdb = pc.test
pdb.get_collection('t', write_concern=WriteConcern(w=1)).update_one({'_id': 1}, {'$set': {'v': 'NEW'}})
print('  已 kill 两个 secondary,并在 primary 上用 w:1 把 v 改成 "NEW"')
for lv in ('local', 'majority'):
    r = pdb.get_collection('t', read_concern=ReadConcern(lv)).find_one({'_id': 1}); print(f'  readConcern {lv:<9}→ v = {r["v"]!r}')
t0 = time.perf_counter()
try: pdb.get_collection('t', read_concern=ReadConcern('linearizable')).find_one({'_id': 1}, max_time_ms=3000); print('  linearizable 成功?')
except PyMongoError as e: print(f'  readConcern linearizable(max_time_ms=3000):{(time.perf_counter() - t0) * 1000:.0f} ms 后 {type(e).__name__}(code {getattr(e, "code", None)}): {str(e)[:90]}')
try:
    pdb.get_collection('t', write_concern=WriteConcern(w='majority', wtimeout=1500)).update_one({'_id': 1}, {'$set': {'x': 1}}); print('  w:majority 写成功?')
except PyMongoError as e: print(f'  同时 w:majority 的写:{type(e).__name__}(code {getattr(e, "code", None)})')
print('== 三:primary 降级后,“NEW” 这次写入还没被多数确认——majority 读看不到它,local 读看得到')
time.sleep(12)
h = pc.admin.command('hello'); print(f'  10 秒后 primary 因看不到多数降级:isWritablePrimary = {h["isWritablePrimary"]}')
sc = MongoClient(pri.uri, directConnection=True, read_preference=__import__('pymongo').ReadPreference.SECONDARY_PREFERRED)
for lv in ('local', 'majority'):
    r = sc.test.get_collection('t', read_concern=ReadConcern(lv)).find_one({'_id': 1}); print(f'  已降级的节点上 readConcern {lv:<9}→ v = {r["v"]!r}')
print('== 四:恢复两个 secondary:集群重新选出 primary 并把 “NEW” 复制出去,这次它被多数确认了,majority 读也看到了')
for nd in sec: nd.start()
rs.wait_primary(60); rs.wait_secondaries(60); time.sleep(2); c = rs.client(); db = c.test
for lv in ('local', 'majority'):
    r = db.get_collection('t', read_concern=ReadConcern(lv)).find_one({'_id': 1}); print(f'  恢复后 readConcern {lv:<9}→ v = {r["v"]!r}')
print('== 五:snapshot 读关注:在事务里默认可用;事务外的 find 指定 snapshot 呢?')
try: print('  事务外 find 带 readConcern snapshot:', db.get_collection('t', read_concern=ReadConcern('snapshot')).find_one({'_id': 1}))
except PyMongoError as e: print(f'  事务外 find 带 readConcern snapshot:{type(e).__name__}: {str(e)[:110]}')
with c.start_session() as s:
    with s.start_transaction(read_concern=ReadConcern('snapshot')): print('  事务内 snapshot 读:', db.t.find_one({'_id': 1}, session=s))
print('== 六:默认读关注:没有显式设置时是 local;集群可以设置默认')
msh(rs.primary(), 'db.adminCommand({getDefaultRWConcern: 1}).defaultReadConcern', note='getDefaultRWConcern')
msh(rs.primary(), 'db.t.find({_id: 1}).readConcern("majority").explain().command.readConcern', note='explain 里的读关注')
rs.stop()
