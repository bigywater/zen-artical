import sys, os, time, json, re, statistics, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z56'); R = {}
VOLS = {'APFS(本机系统盘的临时目录)': str(ZDATA / 'z56-apfs'), 'HFS+ 磁盘映像(/Volumes/ZKMED,同一块物理盘上的另一个文件系统)': '/Volumes/ZKMED/z56'}
import fcntl
def raw(path, n=500, full=False):
    os.makedirs(path, exist_ok=True); f = os.open(os.path.join(path, 'probe.bin'), os.O_CREAT | os.O_WRONLY); xs = []
    for i in range(n):
        os.write(f, b'x' * 512); t0 = time.perf_counter()
        if full: fcntl.fcntl(f, fcntl.F_FULLFSYNC)
        else: os.fsync(f)
        xs.append((time.perf_counter() - t0) * 1000)
    os.close(f); xs.sort(); return statistics.median(xs), xs[int(n * 0.99)]
print('== 一:裸刷盘延迟(写 512 字节再刷盘,500 次):普通 fsync 与 macOS 的 F_FULLFSYNC(真正要求存储设备落盘)')
R['raw'] = {}
for k, p in VOLS.items():
    shutil.rmtree(p, ignore_errors=True); md, p99 = raw(p); fm, f99 = raw(p, full=True); R['raw'][k] = dict(fsync=(md, p99), full=(fm, f99)); print(f'  {k:<62} os.fsync 中位 {md:.3f} ms(p99 {p99:.3f})| F_FULLFSYNC 中位 {fm:.3f} ms(p99 {f99:.3f})')
print()
print('== 二:同样的磁盘上,ZooKeeper 的事务日志(dataLogDir)放在不同位置时的同步写延迟(每种 500 次,中位数)与服务端 fsync 平均耗时')
R['zk'] = {}
for i, (k, p) in enumerate(VOLS.items()):
    shutil.rmtree(p + '-zk', ignore_errors=True); os.makedirs(p + '-zk', exist_ok=True)
    n = Node(f'z56-{i}', 7300 + i, conf={'dataLogDir': p + '-zk'}).start(); z = client(f'127.0.0.1:{7300 + i}'); xs = []
    for j in range(500): t0 = time.perf_counter(); z.create(f'/s{j}', b'x' * 100); xs.append((time.perf_counter() - t0) * 1000)
    m = kv(n.four('mntr')); R['zk'][k] = dict(p50=statistics.median(xs), fsync=m.get('zk_avg_fsynctime')); print(f'  {k:<62} 同步写 p50 {statistics.median(xs):.2f} ms  fsync 平均 {m.get("zk_avg_fsynctime")} ms'); z.stop(); n.stop()
print()
print('== 三:fsync 是写延迟的下限:把 fsync 去掉(forceSync=no)后的同步写延迟(同一块盘)')
n = Node('z56c', 7302, jvm=['-Dzookeeper.forceSync=no']).start(); z = client('127.0.0.1:7302'); xs = []
for j in range(500): t0 = time.perf_counter(); z.create(f'/s{j}', b'x' * 100); xs.append((time.perf_counter() - t0) * 1000)
print(f'  forceSync=no:同步写 p50 {statistics.median(xs):.2f} ms(几乎不含落盘时间)'); R['nosync'] = statistics.median(xs); z.stop(); n.stop()
print()
print('  没有验证:机械硬盘、网络磁盘、云盘、带电池缓存的 RAID 卡——本机只有一块 SSD;上面只能说明「同步写延迟 ≈ fsync 延迟 + 其它开销(约 0.3 ms)」。')
save('z56', R)
