import sys, os, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import ReadPreference, monitoring
from pymongo.read_preferences import Secondary
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError
tee('m62'); reset()
DELAY = 8
rs = ReplSet('m62', 4, members=[{'priority': 2}, {}, {'hidden': True, 'priority': 0}, {'hidden': True, 'priority': 0, 'secondaryDelaySecs': DELAY}]).start()
rs.wait_secondaries(); pi = rs.wait_primary(); pri = rs.nodes[pi]; time.sleep(2)
P, S_, H, D = rs.nodes
c = rs.client(); db = c.test
print('== 一:四个成员:P(primary,priority 2)、S(普通 secondary)、H(hidden,priority 0)、D(hidden + priority 0 + secondaryDelaySecs=%d)' % DELAY)
st = c.admin.command('replSetGetStatus'); print('  replSetGetStatus 里的全部成员: ' + ', '.join(f'{m["name"].split(":")[1]}={m["stateStr"]}' for m in st['members']))
h = P.client().admin.command('hello'); print(f'  primary 的 hello.hosts(客户端能看到的成员): {sorted(x.split(":")[1] for x in h["hosts"])};hello 里没有的: {sorted(x["name"].split(":")[1] for x in st["members"] if x["name"] not in h["hosts"])}')
cfg = c.admin.command('replSetGetConfig')['config']['members']
print('  配置里的每个成员: ' + '; '.join(f'{m["host"].split(":")[1]}: priority={m["priority"]} votes={m["votes"]} hidden={m.get("hidden", False)} secondaryDelaySecs={m.get("secondaryDelaySecs", 0)}' for m in cfg))
hd = H.client().admin.command('hello'); print(f'  hidden 成员自己的 hello:hidden = {hd.get("hidden")},secondary = {hd.get("secondary")}')
print('== 二:客户端用 secondary 读偏好时永远读不到 hidden 成员:100 次读,看服务端分布')
class Spy(monitoring.CommandListener):
    def __init__(self): self.hosts = collections.Counter()
    def started(self, e):
        if e.command_name == 'find': self.hosts[str(e.connection_id[1])] += 1
    def succeeded(self, e): pass
    def failed(self, e): pass
spy = Spy(); db.t.insert_one({'_id': 0}); time.sleep(DELAY + 2)
cs = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=Secondary(), event_listeners=[spy])
for _ in range(100): cs.test.t.find_one({'_id': 0})
print(f'  100 次 secondary 读的分布: {dict(spy.hosts)}(H={H.port}、D={D.port} 都没有出现;只有 S={S_.port})')
print('== 三:hidden 节点仍然复制数据,可以直连读(备份、报表常用):直连 H 读到最新数据')
db.get_collection('t', write_concern=WriteConcern(w=3)).insert_one({'_id': 1, 'v': 'fresh'})
print(f'  向 primary 写 {{_id: 1}}(w:3)后,直连 H 读: {H.client().test.t.find_one({"_id": 1}, ) is not None}')
print(f'== 四:delayed 成员落后 {DELAY} 秒:写入后每 0.5 秒直连 D 读一次,多久才出现?')
t0 = time.time(); db.get_collection('t', write_concern=WriteConcern(w=1)).insert_one({'_id': 2, 'v': 'x'}); dc = D.client(); sc_ = S_.client(); seen = {}
while time.time() - t0 < DELAY + 8 and len(seen) < 2:
    if 'S' not in seen and sc_.test.t.find_one({'_id': 2}): seen['S'] = time.time() - t0
    if 'D' not in seen and dc.test.t.find_one({'_id': 2}): seen['D'] = time.time() - t0
    time.sleep(0.05)
print(f'  _id=2 在 primary 上写入后,普通 secondary S 上 {seen["S"]:.2f} s 就能读到;延迟成员 D 上 {seen["D"]:.1f} s 才出现(secondaryDelaySecs = {DELAY})')
print('== 五:用 delayed 成员救回误删的数据:在 primary 上 drop 集合;还在延迟窗口里,D 上的数据还在,把它复制回来')
db.precious.insert_many([{'_id': i, 'v': i} for i in range(100)]); time.sleep(DELAY + 3)
db.precious.drop(); print(f'  primary 上 drop 了 precious;primary 上还有 {db.precious.count_documents({})} 个文档')
time.sleep(1); print(f'  S 上 {S_.client().test.precious.count_documents({})} 个;D 上(延迟窗口内){dc.test.precious.count_documents({})} 个')
saved = list(dc.test.precious.find({})); db.precious.insert_many(saved)
print(f'  从 D 读出 {len(saved)} 个文档,写回 primary:primary 上现在有 {db.precious.count_documents({})} 个(数据救回来了)')
print('== 六:delayed 成员有投票权时拖慢 w:majority:停掉 S 之后,多数(4 个投票成员里要 3 个)除了 P 和 H,还要等 D')
S_.stop(kill=True); time.sleep(3)
wm = db.get_collection('t', write_concern=WriteConcern(w='majority', wtimeout=30000)); t0 = time.perf_counter(); wm.insert_one({'_id': 3}); dt = time.perf_counter() - t0
print(f'  停掉 S 后 w:majority 的 insert 耗时 {dt:.1f} s(≈ 延迟 {DELAY} s:要等延迟成员 D 应用这次写入)')
rs.stop()
