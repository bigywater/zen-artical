from lib import *
S = SS('q14')
steps = [
    step("4.3.6 里 x-queue-mode=lazy 仍然被接受:声明 x-queue-mode=lazy 和 x-queue-mode=default 的经典队列都成功,list_queues 的 arguments 里原样列着 {x-queue-mode, lazy} 和 {x-queue-mode, default},没有报错也没有废弃提示。队列字段里没有任何“模式”一列——它只是一个参数,效果要看下面的内存数字。", t=tl(S(1)), mark=lidx(S(1), 'x-queue-mode=lazy: 声明成功', 'list_queues 能看到'), done=lidx(S(1), 'default: 声明成功', 'rabbitmqctl list_queues 里的参数'), kv=KV([['x-queue-mode=lazy', '仍被接受,不报错'], ['default', '同样接受'], ['队列字段', '没有“模式”列']], ['x-queue-mode=lazy'])),
    step("往没有消费者的队列各放 100000 条 1 KB 的持久化消息:classic.default 的 messages_ram 只有 1(几乎全部不在内存),message_bytes_ram 0.0 MiB,队列进程内存 0.7 MiB,broker 总内存增量 1.3 MiB;加了 x-queue-mode=lazy 的 classic.lazy 完全一样的模式:messages_ram 1,队列进程内存 1.1 MiB,总增量 1.0 MiB。也就是说默认的经典队列已经不在内存里囤消息了,lazy 参数在这里看不出区别。", t=tl(S(2)), mark=lidx(S(2), 'classic.lazy'), done=lidx(S(2), 'classic.default'), b=bars([['classic.default 内存增量', 1.3, '1.3 MiB'], ['classic.lazy 内存增量', 1.0, '1.0 MiB']], 1.3, mark=[1], done=[0]), kv=KV([['messages_ram', '两者都是 1'], ['100000 条 × 1 KB', '内存增量 1~1.3 MiB'], ['lazy 参数', '看不出区别']], ['messages_ram'])),
    step("同样的 100000 条放进 quorum 队列:messages_ram = 0,队列进程内存 4.5 MiB,但整个 broker 的内存增加了 166.3 MiB——比经典队列的 1.3 MiB 大出两个数量级。quorum 队列的 Raft 日志在内存里还保留着最近写入的数据(memtable 之类),这部分不算在“队列进程内存”里,要看 broker 总内存才看得到。", t=tl(S(3)), mark=lidx(S(3), 'quorum.q'), done=lidx(S(3), 'quorum.q'), b=bars([['classic 内存增量', 1.3, '1.3 MiB'], ['quorum 内存增量', 166.3, '166.3 MiB']], 166.3, mark=[1], done=[0]), kv=KV([['quorum 100000 条', 'broker 总内存 +166.3 MiB'], ['队列进程内存', '只看到 4.5 MiB'], ['看哪里', 'erlang:memory(total)']], ['quorum 100000 条'])),
    step("消费者来了以后:classic.default 有消费者(prefetch=100)确认了 2147 条后,messages = 97853,messages_ram = 568、message_bytes_ram = 0.55 MiB、队列进程内存 2.8 MiB——只有正在投递的这一小段会被读进内存,队列整体仍然在磁盘上,内存随处理中的窗口而变,而不是随积压量变。", t=tl(S(4)), mark=lidx(S(4), '消费者确认了'), done=lidx(S(4), '消费者确认了'), kv=KV([['在内存里的', '投递窗口附近的 568 条'], ['积压的 97853 条', '在磁盘'], ['内存', '随窗口,不随积压']], ['在内存里的'])),
    step("重启恢复:带 97853 条持久化消息的经典队列,正常重启 broker(关闭 + 启动 + await_startup)总共 11.1 s;重启后 messages = 97853,messages_ram = 1,队列进程内存几乎为 0(队列进程还没有被唤醒);之后取 100 条用了 14 ms,消息是按需从磁盘读出来的。积压很多也不会让重启时把所有消息装进内存。", t=tl(S(5)), mark=lidx(S(5), '重启(关闭'), done=lidx(S(5), '取 100 条'), kv=KV([['重启', '11.1 s(含关闭与启动)'], ['重启后 messages_ram', '1'], ['取 100 条', '14 ms,按需读盘']], ['重启'])),
]
A = mkartq('q14', 14, 'RabbitMQ,惰性队列,lazy,内存,classic queue,quorum,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测惰性队列:x-queue-mode=lazy 仍被接受但与默认经典队列在内存上看不出区别(都是 messages_ram≈1,100000 条 1 KB 只增 1~1.3 MiB);quorum 队列同样数据让 broker 总内存增加 166.3 MiB;消费时内存随投递窗口走;重启 11.1 s 后消息按需读盘。',
    '“lazy 队列”曾是对付积压的标准做法:让队列尽量把消息写盘、少占内存。到了 4.x 默认的经典队列又是什么样?x-queue-mode=lazy 还有用吗?quorum 队列的内存账怎么算?这篇用 100000 条消息实际量一遍。',
    [('1.3 MiB', '100000 条 1 KB 消息放进默认经典队列后 broker 总内存的增量'), ('166.3 MiB', '同样数据放进 quorum 队列后 broker 总内存的增量'), ('1 条', '两种经典队列(默认与 lazy)堆了 100000 条后,内存里的消息数 messages_ram')],
    [('lazy 参数', '<p>x-queue-mode=lazy 在 4.3.6 仍能声明,没有报错;但经典队列默认就不再把积压的消息放在内存里,所以带不带这个参数在内存数字上看不出区别。</p>'),
     ('积压时的内存', '<p>100000 条 1 KB 的持久化消息(共约 100 MB)放进经典队列,messages_ram 只有 1,broker 总内存只增加 1.0~1.3 MiB。</p>'),
     ('quorum 队列的账', '<p>同样的消息进 quorum 队列,队列进程内存 4.5 MiB,可是 broker 总内存涨了 166.3 MiB;看队列自己的 memory 字段会低估它。</p>'),
     ('消费时', '<p>消费者在线时,内存里只有投递窗口附近的消息(568 条、0.55 MiB),积压的 97853 条仍在磁盘上。</p>'),
     ('重启', '<p>重启不会把积压的消息整个装进内存:11.1 s 启动后队列里 messages_ram 只有 1,取 100 条用 14 ms 按需读盘。</p>')],
    steps,
    [ENV_Q + '。内存数字来自 rabbitmqctl list_queues(messages_ram、message_bytes_ram、memory)和 rabbitmqctl eval erlang:memory(total).(放入前后的差);每个队列单独放 100000 条 1 KB 持久化消息,等 3 秒再读;第五节计时包含 rabbitmqctl shutdown、重新启动和 await_startup',
     '没有验证:早期版本(3.x)的 lazy 行为对比;内存水位触发流控时经典队列的表现(见第 20 篇);更大的积压(千万级);quorum 队列内存占用随 Raft 日志截断的变化(没有看 166.3 MiB 何时回落);非持久化消息或有消费者时的内存差异;消息体更小时的占用'],
    '惰性队列')
