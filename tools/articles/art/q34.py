from lib import *
S = SS('q34')
steps = [
    step("对比的前提:同一台机器上各起一个单节点 broker——RabbitMQ 4.3.6(经典队列、持久化消息)和 Kafka 4.3.1(KRaft、1 个分区、1 副本)。两边的客户端库不同:pika 是纯 Python,confluent-kafka 是 C 实现的 librdkafka。所以下面的绝对数字主要反映“客户端 + 默认批量策略”,只能看数量级和趋势,不能当成两个 broker 的上限。", t=tl(S(1)), mark=lidx(S(1), 'RabbitMQ: 4.3.6'), done=lidx(S(1), 'RabbitMQ: 4.3.6'), kv=KV([['RabbitMQ', '4.3.6,经典队列,持久化'], ['Kafka', '4.3.1,KRaft,1 分区 1 副本'], ['客户端', 'pika(Python)vs librdkafka(C)']], ['客户端'])),
    step("发布吞吐(100000 条 100 字节,3 轮中位数):RabbitMQ 异步 confirm(在途 1000、持久化)1635 ms,61155 条/秒;Kafka acks=all、linger.ms=5 只要 47 ms,2135302 条/秒;linger.ms=0 是 65 ms,1549576 条/秒。差了 25~35 倍——一部分来自 broker 设计(Kafka 顺序追加日志、客户端把很多条合成一批发送),一部分来自客户端(librdkafka 是 C,pika 是纯 Python),这里没法拆开。", t=tl(S(2)), mark=lidx(S(2), 'Kafka acks=all linger.ms=5'), done=lidx(S(2), 'RabbitMQ 异步 confirm'), b=bars([['RabbitMQ 异步 confirm', 61155, '61155 条/秒'], ['Kafka linger.ms=0', 1549576, '1549576 条/秒'], ['Kafka linger.ms=5', 2135302, '2135302 条/秒']], 2135302, mark=[1, 2], done=[0]), kv=KV([['RabbitMQ', '61155 条/秒'], ['Kafka', '150 万~210 万条/秒'], ['解读', 'broker 设计 + 客户端批量 + 语言,不可拆']], ['解读'])),
    step("低速率下的端到端延迟(每秒 500 条,各 2000 条,消息里放发送时刻):RabbitMQ(推送,带 confirm)p50 0.60 ms、p99 3.37 ms;Kafka(acks=all,linger.ms=0,拉取)p50 0.34 ms、p99 5.44 ms。p50 都在亚毫秒,量级相同;p99 在我跑的两次之间差别明显(两边的排名都翻过),不能据此说谁的尾延迟更好。", t=tl(S(3)), mark=lidx(S(3), 'RabbitMQ(推送', 'Kafka(acks=all'), done=lidx(S(3), 'RabbitMQ(推送'), b=bars([['RabbitMQ p50', 0.6, '0.60 ms'], ['Kafka p50', 0.34, '0.34 ms'], ['RabbitMQ p99', 3.37, '3.37 ms'], ['Kafka p99', 5.44, '5.44 ms']], 5.44, mark=[2, 3], done=[0, 1]), kv=KV([['p50', '都是亚毫秒'], ['p99', '多次运行波动大,不下结论'], ['模式', 'RabbitMQ 推送 / Kafka 拉取']], ['p99'])),
    step("一份数据给 3 个独立的下游:RabbitMQ 要 fanout exchange 加 3 个队列,每个队列存一份;Kafka 是 1 个 topic、3 个 consumer group 各读各的,日志只存一份。写入 50000 条 1 KB 之后,RabbitMQ 的数据目录增长 174 MiB,Kafka 的增长 49 MiB——约 3.6 倍。扇出越多,RabbitMQ 的存储越线性增长;Kafka 的扇出是读取侧的事。", t=tl(S(4)), mark=lidx(S(4), 'RabbitMQ(3 个队列', 'Kafka(1 个 topic'), done=lidx(S(4), 'RabbitMQ(3 个队列'), b=bars([['RabbitMQ(3 个队列)', 174, '174 MiB'], ['Kafka(1 个 topic)', 49, '49 MiB']], 174, mark=[0], done=[1]), kv=KV([['RabbitMQ 扇出', '每个下游一个队列,存 N 份'], ['Kafka 扇出', '每个下游一个 group,存 1 份'], ['实测', '174 MiB vs 49 MiB']], ['实测'])),
    step("读完能不能再读:20000 条消息读完之后再从头读一遍。RabbitMQ 经典队列第一次读 20000 条,第二次读 0 条——被 ack 就删除了;Kafka 第一个 group 读 20000 条,另一个 group 再从头读还是 20000 条——日志保留着,读取不删除。需要“重放”“多个独立读者”“回溯”的场景是 Kafka 型的日志天然擅长的(RabbitMQ 的 stream 队列也有这个能力,见第 17 篇)。", t=tl(S(5)), mark=lidx(S(5), 'RabbitMQ 经典队列', 'Kafka:第一个 group'), done=lidx(S(5), 'RabbitMQ 经典队列'), b=bars([['RabbitMQ 第 1 次', 20000, '20000 条'], ['RabbitMQ 第 2 次', 0, '0 条'], ['Kafka 第 2 个 group', 20000, '20000 条']], 20000, mark=[1], done=[0, 2]), kv=KV([['RabbitMQ 经典队列', '读后即删'], ['Kafka', '日志保留,可重放'], ['RabbitMQ stream', '也可重放(第 17 篇)']], ['Kafka'])),
]
A = mkartq('q34', 34, 'RabbitMQ,Kafka,对比,吞吐,延迟,扇出,重放,真实验证,动画演示',
    '在同一台机器上对比 RabbitMQ 4.3.6 与 Kafka 4.3.1:发布 10 万条 100 字节,RabbitMQ 异步 confirm 61155 条/秒,Kafka 150 万~210 万条/秒(客户端不同,仅看数量级);低速率 p50 延迟 0.60 vs 0.34 ms;扇出给 3 个下游时磁盘 174 vs 49 MiB;RabbitMQ 经典队列读完即删而 Kafka 可从头重放。',
    'RabbitMQ 和 Kafka 到底差在哪?不是谁更好,而是模型不同:队列 vs 日志。这篇在同一台机器上把吞吐、延迟、扇出的存储、重放能力各量一遍,并老实标出哪些数字不能直接比。',
    [('61155 vs 2135302', '发布 10 万条 100 字节,RabbitMQ 异步 confirm 与 Kafka(linger.ms=5)的条/秒,客户端不同,仅看数量级'), ('174 vs 49 MiB', '50000 条 1 KB 的消息扇出给 3 个下游,RabbitMQ(3 个队列)与 Kafka(1 个 topic)的磁盘增长'), ('0 vs 20000', '消息被读完之后再读一遍:RabbitMQ 经典队列 0 条,Kafka 20000 条')],
    [('先说前提', '<p>两个 broker 都是单节点、本机,客户端语言不同(pika 是纯 Python,librdkafka 是 C),数字主要反映客户端与批量策略,不是 broker 上限的比较。</p>'),
     ('吞吐', '<p>Kafka 追加日志并由客户端批量发送,单节点上发布吞吐比 pika 异步 confirm 的 RabbitMQ 高了 25~35 倍;其中多少来自 broker、多少来自客户端,这里没有拆开。</p>'),
     ('延迟', '<p>低速率下 p50 都是亚毫秒(0.60 对 0.34 ms),p99 两次运行排名翻转,不下结论。</p>'),
     ('扇出', '<p>RabbitMQ 用多个队列做扇出,每个下游存一份;Kafka 的多个消费组共享一份日志。50000 条 1 KB 扇出到 3 个下游:174 MiB 对 49 MiB。</p>'),
     ('重放', '<p>RabbitMQ 经典队列读完即删,不能重读;Kafka 日志保留,新的消费组可以从头读(RabbitMQ 的 stream 队列也有类似能力)。</p>')],
    steps,
    [ENV_Q + '。Kafka 用 Homebrew 的 4.3.1,本机单节点 KRaft(broker 与 controller 合一,1 分区、1 副本),客户端 confluent-kafka 2.16.0;RabbitMQ 为经典队列,持久化,pika 异步 confirm;延迟是单次 2000 条的 p50 / p99,p99 波动大;磁盘大小用 du -sk',
     '没有验证:多分区 / 多消费者下的 Kafka 吞吐扩展;多副本 Kafka(acks=all 需要 ISR 同步)与 3 副本 quorum 队列的比较;RabbitMQ stream 队列与 Kafka 的比较(这里只比了经典队列);同一语言客户端下的公平对比;消费吞吐;运维复杂度、生态、事务语义等非性能因素;保留策略与压缩'],
    '与 Kafka 对比')
