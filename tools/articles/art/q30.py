from lib import *
S = SS('q30')
steps = [
    step("动态 shovel:在 A 上用 rabbitmqctl set_parameter shovel my-shovel '{…}' 定义一个,源是 A 的队列 src(amqp091),目的是 B 的队列 dst,ack-mode=on-confirm。参数存在 runtime parameter 里,不用改配置文件或重启。几秒后 shovel_status 显示 my-shovel 的类型 dynamic、状态 running;A.src 里剩 0 条,B.dst 里有 1000 条——shovel 就是一个“消费者 + 发布者”,把一个队列的消息搬到另一个 broker 的队列。", t=tl(S(1)), mark=lidx(S(1), 'shovel_status', 'B.dst 里有 1000 条'), done=lidx(S(1), 'set_parameter'), b=bars([['A.src 搬完后', 0, '0 条'], ['B.dst 搬完后', 1000, '1000 条']], 1000, mark=[1], done=[0]), kv=KV([['shovel', '消费源队列 + 发布到目的'], ['定义', 'runtime parameter,动态生效'], ['状态', 'running']], ['shovel'])),
    step("ack-mode 的吞吐(20000 条 100 字节持久化消息从 A.src 搬到 B.dst,计时从创建 shovel 到 B 上收齐,3 轮中位数):on-confirm 905 ms(22106 条/秒);on-publish 974 ms(20533 条/秒);no-ack 874 ms(22870 条/秒)。三种差别在噪声里:on-confirm 等目的端 confirm 后才 ack 源端消息,不丢;no-ack 最快但搬运中途出问题会丢;这里看不出代价。", t=tl(S(2)), mark=lidx(S(2), 'on-confirm'), done=lidx(S(2), 'on-publish', 'no-ack'), b=bars([['on-confirm', 22106, '22106 条/秒'], ['on-publish', 20533, '20533 条/秒'], ['no-ack', 22870, '22870 条/秒']], 22870, mark=[0], done=[1, 2]), kv=KV([['on-confirm', '目的端确认后才 ack 源,不丢'], ['on-publish', '发布后就 ack'], ['no-ack', '源端自动确认,最快但可能丢']], ['on-confirm'])),
    step("目的端宕机:把 B 停掉,A 上的 shovel 状态变成 terminated,A.src 里的 500 条消息就留在原地,没有丢。B 重新启动、可用之后 0.4 s,B.dst 里就有了 500 条,A.src 里剩 0 条——shovel 自己重连并继续搬,不需要人工干预(reconnect-delay 设成了 1 s)。", t=tl(S(3)), mark=lidx(S(3), 'terminated', '重新启动并可用之后'), done=lidx(S(3), 'A.src 里积压'), kv=KV([['目的端宕机', 'shovel terminated,消息留在源队列'], ['恢复', 'B 可用后 0.4 s 内搬完'], ['reconnect-delay', '控制重试间隔']], ['目的端宕机'])),
    step("交换机联邦:B 是上游,A 是下游。在 A 上设联邦上游 up-b(uri 指向 B),再给交换机 fx 设策略 federation-upstream-set=all。B 上向 fx 发布 5 条 orders.new 和 1 条 other.x,A 上绑定了 orders.# 的队列 fq_local 里收到 5 条——联邦链路把上游交换机的消息按下游的绑定复制过来,不匹配的 other.x 没被拉。联邦状态里链路是 running。", t=tl(S(4)), mark=lidx(S(4), 'fq_local', '联邦链路状态'), done=lidx(S(4), 'federation-upstream', 'fed-x'), b=bars([['B 上发布', 6, '6 条'], ['A.fq_local 收到', 5, '5 条 (orders.#)']], 6, mark=[1], done=[0]), kv=KV([['upstream', 'B(federation-upstream)'], ['policy', 'federation-upstream-set'], ['传的是', '下游绑定感兴趣的消息(复制)']], ['传的是'])),
    step("队列联邦:消息留在上游,有消费者时才被拉过来。B 上 fqq 放 100 条,在 A 上给 fqq 设了联邦策略、链路建好后:A.fqq 0 条,B.fqq 100 条——A 上没有消费者时一条都不动。A 上开一个消费者后(0.0 s 内)收到 100 条,B.fqq 里剩 0 条。联邦队列是“搬”不是“复制”,消息只在有消费者的那一端。", t=tl(S(5)), mark=lidx(S(5), 'A 上开一个消费者后'), done=lidx(S(5), '建好联邦链路'), b=bars([['A 无消费者:B.fqq', 100, '100 条'], ['A 有消费者后:B.fqq', 0, '0 条'], ['A 收到', 100, '100 条']], 100, mark=[1, 2], done=[0]), kv=KV([['没有消费者', '消息留在上游'], ['有消费者', '被搬到下游'], ['语义', '搬运,不是复制']], ['语义'])),
]
A = mkartq('q30', 30, 'RabbitMQ,Shovel,Federation,跨集群,联邦,真实验证,动画演示',
    '在两个 RabbitMQ 4.3.6 节点上实测 Shovel 和 Federation:动态 shovel 把 1000 条消息从 A.src 搬到 B.dst,三种 ack-mode 约 2 万条/秒;目的端宕机时 shovel terminated、消息留在源队列,恢复后 0.4 s 搬完;交换机联邦按下游绑定复制消息(5/6 条);队列联邦只在下游有消费者时才把消息搬过来。',
    '跨数据中心、跨集群搬消息有两个官方工具:Shovel 和 Federation。它们各是什么、怎么配、目的端挂了会怎样、消息是被复制还是被搬走?这篇起了两个独立的 broker,把两者各跑一遍。',
    [('22106 条/秒', 'on-confirm 的 shovel 在本机上搬 20000 条消息的速度'), ('0.4 s', '目的端 B 重新可用后,积压的 500 条消息被搬完所需的时间'), ('5 / 6', '交换机联邦只复制了下游绑定 orders.# 感兴趣的 5 条,没有复制 other.x')],
    [('Shovel', '<p>一个 shovel 就是“在源端当消费者、在目的端当发布者”的进程,用 <code>rabbitmqctl set_parameter shovel</code> 动态定义。ack-mode 决定何时确认源消息:on-confirm 最安全,no-ack 最快但可能丢。</p>'),
     ('ack-mode', '<p>on-confirm(目的端确认后才确认源)、on-publish(发布后就确认)、no-ack(源端自动确认)三种吞吐几乎一样,约 2 万条/秒,差别在噪声内;越保守越不会丢。</p>'),
     ('目的端故障', '<p>目的端宕机时 shovel 终止,源队列保留消息;目的端回来后 shovel 重连、继续搬,按 reconnect-delay 重试。</p>'),
     ('交换机联邦', '<p>下游的联邦交换机按自己的绑定,向上游交换机拉取匹配的消息(复制),不匹配的不传。用 <code>federation-upstream</code> 参数 + policy 配置。</p>'),
     ('队列联邦', '<p>联邦队列只在下游有消费者时才从上游拉消息,是搬运不是复制;没有消费者时消息留在上游。</p>')],
    steps,
    [ENV_Q + '。两个独立节点 A、B(各自数据目录、端口),A 启用 rabbitmq_shovel 与 rabbitmq_federation,B 启用 rabbitmq_federation;吞吐的计时包含创建 shovel 到 B 上收齐;“消息被搬走”由 rabbitmqctl list_queues 的条数佐证',
     '没有验证:AMQP 1.0 shovel;跨广域网的延迟与带宽影响;联邦的 max-hops、expires、message-ttl 等参数;循环联邦(双向)的防环;联邦下游宕机后的行为;shovel 的批量(prefetch-count)调优;大量联邦队列的内存'],
    'Shovel 与 Federation')
