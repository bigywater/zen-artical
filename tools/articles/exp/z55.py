import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z55'); R = {}
def run(label, jvm, port):
    n = Node(f'z55-{port}', port, jvm=jvm).start(); z = client(f'127.0.0.1:{port}')
    xs = []
    for i in range(500): t0 = time.perf_counter(); z.create(f'/s{i}', b'x' * 100); xs.append((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter(); rs = [z.create_async(f'/a{i}', b'x' * 100) for i in range(20000)]; [r.get() for r in rs]; tp = 20000 / (time.perf_counter() - t0)
    m = kv(n.four('mntr')); warn = [l for l in n.log().splitlines() if 'fsync-ing' in l]
    out = dict(p50=statistics.median(xs), tput=tp, fsync_avg=m.get('zk_avg_fsynctime'), fsync_max=m.get('zk_max_fsynctime'), batch=m.get('zk_avg_sync_processor_batch_size'), warns=len(warn), warn_ex=re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', warn[0])[:120] if warn else None)
    print(f'  {label:<40} 同步写 p50 {out["p50"]:.2f} ms | 异步写 {out["tput"]:7.0f} 次/秒 | fsync 平均 {out["fsync_avg"]} ms / 最大 {out["fsync_max"]} ms | 平均批大小 {out["batch"]} | fsync 警告 {out["warns"]} 条')
    z.stop(); n.stop(); return out
print('== 一:fsync 的代价:默认(每批事务 fsync)vs zookeeper.forceSync=no(只写进操作系统缓存,不强制落盘)')
R['default'] = run('默认(forceSync=yes)', [], 7300)
R['nosync'] = run('-Dzookeeper.forceSync=no', ['-Dzookeeper.forceSync=no'], 7301)
print()
print('== 二:fsync 太慢时的日志警告:把阈值 zookeeper.fsync.warningthresholdms 调到 1 ms')
r = run('-Dzookeeper.fsync.warningthresholdms=1', ['-Dzookeeper.fsync.warningthresholdms=1'], 7302); R['warn'] = r
print('  警告原文示例:', r['warn_ex'])
print()
print('== 三:批量 fsync:异步高并发时,多个事务共用一次 fsync(平均批大小 > 1);串行同步写时每个事务各自一次 fsync')
n = Node('z55c', 7303).start(); z = client('127.0.0.1:7303')
for i in range(300): z.create(f'/s{i}', b'x')
m1 = kv(n.four('mntr')); print('  300 次串行同步写之后:avg_sync_processor_batch_size =', m1.get('zk_avg_sync_processor_batch_size'), ', cnt_fsynctime =', m1.get('zk_cnt_fsynctime'))
rs = [z.create_async(f'/a{i}', b'x') for i in range(20000)]; [r.get() for r in rs]; m2 = kv(n.four('mntr'))
print('  再异步写 20000 次之后:avg_sync_processor_batch_size =', m2.get('zk_avg_sync_processor_batch_size'), ', cnt_fsynctime =', m2.get('zk_cnt_fsynctime'), f'(20000 个事务只多出 {int(m2["zk_cnt_fsynctime"]) - int(m1["zk_cnt_fsynctime"])} 次 fsync)'); R['batch'] = dict(sync_cnt=m1.get('zk_cnt_fsynctime'), async_extra=int(m2['zk_cnt_fsynctime']) - int(m1['zk_cnt_fsynctime']), avg_batch=m2.get('zk_avg_sync_processor_batch_size'))
z.stop(); n.stop(); save('z55', R)
