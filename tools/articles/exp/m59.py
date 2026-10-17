import sys, os, threading, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import ReadPreference, monitoring
from pymongo.read_preferences import Secondary
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
tee('m59'); reset()
rs = ReplSet('m59', 3, args=['--setParameter', 'enableTestCommands=1']).start(); rs.wait_secondaries()
pi = rs.wait_primary(); pri = rs.nodes[pi]; secs = [nd for nd in rs.nodes if nd is not pri]
c = rs.client(); db = c.test; db.t.insert_one({'_id': 0, 'v': 0}); time.sleep(1)
def lags():
    st = c.admin.command('replSetGetStatus'); p = [m for m in st['members'] if m['stateStr'] == 'PRIMARY'][0]['optimeDate']
    return {m['name'].split(':')[1]: (p - m['optimeDate']).total_seconds() for m in st['members'] if m['stateStr'] == 'SECONDARY'}
print('== 一:健康时的复制延迟 = primary 的 optimeDate - secondary 的 optimeDate(replSetGetStatus)。在持续写入下取 10 个样本')
stop = threading.Event()
def writer():
    cc = rs.client().test
    while not stop.is_set(): cc.t.update_one({'_id': 0}, {'$inc': {'v': 1}}); time.sleep(0.05)
wt = threading.Thread(target=writer); wt.start(); time.sleep(1)
samples = [lags() for _ in range(10) if not time.sleep(0.3)]
print(f'  10 个样本中各 secondary 的延迟(秒)范围: ' + ', '.join(f'{k}: {min(s[k] for s in samples):.0f}~{max(s[k] for s in samples):.0f}' for k in samples[0]))
msh(pri, 'var h = db.hello(); ({lastWrite: h.lastWrite.lastWriteDate, majorityWrite: h.lastWrite.majorityWriteDate})', note='hello 里的 lastWrite:客户端据此估计 staleness')
print('== 二:让其中一个 secondary 停止拉取 oplog(failpoint stopReplProducer),primary 继续写入,延迟随时间增长')
lag_sec = secs[0]; ok_sec = secs[1]; lc = MongoClient(lag_sec.uri, directConnection=True)
lc.admin.command('configureFailPoint', 'stopReplProducer', mode='alwaysOn'); t_lag = time.time()
LS, OS = str(lag_sec.port), str(ok_sec.port)
for i in range(4):
    time.sleep(30 if i else 5); l = lags(); print(f'  停止拉取后 {time.time() - t_lag:5.0f} s:延迟 {LS}(被停的) = {l[LS]:.0f} s;{OS}(正常的) = {l[OS]:.0f} s')
print('== 三:从 secondary 读:不设 maxStalenessSeconds 时,请求会分摊到两个 secondary,读到被停的那台就是旧数据;读 50 次,看读到各台的次数以及旧值次数')
class Spy(monitoring.CommandListener):
    def __init__(self): self.hosts = collections.Counter()
    def started(self, e):
        if e.command_name == 'find': self.hosts[str(e.connection_id[1])] += 1
    def succeeded(self, e): pass
    def failed(self, e): pass
spy = Spy()
cur = c.test.t.find_one({'_id': 0})['v']
cs = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=Secondary(), event_listeners=[spy]); stale = 0
for _ in range(50):
    if cs.test.t.find_one({'_id': 0})['v'] < cur - 5: stale += 1
print(f'  50 次 secondary 读:服务端分布 {dict(spy.hosts)};读到明显落后(比 primary 少 5 次以上更新)的值 {stale} 次')
print('== 四:加 maxStalenessSeconds=90(最小值):驱动估算每台 secondary 的 staleness,超过 90 秒的被排除在选择之外')
spy2 = Spy()
cm = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=Secondary(max_staleness=90), event_listeners=[spy2]); stale2 = 0
for _ in range(50):
    if cm.test.t.find_one({'_id': 0})['v'] < cur - 5: stale2 += 1
print(f'  50 次 secondary + maxStalenessSeconds=90 的读:服务端分布 {dict(spy2.hosts)};明显落后的值 {stale2} 次(被停的 {LS} 延迟约 {lags()[LS]:.0f} s,已超过 90 s)')
print('== 五:maxStalenessSeconds 的取值限制:不能小于 90,也不能小于 heartbeat + 10 秒')
for ms_ in (30, 90):
    try:
        cx = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=Secondary(max_staleness=ms_), serverSelectionTimeoutMS=3000); cx.test.t.find_one({'_id': 0}); print(f'  max_staleness={ms_}:读成功')
    except Exception as e: print(f'  max_staleness={ms_}:读失败 {type(e).__name__}: {str(e)[:110]}')
print('== 六:放开 failpoint 后 secondary 追上的速度:延迟从上面的值降到 0 要多久')
lc.admin.command('configureFailPoint', 'stopReplProducer', mode='off'); t0 = time.time()
while time.time() - t0 < 60:
    l = lags()[LS]
    if l < 1: break
    time.sleep(0.5)
print(f'  failpoint 关闭后 {time.time() - t0:.1f} s 延迟降到 {l:.0f} s(积压的 oplog 一口气应用)')
stop.set(); wt.join(); rs.stop()
