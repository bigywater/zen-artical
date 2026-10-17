import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z54'); R = {}
n = Node('z54', 7300, conf={'snapCount': 1000}).start(); z = client('127.0.0.1:7300')
v2 = n.dir / 'data' / 'version-2'
def census():
    sn = [p for p in v2.iterdir() if p.name.startswith('snapshot.')]; lg = [p for p in v2.iterdir() if p.name.startswith('log.')]
    return dict(snaps=len(sn), snap_mib=sum(p.stat().st_size for p in sn) / 1048576, logs=len(lg), log_apparent_mib=sum(p.stat().st_size for p in lg) / 1048576, log_disk_mib=sum(p.stat().st_blocks * 512 for p in lg) / 1048576)
print('== 一:不清理会怎样:snapCount=1000,每次写 100 字节,持续写入,每 10000 个事务看一次数据目录')
print(f'  {"累计写入":>8} {"快照数":>6} {"快照合计 MiB":>12} {"日志文件数":>9} {"日志表观 MiB":>12} {"日志实占 MiB":>12}')
R['growth'] = []; done = 0
for target in (10000, 30000, 60000):
    while done < target:
        rs = [z.create_async(f'/n{i}', b'x' * 100) for i in range(done, min(target, done + 5000))]; [r.get() for r in rs]; done = min(target, done + 5000)
    c = census(); R['growth'].append((done, c)); print(f'  {done:>8} {c["snaps"]:>6} {c["snap_mib"]:>12.1f} {c["logs"]:>9} {c["log_apparent_mib"]:>12.0f} {c["log_disk_mib"]:>12.1f}')
print()
print('== 二:官方清理工具 PurgeTxnLog:保留最近 3 个快照(及其之后的日志)')
z.stop(); n.stop(); b = census()
r = subprocess.run([JAVA, '-Xmx64m', '-cp', CP, 'org.apache.zookeeper.server.PurgeTxnLog', str(n.dir / 'data'), str(n.dir / 'data'), '-n', '3'], capture_output=True, text=True)
a = census(); print(f'  清理前:{b["snaps"]} 个快照、{b["logs"]} 个日志文件;清理后:{a["snaps"]} 个快照、{a["logs"]} 个日志文件;日志实占 {b["log_disk_mib"]:.1f} → {a["log_disk_mib"]:.1f} MiB'); R['purge'] = dict(before=b, after=a)
print('  保留下来的快照:', sorted(p.name for p in v2.iterdir() if p.name.startswith('snapshot.')))
n.start(wipe=False); zz = client('127.0.0.1:7300'); print('  清理后重启:znode 数', kv(n.four('mntr')).get('zk_znode_count'), '(数据没丢)'); R['count'] = kv(n.four('mntr')).get('zk_znode_count'); zz.stop(); n.stop()
print()
print('== 三:自动清理 autopurge.snapRetainCount / autopurge.purgeInterval(单位:小时,最小 1)——只验证配置生效,没有等一小时看实际清理')
m = Node('z54b', 7301, conf={'autopurge.snapRetainCount': 3, 'autopurge.purgeInterval': 1}).start()
L = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l) for l in m.log().splitlines() if 'autopurge' in l.lower() or 'Purge task' in l]; [print('  ', l[:100]) for l in L]; R['autopurge'] = L; m.stop()
save('z54', R)
