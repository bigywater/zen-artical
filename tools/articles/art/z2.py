from lib import *
R = J('z2'); ls, lc = R['lat_standalone'], R['lat_cluster']
def S(k): return [l for l in out('z2').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"单机模式(standalone):zoo.cfg 里没有 server.N 行,四字命令 srvr 的 Mode 是 {R['standalone_mode']}。300 次同步 create 的写延迟中位数 {ls:.2f} ms。一个节点就是全部,挂了就不可用。", t=tl(S(1)), kv=KV([['Mode', 'standalone'], ['写延迟(中位数)', f'{ls:.2f} ms']], ['Mode'])),
    step(f"伪集群(一台机器、三个进程、三套端口与数据目录):每个节点的 zoo.cfg 里都有同样的 server.1/2/3=127.0.0.1:<quorum 端口>:<选举端口>,myid 文件里各是 1/2/3。运行后角色是:{', '.join(f'{k.split(chr(45))[1]} 号 {v}' for k, v in R['roles'].items())}。写延迟中位数 {lc:.2f} ms——写要经过 leader 并等多数派确认,比单机慢约 {lc / ls:.1f} 倍(本机回环、同一块磁盘)。", t=tl(S(2)), b=bars([['单机', ls, f'{ls:.2f} ms'], ['3 节点集群', lc, f'{lc:.2f} ms']], lc * 1.15, mark=[1], done=[0]), kv=KV([['集群写延迟', f'约单机的 {lc / ls:.1f} 倍'], ['配置', 'server.N + myid']], ['集群写延迟'])),
    step("3 个节点只起 1 个:进程在、四字命令 ruok 回 imok,但 srvr 回「This ZooKeeper instance is not currently serving requests」,客户端连接 / create 得到 KazooTimeoutError——没有多数派就不服务,ruok 只代表进程活着。", t=tl(S(3)[:3]), mark=[0, 1, 2], kv=KV([['ruok = imok', '进程活着'], ['不服务', '没有多数派']], ['不服务'])),
    step(f"再起第 2 个节点:选出 leader({', '.join(f'{k.split(chr(45))[1]} 号 {v}' for k, v in R['quorum'].items())}),2/3 满足多数派,客户端 create 成功。", t=tl(S(3)[3:]), done=[0, 1], kv=KV([['2 / 3', '够多数派,能服务']], ['2 / 3'])),
]
A = dict(
    n=2, series='zookeeper', tags='ZooKeeper,部署,集群,真实验证,动画演示',
    desc=f'单机、伪集群与集群的区别(ZooKeeper 3.9.6 实测):单机 Mode=standalone,写延迟 {ls:.2f} ms;3 节点伪集群 server.N + myid,写延迟 {lc:.2f} ms;只起 1/3 时进程在、ruok=imok 但不服务,起到 2/3 才能服务。',
    lead='ZooKeeper 有单机、伪集群、集群三种部署方式。它们在配置、角色和可用性上有什么区别?这篇自己起进程逐个验证,包括「只起一部分节点」这种最容易让人误会的状态。',
    facts=[('standalone / leader / follower', '用四字命令 srvr 的 Mode 就能看出节点的角色'), (f'{lc / ls:.1f} 倍', '3 节点集群的同步写延迟与单机的比(本机)'), ('1/3 不服务', '进程在、ruok 回 imok,但没有多数派就拒绝服务')],
    body=[
        sec('单机模式', '', term('', blk('z2', 1)), '<p>没有 <code>server.N</code> 配置就是单机。适合开发测试,不适合生产(没有容错)。</p>'),
        sec('伪集群', '', term('', blk('z2', 2)), '<p>「伪集群」只是把多个节点放在同一台机器上,靠不同的端口与数据目录区分;配置与真正的集群完全一样(<code>server.N=host:quorumPort:electionPort</code> 加 <code>myid</code> 文件)。它不提供机器级别的容错,但用来学习与测试一致性行为非常合适——本系列后面的集群实验都是这样做的。</p>'),
        sec('只起了一部分节点', '', term('', blk('z2', 3)), '<p>用 <code>ruok</code> 做健康检查会被骗:它只表示进程能响应,不表示能服务。更可靠的是 <code>srvr</code> 的 Mode 或 <code>mntr</code>。</p>'),
        sec('分步演示', '', demo('三种部署方式', [('t', 'term', '输出'), ('b', 'bars', '写延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。伪集群 3 个进程同一台机器;写延迟是 300 次同步 create 的中位数,磁盘为本机 SSD,默认会 fsync', '没有验证:跨机器的网络延迟、3 节点以外的规模(第 31 篇量 5 节点)、observer(第 29 篇)、仲裁方式的其它配置(如分组权重)'],
)
