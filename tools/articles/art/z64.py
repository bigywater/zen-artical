from lib import *
R = J('z64')
def S(k): return [l for l in out('z64').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("JMX:启动时加 -Dcom.sun.management.jmxremote.port=7391(本实验只绑定本机、关闭认证与 SSL,仅用于实验)。用一个我写的 20 行 Java 程序(JMXConnector)读取:单机节点注册的 ZooKeeper MBean 只有两个:StandaloneServer_port7300 和它下面的 InMemoryDataTree。", t=tl(S(1)), done=[0], kv=KV([['MBean', 'StandaloneServer + InMemoryDataTree']], ['MBean'])),
    step("StandaloneServer MBean 的属性(读到的实际值):TickTime=2000、MinSessionTimeout=4000、MaxSessionTimeout=40000、ClientPort=7300、MaxClientCnxnsPerHost=60、NumAliveConnections=1、OutstandingRequests=0、PacketsReceived、AvgRequestLatency、MaxRequestLatency、Version;可调用的操作有 resetStatistics、resetLatency、resetMaxLatency 等——JMX 既能读也能(重置统计)写。", t=tl(S(2)), done=[0, 1, 2, 3, 4, 5], kv=KV([['属性', '配置 + 统计'], ['操作', 'reset* 系列']], ['属性'])),
    step("集群节点的 MBean 层次更多:ReplicatedServer_id<N> → replica.1 / replica.2 / replica.3(每个成员各一个)→ 当前角色(leader 下有 Leader、follower 下有 Follower)→ InMemoryDataTree;leader 下还有每个 follower 的 Learner_Connections(含 id)。从 MBean 的名字就能看出节点现在是 leader 还是 follower。", t=tl(S(3)), done=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], kv=KV([['leader', 'Leader + Learner_Connections'], ['follower', 'Follower']], ['leader'])),
]
A = dict(
    n=64, series='zookeeper', tags='ZooKeeper,JMX,监控,MBean,真实验证,动画演示',
    desc='ZooKeeper JMX 监控实测:单机注册 StandaloneServer + InMemoryDataTree 两个 MBean,可读 TickTime / NumAliveConnections / AvgRequestLatency / Version 等属性,可调用 resetStatistics;集群节点的 MBean 按 ReplicatedServer → replica.N → Leader / Follower 分层,leader 下有每个 follower 的 Learner_Connections。',
    lead='JMX 是 Java 世界的标准监控接口,ZooKeeper 也通过它暴露状态。这篇开启 JMX,用一个小 Java 程序连上去,把单机与集群节点注册的 MBean 和它们的属性、操作列出来。',
    facts=[('2 个 / 层次化', '单机只注册 2 个 MBean;集群按 ReplicatedServer → replica → Leader / Follower 分层'), ('reset* 操作', 'JMX 不只是读,也能重置统计'), ('无认证', '实验里的 JMX 只绑定本机且关闭了认证,生产环境必须开认证与 SSL')],
    body=[
        sec('单机的 MBean', '', term('', blk('z64', 1))),
        sec('属性与操作', '', term('', blk('z64', 2)), '<p>属性值与 mntr / Prometheus 里的同名指标同源(NumAliveConnections ↔ zk_num_alive_connections)。</p>'),
        sec('集群节点', '', term('', blk('z64', 3))),
        sec('安全提醒', '', '<p>远程 JMX 如果不开认证,任何人连上就能调用 MBean 的操作;而且 JMX 基于 RMI,配置不当会有反序列化类的风险(这是通用的 Java 安全常识,本文没有测)。生产环境应当开认证 + SSL,或者干脆用 Prometheus 端点(第 63 篇)并关闭 JMX 远程端口。</p>'),
        sec('分步演示', '', demo('JMX', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。JMX 端口 7391 / 7392+,仅本机、无认证、无 SSL(实验用);客户端是自己写并用 javac 编译的 JmxProbe.java', '没有验证:JConsole / VisualVM 等图形工具、带认证与 SSL 的 JMX、MBean 的每一个属性的含义、通过 JMX 调用 reset 操作后指标的变化'],
)
