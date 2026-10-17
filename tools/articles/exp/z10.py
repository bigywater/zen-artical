import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z10'); R = {}
n = Node('z10', 7300, xmx=256, conf={'snapCount': 200000}).start(); z = client('127.0.0.1:7300')
def rss(): return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(n.p.pid)], capture_output=True, text=True).stdout.strip()) / 1024
def jheap():
    subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.run'], capture_output=True); r = subprocess.run(['/usr/bin/jcmd', str(n.p.pid), 'GC.heap_info'], capture_output=True, text=True).stdout
    m = re.search(r'used (\d+)K', r); return int(m.group(1)) / 1024 if m else None
def fmt(): m = kv(n.four('mntr')); return int(m['zk_znode_count']), int(m['zk_approximate_data_size'])
print('== 一:znode 越多,服务端内存越大(每个 znode 数据 200 字节,路径形如 /d/k00001);mntr 的 znode 数 / 近似数据大小,JVM 已用堆(每次先触发一次 GC),进程 RSS')
R['grow'] = []
z.create('/d', b''); done = 0
print(f'  {"znode 数":>9} {"近似数据大小":>12} {"JVM 已用堆":>11} {"进程 RSS":>9}')
for target in (0, 10000, 50000, 100000, 200000):
    while done < target:
        batch = min(5000, target - done); rs = [z.create_async(f'/d/k{done + i:06d}', b'v' * 200) for i in range(batch)]; [r.get() for r in rs]; done += batch
    c, sz = fmt(); h = jheap(); r_ = rss(); R['grow'].append((c, sz, h, r_)); print(f'  {c:>9} {sz / 1048576:>9.1f} MiB {h:>8.1f} MiB {r_:>6.0f} MiB')
print()
print('== 二:读取不走磁盘:先用 srst 清零统计,再读 20000 次随机 znode,看服务端 srvr 的延迟(ms)')
import random
n.four('srst')
for _ in range(20000): z.get(f'/d/k{random.randrange(200000):06d}')
lt = re.search(r'Latency min/avg/max: (\S+)', n.four('srvr')).group(1); print('  srvr 的 Latency min/avg/max(毫秒):', lt); R['lat'] = lt
print()
print('== 三:重启:从快照把整棵树读回内存要多久(200000 个 znode)')
z.stop(); n.stop()
sz = sum(p.stat().st_size for p in (n.dir / 'data' / 'version-2').iterdir() if p.name.startswith('snapshot.')); logsz = sum(p.stat().st_blocks * 512 for p in (n.dir / 'data' / 'version-2').iterdir() if p.name.startswith('log.'))
print(f'  停机时 data/version-2 里快照文件总大小 {sz / 1048576:.1f} MiB,事务日志实际占盘 {logsz / 1048576:.1f} MiB(没有触发快照时数据主要在事务日志里)')
(n.dir / 'zk.log').rename(n.dir / 'zk-before.log')
t0 = time.perf_counter(); n.start(wipe=False); t1 = (time.perf_counter() - t0) * 1000
m = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l) for l in n.log().splitlines() if 'Snapshot loaded' in l or 'Reading snapshot' in l or 'Snapshot taken' in l or 'Reading txn' in l or 'Replaying' in l]
for l in m[:4]: print('  日志:', re.sub(r'/private\S+/', '…/', l)[:130])
print(f'  重启到能响应 {t1:.0f} ms;重启后 znode 数 {fmt()[0]}'); R['restart'] = dict(ms=t1, count=fmt()[0], snap_mib=sz / 1048576)
n.stop(); save('z10', R)
