from lib import *
R = J('z1'); sz = R['size']; sy = R['sync']; mt = R['mntr']
def S(k): return [l for l in out('z1').split('== ')[k].splitlines()[1:] if l.strip()]
ok_max = max(kb for kb, r in sz if r == 'OK'); fail_min = min(kb for kb, r in sz if r != 'OK')
steps = [
    step(f"ZooKeeper 的数据是「小而快」的:单个 znode 的数据上限约 1 MiB。实测创建 1 / 512 / 1000 / {ok_max} KiB 的 znode 都成功;{fail_min} KiB 和 2048 KiB 的得到 ConnectionLoss(请求超过 jute.maxbuffer 默认值,服务端直接断开连接)。", t=tl(S(1)), done=[0, 1, 2, 3], mark=[4, 5], kv=KV([['上限', '约 1 MiB'], ['超过时', 'ConnectionLoss,不是友好的错误']], ['超过时'])),
    step(f"读写不对称:单机、同步调用,写 {sy['w']:.0f} 次/秒(约 3 ms/次)、读 {sy['r']:.0f} 次/秒(约 0.16 ms/次);用流水线异步写 5000 次能到 {R['async_w']:.0f} 次/秒。写要经过事务日志落盘,读直接读内存。(单机、本机回环,只用来看相对关系。)", t=tl(S(2)), b=bars([['同步读', sy['r'], f"{sy['r']:.0f}/s"], ['同步写', sy['w'], f"{sy['w']:.0f}/s"], ['异步写(流水线)', R['async_w'], f"{R['async_w']:.0f}/s"]], R['async_w'] * 1.1, mark=[1], done=[0, 2]), kv=KV([['读', '内存,快'], ['写', '落盘,慢约 20 倍(同步)']], ['写'])),
    step(f"强顺序:每个写事务都有全局递增的 zxid。连续创建 /o1、/o2、/o3,czxid 依次是 {', '.join(hex(x) for x in R['zxid'])},严格递增。「谁先谁后」在整个集群里有唯一答案,这是协调服务最需要的性质。", t=tl(S(3)), done=[0], kv=KV([['zxid', '全局单调递增']], ['zxid'])),
    step(f"整棵树在内存里:创建了 {mt['zk_znode_count']} 个 znode 之后,mntr 显示近似数据大小 {int(mt['zk_approximate_data_size']) / 1048576:.1f} MiB。没有查询语言,只能按路径读、列子节点——它是协调服务,不是数据库(第 10 篇会量内存随 znode 数增长)。", t=tl(S(4)), kv=KV([['数据模型', '路径 → 小块数据'], ['存储', '整棵树常驻内存']], ['存储'])),
]
A = dict(
    n=1, series='zookeeper', tags='ZooKeeper,协调服务,真实验证,动画演示',
    desc=f'ZooKeeper 3.9.6 单机实测:单个 znode 上限约 1 MiB({fail_min} KiB 会 ConnectionLoss),同步写约 {sy["w"]:.0f} 次/秒、同步读约 {sy["r"]:.0f} 次/秒,每个写都有全局递增的 zxid,整棵树常驻内存——小数据、强顺序、读多写少的协调服务。',
    lead='ZooKeeper 常被叫做「分布式协调服务」,但它到底擅长什么、不擅长什么?这篇不讲概念,直接在自己起的 ZooKeeper 3.9.6 上量:数据大小的上限、读写速度的差别、顺序保证和内存里的树,再据此回答它的定位。',
    facts=[('约 1 MiB', f'单个 znode 数据的上限:{ok_max} KiB 成功,{fail_min} KiB ConnectionLoss'), (f'{sy["r"] / sy["w"]:.0f} 倍', '同步读与同步写的速度比(单机,本机回环)'), ('全局递增 zxid', '每个写事务一个编号,顺序在整个集群里只有一个答案')],
    body=[
        sec('数据大小的上限', '', term('', blk('z1', 1)), '<p>超过上限时,客户端得到的是 <code>ConnectionLoss</code>(连接被服务端断开),而不是一个「数据太大」的错误,排查时容易误判成网络问题。上限由 <code>jute.maxbuffer</code> 决定(第 24 篇)。</p>'),
        sec('读写速度', '', term('', blk('z1', 2)), '<p>写必须先写事务日志再应用到内存,读只读内存。集群里写还要多数派确认(第 2 篇量了单机与 3 节点的写延迟差别)。所以 ZooKeeper 适合读多写少、数据小的场景:配置、成员列表、锁的状态——不适合存业务数据或做高吞吐写入。</p>'),
        sec('顺序', '', term('', blk('z1', 3))),
        sec('一棵常驻内存的树', '', term('', blk('z1', 4))),
        sec('怎么定位它', '', '<p>综合上面四点:ZooKeeper 提供的是<b>小块数据 + 全局顺序 + 通知</b>(通知机制在第 15 篇)。它适合做配置中心、服务发现、分布式锁、选举这类「大家需要对少量状态达成一致」的事;不适合当数据库、缓存或消息队列。这个归纳来自上面的实测和后面章节,本文没有拿它去对比别的系统(第 108–110 篇再比较 etcd、Consul)。</p>'),
        sec('分步演示', '', demo('ZooKeeper 的边界', [('t', 'term', '输出'), ('b', 'bars', '速度'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单个单机节点,默认 tickTime=2000;客户端用 kazoo 2.11.0;读写各跑一次', '没有验证:集群里的写延迟(第 2 篇)、watch 通知的延迟与数量上限(第 15、17 篇)、多客户端并发写的吞吐、更大的 jute.maxbuffer 设置、SSD 与机械盘的差别'],
)
