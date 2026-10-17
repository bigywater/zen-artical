import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from pymongo.errors import PyMongoError, WTimeoutError
tee('m61'); reset()
rs = ReplSet('m61', 3, members=[{}, {}, {'arbiterOnly': True}]).start(); rs.wait_primary(); time.sleep(3)
pi = rs.wait_primary(); pri = rs.nodes[pi]; arb = rs.nodes[2]; sec = [nd for i, nd in enumerate(rs.nodes[:2]) if nd is not pri][0]
c = rs.client(); db = c.test
print('== 一:PSA 结构:一个 primary、一个 secondary、一个 arbiter(只投票、不存数据)')
st = c.admin.command('replSetGetStatus'); print('  成员: ' + ', '.join(f'{m["name"].split(":")[1]}={m["stateStr"]}' for m in st['members']))
msh(pri, 'var r = db.adminCommand({getDefaultRWConcern: 1}); ({defaultWriteConcern: r.defaultWriteConcern, defaultWriteConcernSource: r.defaultWriteConcernSource})', note='有 arbiter 时的默认写关注')
ac = MongoClient(arb.uri, directConnection=True); hh = ac.admin.command('hello')
try: ac.test.t.find_one(); rd = '读成功?'
except Exception as e: rd = f'{type(e).__name__}: {str(e)[:80]}'
print(f'  arbiter {arb.port}:hello.arbiterOnly = {hh.get("arbiterOnly")};向它读数据:{rd}(它没有数据)')
print('== 二:三个节点都在时 w:majority 的延迟(各 200 次中位数)')
def lat(wc, n=200):
    col = db.get_collection('t', write_concern=wc); ts = []
    for i in range(n):
        t0 = time.perf_counter(); col.insert_one({'i': i}); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
print(f'  w:1 {fm(lat(WriteConcern(w=1)))};w:majority {fm(lat(WriteConcern(w="majority")))}')
print('== 三:停掉那个 secondary(kill -9):primary + arbiter 仍是多数,primary 保持 primary;w:1 的写入成功,w:majority 却等不到确认(arbiter 不存数据,不能确认写入)')
sec.stop(kill=True); time.sleep(3)
h = pri.client().admin.command('hello'); print(f'  primary 还是 primary: isWritablePrimary = {h["isWritablePrimary"]}')
t0 = time.perf_counter(); db.get_collection('t', write_concern=WriteConcern(w=1)).insert_one({'k': 'w1'}); print(f'  w:1 的 insert:成功,{(time.perf_counter() - t0) * 1000:.1f} ms')
t0 = time.perf_counter(); db.t.insert_one({'k': 'implicit'}); print(f'  不指定写关注(集群默认写关注是 implicit):insert 成功,{(time.perf_counter() - t0) * 1000:.1f} ms——有 arbiter 时隐式默认是 w:1,不是 w:majority')
t0 = time.perf_counter()
try: db.get_collection('t', write_concern=WriteConcern(w='majority', wtimeout=2000)).insert_one({'k': 'wmaj'}); print('  w:majority 成功?')
except PyMongoError as e: print(f'  w:majority(wtimeout=2000):{(time.perf_counter() - t0) * 1000:.0f} ms 后 {type(e).__name__}(code {getattr(e, "code", None)})')
print('== 四:majority 的“提交点”停住了:新写入在 majority 读关注下看不到(提交点只能随多数节点确认前进)')
r_local = db.get_collection('t', read_concern=ReadConcern('local')).find_one({'k': 'w1'}); r_maj = db.get_collection('t', read_concern=ReadConcern('majority')).find_one({'k': 'w1'})
print(f'  刚写入的 {{k: "w1"}}:readConcern local → {r_local is not None};readConcern majority → {r_maj is not None}')
print('== 五:继续写入,applied 位置不断前进,lastCommittedOpTime(多数提交点)却停在原地:差距越拉越大')
def optimes():
    o = pri.client().admin.command('replSetGetStatus')['optimes']; return o['appliedOpTime']['ts'], o['lastCommittedOpTime']['ts']
a0, c0 = optimes()
for i in range(5):
    db.get_collection('t', write_concern=WriteConcern(w=1)).insert_many([{'x': j} for j in range(2000)]); time.sleep(1)
    a, cm = optimes(); print(f'  已多写 {(i + 1) * 2000} 个文档:appliedOpTime.ts = {a.time}.{a.inc};lastCommittedOpTime.ts = {cm.time}.{cm.inc}(提交点相对开始时 {"没动" if cm == c0 else "动了"});落后 {a.time - cm.time} 秒')
print('== 六:把 secondary 开回来,提交点追上;作为对比,PSS(三个数据节点)停掉一个 secondary 后 w:majority 仍然成功')
sec.start(); rs.wait_secondaries(60); time.sleep(2)
a, cm = optimes(); print(f'  secondary 回来后:appliedOpTime.ts = {a.time}.{a.inc};lastCommittedOpTime.ts = {cm.time}.{cm.inc}')
t0 = time.perf_counter(); db.get_collection('t', write_concern=WriteConcern(w='majority', wtimeout=5000)).insert_one({'k': 'after'}); print(f'  w:majority 又能成功了:{(time.perf_counter() - t0) * 1000:.1f} ms')
rs.stop()
rs2 = ReplSet('m61b', 3).start(); rs2.wait_secondaries(); p2 = rs2.nodes[rs2.wait_primary()]; s2 = [nd for nd in rs2.nodes if nd is not p2][0]; s2.stop(kill=True); time.sleep(3)
c2 = rs2.client(); t0 = time.perf_counter(); c2.test.get_collection('t', write_concern=WriteConcern(w='majority', wtimeout=5000)).insert_one({'k': 'pss'})
print(f'  PSS(primary + 2 个 secondary)停掉一个 secondary:w:majority 成功,{(time.perf_counter() - t0) * 1000:.1f} ms')
rs2.stop()
