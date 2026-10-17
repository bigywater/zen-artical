from lib import *
S = SS('q24')
steps = [
    step("consumer_timeout 的默认值:不改配置的节点上 rabbitmqctl eval \"application:get_env(rabbit, consumer_timeout).\" 返回 {ok,1800000}——30 分钟;在 rabbitmq.conf 里写 consumer_timeout = 10000 后,同样的命令返回 {ok,10000}。配置项被识别、被读到,和 rabbit.schema 里的说明一致:它是“消费者处理一条消息的大致最长时间,超过则终止 channel”(单位毫秒)。", t=tl(S(1)), mark=lidx(S(1), '{ok,10000}'), done=lidx(S(1), '{ok,1800000}'), b=bars([['默认', 1800000, '1,800,000 ms'], ['这里的配置', 10000, '10,000 ms']], 1800000, mark=[1], done=[0]), kv=KV([['默认', '1800000 ms = 30 分钟'], ['配置项', 'consumer_timeout(毫秒)'], ['作用', '未确认太久 → 终止 channel']], ['默认'])),
    step("单个队列的覆盖方式:经典队列声明时带 x-consumer-timeout=2000,被拒绝:406 PRECONDITION_FAILED invalid arg 'x-consumer-timeout' for queue … of queue type rabbit_classic_queue;quorum 队列带同样的参数则声明成功。policy 方式 consumer-timeout 的 set_policy 也成功(list_policies 里有 ct-pol,定义 {\"consumer-timeout\":3000})。也就是说按队列覆盖超时的参数只有 quorum 队列接受,经典队列不接受队列参数,可以走 policy。", t=tl(S(2)), mark=lidx(S(2), '经典队列带 x-consumer-timeout', 'quorum 队列带'), done=lidx(S(2), 'set_policy', 'list_policies'), kv=KV([['经典队列 + x-consumer-timeout', '406 invalid arg'], ['quorum 队列 + x-consumer-timeout', '成功'], ['policy consumer-timeout', 'set_policy 成功']], ['经典队列 + x-consumer-timeout'])),
    step("真正去触发它:consumer_timeout 配成 10 s,一个消费者(prefetch=10)收到消息后一直不确认,经典队列和 quorum 队列各一个,等 420 秒(7 分钟,心跳正常):channel 没有被关。经典队列的 (ready, unacked) 是 (0, 1),这条消息一直在“未确认”里;quorum 队列的统计是 (1, 0)(这个统计与消息是否仍被消费者持有是否一致,我没有核实)。broker 日志里没有任何超时相关的行。我没有找到原因,所以这一篇没有能验证“超时后 channel 被关闭、消息回队列”这一行为本身。", t=tl(S(3)), mark=lidx(S(3), '420 s 内 channel 没有被关', '结论'), done=lidx(S(3), 'ct.classic', 'ct.quorum'), kv=KV([['配置 10 s,等 420 s', 'channel 仍然开着'], ['未确认的消息', '一直在 unacked'], ['原因', '没有查清']], ['配置 10 s,等 420 s'])),
]
A = mkartq('q24', 24, 'RabbitMQ,consumer_timeout,消费者超时,未确认,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上验证 consumer_timeout:默认 1800000 ms,rabbitmq.conf 改成 10000 后 eval 读到 {ok,10000};x-consumer-timeout 队列参数经典队列返回 406、quorum 队列成功,policy consumer-timeout 可设;但把超时配成 10 s、消费者收到消息不确认,等 7 分钟 channel 没有被关——原因没查清,如实记录。',
    '消费者拿了消息却不确认(处理卡死、死循环),消息会被一直占着。consumer_timeout 是 RabbitMQ 的兜底。它默认多久、怎么按队列覆盖、真的会在超时后关掉 channel 吗?这篇如实记录能验证的和没验证到的。',
    [('1800000 ms', 'consumer_timeout 的默认值(30 分钟)'), ('406', '经典队列声明 x-consumer-timeout 的错误码;quorum 队列接受'), ('420 s', '超时配成 10 s,等 7 分钟 channel 仍没被关——这一篇没验证到“超时关闭”')],
    [('默认值与配置', '<p>默认 <code>consumer_timeout</code> 是 1800000 ms(30 分钟),可在 <code>rabbitmq.conf</code> 里设置;<code>rabbitmqctl eval</code> 能读到当前值。</p>'),
     ('按队列覆盖', '<p>quorum 队列接受队列参数 <code>x-consumer-timeout</code>,经典队列返回 406 invalid arg;policy <code>consumer-timeout</code> 都可以设置。</p>'),
     ('没验证到的部分', '<p>把超时配成 10 秒,消费者收到消息后不确认,等了 7 分钟,channel 没有被关,日志里也没有相关记录。可能是这个检查的触发条件我没有满足,也可能是 4.3.6 的行为与我预期不同——这里没有查清,所以不写“超时之后一定会怎样”。</p>')],
    steps,
    [ENV_Q + '。参数 / policy 的验证是真实的声明与 set_policy;第三节的消费者用 pika,prefetch=10,不 ack,心跳 60 s,经典队列与 quorum 队列各一个,等 420 秒,期间观察 channel 的 close 回调与 rabbitmqctl list_queues',
     '没有验证:超时真的触发时的错误文本、被终止的 channel 上未确认消息的去向(回队列并 redelivered)、检查的周期;为什么 10 s 的配置在 7 分钟内没有生效;更长时间(超过 7 分钟)的观察;AMQP 1.0 消费者;前两次更早的实验(240 秒、170 秒)也同样没有看到 channel 被关'],
    '消费者超时')
