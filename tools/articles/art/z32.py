from lib import *
R = J('z32')
def S(k): return [l for l in out('z32').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("一个节点从启动到稳定的状态变化(日志里的 Peer state changed):following → discovery → synchronization(diff / snap)→ broadcast。刚启动的节点先 LOOKING(选举),选完变成 following 或 leading,然后依次经过发现、同步、广播三个阶段才开始服务。", t=tl(S(1)), done=[0, 1, 2, 3, 4, 5, 6], kv=KV([['QuorumPeer 状态', 'LOOKING / FOLLOWING / LEADING / OBSERVING'], ['再往下', 'discovery → synchronization → broadcast']], ['QuorumPeer 状态'])),
    step("杀掉 leader 之后存活节点的状态变化(相对杀的时刻):broadcast 状态下突然出现 looking(约 +5 ms 感知到 leader 没了),约 +216 ms 其中一个变成 leading、另一个变成 following,约 +340 ms 同步完成进入 broadcast——整个选举 + 同步约 0.35 秒。注意「broadcast」前面的负数时间(−64~−81 ms)是上一条状态变化发生在杀之前。", t=tl(S(2)), mark=[1], done=[2, 3, 4, 5, 6, 7, 8], kv=KV([['LOOKING → LEADING/FOLLOWING', '约 +216 ms'], ['进入 broadcast', '约 +340 ms']], ['进入 broadcast'])),
    step("四个状态与 srvr 的对应:LOOKING 时 srvr 返回「not currently serving requests」(不服务);FOLLOWING / LEADING / OBSERVING 对应 Mode: follower / leader / observer。重新启动原 leader 0.3 秒后看它,Mode 已经是 follower(它以 follower 身份加入新一任 leader)。", t=tl(S(3)), done=[2], kv=KV([['LOOKING', '选举中,不服务'], ['旧 leader 回来', '以 follower 加入']], ['LOOKING'])),
]
A = dict(
    n=32, series='zookeeper', tags='ZooKeeper,QuorumPeer,状态机,选举,真实验证,动画演示',
    desc='QuorumPeer 状态机实测:LOOKING → FOLLOWING/LEADING → discovery → synchronization → broadcast;杀掉 leader 后存活节点约 +5 ms 进入 LOOKING,约 +216 ms 选出新 leader,约 +340 ms 完成同步;LOOKING 时 srvr 不服务;旧 leader 重启后以 follower 加入。',
    lead='每个 ZooKeeper 节点内部有一个状态机(QuorumPeer):它在 LOOKING、FOLLOWING、LEADING、OBSERVING 之间切换。这篇不画状态图,直接把节点日志里的 Peer state changed 按时间排出来。',
    facts=[('4 个状态', 'LOOKING / FOLLOWING / LEADING / OBSERVING'), ('约 0.35 s', '杀掉 leader 到新一任进入 broadcast 的时间(本机,3 节点)'), ('LOOKING = 不服务', 'srvr 返回 not currently serving requests')],
    body=[
        sec('启动时的状态变化', '', term('', blk('z32', 1))),
        sec('leader 被杀之后', '', term('', blk('z32', 2)), '<p>时间点来自日志时间戳与我脚本里记录的「杀」的时刻(同一台机器),所以相对值可信,绝对值有毫秒级误差。</p>'),
        sec('状态与对外表现', '', term('', blk('z32', 3))),
        sec('分步演示', '', demo('QuorumPeer 状态', [('t', 'term', '日志'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;状态变化取自节点日志(INFO),杀 leader 用 kill -9', '没有验证:OBSERVING 状态的变化(第 28 篇只验证了角色)、选举反复失败时的状态(第 38 篇)、状态机的内部实现'],
)
