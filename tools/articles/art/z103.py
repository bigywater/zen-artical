from lib import *
R = J('z103'); ct = R['ctl']; mn = R['mntr']; tops = R['tops']
def S(k): return [x for x in out('z103').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step(f"3 个 Kafka 3.9.2 broker(ZooKeeper 模式)启动后,ZooKeeper 里的顶层 znode:{'、'.join(tops)}。每个 broker 在 /brokers/ids/<id> 建一个临时节点(JSON:地址、端口、版本、时间戳);/controller 也是临时节点,谁建成功谁是 controller;/controller_epoch 是 controller 的任期号。", t=tl(S(1)), done=[0], kv=KV([['broker 注册', '/brokers/ids/<id>(临时)'], ['controller', '/controller(临时)']], ['broker 注册'])),
    step("建 3 分区 3 副本的主题 t1:/brokers/topics/t1 里是分区 → 副本列表的分配;每个分区另有 /brokers/topics/t1/partitions/<p>/state,记录 leader、leader_epoch、isr、controller_epoch。生产 1000 条、消费组 g1 消费并提交 offset 之后,ZooKeeper 里 137 个 znode 的路径里没有任何一个含 g1:消费组 offset 不存 ZooKeeper,存在 Kafka 自己的内部主题 __consumer_offsets(它自己也是 /brokers/topics 下的一个主题)。", t=tl(S(2)), done=[0, 1], kv=KV([['分区元数据', '/brokers/topics/<t>/…'], ['消费 offset', '不在 ZooKeeper']], ['消费 offset'])),
    step(f"kill -9 当前 controller(broker {ct['dead']}):{ct['t_ctl']:.1f} s 后 /controller 换成了别的 broker,/controller_epoch {ct['ep0']} → {ct['ep1']};主题 t1 所有分区的 leader 也在 {ct['t_lead']:.1f} s 内全部离开了死掉的 broker。这个时间 ≈ 会话超时(我设为 6 s)—— Kafka 的故障发现速度由 zookeeper.session.timeout.ms 决定(本实验显式设为 6 s,默认值我没有测)。", t=tl(S(3)), mark=[1], b=bars([['controller 切换', ct['t_ctl'], f"{ct['t_ctl']:.1f} s"], ['分区 leader 全部迁走', ct['t_lead'], f"{ct['t_lead']:.1f} s"], ['会话超时(设置值)', 6.0, '6 s']], 8, done=[0, 1, 2]), kv=KV([['controller 切换', f"{ct['t_ctl']:.1f} s"], ['epoch', f"{ct['ep0']} → {ct['ep1']}"]], ['controller 切换'])),
    step("重新启动被杀的 broker:/brokers/ids 恢复成 3 个,t1 各分区的 ISR 又包含它。", t=tl(S(4)), done=[0], kv=KV([['重启', '回到 ISR']], ['重启'])),
    step(f"空闲的 Kafka 集群给 ZooKeeper 的负载:zk_znode_count={mn['zk_znode_count']},watch {mn['zk_watch_count']} 个,临时节点 {mn['zk_ephemerals_count']} 个(3 个 broker + controller),连接 {mn['zk_num_alive_connections']} 个。元数据量随分区数增长 —— 这是 Kafka 3.x 以前集群规模受限的原因之一(分区数的影响我没有在这里测)。", t=tl(S(5)), done=[0], kv=KV([['znode 数', mn['zk_znode_count']], ['watch 数', mn['zk_watch_count']]], ['znode 数'])),
]
A = dict(
    n=103, series='zookeeper', tags='ZooKeeper,Kafka,controller,真实验证,动画演示',
    desc=f'真实运行 Kafka 3.9.2 的 ZooKeeper 模式(3 个 broker):看它在 ZooKeeper 里建的节点(brokers/controller/分区状态)、消费组 offset 不在 ZooKeeper 里、kill -9 controller 后 {ct["t_ctl"]:.1f} s 换主(会话超时 6 s)、空闲集群的 ZooKeeper 负载。',
    lead='Kafka 4.0 之前,ZooKeeper 是 Kafka 集群的「元数据库」。这篇真起一个 3 broker 的 Kafka 3.9.2(ZooKeeper 模式),看它在 ZooKeeper 里到底存了什么、没有存什么(比如消费 offset),以及 controller 被杀之后多久恢复。',
    facts=[('临时节点', 'broker 注册与 controller 选举都靠临时节点'), ('不在 ZK', '消费组 offset 存在 __consumer_offsets 主题里,ZooKeeper 里没有'), (f'{ct["t_ctl"]:.1f} s', 'kill -9 controller 后 /controller 换主(会话超时 6 s)')],
    body=[
        sec('Kafka 在 ZooKeeper 里的节点', '', term('', blk('z103', 1)), '<p>整个 controller 选举就是<a href="zookeeper-leader-election.html">之前讲的 Leader 选举</a>:抢 <code>/controller</code> 这个临时节点。</p>'),
        sec('主题与分区', '', term('', blk('z103', 2))),
        sec('controller 被杀', '', term('', blk('z103', 3)), '<p>空窗由 broker 的会话超时决定,与<a href="zookeeper-session-expire.html">会话过期</a>那篇的结论一致。</p>'),
        sec('重启', '', term('', blk('z103', 4))),
        sec('对 ZooKeeper 的负载', '', term('', blk('z103', 5)), '<p>负载很小;但分区越多 znode 越多,watch 也越多,这与<a href="zookeeper-many-znodes.html">大量 znode</a>那篇的结论方向相同。</p>'),
        sec('分步演示', '', demo('Kafka 与 ZooKeeper', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Kafka 3.9.2(archive.apache.org 的 kafka_2.13-3.9.2.tgz,自带 ZooKeeper 3.8.4 客户端)连接我的 ZooKeeper 3.9.6;3 个 broker 端口 7901–7903,zookeeper.session.timeout.ms=6000,replica.lag.time.max.ms=10000;生产与消费用 kafka-python-ng', '没有验证:Kafka 旧版本(0.8 以前把消费 offset 存在 ZooKeeper 里)的历史说法、默认会话超时下的切换时间、大量分区时的 ZooKeeper 负载、/consumers 为什么还在、unclean leader election、ISR 变化通知(/isr_change_notification)的细节'],
)
