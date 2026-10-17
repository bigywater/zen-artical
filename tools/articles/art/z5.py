from lib import *
R = J('z5'); af = R['after']; sp = R['split']
def S(k): return [l for l in out('z5').split('== ')[k].splitlines()[1:] if l.strip()]
logs = [x for x in af if x[0].startswith('log.')]; snaps = [x for x in af if x[0].startswith('snapshot.')]
steps = [
    step("刚启动、没有写入:version-2 里有 log.1(事务日志,大小 67108880 字节 ≈ 64 MiB,实际占盘只有 20 KiB——ZooKeeper 预分配了 64 MiB 的稀疏文件)和 snapshot.0(478 字节,只有根节点与 /zookeeper 的空树)。dataDir 下除了 version-2 没有别的(单机没有 myid)。", t=tl(S(1)), kv=KV([['log.1', '预分配 64 MiB(稀疏)'], ['snapshot.0', '空树']], ['log.1'])),
    step(f"写入 300 个 znode(snapCount=100)之后:事务日志有 {len(logs)} 个({', '.join(x[0] for x in logs)}),快照有 {len(snaps)} 个({', '.join(x[0] for x in snaps)});文件名里的十六进制是 zxid——log.<该文件第一条事务的 zxid>,snapshot.<做快照时的最大 zxid>。每做一次快照,事务日志就换一个新文件。快照间隔落在 snapCount/2 ~ snapCount 之间(本次间隔:{', '.join(str(int(b[0][9:], 16) - int(a[0][9:], 16)) for a, b in zip(snaps[:-1], snaps[1:]))} 个事务)。", t=tl(S(2)), done=list(range(len(af))), kv=KV([['快照', '每 snapCount/2 ~ snapCount 个事务一次'], ['事务日志', '随快照滚动']], ['快照'])),
    step("用官方工具 TxnLogToolkit 读事务日志:头一行「ZooKeeper Transactional Log File with dbid 0 txnlog format version 2」,之后每行一条事务——会话 id、cxid、zxid、操作类型和内容:先是 createSession(zxid 0x1),然后是一条条 create /n0、/n1……;最后是「EOF reached after … txns」。事务日志是按顺序追加的操作流水,回放它就能重建数据。", t=tl(S(3)), kv=KV([['事务日志', '操作流水,按 zxid 追加']], ['事务日志'])),
    step("用 SnapshotFormatter 读快照:每个 znode 一段,列出 cZxid、ctime、mZxid、mtime、pZxid、cversion、dataVersion、aclVersion、ephemeralOwner、dataLength、numChildren——就是 znode 的 stat(第 7 篇);最后一行是「Last zxid」。快照是某一刻整棵树的全量转储。", t=tl(S(4)), kv=KV([['快照', '整棵树的全量转储']], ['快照'])),
    step(f"dataLogDir 可以和 dataDir 分开:配置 dataLogDir 后,dataDir/version-2 里只有 {', '.join(sp['data'])}(快照),事务日志 {', '.join(sp['log'])} 在 dataLogDir/version-2。事务日志要 fsync,把它放到单独的盘上可以避免和快照写入抢 IO。", t=tl(S(5)), done=[0, 1], kv=KV([['dataDir', '快照'], ['dataLogDir', '事务日志']], ['dataLogDir'])),
]
A = dict(
    n=5, series='zookeeper', tags='ZooKeeper,数据目录,事务日志,快照,真实验证,动画演示',
    desc='ZooKeeper 数据目录实测:version-2 里是 log.<zxid> 事务日志(预分配 64 MiB,稀疏)和 snapshot.<zxid> 快照;每做一次快照事务日志就滚动;用 TxnLogToolkit 与 SnapshotFormatter 读出里面的内容;dataLogDir 可把事务日志放到另一块盘。',
    lead='ZooKeeper 把数据放在哪?事务日志和快照是什么关系?文件名里的十六进制数字是什么意思?这篇看一遍真实的 version-2 目录,并用官方自带的两个工具把里面的内容读出来。',
    facts=[('64 MiB 预分配', '每个事务日志文件的表观大小;实际占盘只有 20 KiB(稀疏文件)'), ('文件名 = zxid', 'log.<首条事务 zxid>、snapshot.<快照时最大 zxid>'), ('snapCount/2 ~ snapCount', '两次快照之间的事务数范围(实测间隔都在 snapCount=100 的这个范围内)')],
    body=[
        sec('刚启动时', '', term('', blk('z5', 1))),
        sec('写入之后', '', term('', blk('z5', 2)), '<p>「实际占盘」取自文件系统的块数(<code>st_blocks</code>),在 APFS 上预分配的 64 MiB 是稀疏的;别的文件系统上表现可能不同,本文只验证了 macOS。</p>'),
        sec('事务日志里有什么', '', term('', blk('z5', 3))),
        sec('快照里有什么', '', term('', blk('z5', 4))),
        sec('dataLogDir', '', term('', blk('z5', 5))),
        sec('分步演示', '', demo('数据目录', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。snapCount=100(默认是 100000,这里调小是为了几百个事务就能看到快照);TxnLogToolkit 与 SnapshotFormatter 是 3.9.6 jar 里的官方类', '没有验证:快照与日志的清理(autopurge,第 54 篇)、事务日志 fsync 的耗时(第 55、56 篇)、非 APFS 文件系统的预分配行为、快照压缩(zookeeper.snapshot.compression.method)'],
)
