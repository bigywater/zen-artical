from lib import *
R = J('z54'); g = R['growth']; pg = R['purge']
def S(k): return [l for l in out('z54').split('== ')[k].splitlines()[1:] if l.strip()]
b, a = pg['before'], pg['after']
steps = [
    step("不清理会怎样:snapCount=1000、每个写 100 字节,持续写入:" + ';'.join(f"{n} 次写 → {c['snaps']} 个快照 {c['snap_mib']:.0f} MiB、{c['logs']} 个日志文件" for n, c in g) + "。每做一次快照事务日志就换一个新文件(每个预分配 64 MiB 的稀疏文件,表观大小 5 GiB,实际占盘 12.6 MiB)——所以看磁盘用量要用实占而不是表观大小;而快照是实打实的,而且随树变大越来越大(快照合计增长很快)。", t=tl(S(1)), b=bars([[f'{n} 次写', c['snap_mib'], f"{c['snap_mib']:.0f} MiB"] for n, c in g], g[-1][1]['snap_mib'] * 1.1, done=[0, 1, 2]), kv=KV([['快照合计', '随写入次数与树大小增长'], ['日志表观大小', '每个文件 64 MiB(稀疏),别被 du 吓到']], ['快照合计'])),
    step(f"官方清理工具 PurgeTxnLog(-n 3 保留最近 3 个快照及其之后的日志):清理前 {b['snaps']} 个快照、{b['logs']} 个日志文件,清理后 {a['snaps']} 个快照、{a['logs']} 个日志文件;日志实占 {b['log_disk_mib']:.1f} → {a['log_disk_mib']:.1f} MiB。保留下来的是最新的 3 个快照;清理后重启 znode 数 {R['count']},数据没丢。", t=tl(S(2)), done=[0, 1, 2], kv=KV([['PurgeTxnLog -n 3', f"{b['snaps']} → {a['snaps']} 个快照"]], ['PurgeTxnLog -n 3'])),
    step("自动清理:autopurge.snapRetainCount=3、autopurge.purgeInterval=1(小时,最小值 1),启动日志是「autopurge.snapRetainCount set to 3」「autopurge.purgeInterval set to 1」「Purge task started.」「Purge task completed.」——启动时就立即执行了一次清理,之后每小时一次(我没有等一小时验证后续)。默认 purgeInterval=0,即不自动清理。", t=tl(S(3)), done=[2, 3], kv=KV([['默认', 'purgeInterval = 0,不清理'], ['开启', 'purgeInterval ≥ 1 小时']], ['默认'])),
]
A = dict(
    n=54, series='zookeeper', tags='ZooKeeper,快照,事务日志,autopurge,真实验证,动画演示',
    desc=f'快照频率与事务日志增长实测:不清理时 6 万次写产生 {g[-1][1]["snaps"]} 个快照({g[-1][1]["snap_mib"]:.0f} MiB)、{g[-1][1]["logs"]} 个日志文件(表观 5 GiB、实占 {g[-1][1]["log_disk_mib"]:.0f} MiB);PurgeTxnLog -n 3 清理后剩 {a["snaps"]} 个快照;autopurge 配置启动时即执行一次。',
    lead='ZooKeeper 默认不清理旧的快照和事务日志,磁盘会一直涨,直到写满(第 57 篇看写满的后果)。这篇量一下增长有多快,再用官方清理工具和 autopurge 清理。',
    facts=[(f'{g[-1][1]["snaps"]} 个 / {g[-1][1]["snap_mib"]:.0f} MiB', '6 万次写之后的快照个数与合计大小(不清理)'), ('5 GiB vs 12.6 MiB', f'{g[-1][1]["logs"]} 个日志文件的表观大小与实占'), (f'{b["snaps"]} → {a["snaps"]}', 'PurgeTxnLog -n 3 前后的快照数')],
    body=[
        sec('不清理的增长', '', term('', blk('z54', 1)), '<p>磁盘监控要看实际占用(文件系统块数),不要用 <code>ls -l</code> 的表观大小——事务日志是预分配的稀疏文件(这是 macOS APFS 上的现象,别的文件系统可能不是稀疏的)。</p>'),
        sec('PurgeTxnLog', '', term('', blk('z54', 2))),
        sec('autopurge', '', term('', blk('z54', 3))),
        sec('分步演示', '', demo('清理', [('t', 'term', '输出'), ('b', 'bars', '快照合计'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,snapCount=1000;数据 100 字节;PurgeTxnLog 是 3.9.6 jar 里的官方类', '没有验证:autopurge 在一小时之后的实际清理、保留数量对恢复能力的影响(保留 3 个够不够,要看备份策略)、集群里各节点各自清理的互不影响'],
)
