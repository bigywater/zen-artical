from lib import *
S = SS('q36')
steps = [
    step("消费者进程被 kill -9:持有 100 条未确认消息(队列共 200 条,kill 之前 (ready, unacked) = (100, 100))。进程一死,操作系统关掉它的 TCP 连接,broker 立刻发现:381 ms 之后 unacked 变回 0,(ready, unacked) = (200, 0)——100 条未确认的消息全部回到队列。", t=tl(S(1)), mark=lidx(S(1), 'kill -9 之后'), done=lidx(S(1), 'kill 之前'), b=bars([['kill 前 unacked', 100, '100'], ['kill 后 unacked', 0, '0'], ['kill 后 ready', 200, '200']], 200, mark=[1, 2], done=[0]), kv=KV([['进程被 kill -9', 'TCP 连接立即断开'], ['回队列的时间', '381 ms'], ['unacked', '100 → 0']], ['回队列的时间'])),
    step("先确认一部分再崩溃:队列共 150 条,消费者确认前 40 条(m0~m39)、接下来 60 条(m40~m99)没确认,prefetch=60,然后被 kill -9。重新取回队列:共 110 条——redelivered=True 的 60 条正是 m40~m99(没确认的那批),全新的 50 条是 m100~m149;前 40 条已确认,没有再出现。顺序是 m40、m41、m42、m43、m44……:被重新投递的回到队首,原来的先后顺序保持不变。", t=tl(S(2)), mark=lidx(S(2), 'redelivered=True 的 60 条', '顺序:'), done=lidx(S(2), '队列里剩 110 条'), b=bars([['已确认(不再出现)', 40, '40 条 m0~m39'], ['重新投递 redelivered', 60, '60 条 m40~m99'], ['全新', 50, '50 条 m100~m149']], 60, mark=[1], done=[0, 2]), kv=KV([['已 ack', '不会重投'], ['未 ack', '全部重投,redelivered=True'], ['位置', '回到队首,保持原顺序']], ['未 ack'])),
    step("网络黑洞(消费者进程还活着,但网络不通,没有 TCP 关闭):靠心跳发现。经过代理停止转发,heartbeat=3 的消费者持有 50 条未确认消息:黑洞开始后 8.6 秒 unacked 才回到 0,(ready, unacked) = (100, 0)。约是心跳超时的 3 倍,和第 22 篇测到的黑洞检测时间一致。比进程被杀慢了 20 多倍——这段时间里那 50 条消息谁都拿不到。", t=tl(S(3)), mark=lidx(S(3), '黑洞开始后 8.6 s'), done=lidx(S(3), '黑洞开始前'), b=bars([['kill -9 回队列', 0.381, '0.381 s'], ['黑洞回队列', 8.6, '8.6 s']], 8.6, mark=[1], done=[0]), kv=KV([['进程被杀', '≈ 0.4 s'], ['网络黑洞', '≈ 3 倍心跳超时(8.6 s)'], ['期间', '未确认消息谁也拿不到']], ['网络黑洞'])),
    step("poison 消息的重投次数:经典队列只有一个 redelivered 布尔值;quorum 队列的消息带 x-delivery-count 头,并可以用队列参数 x-delivery-limit 限制次数。让一条 poison 消息每次被取到就“崩溃”(断开连接):第 1 次 (redelivered=False, 无计数头),第 2 次 (True, 1),第 3 次 (True, 2),第 4 次 (True, 3),第 5 次队列里已经没有这条消息——x-delivery-limit=3 的队列在重投 3 次之后丢弃它,最后 (ready, unacked) = (0, 0)。(没配死信交换机,所以直接丢了;配了就会成为死信。)", t=tl(S(4)), mark=lidx(S(4), '每次拿到时', 'x-delivery-limit=3'), done=lidx(S(4), '每次拿到时'), b=bars([['第 1 次 count', 0, '无'], ['第 2 次', 1, '1'], ['第 3 次', 2, '2'], ['第 4 次', 3, '3']], 3, mark=[3], done=[0, 1, 2]), kv=KV([['x-delivery-count', 'quorum 队列才有'], ['x-delivery-limit=3', '重投 3 次后丢弃(或死信)'], ['经典队列', '只有 redelivered 布尔值']], ['x-delivery-limit=3'])),
    step("经典队列拿不到重投次数:同一条消息被 nack 并 requeue 5 次,redelivered 依次是 False、True、True、True、True,x-delivery-count 头始终没有(None)。要限制毒消息的重试,经典队列只能靠应用自己计数,或走死信队列做重试环(第 10 篇);quorum 队列直接用 delivery-limit。", t=tl(S(5)), mark=lidx(S(5), '经典队列 5 次'), done=lidx(S(5), '经典队列 5 次'), kv=KV([['经典队列', 'redelivered 布尔,无计数'], ['限制重试', '应用计数 / 死信重试环'], ['quorum 队列', 'x-delivery-count + delivery-limit']], ['经典队列'])),
]
A = mkartq('q36', 36, 'RabbitMQ,未确认,重新投递,redelivered,x-delivery-count,delivery-limit,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测消费者崩溃后未确认消息的重新投递:kill -9 后 381 ms 回队列;确认过的不重投、未确认的回到队首且 redelivered=True;网络黑洞靠心跳 8.6 s 才回队列;quorum 队列有 x-delivery-count 和 x-delivery-limit(重投 3 次后丢弃),经典队列只有 redelivered 布尔值。',
    '消费者拿了消息没来得及确认就挂了,消息去哪里、多久回来、会不会无限重投?进程被杀和网络不通有什么差别?quorum 队列怎么限制重试?这篇把本系列前面几篇的零散结论补成完整的一套。',
    [('381 ms', 'kill -9 消费者进程后,100 条未确认消息全部回到队列的时间'), ('8.6 s', '网络黑洞下(heartbeat=3)同样的消息回队列的时间'), ('3 次', 'x-delivery-limit=3 的 quorum 队列对 poison 消息重投的次数,之后丢弃')],
    [('进程被杀', '<p>操作系统关闭 TCP 连接,broker 立即发现,未确认消息很快(约 0.4 s)回到队列。</p>'),
     ('部分确认', '<p>确认过的消息不会重投;未确认的回到队首并带 <code>redelivered=True</code>,顺序不变。</p>'),
     ('网络黑洞', '<p>没有 TCP 关闭时只能靠心跳超时发现,约 3 倍超时(8.6 s),这段时间里未确认的消息被卡着。</p>'),
     ('毒消息', '<p>quorum 队列在重投的消息上带 <code>x-delivery-count</code>,配合 <code>x-delivery-limit</code> 限制重试次数,超过后丢弃或进入死信。</p>'),
     ('经典队列', '<p>只有 redelivered 布尔值,没有计数;需要限制重试就在应用里数,或用死信重试环。</p>')],
    steps,
    [ENV_Q + '。消费者是 qcons.py 子进程(pika),收满消息后挂着等被 kill -9;回队列时间是从 kill 到 rabbitmqctl list_queues 的 unacked 变 0(轮询间隔 50 ms,每次读本身要几百毫秒);黑洞经自己写的代理,heartbeat=3;quorum 的重投实验每次取到就断开连接',
     '没有验证:delivery-limit 配合死信交换机(dead-letter-strategy);多节点下 leader 切换时的重投;大量未确认消息(几万)回队列的耗时;stream 队列没有这个机制;自动重试(应用侧)的退避策略;网络黑洞时间的多次统计(这里每次只测一次)'],
    '未确认重投')
