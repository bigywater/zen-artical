from lib import *
S = SS('q16')
steps = [
    step("rabbitmq-queues quorum_status rq 列出每个成员的 Raft 状态:刚建好的 quorum 队列 rq,n1 是 leader,n2、n3 是 follower,三个成员的 Term 都是 1,Last Log、Commit、Applied 都是 2——日志里已经有两条条目(建队列和选主时写进去的),三个成员完全同步。quorum 队列的每个队列就是一个独立的 Raft 组。", t=tl(S(1)), mark=lidx(S(1), 'leader', 'follower'), done=lidx(S(1), 'Raft 状态', '$ rabbitmq-queues'), kv=KV([['每个 quorum 队列', '一个独立的 Raft 组'], ['成员', '1 个 leader + 2 个 follower'], ['初始日志', 'index 2,term 1']], ['每个 quorum 队列'])),
    step("发布 1000 条消息(每条等 confirm)之后:三个成员的 Last Log、Commit Index、Last Applied 全是 1003,Term 仍是 1,leader 还是 n1。每条消息一条日志条目(1003 = 原来的 2 + 1000 条消息 + 另外 1 条内部条目,具体是什么我没有查);leader 把条目复制给 follower,多数派落盘后才提交,提交了才回 confirm,所以平静时三个成员的下标一致。", t=tl(S(2)), mark=lidx(S(2), '1003'), done=lidx(S(2), '当前 leader'), b=bars([['Last Log', 1003, '1003'], ['Commit Index', 1003, '1003'], ['Last Applied', 1003, '1003']], 1003, mark=[1]), kv=KV([['每条消息', '一条 Raft 日志条目'], ['confirm', '多数派落盘并提交后才回'], ['平静时', '三个成员下标一致']], ['confirm'])),
    step("杀掉 leader 所在的 n1(kill -9):从杀掉到第一次带 confirm 的发布成功只用了 360 ms。quorum_status 里 n1 显示 noconnection,剩下 n3 成了新 leader(Term 从 1 变成 2),n2 是 follower,两者的 Last Log / Commit / Applied 都是 1008。Term 加 1 就是一次选举;follower 发现 leader 没有心跳,发起选举,拿到多数票的成为新 leader。", t=tl(S(3)), mark=lidx(S(3), '360 ms', 'noconnection'), done=lidx(S(3), 'n3    leader', 'n2    follower'), b=bars([['Term 之前', 1, '1'], ['Term 之后', 2, '2']], 2, mark=[1], done=[0]), kv=KV([['选举', 'Term 1 → 2'], ['时间', '360 ms 内恢复发布'], ['n1', 'noconnection,日志下标未知']], ['选举'])),
    step("再杀一个,3 个成员只剩 1 个:带 confirm 的发布等 8 秒仍然没有 ack 也没有 nack——写必须多数派(3 个里的 2 个)确认,一个人凑不齐就一直等;basic_get 则是直接失败,broker 关闭连接,541 INTERNAL_ERROR \"Cannot get a message from queue 'rq'…\"。没有多数派时 quorum 队列选择一致性:宁可不可用,也不接收可能丢的写入。", t=tl(S(4)), mark=lidx(S(4), '仍在等待 confirm', 'ConnectionClosedByBroker'), done=lidx(S(4), '只剩 1/3'), kv=KV([['发布', '一直等,没有 ack / nack'], ['basic_get', '直接失败(541)'], ['原则', '没有多数派就不接受写']], ['发布'])),
    step("把被杀的两个节点重新启动:之前挂起的那条发布最终得到了 ack,三个成员追平,Term 变成 3(又一次选举),Last Log / Commit / Applied 都是 1015,n3 仍是 leader,n1、n2 是 follower。队列里共有 1002 条,正好是 1000 + 选举后的 1 条 + 无多数派时的 1 条(挂起的那条没有丢);之前挂起的 basic_get 没有取到消息。", t=tl(S(5)), mark=lidx(S(5), '最终结果: ack', '1002 条'), done=lidx(S(5), 'n3    leader'), kv=KV([['挂起的发布', '恢复后得到 ack'], ['Term', '3(又选了一次)'], ['队列', '1002 条,一条没丢']], ['挂起的发布'])),
    step("写路径的代价:同一个集群里,成员数为 1 的 quorum 队列 rq1(只有 n2)和成员数为 3 的 rq3,带 confirm 异步发布 20000 条 100 字节的持久化消息(在途 1000,3 轮中位数):rq1 333 ms(60126 条/秒),rq3 396 ms(50514 条/秒),三副本慢约 19%——多出来的是向两个 follower 复制并等一个确认。", t=tl(S(6)), mark=lidx(S(6), 'rq3: 396 ms', 'rq3: members'), done=lidx(S(6), 'rq1: 333 ms', 'rq1: members'), b=bars([['rq1 (1 成员)', 60126, '60126 条/秒'], ['rq3 (3 成员)', 50514, '50514 条/秒']], 60126, mark=[1], done=[0]), kv=KV([['1 成员', '333 ms'], ['3 成员', '396 ms(慢约 19%)'], ['原因', '复制给 follower 并等多数派']], ['3 成员'])),
]
A = mkartq('q16', 16, 'RabbitMQ,quorum队列,Raft,选举,多数派,真实验证,动画演示',
    '在 3 节点 RabbitMQ 4.3.6 集群上看 quorum 队列的 Raft:quorum_status 里的 Term 与日志下标;发布 1000 条后三成员下标一致;杀掉 leader 360 ms 内选出新 leader(Term 1→2);只剩 1/3 成员时发布一直挂起、basic_get 报 541;恢复后挂起的发布得到 ack,1002 条一条不丢;3 副本比 1 副本慢约 19%。',
    'quorum 队列每个队列是一个 Raft 组:leader、follower、term、日志下标到底长什么样?杀掉 leader 选举要多久?只剩一个节点时发布和读取各是什么表现?这篇用 rabbitmq-queues quorum_status 一步步看。',
    [('Term 1→2→3', '每次选举 Term 加 1;杀 leader 一次、恢复时再选一次'), ('360 ms', 'kill -9 掉 leader 后,quorum 队列重新能带 confirm 发布的时间'), ('1002 条', '无多数派时挂起的发布恢复后也得到 ack,一条没丢')],
    [('Raft 组', '<p>每个 quorum 队列有自己的一个 Raft 组:一个 leader 和若干 follower(默认三个成员)。<code>rabbitmq-queues quorum_status</code> 给出每个成员的 Raft 状态、Term 和日志下标(Last Log、Commit Index、Last Applied)。</p>'),
     ('写入路径', '<p>发布的消息先到 leader,作为日志条目复制给 follower,多数派落盘后提交,提交后才回 publisher confirm。平静时三个成员的下标一致。</p>'),
     ('选举', '<p>leader 所在节点被杀后,剩下的成员发现没有心跳,发起选举,Term 加 1,拿到多数票的成为新 leader,本次实测 360 ms 内恢复发布。</p>'),
     ('没有多数派', '<p>三个成员只剩一个时写入一直挂起(没有 ack 也没有 nack),读取直接报错。quorum 队列选择一致性。</p>'),
     ('恢复', '<p>节点回来、追平日志后,挂起的发布得到 ack,数据一条不丢。</p>'),
     ('代价', '<p>三成员比单成员慢了约 19%(396 对 333 ms 发布 20000 条),在本机回环上。</p>')],
    steps,
    [ENV_Q + '。集群是 3 个本机节点;quorum_status 用 rabbitmq-queues --formatter json 取出后自己排版;选举时间是循环重试带 confirm 发布的第一次成功;无多数派的试验杀了两个节点,发布与 basic_get 各等 8 秒;吞吐是 pika SelectConnection 异步 confirm 发布,3 轮取中位数',
     '没有验证:网络分区(而不是节点被杀)下的行为;Raft 日志的 snapshot / 截断与 WAL、segment 文件;选举超时的参数调整;多次选举时间的分布(只测了一次 360 ms);大消息、多队列并发时 WAL 的写入合并;成员加减(grow / shrink)的过程'],
    'quorum 与 Raft')
