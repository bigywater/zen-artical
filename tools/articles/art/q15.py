from lib import *
S = SS('q15')
steps = [
    step("三个节点(n1、n2、n3)组成的集群,rabbitmqctl cluster_status 里 Disk Nodes 和 Running Nodes 都是 n1、n2、n3,Versions 都是 RabbitMQ 4.3.6 on Erlang 28.5.0.7。集群之间共享的是元数据(用户、vhost、exchange、队列定义、绑定),队列里的消息却只存在队列所在的节点——这是理解下面几节的前提。", t=tl(S(1)), mark=lidx(S(1), 'Disk Nodes', 'Running Nodes'), done=lidx(S(1), 'Versions'), kv=KV([['共享', '元数据:vhost / exchange / 队列定义 / 绑定'], ['不共享', '经典队列里的消息,只在队列所在节点'], ['节点数', '3']], ['不共享'])),
    step("在 n1 上声明两个队列各放 1000 条持久化消息:经典队列 cq 的 type=classic,leader=n1,members 只有 [n1];quorum 队列 qq 的 type=quorum,leader=n1,members=[n1, n2, n3],online 也是三个。同一个集群里,经典队列是单副本,quorum 队列默认三个节点各一份。(qq 行的 messages=0 是 list_queues 的统计还没刷新,不是消息丢了。)", t=tl(S(2)), mark=lidx(S(2), 'cq\tclassic', 'qq\tquorum'), done=lidx(S(2), 'name\ttype'), kv=KV([['classic', '1 个成员(n1)'], ['quorum', '3 个成员,leader + 2 follower'], ['list_queues', 'type / leader / members / online']], ['quorum'])),
    step("经典队列的镜像(ha-mode)在 4.3.6 里已经没有了:rabbitmqctl set_policy 设 {\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"},直接 Validation failed,提示这两个键 are not recognised policy settings;list_deprecated_features 里 classic_queue_mirroring 的阶段是 removed、状态 denied。cq 仍然只有 n1 一个成员。以前靠 ha-mode 做的高可用,现在要用 quorum 队列(或 stream)。", t=tl(S(3)), mark=lidx(S(3), 'Validation failed', 'are not recognised'), done=lidx(S(3), '策略生效后 cq 仍是', 'classic_queue_mirroring'), kv=KV([['ha-mode / ha-sync-mode', '不被识别,set_policy 失败'], ['classic_queue_mirroring', 'removed'], ['替代', 'quorum 队列']], ['ha-mode / ha-sync-mode'])),
    step("kill -9 掉 n1:quorum 队列 qq 从杀掉到第一次带 confirm 发布成功只用了 303 ms,list_queues 里 leader 已经是 n2,online=[n2, n3](n1 还在 members 里,只是不在线),n2 上能把队列取空,共 1001 条(1000 条原有 + 杀掉之后发的 1 条)。经典队列 cq 只在 n1 上,从 n2 去 passive declare 它,等了 66.6 s 才失败:404 NOT_FOUND failed to perform operation on queue 'cq' … due to timeout。单副本的队列,节点一死就既不可用、客户端还要等很久。", t=tl(S(4)), mark=lidx(S(4), '303 ms', '66.6 s'), done=lidx(S(4), 'qq\tquorum', '共 1001 条'), b=bars([['quorum 恢复可用', 303, '303 ms'], ['classic 报错', 66600, '66.6 s']], 66600, mark=[0, 1]), kv=KV([['quorum', '303 ms 内新 leader 就绪'], ['classic', '队列不可用,66.6 s 超时才报错'], ['数据', 'quorum 1001 条一条没丢']], ['quorum'])),
    step("重启 n1:经典队列 cq 回来了,messages=1000,取一条是 m0——持久化的消息还在,只是它在 n1 down 的这段时间里不可用。quorum 队列 qq 的 leader 仍然是 n2(杀掉 n1 后选出来的那个,不会自动还给 n1),n1 回来后作为 follower 加入,online 又是三个。", t=tl(S(5)), mark=lidx(S(5), 'cq\tclassic', "取一条"), done=lidx(S(5), 'qq\tquorum'), kv=KV([['classic', '重启后恢复,消息还在'], ['quorum', 'n1 作为 follower 追上'], ['leader', '不会自动回到 n1']], ['classic'])),
    step("复制的代价:同一个集群里带 confirm 异步发布 20000 条 100 字节的持久化消息(在途 1000),3 轮取中位数:classic(1 副本)371 ms(53882 条/秒),quorum(3 副本)372 ms(53750 条/秒),几乎一样。三副本的 Raft 写入在本机回环上没有比单副本慢多少——代价只有在真实网络、真实磁盘上才会显出来(这里没有测)。", t=tl(S(6)), mark=lidx(S(6), 'bench.quorum'), done=lidx(S(6), 'bench.classic'), b=bars([['classic 1 副本', 53882, '53882 条/秒'], ['quorum 3 副本', 53750, '53750 条/秒']], 53882, mark=[1], done=[0]), kv=KV([['classic', '371 ms'], ['quorum', '372 ms'], ['结论', '本机回环上看不出复制代价']], ['结论'])),
]
A = mkartq('q15', 15, 'RabbitMQ,quorum队列,镜像队列,ha-mode,集群,真实验证,动画演示',
    '在 3 节点 RabbitMQ 4.3.6 集群上对比 quorum 队列和经典队列:ha-mode 策略已被移除(set_policy 失败,classic_queue_mirroring=removed);kill -9 队列所在节点后,quorum 队列 303 ms 就能继续发布且不丢数据,经典队列要等 66.6 s 超时;本机回环上 3 副本与单副本的吞吐几乎一样。',
    '镜像队列(ha-mode)曾是 RabbitMQ 高可用的标配,quorum 队列取代了它。到了 4.3.6 镜像到底还剩什么?杀掉队列所在的节点,两种队列分别怎么表现?三副本写入的吞吐代价有多大?这篇起了一个真实的三节点集群来验证。',
    [('303 ms', 'kill -9 掉 quorum 队列 leader 所在节点后,到能带 confirm 继续发布的时间'), ('66.6 s', '经典队列所在节点被杀后,客户端访问该队列等到超时报 404 的时间'), ('removed', '4.3.6 里 classic_queue_mirroring 的废弃阶段,ha-mode 策略已被拒绝')],
    [('集群里放什么', '<p>集群共享元数据(用户、vhost、exchange、队列定义、绑定),而经典队列的消息只存在它所在的节点。所以“节点挂了”对单副本的经典队列是实打实的不可用。</p>'),
     ('队列成员', '<p><code>rabbitmqctl list_queues name type leader members online</code> 能看到每个队列的类型、leader、成员和在线成员:经典队列只有一个成员,quorum 队列默认每个节点一个副本。</p>'),
     ('镜像队列已移除', '<p>在 4.3.6 里设置 <code>ha-mode</code> 策略直接被拒绝(not recognised policy settings),<code>classic_queue_mirroring</code> 的阶段是 removed。想要多副本就用 quorum 队列。</p>'),
     ('节点挂了', '<p>杀掉 leader 所在的节点后,quorum 队列在 303 ms 内选出新 leader 继续服务,数据没丢;经典队列要等客户端超时(66.6 s)才报 404。</p>'),
     ('恢复', '<p>节点回来后经典队列的持久消息还在,quorum 队列的副本作为 follower 追上进度,leader 不会自动回到原来的节点。</p>'),
     ('复制的代价', '<p>在本机回环上,三副本的 quorum 队列和单副本经典队列的发布吞吐几乎一样(53750 与 53882 条/秒)。真实网络、磁盘上的代价没有在这里测。</p>')],
    steps,
    [ENV_Q + '。集群是 3 个本机节点(n1、n2、n3,每个独立的数据目录与端口),节点通过 join_cluster 加入;kill -9 的恢复时间来自循环重连并带 confirm 发布的第一次成功;经典队列的超时是客户端 passive declare 等到的 404;吞吐是 pika SelectConnection 异步 confirm 发布 20000 条,3 轮取中位数',
     '没有验证:跨机器网络下的复制延迟;磁盘慢时 quorum 的吞吐;多于 3 个成员的 quorum 队列;节点被杀时在途消息的结果(只看了杀掉之后的第一次成功发布);退役 / 滚动升级;选举时间的分布(只测了一次 303 ms,没有多次统计)'],
    'quorum 与镜像')
