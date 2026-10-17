from lib import *
S = SS('q18')
steps = [
    step("在 n1 上声明 exchange x.meta 和队列 q.meta,n1、n2、n3 三个节点上的 list_exchanges / list_queues 看到的是同样的东西:x.meta,以及 q.meta(leader/所在节点是 n1)。元数据——用户、vhost、exchange、队列定义、绑定——在所有节点上一致。4.3.6 里存放它的是 Khepri(基于 Raft 的存储),feature flag khepri_db 的状态是 enabled。", t=tl(S(1)), mark=lidx(S(1), 'n2@localhost 上看到', 'n3@localhost 上看到'), done=lidx(S(1), 'n1@localhost 上看到', 'khepri_db'), kv=KV([['元数据', '每个节点都有一份'], ['存储', 'Khepri(Raft)'], ['q.meta', '定义到处可见,消息只在 n1']], ['元数据'])),
    step("经典队列 q.meta 只在 n1 上。客户端连到别的节点发布也行,消息被转发到 n1:带 confirm 同步发 3000 条的延迟,连 n1 时 p50 0.086 ms、p99 0.158 ms;连 n2 时 p50 0.122 ms、p99 0.219 ms;连 n3 时 p50 0.122 ms、p99 0.218 ms。多一跳带来约 0.036 ms(约 40%)的额外 p50 延迟——在本机回环上很小,跨机器会更明显。", t=tl(S(2)), mark=lidx(S(2), '连到 n2', '连到 n3'), done=lidx(S(2), '连到队列所在的 n1'), b=bars([['连 n1(队列所在)', 0.086, 'p50 0.086 ms'], ['连 n2', 0.122, 'p50 0.122 ms'], ['连 n3', 0.122, 'p50 0.122 ms']], 0.122, mark=[1, 2], done=[0]), kv=KV([['连队列所在节点', 'p50 0.086 ms'], ['连别的节点', 'p50 0.122 ms'], ['原因', '多一次节点间转发']], ['连别的节点'])),
    step("队列落在哪个节点:默认的 queue-leader-locator 是 client-local,谁声明就放在谁那里——从 n1、n2、n3 的客户端各声明 3 个 quorum 队列,leader 分布是各 3 个,loc.1.* 的 leader 全在 n1。如果全部从 n1 的客户端声明 9 个队列:不设策略的 cl.* 全是 n1(9 个);给这类队列设 policy queue-leader-locator=balanced 后,9 个 bal.* 的 leader 均匀落在 n1、n2、n3(各 3 个)。只从一个节点建队列的应用,要设 balanced,不然负载全压在一个节点上。", t=tl(S(3)), mark=lidx(S(3), '全部从 n1 的客户端声明 9 个队列'), done=lidx(S(3), '默认(client-local)', 'loc.1.*'), b=bars([['client-local: n1', 9, '9 个'], ['balanced: n1', 3, '3 个'], ['balanced: n2', 3, '3 个'], ['balanced: n3', 3, '3 个']], 9, mark=[0], done=[1, 2, 3]), kv=KV([['client-local', '放在声明它的客户端所连的节点'], ['balanced', '按各节点现有队列数放置'], ['风险', '所有队列都从一个节点建 → 全压一个节点']], ['client-local'])),
    step("节点离开:停掉 n3,cluster_status 里 Running Nodes 只剩 n1、n2,但 Disk Nodes 里 n3 还在——它还是集群的成员,只是没在跑。rabbitmqctl forget_cluster_node n3@localhost 才把它从成员里移除,之后 Disk Nodes 和 Running Nodes 都是 n1、n2。永久下线一个节点,要记得做这一步。", t=tl(S(4)), mark=lidx(S(4), 'forget_cluster_node', 'forget 之后'), done=lidx(S(4), '停掉 n3 之后'), kv=KV([['停掉节点', '仍是成员(Disk Nodes 里还在)'], ['forget_cluster_node', '把它移出成员'], ['永久下线', '必须 forget']], ['forget_cluster_node'])),
    step("Erlang cookie 不一致的节点加不进集群:新节点用另一个 HOME(另一个 .erlang.cookie),rabbitmqctl join_cluster 报 Feature flags: exception error {erpc,noconnection},最后 Error: aborted_feature_flags_compat_check {error,{erpc,noconnection}}。从错误里看不出“cookie 不对”——只是连不上。节点间能互相连是 cookie 相同的前提。", t=tl(S(5)), mark=lidx(S(5), 'noconnection', 'aborted_feature_flags_compat_check'), done=lidx(S(5), 'Clustering node'), kv=KV([['cookie 不同', '节点间 Erlang 连接建立不起来'], ['报错', 'noconnection,不提 cookie'], ['排查', '对比各节点的 .erlang.cookie']], ['cookie 不同'])),
    step("元数据的写需要多数派:3 个节点只剩 n1。往已有的 exchange 和队列发布一条消息(带 confirm)照样成功,只用 1 ms;可是声明一个新队列 q.new,20 秒都没有返回——元数据变更要通过 Khepri 的 Raft 提交,一个节点凑不齐 3 个里的多数。已有队列的数据路径不依赖它,新建/删除/绑定等变更都会卡住。", t=tl(S(6)), mark=lidx(S(6), '声明新队列 q.new'), done=lidx(S(6), '往已有的'), b=bars([['发布(已有队列)', 1, '1 ms'], ['声明新队列', 20000, '20 s 无返回']], 20000, mark=[1], done=[0]), kv=KV([['已有队列的收发', '照常'], ['元数据变更', '卡住(无多数派)'], ['3 节点', '至少 2 个在线']], ['元数据变更'])),
]
A = mkartq('q18', 18, 'RabbitMQ,集群,Khepri,元数据,queue-leader-locator,forget_cluster_node,真实验证,动画演示',
    '在 3 节点 RabbitMQ 4.3.6 集群上实测:元数据在所有节点上(Khepri 存储),消息只在队列所在节点;连别的节点发布 p50 多 0.036 ms;client-local 把队列放在声明它的节点,balanced 策略让 9 个队列均分;停掉的节点仍是成员,要 forget_cluster_node;cookie 不一致只报 noconnection;只剩 1/3 节点时已有队列照常收发、新建队列卡住。',
    '集群里到底哪些东西是所有节点共享的,哪些只在一个节点?队列放在哪个节点由谁决定?节点永久下线要做什么?少数派的节点能做什么、不能做什么?这篇起了一个真实的三节点集群一项项验证。',
    [('+0.036 ms', '经典队列在 n1,客户端连别的节点发布 p50 比直连多出的延迟'), ('9 → 3+3+3', '全部从 n1 声明 9 个队列:client-local 全在 n1,balanced 均分到三个节点'), ('20 s', '三个节点只剩一个时声明新队列的等待——没有返回')],
    [('元数据', '<p>用户、vhost、exchange、队列定义和绑定在每个节点上都有,4.3.6 的元数据存储是基于 Raft 的 Khepri。队列里的消息则只在队列所在的节点(经典队列)或副本节点(quorum / stream)。</p>'),
     ('多一跳', '<p>客户端可以连任意节点操作任意队列,不在队列所在节点时消息被转发,本机上 p50 从 0.086 ms 增加到 0.122 ms。</p>'),
     ('队列放哪里', '<p>默认 <code>queue-leader-locator=client-local</code>:放在声明它的客户端所连的节点;<code>balanced</code> 按节点现有队列数放置。队列都从同一个节点创建的应用要设成 balanced。</p>'),
     ('节点离开', '<p>停掉的节点仍是集群成员(Disk Nodes 里还在),永久下线要 <code>rabbitmqctl forget_cluster_node</code>。</p>'),
     ('cookie', '<p>节点靠相同的 Erlang cookie 互相认证。cookie 不一致时 join_cluster 只报 noconnection,看不出是 cookie 的问题。</p>'),
     ('少数派', '<p>元数据变更需要多数派。三个节点只剩一个时,已有队列的发布照常,新建队列等不到返回。</p>')],
    steps,
    [ENV_Q + '。集群是 3 个本机节点(各自的数据目录、端口、节点名 n1~n3,共享同一个 .erlang.cookie);延迟用同步 confirm 发布 3000 条取 p50 / p99,各连接 3 轮取中位数;cookie 不一致的节点是另一个 HOME 里写了不同 cookie 的新节点',
     '没有验证:真实多机网络下的转发延迟;网络分区(而不是节点被杀)下 Khepri 的表现(见第 19 篇);滚动升级;节点数为 5、7 时的多数派;vhost 的 default-queue-type;队列迁移(rebalance)命令;客户端负载均衡'],
    '集群')
