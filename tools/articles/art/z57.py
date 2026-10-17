from lib import *
R = J('z57')
def S(k): return [l for l in out('z57').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"事务日志与快照放在一个只有 24 MiB 的小盘上(先放 6 MiB 的压舱文件、preAllocSize=512 KB),不断写入 100 KiB 的 znode:成功写入 {R['fill']['count']} 个(约 17 MiB)后第 {R['fill']['count'] + 1} 次写入失败,客户端看到 {R['fill']['err']};此时盘上只剩 0.38 MiB。", t=tl(S(1)[:3]), done=[1], mark=[2], kv=KV([['盘满', '写入失败 → ConnectionLoss']], ['盘满'])),
    step("服务端的反应:SyncThread 抛出「Severe unrecoverable error, from thread : SyncThread:0」「java.io.IOException: No space left on device」然后整个服务端进程自己关闭(日志里一连串 Shutting down,退出码 0)。不是「只拒绝写、继续服务读」,而是整个节点下线——读、新连接都不可能(对 7300 端口发 ruok 得到 ConnectionRefused)。", t=tl(S(1)[3:] + S(2)), mark=[0, 1], kv=KV([['事务日志写失败', '节点自己退出,读也不可用']], ['事务日志写失败'])),
    step("腾出 6 MiB(删掉压舱文件)后重启:启动时服务端要先写一份新快照,而完整的快照要约 17 MiB,空间还是不够——启动失败,退出码 10,日志「Severe unrecoverable error, exiting」「No space left on device」「Exiting JVM with code 10」,还留下了一个写了一半的快照文件 snapshot.af(6.4 MiB)。", t=tl(S(3)), mark=[1, 2], kv=KV([['恢复需要空间', '≥ 一份完整快照'], ['失败时', '留下写了一半的快照']], ['恢复需要空间'])),
    step(f"删掉那个写了一半的快照后再启动,还是失败(退出码 10)——可用空间仍然只有 6.4 MiB。把数据目录搬到 256 MiB 的大盘上启动:成功,写入成功的 {R['fill']['count']} 个 100 KiB 的 znode 都在,可以继续写(znode 数 {R['moved']['count']} 含根与系统节点)。结论:没有丢数据,但恢复需要比数据更大的可用空间。", t=tl(S(4)), done=[2], kv=KV([['搬到大盘', '数据完整,可继续写']], ['搬到大盘'])),
]
A = dict(
    n=57, series='zookeeper', tags='ZooKeeper,磁盘满,故障,真实验证,动画演示',
    desc=f'磁盘满时的服务行为实测(24 MiB 小盘):写入 {R["fill"]["count"]} 个 100 KiB znode 后失败,服务端因「No space left on device」自己退出(退出码 0);腾出 6 MiB 重启仍因写不下启动快照而失败(退出码 10,留下写了一半的快照);搬到 256 MiB 盘后数据完整。',
    lead='ZooKeeper 的数据盘写满了会怎样?是只拒绝写,还是整个服务不可用?腾出一点空间就能恢复吗?这篇用一块只有 24 MiB 的磁盘映像把它们都试一遍。',
    facts=[('节点自己退出', '事务日志写失败后整个进程关闭,读也不可用'), ('退出码 10', '腾出 6 MiB 重启仍失败:启动时要写一份完整快照'), ('数据不丢', '搬到更大的盘后全部在')],
    body=[
        sec('写到盘满', '', term('', blk('z57', 1))),
        sec('进程已经退出', '', term('', blk('z57', 2))),
        sec('腾出空间重启', '', term('', blk('z57', 3)), '<p>启动时写快照的行为在第 4 篇的日志里能看到(「Snapshot taken in … ms」)。恢复前先确认可用空间 &gt; 当前数据的快照大小(第 53 篇)。</p>'),
        sec('搬到更大的盘', '', term('', blk('z57', 4))),
        sec('分步演示', '', demo('磁盘满', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。事务日志与快照放在 24 MiB 的 HFS+ 磁盘映像上,preAllocSize=512 KB;集群里单个节点盘满的情形没有测(其它节点会继续服务)', '没有验证:集群里一个节点盘满对整体的影响、dataLogDir 与 dataDir 分盘时只有一块盘满、监控磁盘使用率的告警阈值、Linux 上的错误码(本机是 macOS)'],
)
