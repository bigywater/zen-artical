from lib import *
S = SS('q13')
steps = [
    step("x-max-length=5、默认溢出策略 drop-head:发 m0~m9 共 10 条,队列里剩 m5、m6、m7、m8、m9——最新的 5 条留下,最老的 5 条被丢掉,发布方没有任何通知。", t=tl(S(1)), mark=lidx(S(1), '队列里剩'), done=lidx(S(1), '队列里剩'), b=bars([['发布', 10, '10 条'], ['留下', 5, '5 条 (m5~m9)']], 10, mark=[1], done=[0]), kv=KV([['drop-head', '挤掉最老的'], ['通知', '没有'], ['留下', '最新的 5 条']], ['drop-head'])),
    step("x-overflow=reject-publish:队列满了拒绝新的。不开 confirm 连发 10 条,队列里是最先到的 m0~m4,后 5 条悄悄丢了,发布方不知道;开 confirm 发 10 条的结果是 5 个 ack 后 5 个 NACK(NackError)。同样的“满”,drop-head 丢旧的,reject-publish 丢新的并(在有 confirm 时)告诉发布方。", t=tl(S(2)), mark=lidx(S(2), '开 confirm 发 10 条'), done=lidx(S(2), '不开 confirm 发 10 条'), kv=KV([['reject-publish', '丢新的'], ['没开 confirm', '发布方不知道'], ['开 confirm', '收到 Nack']], ['reject-publish'])),
    step("x-overflow=reject-publish-dlx:被拒绝的新消息不是丢弃,而是进死信交换机。上限 3、发 m0~m5:主队列留下 m0、m1、m2,死信队列收到 m3、m4、m5,reason 都是 maxlen。对比 drop-head + 死信:主队列留下 m3、m4、m5,被挤出去的最老的 m0、m1、m2 进死信队列。两种策略死的是不同的消息,reason 都叫 maxlen。", t=tl(S(3)), mark=lidx(S(3), '死信队列: [(', '对比 drop-head'), done=lidx(S(3), '主队列:'), kv=KV([['reject-publish-dlx', '新消息死信'], ['drop-head + 死信', '最老的死信'], ['reason', '都是 maxlen']], ['reason'])),
    step("x-max-length-bytes:100 字节的消息体、限制 1000 字节,发 30 条留下 10 条;再给每条加上约 100 字节的头和属性,仍是留下 10 条——限制只数消息体,不数属性。单条 2000 字节(比整个限制还大)的消息发 3 条,留下 0 条。", t=tl(S(4)), mark=lidx(S(4), '留下 0 条', '不数属性'), done=lidx(S(4), '留下 10 条(100'), b=bars([['100 字节×30', 10, '留下 10 条'], ['加头/属性', 10, '留下 10 条'], ['单条 2000 字节×3', 0, '留下 0 条']], 10, mark=[2], done=[0, 1]), kv=KV([['数什么', '只数消息体字节'], ['不数', '头和属性'], ['超大单条', '直接留不下']], ['数什么'])),
    step("两个限制一起设,先到的算:max-length=10 且 max-bytes=500,发 20 条 100 字节,留下 5 条(字节限制先到)。队列参数 x-max-length=10 再加一条 policy max-length=4,发 20 条留下 4 条——队列参数和 policy 同时存在时取较小的那个。", t=tl(S(5)), mark=lidx(S(5), '留下 5 条', '留下 4 条'), done=lidx(S(5), '留下 5 条'), kv=KV([['长度 + 字节', '先到的生效'], ['参数 + policy', '取较小的'], ['policy 好处', '不用重建队列就能改']], ['参数 + policy'])),
    step("未确认的消息不占长度限制:max-length=3,消费者先取走 3 条不 ack,此时 (ready, unacked) = (0, 3);再发 10 条,(ready, unacked) = (3, 3)——ready 里只留 3 条,unacked 里的 3 条不计入。所以上限只约束 ready,实际队列里可以有 ready + unacked 那么多。", t=tl(S(6)), mark=lidx(S(6), '(3, 3)'), done=lidx(S(6), '(0, 3)'), b=bars([['取走 3 条后 ready', 0, '0'], ['取走 3 条后 unacked', 3, '3'], ['再发 10 条后 ready', 3, '3'], ['再发 10 条后 unacked', 3, '3']], 3, mark=[2], done=[0, 1, 3]), kv=KV([['限制范围', '只管 ready'], ['unacked', '不计入'], ['实际上限', '≈ max-length + prefetch 在途']], ['限制范围'])),
    step("quorum 队列也支持 x-max-length,但 reject-publish 是“大约”的:drop-head 连发 10 条留下 m5~m9 和经典队列一致;reject-publish 不开 confirm 连发 10 条(上限 5)却留下了 10 条;开 confirm、每条间隔 10 ms 发 30 条的结果是 AAAAAA 后全是 N——先 6 个 Ack 才开始拒绝,队列里最后 6 条,比上限 5 多一条。快速连发时 quorum 队列不能当成精确的限流器。", t=tl(S(7)), mark=lidx(S(7), '留下 10 条', 'AAAAAANNN'), done=lidx(S(7), 'drop-head'), b=bars([['上限', 5, '5'], ['连发 10 条后留下', 10, '10'], ['逐条 confirm 后留下', 6, '6']], 10, mark=[1], done=[0, 2]), kv=KV([['drop-head', '与经典队列一致'], ['reject-publish', '连发时会超限'], ['逐条 confirm', '多 1 条后才拒绝']], ['reject-publish'])),
]
A = mkartq('q13', 13, 'RabbitMQ,队列长度限制,x-max-length,overflow,drop-head,reject-publish,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测队列长度限制:drop-head 丢最老的、reject-publish 丢新的并在有 confirm 时 Nack、reject-publish-dlx 把新的死信;x-max-length-bytes 只数消息体;参数与 policy 取较小的;unacked 不计入;quorum 队列的 reject-publish 连发时会超限(连发 10 条全留下,上限 5)。',
    '队列长度限制是保护 broker 的第一道防线,但“满了之后丢谁”“限制到底数什么”“quorum 队列也一样吗”都有细节。这篇在 RabbitMQ 4.3.6 上把每种溢出策略和计数口径都量一遍。',
    [('m5~m9', 'drop-head 上限 5、发 10 条后留下的消息——最老的 5 条被丢'), ('0 条', '单条 2000 字节、字节上限 1000 时留下的消息数'), ('10 > 5', 'quorum 队列 reject-publish、上限 5,不开 confirm 连发 10 条后队列里的条数')],
    [('drop-head', '<p>默认策略:队列满了把队头(最老的)挤出去,留下最新的。没有通知,配了死信交换机时则变成 maxlen 死信(见死信那篇)。</p>'),
     ('reject-publish', '<p>满了拒绝新发布。开了 publisher confirm 的发布方收到 Nack;没开就悄悄丢。</p>'),
     ('reject-publish-dlx', '<p>在拒绝新发布的同时把被拒绝的消息送进死信交换机,reason=maxlen。</p>'),
     ('按字节限制', '<p><code>x-max-length-bytes</code> 只数消息体,不数头和属性;比上限还大的单条消息留不下来。</p>'),
     ('参数与 policy', '<p>队列参数和 policy 同时给了长度限制,取较小的;和字节限制一起设,先到的生效。policy 的好处是可以不重建队列就改。</p>'),
     ('unacked 不算', '<p>已经投递出去等确认的消息不计入长度,所以 ready + unacked 可以超过上限。</p>'),
     ('quorum 队列', '<p>drop-head 与经典队列一致;reject-publish 不精确:快速连发会超限,逐条 confirm 时也多收一条才开始 Nack。</p>')],
    steps,
    [ENV_Q + '。读队列内容用 basic_get 取空;第六节 (ready, unacked) 来自 rabbitmqctl list_queues;第七节 reject-publish 的 confirm 实验每条间隔 10 ms',
     '没有验证:policy 的 max-length 与 operator policy 的优先级;stream 队列的长度限制(用 retention,见第 17 篇);集群里 quorum 的限制精度在节点故障时;更大的消息、更高的并发下 quorum reject-publish 超出上限的幅度;x-max-length-bytes 在 quorum 队列上的口径'],
    '队列长度限制')
