from lib import *
S = SS('q19')
steps = [
    step("分区处理策略 cluster_partition_handling 在 4.3.6 里没配置就是 undefined(行为等同 ignore)。准备:经典队列 cq1 在 n1、cq3 在 n3、quorum 队列 qq 的 leader 在 n3,各放 10 条持久化消息。4.3.x 的元数据存储是 Khepri(基于 Raft),分区时是否能写元数据,看的是有没有多数派,而不是这个配置项。", t=tl(S(1)), mark=lidx(S(1), 'undefined'), done=lidx(S(1), '队列: cq1'), kv=KV([['cluster_partition_handling', '默认没配置(undefined)'], ['元数据', 'Khepri:多数派才能写'], ['准备', 'cq1@n1、cq3@n3、qq(leader n3)']], ['cluster_partition_handling'])),
    step("制造分区 {n1, n2} | {n3}:把 n3 自己的 Erlang cookie 改掉并断开所有连接——n3 和另外两个节点都连不上彼此,但进程都活着(模拟网络不通)。从 n1 看 Running Nodes 只剩 n1、n2;从 n3 看 Running Nodes 只剩 n3;两边的 Network Partitions 都是 (none)。各自都认为对方是“down”,没有“partition 被检测到”的记录。", t=tl(S(2)), mark=lidx(S(2), '从 n1@localhost 看', '从 n3@localhost 看'), done=lidx(S(2), '从 n1@localhost 看'), kv=KV([['n1 看到', 'Running = n1、n2'], ['n3 看到', 'Running = n3'], ['Network Partitions', '两边都是 (none)']], ['Network Partitions'])),
    step("分区期间两边各自能做什么:多数派侧 n1 声明新队列 new.maj 立刻成功;少数派侧 n3 声明新队列 new.min 15 秒都没有返回(元数据写需要多数派)。往已有队列发布:n3 往本地的经典队列 cq3、n1 往 n1 上的经典队列 cq1 都立刻带 confirm 成功;quorum 队列 qq 在多数派侧选出了新 leader(n2,online 只有 n2、n1),n1 往它发布成功;n3 往 qq 发布 10 秒没有返回——少数派侧没有多数,写不进。单副本的经典队列两边各自照常工作,quorum 只有多数派那边活着。", t=tl(S(3)), mark=lidx(S(3), '少数派侧 n3', 'n3 往 quorum 队列 qq'), done=lidx(S(3), '多数派侧 n1', 'n3 往本地', 'n1 往 n1 上', 'n1 往 quorum', 'list_queues'), kv=KV([['多数派侧', '元数据 + quorum 都能写'], ['少数派侧', '元数据与 quorum 写挂起'], ['本地经典队列', '两边照常']], ['少数派侧'])),
    step("恢复网络(cookie 改回来、重新连接)后:从 n1 和 n3 看 Running Nodes 都是三个节点,Network Partitions 是 (none)——没有需要人工重启的“已检测到分区”状态,不像旧版 Mnesia 那样要手工处理。分区期间 n3 本地写进 cq3 的 1 条消息还在,取出共 11 条(10 + 1);cq1 取出 11 条;愈合后在 n3 上声明新队列 new.after 立刻成功。", t=tl(S(4)), mark=lidx(S(4), '愈合后从 n1', '愈合后从 n3'), done=lidx(S(4), 'cq3', 'cq1', 'new.after'), b=bars([['cq3 取出', 11, '11 条 (10+1)'], ['cq1 取出', 11, '11 条']], 11, done=[0, 1]), kv=KV([['愈合后', '自动重新成为一个集群'], ['人工干预', '不需要重启'], ['分区期间的本地写', '保留(经典队列)']], ['愈合后'])),
    step("pause_minority 在 4.3.6 里的表现:配置 cluster_partition_handling = pause_minority 后(eval 返回 {ok,pause_minority}),用同样的方法隔离 n3,等 10 秒:客户端仍然能连 n1,也仍然能连 n3 的 AMQP 端口——n3 没有按这个策略“暂停”。n1 看到 Running Nodes 是 n1、n2;愈合后 n3 可以连接,自动恢复。也就是说这个老配置项在 Khepri 的 4.3.6 里没有观察到我预期的效果(预期是少数派节点关闭监听);多数/少数的行为来自 Khepri 与 quorum 队列自己的多数派规则,而不是这个设置。", t=tl(S(5)), mark=lidx(S(5), '客户端连 n3@localhost', '{ok,pause_minority}'), done=lidx(S(5), '客户端连 n1@localhost', '愈合后客户端连 n3'), kv=KV([['pause_minority', '配置生效({ok,pause_minority})'], ['n3 被隔离 10 s 后', '仍接受 AMQP 连接'], ['实际的保护', 'Khepri / quorum 的多数派规则']], ['n3 被隔离 10 s 后'])),
]
A = mkartq('q19', 19, 'RabbitMQ,网络分区,partition handling,pause_minority,Khepri,真实验证,动画演示',
    '在 3 节点 RabbitMQ 4.3.6 集群上真实隔离一个节点:多数派侧能建新队列、quorum 队列选出新 leader 继续写;少数派侧元数据写和 quorum 写都挂起,但本地经典队列照常;愈合后自动恢复且 Network Partitions 为空、分区期间的本地消息保留;pause_minority 在这里没有让少数派节点拒绝连接。',
    '网络分区是集群最危险的故障。4.3.6 用 Khepri 存元数据、quorum 队列用 Raft,分区时到底哪一边还能工作?cluster_partition_handling 还有用吗?愈合后要人工处理吗?这篇真的把一个节点隔离出去观察。',
    [('15 秒', '少数派节点声明新队列时的等待——挂起,没有返回'), ('11 条', '分区期间少数派节点本地写入的经典队列愈合后取出的条数(10 + 1),一条没丢'), ('(none)', '愈合后 Network Partitions 的内容——没有需要手工处理的分区状态')],
    [('怎么隔离', '<p>把一个节点自己的 Erlang cookie 改掉并断开连接:它和其余节点都互相连不上,但进程还在运行。这比直接 kill 更接近“网络不通”,因为少数派一侧还在接受客户端连接。</p>'),
     ('多数派一侧', '<p>元数据可写(新队列声明成功),quorum 队列重新选出 leader,发布成功。</p>'),
     ('少数派一侧', '<p>声明新队列和写 quorum 队列都会一直挂起;只靠本地数据的经典队列照常收发——这也意味着少数派一侧可能继续接收一些只存在这一侧的消息。</p>'),
     ('愈合', '<p>网络恢复后集群自动合并,Network Partitions 为空,不需要重启节点;经典队列在分区期间收到的消息保留。</p>'),
     ('旧配置项', '<p><code>cluster_partition_handling</code> 默认没有配置。配成 <code>pause_minority</code> 后,被隔离的节点在 10 秒内仍然接受 AMQP 连接,没有观察到暂停。这是在 4.3.6 上的观察,没有进一步查源码确认原因。</p>')],
    steps,
    [ENV_Q + '。集群是 3 个本机节点;分区是把 n3 的 Erlang cookie 改成别的值并断开,别的节点连不上它、它也连不上别的节点(rabbitmqctl 用 --erlang-cookie 访问被隔离的 n3);愈合是改回 cookie 并重新 connect_node;挂起的操作各等 10~15 秒',
     '没有验证:真实的网络丢包 / 延迟型分区(这里是完全断开);非对称分区(A 能连 B、B 能连 C、A 连不上 C);pause_minority 与 autoheal 在更长等待时间下的行为;分区期间 quorum 队列的 leader 在少数派一侧时的消息归宿(这里 leader 在 n3,多数派侧重选了 leader,n3 侧写入挂起,愈合后挂起的发布结果没有跟踪);大消息量下愈合的追赶时间'],
    '网络分区')
