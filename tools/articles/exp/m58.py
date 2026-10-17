import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m58'); reset()
rs = ReplSet('m58', 1, oplog=512).start(); rs.wait_primary()
c = rs.client(); db = c.test
N = 600000
fill(db.big, N, lambda i: {'_id': i, 'k': i % 1000, 'pad': 'x' * 180}, batch=30000)
db.big.create_index('k'); db.small.insert_many([{'_id': i} for i in range(1000)])
st = db.command('collStats', 'big'); print(f'== 一:primary 上先放 {N:,} 个文档(dataSize {st["size"] / 1048576:.0f} MB,2 个索引),再加一个新成员,每 0.25 秒记录它的状态')
sec = Node('m58/n1', args=['--replSet', rs.rs, '--oplogSize', '512'], cache=0.25, root=mdir('m58/n1')); sec.start()
stop_w = threading.Event(); wcount = [0]
def writer():
    cc = rs.client().test
    while not stop_w.is_set():
        cc.small.update_one({'_id': wcount[0] % 1000}, {'$inc': {'n': 1}}); cc.live.insert_one({'i': wcount[0]}); wcount[0] += 1
        time.sleep(0.002)
wt = threading.Thread(target=writer); wt.start()
cfg = c.admin.command('replSetGetConfig')['config']; cfg['version'] += 1; cfg['members'].append({'_id': 1, 'host': sec.addr, 'priority': 0, 'votes': 0})
t0 = time.time(); c.admin.command('replSetReconfig', cfg)
states = []; snaps = []; sc = MongoClient(sec.uri, directConnection=True)
while time.time() - t0 < 180:
    try:
        rst = c.admin.command('replSetGetStatus'); m = [x for x in rst['members'] if x['_id'] == 1][0]
        s = m['stateStr']
        if not states or states[-1][1] != s: states.append((round(time.time() - t0, 2), s))
        try:
            ist = sc.admin.command('replSetGetStatus').get('initialSyncStatus')
            if ist: snaps.append((round(time.time() - t0, 2), ist))
        except Exception: pass
        if s == 'SECONDARY': break
    except Exception: pass
    time.sleep(0.25)
stop_w.set(); wt.join()
print(f'  成员状态变化(距加入的秒数): {states}')
print(f'  initial sync 总耗时约 {states[-1][0]:.1f} s(数据 {st["size"] / 1048576:.0f} MB);同步期间 primary 上并发写入了 {wcount[0]:,} 轮(每轮一个 $inc 加一个 insert)')
print('== 二:同步过程中,新成员的 replSetGetStatus 里有 initialSyncStatus,其中 approxTotalDataSize / approxTotalBytesCopied 给出进度')
if snaps:
    ist0 = snaps[0][1]; print(f'  initialSyncStatus 的键: {sorted(ist0.keys())}')
    print(f'  method = {ist0.get("method")};maxFailedInitialSyncAttempts = {ist0.get("maxFailedInitialSyncAttempts")};failedInitialSyncAttempts = {ist0.get("failedInitialSyncAttempts")}')
    print(f'  {"距加入":>8}{"已复制":>12}{"总量":>12}{"复制速度":>14}{"已应用的 oplog":>14}')
    for tt, ist in snaps[::max(1, len(snaps) // 6)]: print(f'  {tt:>6.2f} s{ist.get("approxTotalBytesCopied", 0) / 1048576:>9.1f} MB{ist.get("approxTotalDataSize", 0) / 1048576:>9.1f} MB{ist.get("bytesPerSecond", 0) / 1048576:>10.1f} MB/s{ist.get("appliedOps")!s:>10}')
else: print('  没有取到快照')
print('== 三:日志里 initial sync 的几个里程碑(新成员的 mongod 日志)')
lg = sec.logs(r'(?i)initial sync')
seen = []
for j in lg:
    m = j.get('msg', '')
    if m not in seen:
        seen.append(m); print(f'  {j["t"]["$date"][11:23]}  {m[:100]}')
    if len(seen) >= 12: break
print('== 四:同步完成后,primary 与新成员的数据是否一致:文档数与整个集合的哈希(dbHash)')
time.sleep(2)
for nm, cl in (('primary', c), ('新成员', sc)):
    cc = cl.test; dh = cl.test.command('dbHash')
    print(f'  {nm:<6}big={cc.big.count_documents({}):,} small={cc.small.count_documents({})} live={cc.live.count_documents({})}  dbHash(big)={dh["collections"]["big"][:12]}…  dbHash(live)={dh["collections"].get("live", "")[:12]}…')
print('== 五:新成员的 oplog 从同步点开始(比 primary 晚得多):它不能为比这更早的 change stream / secondary 读提供历史')
fp = c.local['oplog.rs'].find_one(sort=[('$natural', 1)])['ts']; fs = sc.local['oplog.rs'].find_one(sort=[('$natural', 1)])['ts']
print(f'  primary oplog 最早 ts = {fp};新成员 oplog 最早 ts = {fs};primary oplog 条目数 {c.local["oplog.rs"].count_documents({}):,},新成员 {sc.local["oplog.rs"].count_documents({}):,}')
print('== 六:initial sync 的耗时随数据量变化:再加一个成员,但这次先把 big 集合删掉,只剩小数据,initial sync 多快?')
db.big.drop(); db.small.drop()
for i in range(3): db['t%d' % i].insert_many([{'_id': j} for j in range(1000)])
sec2 = Node('m58/n2', args=['--replSet', rs.rs, '--oplogSize', '512'], cache=0.25, root=mdir('m58/n2')); sec2.start()
cfg = c.admin.command('replSetGetConfig')['config']; cfg['version'] += 1; cfg['members'].append({'_id': 2, 'host': sec2.addr, 'priority': 0, 'votes': 0})
t1 = time.time(); c.admin.command('replSetReconfig', cfg)
while time.time() - t1 < 60:
    m = [x for x in c.admin.command('replSetGetStatus')['members'] if x['_id'] == 2][0]
    if m['stateStr'] == 'SECONDARY': break
    time.sleep(0.25)
print(f'  数据只剩几千个文档:新成员 {time.time() - t1:.1f} s 就进入 SECONDARY(对比 {st["size"] / 1048576:.0f} MB 时的 {states[-1][0]:.1f} s)')
sec.stop(); sec2.stop(); rs.stop()
