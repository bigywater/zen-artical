import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z5'); R = {}
n = Node('z5', 7300, conf={'snapCount': 100}).start()
z = client('127.0.0.1:7300')
v2 = n.dir / 'data' / 'version-2'
def ls():
    return [(p.name, p.stat().st_size, p.stat().st_blocks * 512) for p in sorted(v2.iterdir())]
print('== 一:刚启动、还没有写入:数据目录里有什么')
for name, sz, disk in ls(): print(f'  {name:<22} 大小 {sz:>9} 字节  实际占盘 {disk:>9} 字节')
print('  dataDir 下还有:', sorted(p.name for p in (n.dir / 'data').iterdir()))
R['empty'] = ls()
print()
print('== 二:写入 300 个 znode(snapCount=100)之后')
for i in range(300): z.create(f'/n{i}', b'x' * 50)
files = ls()
for name, sz, disk in files: print(f'  {name:<22} 大小 {sz:>9} 字节  实际占盘 {disk:>9} 字节')
R['after'] = files
print('  文件名里的十六进制是 zxid:log.<该文件第一条事务的 zxid>、snapshot.<快照时已处理的最大 zxid>;当前最大 zxid =', n.srvr().get('zxid'))
print()
print('== 三:用官方工具 TxnLogToolkit 读事务日志(第一个日志文件的前几条)')
first_log = [p for p in sorted(v2.iterdir()) if p.name.startswith('log.')][0]
r = subprocess.run([JAVA, '-Xmx64m', '-cp', CP, 'org.apache.zookeeper.server.persistence.TxnLogToolkit', str(first_log)], capture_output=True, text=True)
txt = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not re.match(r'^\d\d:\d\d:\d\d', l)]
for l in txt[:7]: print('  ', re.sub(r'\s+', ' ', l)[:150])
print('  ……共', len(txt), '行输出;最后一行:', txt[-1][:100]); R['txn'] = txt[:7]
print()
print('== 四:用 SnapshotFormatter 读最新的快照(树里有什么)')
snap = [p for p in sorted(v2.iterdir()) if p.name.startswith('snapshot.')][-1]
r = subprocess.run([JAVA, '-Xmx64m', '-cp', CP, 'org.apache.zookeeper.server.SnapshotFormatter', str(snap)], capture_output=True, text=True)
sl = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not re.match(r'^\d\d:\d\d:\d\d', l)]
for l in sl[:12]: print('  ', l[:120])
print('  ……共', len(sl), '行(每个 znode 一段);最后一行:', sl[-1][:80]); R['snap'] = sl[:12]
z.stop(); n.stop()
print()
print('== 五:dataDir 与 dataLogDir 分开配置时:事务日志放到另一块盘')
m = Node('z5b', 7301, conf={'dataLogDir': str(ZDATA / 'z5b' / 'txnlog')}).start()
z = client('127.0.0.1:7301'); [z.create(f'/n{i}', b'x') for i in range(5)]; z.stop()
print('  dataDir/version-2:', sorted(p.name for p in (m.dir / 'data' / 'version-2').iterdir())); print('  dataLogDir/version-2:', sorted(p.name for p in (m.dir / 'txnlog' / 'version-2').iterdir()))
R['split'] = dict(data=sorted(p.name for p in (m.dir / 'data' / 'version-2').iterdir()), log=sorted(p.name for p in (m.dir / 'txnlog' / 'version-2').iterdir()))
m.stop(); save('z5', R)
