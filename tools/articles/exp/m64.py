import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m64'); reset()
rs = ReplSet('m64', 3, oplog=128).start(); rs.wait_secondaries(); pi = rs.wait_primary(); pri = rs.nodes[pi]; sec = [nd for nd in rs.nodes if nd is not pri][0]
c = rs.client(); db = c.test; pc = pri.client(); ol = pc.local['oplog.rs']
def osz(): return pc.local.command('collStats', 'oplog.rs')
print('== 一:oplog 窗口 = oplog 里最早一条与最晚一条的时间差;db.getReplicationInfo() 一次给出这些数')
db.t.insert_many([{'_id': i, 'p': 'x' * 1000} for i in range(2000)]); time.sleep(1)
msh(pri, 'var r = db.getReplicationInfo(); ({logSizeMB: r.logSizeMB, usedMB: r.usedMB, timeDiff: r.timeDiff, timeDiffHours: r.timeDiffHours, tFirst: r.tFirst, tLast: r.tLast})')
print('== 二:不同写入的 oplog 条目大小:同样“改一个字段”,用 $set、整个替换、插入、删除各写 200 次,看 oplog 增长的字节数 / 条目')
def per_op(label, fn, n=200):
    s0 = osz(); c0 = s0['count']; b0 = s0['size']
    for i in range(n): fn(i)
    s1 = osz(); avg = (s1["size"] - b0) / max(1, s1["count"] - c0); print(f'  {label:<34}oplog 新增 {s1["count"] - c0:>4} 条,共 {s1["size"] - b0:>9,} 字节,平均每条 {avg:>8.0f} 字节'); return avg
db.u.insert_many([{'_id': i, 'n': 0, 'p': 'x' * 1000} for i in range(200)])
c2 = MongoClient(rs.uri(), replicaSet=rs.rs, retryWrites=False); d2 = c2.test
B = {}
B['upd'] = per_op('update_one $inc 一个字段', lambda i: d2.u.update_one({'_id': i}, {'$inc': {'n': 1}}))
per_op('replace_one 整个文档(1 KB)', lambda i: d2.u.replace_one({'_id': i}, {'n': 9, 'p': 'y' * 1000}))
B['ins1'] = per_op('insert_one 1 KB 文档', lambda i: d2.v.insert_one({'_id': i, 'p': 'z' * 1000}))
B['ins10'] = per_op('insert_one 10 KB 文档', lambda i: d2.w.insert_one({'_id': i, 'p': 'z' * 10000}))
per_op('delete_one', lambda i: d2.v.delete_one({'_id': i}))
print('== 三:按这个速度,多大的 oplog 能撑多久?用上面实测的字节数 / 条,假设一个持续 1,000 次 / 秒的写入负载')
for label, bpo in [('小更新($inc)', B['upd']), ('1 KB 文档插入', B['ins1']), ('10 KB 文档插入', B['ins10'])]:
    rate = bpo * 1000
    print(f'  {label:<14}平均 {bpo:>6.0f} 字节 / 条 × 1000 条 / 秒 = {rate / 1048576:>6.1f} MB / 秒:128 MB 的 oplog 撑 {128 * 1048576 / rate:>7.0f} 秒,1 GB 撑 {1024 * 1048576 / rate:>7.0f} 秒,10 GB 撑 {10240 * 1048576 / rate / 3600:>6.1f} 小时')
print('== 四:oplog 的 size(逻辑大小)与 storageSize(磁盘上压缩后的大小):可压缩的数据在磁盘上小得多')
s = osz(); print(f'  collStats: size = {s["size"] / 1048576:.1f} MB,storageSize = {s["storageSize"] / 1048576:.1f} MB,maxSize = {s["maxSize"] / 1048576:.0f} MB,count = {s["count"]:,}')
print('== 五:在线调整 oplog 大小:replSetResizeOplog,最小 990 MB')
for sz in (100, 990):
    try: r = pc.admin.command('replSetResizeOplog', 1, size=sz); print(f'  replSetResizeOplog size={sz} MB → ok={r["ok"]};maxSize 现在 {osz()["maxSize"] / 1048576:.0f} MB')
    except Exception as e: print(f'  replSetResizeOplog size={sz} MB → 失败 {type(e).__name__}: {str(e)[:100]}')
print('== 六:secondary 短暂离线:停 15 秒期间 primary 持续写入(1 KB 的文档),重启后它靠 oplog 追上——需要的 oplog 量就是离线期间产生的量')
stop = threading.Event(); w = [0]
def writer():
    cc = rs.client().test
    while not stop.is_set(): cc.live.insert_one({'p': 'x' * 1000}); w[0] += 1; time.sleep(0.003)
sec.stop(kill=True); s_before = osz()['count']; s_size = osz()['size']; wt = threading.Thread(target=writer); wt.start(); time.sleep(15); stop.set(); wt.join()
new_ops = osz()['count'] - s_before; print(f'  secondary 离线 15 秒:primary 写入 {w[0]:,} 条,oplog 新增 {new_ops:,} 条 / {(osz()['size'] - s_size) / 1048576:.1f} MB')
sec.start(); t0 = time.time()
while time.time() - t0 < 120:
    try:
        m = [x for x in pc.admin.command('replSetGetStatus')['members'] if x['name'].endswith(str(sec.port))][0]
        if m['stateStr'] == 'SECONDARY' and (pc.admin.command('replSetGetStatus')['optimes']['appliedOpTime']['ts'].time - m['optime']['ts'].time) <= 1: break
    except Exception: pass
    time.sleep(0.3)
print(f'  重启后 {time.time() - t0:.1f} s 回到 SECONDARY 并追平;追到之后它的 live 集合 {sec.client().test.live.count_documents({}):,} 条(primary 上 {db.live.count_documents({}):,} 条)')
rs.stop()
