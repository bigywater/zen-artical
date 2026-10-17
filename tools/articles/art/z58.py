from lib import *
R = J('z58')
def S(k): return [l for l in out('z58').split('== ')[k].splitlines()[1:] if l.strip()]
t4 = S(4)
steps = [
    step("基准:写 1500 个 znode(snapCount=300,所以有很多快照与日志文件)后正常重启,znode 数 1505(1500 + 根与系统节点)。", t=tl(S(0) if False else [out('z58').splitlines()[1], out('z58').splitlines()[2]]), done=[0, 1], kv=KV([['基准', '1505 个 znode']], ['基准'])),
    step("最新的快照被截断(只剩一半)或清零(0 字节):启动成功,znode 数仍是 1505。日志里是「Invalid snapshot snapshot.514. len = …」,ZooKeeper 跳过这个坏快照,改用更旧的快照,再回放之后的事务日志补齐——所以保留多个快照是一种保险。", t=tl(S(1) + S(2)), done=[0, 1], kv=KV([['最新快照损坏', '回退到旧快照 + 回放日志,不丢数据']], ['最新快照损坏'])),
    step("所有快照都被删掉、只剩事务日志:默认拒绝启动,日志「java.io.IOException: No snapshot found, but there are log entries. Something is broken!」「Exiting JVM with code 1」(宁可停机也不静默丢数据);加 -Dzookeeper.snapshot.trust.empty=true 才放行,日志警告「No snapshot found, but there are log entries. This should only be allowed during upgrading.」,这次回放日志恢复出全部 1505 个 znode(因为我的日志是从头完整保留的)。", t=tl(S(3)), mark=[1, 2, 3], done=[4, 5], kv=KV([['无快照', '默认拒绝启动'], ['trust.empty=true', '放行,靠日志回放']], ['无快照'])),
    step("事务日志被破坏:(a) 把最后一条事务尾部的 16 字节改成 0xFF、(b) 把日志中间的 16 字节改成 0xFF,两种情况都是启动失败、退出码 1,日志「java.io.IOException: CRC check failed」。ZooKeeper 校验每条事务的 CRC,不会静默跳过损坏的记录。", t=tl(t4[:8]), mark=[1, 2, 3, 5, 6, 7], kv=KV([['日志内容被改坏', 'CRC check failed,拒绝启动']], ['日志内容被改坏'])),
    step("但「撕裂写」(断电造成最后一条事务只写了一半,这里把日志最后 30 字节清零)不是错误:启动成功、znode 数 1505,日志只有「Last transaction was partial.」——不完整的最后一条事务被丢弃,因为它从未向客户端确认过。(我的最后一条恰好是 closeSession,所以 znode 数没变。)", t=tl(t4[8:]), done=[0, 1], kv=KV([['撕裂写', '丢弃不完整的最后一条,正常启动']], ['撕裂写'])),
    step("集群里的补救:一个节点的数据损坏,直接清空它的数据目录再启动,它作为 follower 加入后从 leader 同步(第 42 篇的 SNAP),znode 数与 leader 都是 205。单机没有这个选项,所以备份(第 59 篇)很重要。", t=tl(S(5)), done=[0], kv=KV([['集群', '损坏的节点清空后从 leader 重新同步']], ['集群'])),
]
A = dict(
    n=58, series='zookeeper', tags='ZooKeeper,数据损坏,启动失败,真实验证,动画演示',
    desc='文件损坏后的启动失败实测:最新快照截断 / 清零 → 回退旧快照 + 回放日志,数据不丢;无快照只剩日志 → 默认拒绝启动(trust.empty=true 放行);日志内容被改坏 → CRC check failed 拒绝启动;断电式撕裂写 → 丢弃不完整的最后一条正常启动;集群里清空数据目录可重新同步。',
    lead='数据文件坏了,ZooKeeper 启动时怎么处理?这篇故意制造几种损坏——快照截断、快照清零、快照全丢、日志内容被改、日志尾部撕裂——看它是容错启动、拒绝启动、还是悄悄丢数据。',
    facts=[('旧快照兜底', '最新快照损坏时回退到旧快照并回放日志,数据不丢'), ('CRC check failed', '日志内容被改坏时拒绝启动,不会静默跳过'), ('Last transaction was partial', '断电撕裂写:丢弃不完整的最后一条,正常启动')],
    body=[
        sec('快照损坏', '', term('', blk('z58', 1) + '\n' + blk('z58', 2))),
        sec('没有快照', '', term('', blk('z58', 3))),
        sec('日志损坏', '', term('', blk('z58', 4)), '<p>我最先一次手工破坏日志时,在一个很小的日志文件里看到过「Last transaction was partial」加上 9 个 znode 丢失(1505 → 1496)的结果;但后来用更干净的方法重复,同样的「改坏中间字节」得到的是 CRC 失败。能不能稳定复现那种「丢数据但启动成功」的情形,我没有确认,所以不把它当结论。</p>'),
        sec('集群里的补救', '', term('', blk('z58', 5))),
        sec('分步演示', '', demo('数据损坏', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,snapCount=300,1500 个 znode;用 truncate / 覆写字节制造损坏;每个场景一个新节点', '没有验证:真实磁盘坏块、事务日志中间被截断(而不是改写)、快照与日志不同步(日志缺一段)、检查工具 zkSnapShotToolkit 的校验、更多的 zookeeper.* 恢复开关'],
)
