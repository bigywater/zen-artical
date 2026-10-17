from lib import *
S = SS('q21')
steps = [
    step("channel 数有硬上限:broker 在 Connection.Tune 里给出 channel_max = 2047,pika 请求的是 0(不限制),协商结果取 broker 的 2047。一条连接上开 channel,成功开到第 2047 个后再开下一个失败,pika 抛 NoFreeChannels;list_connections 的 channels 列显示 2047。所以“一个连接上开多少 channel”不是无限的,默认上限是 2047 个。", t=tl(S(1)), mark=lidx(S(1), 'NoFreeChannels', '2047(pika'), done=lidx(S(1), 'list_connections 的 channels 列'), kv=KV([['channel_max', 'broker 给 2047'], ['达到上限后', '再开 channel 失败(NoFreeChannels)'], ['pika 默认请求', '0 = 不限,取 broker 的值']], ['channel_max'])),
    step("每个 channel 的开销随数量线性增长:一条连接上开 100 个 channel,broker 里多 407 个 Erlang 进程、内存多 2.5 MiB(每个 25.3 KiB、约 4.1 个进程);1000 个时 4007 个进程、17.8 MiB(每个 18.2 KiB);2000 个时 8006 个进程、44.2 MiB(每个 22.6 KiB)。一个 channel 约 4 个 Erlang 进程、20 KiB 上下,空 channel 也不是免费的。", t=tl(S(2)), mark=lidx(S(2), '2000 '), done=lidx(S(2), '100 ', '1000 '), b=bars([['100 个 channel', 407, '407 进程'], ['1000 个', 4007, '4007 进程'], ['2000 个', 8006, '8006 进程']], 8006, mark=[2], done=[0, 1]), kv=KV([['每个 channel', '约 4 个 Erlang 进程'], ['内存', '约 18~25 KiB'], ['2000 个', '约 44 MiB']], ['每个 channel'])),
    step("一条连接上开更多 channel 并不能提高吞吐:同一个进程里 1 / 4 / 16 / 64 个 channel 轮流发布 100000 条 100 字节消息(不开 confirm,3 轮中位数),分别是 2635、2689、2688、2779 ms(37945、37188、37197、35980 条/秒)——差别在噪声范围内,64 个 channel 还略慢一点。channel 的作用是并发组织(各自的消费者、确认、错误隔离),而不是提速。", t=tl(S(3)), mark=lidx(S(3), '× 64'), done=lidx(S(3), '×  1', '×  4', '× 16'), b=bars([['1 channel', 37945, '37945 条/秒'], ['4 个', 37188, '37188 条/秒'], ['16 个', 37197, '37197 条/秒'], ['64 个', 35980, '35980 条/秒']], 37945, mark=[3], done=[0, 1, 2]), kv=KV([['1 → 64 个 channel', '吞吐几乎不变'], ['channel 的价值', '隔离与并发,不是提速'], ['单进程发布', '约 37000 条/秒']], ['1 → 64 个 channel'])),
    step("加连接(每个客户端进程一条连接,各发 50000 条到自己的队列)才提高总吞吐:1 个连接 36805 条/秒;2 个 67609 条/秒;4 个 94976 条/秒;8 个 97867 条/秒。2、4 个时接近线性,到 8 个就不再涨了(这台机器 10 个核,客户端进程和 broker 抢 CPU;这里没有区分瓶颈在客户端还是 broker)。要更高吞吐靠多连接,而不是多 channel;但连接也比 channel 贵得多(第 1 篇:约 11 个进程 / 74 KiB)。", t=tl(S(4)), mark=lidx(S(4), '4 个连接', '8 个连接'), done=lidx(S(4), '1 个连接', '2 个连接'), b=bars([['1 个连接', 36805, '36805 条/秒'], ['2 个连接', 67609, '67609 条/秒'], ['4 个连接', 94976, '94976 条/秒'], ['8 个连接', 97867, '97867 条/秒']], 97867, mark=[3], done=[0, 1, 2]), kv=KV([['1 → 4 个连接', '36805 → 94976 条/秒'], ['4 → 8 个连接', '基本不再增长'], ['结论', '提速靠多连接,不靠多 channel']], ['结论'])),
]
A = mkartq('q21', 21, 'RabbitMQ,连接,channel,channel_max,吞吐,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测连接与 channel 的数量:channel_max 默认 2047,开到上限后再开失败;每个 channel 约 4 个 Erlang 进程、20 KiB 左右;一条连接上 1~64 个 channel 的发布吞吐没有变化(约 37000 条/秒);多连接才能提高总吞吐(1 个 36805 → 4 个 94976 条/秒)。',
    '一个连接开多少 channel 合适?channel 多了会不会拖慢?想提高吞吐,该多开 channel 还是多开连接?这篇量了上限、每个 channel 的开销,以及 channel 和连接两种扩展方式各自的吞吐。',
    [('2047', 'channel_max:broker 允许一条连接上最多开的 channel 数'), ('~4 进程 / ~20 KiB', '每个 channel 在 broker 里的 Erlang 进程数和内存'), ('36805 → 94976', '1 个连接与 4 个连接(各一个客户端进程)的总发布吞吐,条/秒')],
    [('上限', '<p>broker 在 <code>Connection.Tune</code> 里告诉客户端 <code>channel_max</code>(默认 2047),客户端协商后不能超过。超过时客户端库(这里是 pika)直接抛 NoFreeChannels。</p>'),
     ('开销', '<p>每个 channel 在 broker 里约 4 个 Erlang 进程、18~25 KiB,线性增长;2000 个 channel 就是 8006 个进程、约 44 MiB。</p>'),
     ('channel 不提速', '<p>同一个连接上开 1、4、16、64 个 channel 并轮流发布,吞吐都在 36000~38000 条/秒,没有区别。channel 的价值是隔离(各自的错误、确认、消费者),不是并行度。</p>'),
     ('连接提速', '<p>多开连接(每个连接一个客户端进程)才增加总吞吐:到 4 个连接时 94976 条/秒,8 个连接就不再增长了(机器 CPU 被客户端和 broker 共用)。</p>')],
    steps,
    [ENV_Q + '。第一节直连 broker 读 channel_max 并一直开到失败;第二节用 rabbitmqctl eval 读 erlang:system_info(process_count) 与 erlang:memory(total),开 channel 后等 2 秒;第三节同一个 pika 连接内轮流发布(不开 confirm,用 queue_declare passive 往返确认发完),3 轮中位数;第四节是 qwork.py 子进程各开一条连接,各发 50000 条,取最慢一个的耗时,3 轮中位数',
     '没有验证:开 confirm 时多 channel 的吞吐;消费端的多 channel / 多连接对比;服务器 CPU 核数更多时多连接的扩展上限;客户端换成多线程或异步客户端(这里是单线程 pika 的同步发布);连接数很大(几千)时 broker 的行为;TLS 连接的开销'],
    '连接与 channel 数量')
