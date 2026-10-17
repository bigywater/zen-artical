from lib import *
R = J('z49'); bd = R['badid']; un = R['unknown']
def S(k): return [l for l in out('z49').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("静态配置的 3 节点集群:每个节点的 conf 里的成员列表完全一致——server.1=127.0.0.1:7400:7500:participant、server.2、server.3(host:quorum 端口:选举端口:角色)。成员关系就是每个节点 zoo.cfg 里的这份列表加上各自的 myid 文件。", t=tl(S(1)), done=[0, 1, 2], kv=KV([['成员', 'server.N 列表 + myid']], ['成员'])),
    step(f"myid 不在 server 列表里:节点启动失败,退出码 {bd['code']},日志是「java.lang.RuntimeException: My id 9 not in the peer list」「Exiting JVM with code 1」。配错 myid 会在启动时立刻暴露。", t=tl(S(2)), mark=[1, 2], kv=KV([['myid 配错', '启动失败,退出码 1']], ['myid 配错'])),
    step("成员列表不一致:节点 3 的配置里少了 server.1,其它两个节点是完整的 3 成员列表。结果 1、2 号节点正常(follower / leader),节点 3「不服务」,它的 conf 里甚至看不到成员——列表不一致的节点无法加入。", t=tl(S(3)), mark=[0, 1], kv=KV([['成员列表不一致', '这个节点无法加入集群']], ['成员列表不一致'])),
    step(f"意外的情形:一个不在原 3 个节点名单里的新节点(myid=4,它自己的配置里有 4 个成员)启动后,Mode 居然是 {un['mode']},原 leader 的 zk_synced_followers = {un['synced']}(包含了它)。但它不被算进多数派:停掉原来的两个 follower,只剩原 leader + 这个节点,写入{'成功' if un['write_ok'] else '失败'},两者都变成「不服务」。静态配置下,名单外的节点可以作为 learner 连上并同步数据,但不参与投票。", t=tl(S(4)), mark=[4, 5], kv=KV([['名单外的节点', '能同步,但不算多数派']], ['名单外的节点'])),
]
A = dict(
    n=49, series='zookeeper', tags='ZooKeeper,集群成员,myid,配置,真实验证,动画演示',
    desc=f'集群成员管理实测(静态配置):成员 = 每个节点 zoo.cfg 里的 server.N 列表 + myid;myid 不在列表里节点启动失败(退出码 1);成员列表不一致的节点无法加入;名单外的节点(myid=4)能以 follower 身份连上并同步,但不被算进多数派。',
    lead='ZooKeeper 集群的「成员」是怎么定义的?配错了会怎样?这篇用静态配置的集群验证几种最常见的成员配置错误:myid 不在列表里、成员列表不一致、名单外的节点自己加入。',
    facts=[('server.N + myid', '成员关系 = 配置里的列表 + 每个节点的 myid 文件'), ('退出码 1', 'myid 不在 server 列表里,启动即失败'), ('名单外的节点', '能连上并同步,但不参与多数派')],
    body=[
        sec('成员列表', '', term('', blk('z49', 1))),
        sec('myid 配错', '', term('', blk('z49', 2))),
        sec('列表不一致', '', term('', blk('z49', 3)), '<p>这是我构造的一种不一致(少一个成员);其它的不一致(端口写错、地址不同)没有逐个测。</p>'),
        sec('名单外的节点', '', term('', blk('z49', 4)), '<p>这是一个值得警惕的现象:它没有破坏一致性(多数派仍只按名单内的节点计算),但意味着配置错误的节点可能静悄悄地连上集群、读到数据。动态配置(第 50 篇)用 reconfig 来管理成员变化,不依赖这种「自己加入」。</p>'),
        sec('分步演示', '', demo('集群成员', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。静态配置伪集群;每个场景一个新实例', '没有验证:成员的 DNS 名与 IP 变化、成员端口冲突、observer 成员的配置错误(第 28 篇)、动态配置下的成员管理(第 50、51 篇)'],
)
