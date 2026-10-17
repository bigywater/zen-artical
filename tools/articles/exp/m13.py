import sys, os, threading, datetime as dt; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m13'); reset()
n = Node('m13'); n.start(); c = n.client(); db = c.test
def ttl():
    m = c.admin.command('serverStatus')['metrics']['ttl']; return m['passes'], m['deletedDocuments']
def now(): return dt.datetime.now(dt.timezone.utc)
print('== 一:TTL 索引(expireAfterSeconds=5):文档 5 秒后“过期”,但什么时候真的被删?每 0.5 秒查一次文档数和后台 TTL 线程的运行次数')
msh(n, 'db.getSiblingDB("admin").runCommand({getParameter: 1, ttlMonitorSleepSecs: 1})')
db.t1.create_index('createdAt', expireAfterSeconds=5)
T0 = time.time(); db.t1.insert_many([{'_id': i, 'createdAt': now()} for i in range(100)])
print(f'  已插入 100 个文档,createdAt = 当前时间;索引 expireAfterSeconds=5')
p0, d0 = ttl(); last = (p0, 100); events = []; passes = []; ppass = p0
while time.time() - T0 < 135:
    k = db.t1.count_documents({}); p, d = ttl(); t = time.time() - T0
    if k != last[1]: events.append((round(t, 1), k))
    if p != ppass: passes.append(round(t, 1)); ppass = p
    last = (p, k)
    if k == 0 and len(passes) >= 2: break
    time.sleep(0.25)
print(f'  文档数变化(距插入的秒数, 剩余): {events}')
print(f'  TTL 线程的运行时刻(距插入的秒数): {passes};相邻两次相隔 {passes[1] - passes[0]:.1f} s')
print(f'  文档在 5 s 时就已过期,实际在 {events[-1][0]} s 才被删——等到了第一次 TTL 线程运行')
print('== 二:哪些文档会被 TTL 删:只有 BSON 日期(或日期数组)。字符串形式的日期、数字、缺失字段都不会过期。把监控间隔调到 1 秒以便观察')
msh(n, 'db.adminCommand({setParameter: 1, ttlMonitorSleepSecs: 1})')
db.t2.create_index('t', expireAfterSeconds=1)
old = now() - dt.timedelta(hours=1)
db.t2.insert_many([{'_id': 'date', 't': old}, {'_id': 'iso字符串', 't': old.isoformat()}, {'_id': '毫秒整数', 't': int(old.timestamp() * 1000)}, {'_id': '缺失'}, {'_id': 'null', 't': None},
                   {'_id': '日期数组(最小的过期)', 't': [old, now() + dt.timedelta(days=1)]}, {'_id': '日期数组(都没过期)', 't': [now() + dt.timedelta(days=1), now() + dt.timedelta(days=2)]}, {'_id': '未来的日期', 't': now() + dt.timedelta(days=1)}])
time.sleep(4)
left = sorted(d['_id'] for d in db.t2.find())
print(f'  一小时前的日期等 4 秒之后,还留下: {left}')
print('== 三:expireAfterSeconds=0 + 未来时间:到了“过期时间”字段本身给出的时刻才删(适合每个文档自己定过期时间)')
db.t3.create_index('expireAt', expireAfterSeconds=0)
T1 = time.time(); db.t3.insert_many([{'_id': i, 'expireAt': now() + dt.timedelta(seconds=3 * (i + 1))} for i in range(3)])
ev = []; last = 3
while time.time() - T1 < 14:
    k = db.t3.count_documents({})
    if k != last: ev.append((round(time.time() - T1, 1), k)); last = k
    time.sleep(0.25)
print(f'  三个文档的过期时间分别是 +3 s、+6 s、+9 s;(距插入的秒数, 剩余数): {ev}')
print('== 四:在线修改 expireAfterSeconds(collMod):先设成 1 小时,再改成 2 秒,已有文档立即按新规则判断')
db.t4.create_index('c', expireAfterSeconds=3600); db.t4.insert_many([{'_id': i, 'c': now() - dt.timedelta(seconds=30)} for i in range(20)])
time.sleep(3); print(f'  expireAfterSeconds=3600 时,3 秒后还有 {db.t4.count_documents({})} 个文档(30 秒前创建的还没到 1 小时)')
r = db.command('collMod', 't4', index={'keyPattern': {'c': 1}, 'expireAfterSeconds': 2}); print(f'  collMod → {{expireAfterSeconds_old: {r.get("expireAfterSeconds_old")}, expireAfterSeconds_new: {r.get("expireAfterSeconds_new")}}}')
time.sleep(3.5); print(f'  改成 2 秒后 3.5 秒:剩 {db.t4.count_documents({})} 个')
msh(n, 'db.t4.getIndexes()')
print('== 五:TTL 线程的统计:serverStatus().metrics.ttl,以及 ttlMonitorSleepSecs 的默认值')
msh(n, 'db.serverStatus().metrics.ttl')
n.restart(); c = n.client(); db = c.test
msh(n, 'db.adminCommand({getParameter: 1, ttlMonitorSleepSecs: 1})', label='db.adminCommand({getParameter: 1, ttlMonitorSleepSecs: 1})    // 重启后')
print('== 六:一次过期很多文档:20 万个文档同时过期,TTL 线程每一轮删多少、总共花多久(监控间隔 1 秒)')
msh(n, 'db.adminCommand({setParameter: 1, ttlMonitorSleepSecs: 1})')
big = [{'_id': i, 'c': now() - dt.timedelta(hours=1), 'pad': 'x' * 100} for i in range(200000)]
db.big.create_index('c', expireAfterSeconds=60); a = ttl(); T2 = time.time(); stop = threading.Event(); samples = []
for i in range(0, 200000, 10000): db.big.insert_many(big[i:i + 10000], ordered=False)
while time.time() - T2 < 120:
    k = db.big.count_documents({}); samples.append((round(time.time() - T2, 1), k)); 
    if k == 0: break
    time.sleep(1)
b = ttl()
print(f'  (距开始插入的秒数, 剩余文档数): {samples[::max(1, len(samples) // 12)] + [samples[-1]]}')
print(f'  TTL 线程运行了 {b[0] - a[0]} 轮,共删除 {b[1] - a[1]:,} 个文档;从插入完成到删完 {samples[-1][0]} 秒')
n.stop()
