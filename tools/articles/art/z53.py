from lib import *
R = J('z53'); iv = R['intervals']; sz = R['sizes']; bl = R['block']; cn, cg = R['comp_none'], R['comp_gz']
def S(k): return [l for l in out('z53').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"快照什么时候做:snapCount=1000,写 12000 个 znode,得到 {len(iv) + 1} 个快照,相邻间隔(事务数)是 {iv}——最小 {min(iv)}、最大 {max(iv)},都落在 snapCount/2 = 500 到 snapCount = 1000 之间。间隔是随机的,为的是让集群里各个节点不要同时做快照。", t=tl(S(1)), done=[0, 1], kv=KV([['触发', '每 snapCount/2 ~ snapCount 个事务,随机'], ['为什么随机', '避免所有节点同时做快照']], ['触发'])),
    step("快照的耗时与大小(每个 znode 数据 200 字节):" + ';'.join(f"{N} 个 znode → 写快照 {ms} ms、文件 {mib:.1f} MiB" for N, ms, mib in sz) + "。耗时和文件大小都近似与 znode 数成正比(每个 znode 约 280 字节的快照空间)。", t=tl(S(2)), b=bars([[f'{N} 个', ms, f'{ms} ms'] for N, ms, mib in sz], max(ms for N, ms, mib in sz) * 1.1, done=[0, 1, 2]), kv=KV([['20 万 znode', f'{sz[2][1]} ms / {sz[2][2]:.0f} MiB']], ['20 万 znode'])),
    step(f"快照不阻塞写:树里 10 万个 znode,后台连续写触发 {bl['with_snap']['snaps']} 次快照时,前台同步写 p50 {bl['with_snap']['p50']:.2f} ms / p99 {bl['with_snap']['p99']:.2f} ms / 最大 {bl['with_snap']['mx']:.0f} ms;不触发快照的对照 p50 {bl['without']['p50']:.2f} / p99 {bl['without']['p99']:.2f} / 最大 {bl['without']['mx']:.0f} ms——没有可见的差别。快照由单独的线程在后台写,事务继续处理(所以快照是「模糊」的,恢复时靠回放事务日志补齐)。", t=tl(S(3)), b=bars([['有快照 p99', bl['with_snap']['p99'], f"{bl['with_snap']['p99']:.1f} ms"], ['无快照 p99', bl['without']['p99'], f"{bl['without']['p99']:.1f} ms"]], max(bl['with_snap']['p99'], bl['without']['p99']) * 1.3, done=[0, 1]), kv=KV([['快照', '后台线程,不阻塞写']], ['快照'])),
    step(f"快照压缩 zookeeper.snapshot.compression.method=gz:10 万个 znode(数据是重复的 v,压缩率很高),默认格式的快照 {cn['mib']:.1f} MiB、写 {cn['ms']} ms;gz 压缩后 {cg['mib']:.1f} MiB({cn['mib'] / cg['mib']:.0f} 倍小)、写 {cg['ms']} ms(慢 {cg['ms'] / cn['ms']:.1f} 倍),文件名多了 .gz 后缀。压缩率取决于数据内容,这里的数据非常容易压缩。", t=tl(S(4)), b=bars([['默认', cn['mib'], f"{cn['mib']:.1f} MiB"], ['gz', cg['mib'], f"{cg['mib']:.1f} MiB"]], cn['mib'] * 1.1, done=[0, 1]), kv=KV([['gz', f"{cn['mib'] / cg['mib']:.0f} 倍小,慢 {cg['ms'] / cn['ms']:.1f} 倍(本数据)"]], ['gz'])),
]
A = dict(
    n=53, series='zookeeper', tags='ZooKeeper,快照,snapshot,真实验证,动画演示',
    desc=f'快照机制实测:每 snapCount/2~snapCount 个事务随机一次({min(iv)}~{max(iv)});20 万 znode 的快照 {sz[2][2]:.0f} MiB、写 {sz[2][1]} ms;后台快照不影响前台写延迟;gz 压缩使 10 万 znode 的快照从 {cn["mib"]:.1f} MiB 降到 {cg["mib"]:.1f} MiB(写 {cg["ms"]} ms)。',
    lead='快照是 ZooKeeper 持久化的第二条腿(第一条是事务日志)。它什么时候做、要多久、多大、会不会拖慢写?这篇逐项量出来,还试了快照压缩。',
    facts=[(f'{min(iv)}~{max(iv)}', 'snapCount=1000 时相邻快照间隔的事务数(随机)'), (f'{sz[2][1]} ms / {sz[2][2]:.0f} MiB', '20 万 znode 写一份快照的耗时与大小'), (f'{cn["mib"] / cg["mib"]:.0f} 倍', 'gz 压缩后快照缩小的倍数(这份高度可压缩的数据)')],
    body=[
        sec('什么时候做快照', '', term('', blk('z53', 1))),
        sec('耗时与大小', '', term('', blk('z53', 2)), '<p>耗时是启动时写新快照的日志耗时(「Snapshot taken in X ms」),单线程写一份完整的树。</p>'),
        sec('不阻塞写', '', term('', blk('z53', 3)), '<p>前台与后台测的是同一个节点;两种情形下后台都在持续写,所以延迟分布的差别只来自快照本身。</p>'),
        sec('压缩', '', term('', blk('z53', 4)), '<p>压缩换来更小的磁盘占用和更快的网络传输(SNAP 同步时),代价是写快照时更多 CPU 与时间。</p>'),
        sec('分步演示', '', demo('快照', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;数据 200 字节;耗时来自日志;前台延迟是 12 秒内的同步写分布', '没有验证:快照 snappy 压缩(需要额外 jar)、集群里快照对 follower 同步的影响、很大的树(千万级 znode)上的快照耗时、磁盘较慢时快照对写入的影响'],
)
