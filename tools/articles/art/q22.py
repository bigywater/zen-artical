from lib import *
S = SS('q22')
steps = [
    step("心跳时间由两端协商:不指定时,客户端接受 broker 的默认值,list_connections 的 timeout 列是 60;客户端请求 0 就是 0(关掉心跳);请求 5、30、120 分别得到 5、30、120——这几个取值里客户端的值都被采用了,包括比 broker 默认大的 120。", t=tl(S(1)), mark=lidx(S(1), 'heartbeat=0 ', 'heartbeat=120'), done=lidx(S(1), 'heartbeat=None', 'heartbeat=5 ', 'heartbeat=30'), b=bars([['None → 默认', 60, '60 s'], ['请求 5', 5, '5 s'], ['请求 30', 30, '30 s'], ['请求 120', 120, '120 s']], 120, mark=[3], done=[0, 1, 2]), kv=KV([['不指定', '60 s(broker 默认)'], ['请求 0', '0 = 关闭心跳'], ['请求 5 / 30 / 120', '客户端的值生效']], ['请求 0'])),
    step("经过代理看心跳帧:heartbeat=2 的空闲连接,10 秒里客户端和 broker 各发了 10 个 Heartbeat,每个只有 8 字节(帧头 7 + 结尾 1),相邻间隔都是 1.0 秒——也就是超时时间的一半。一个方向的流量:每秒 8 字节,忽略不计。", t=tl(S(2)), mark=lidx(S(2), 'C→S', 'S→C'), done=lidx(S(2), '间隔约 1 秒'), b=bars([['C→S Heartbeat', 10, '10 个'], ['S→C Heartbeat', 10, '10 个']], 10, done=[0, 1]), kv=KV([['帧大小', '8 字节'], ['发送间隔', '超时的一半(2 s → 1 s)'], ['双方', '各发各的']], ['发送间隔'])),
    step("对端悄悄消失:代理停止转发但不断开 TCP(模拟网络黑洞),heartbeat=2 的连接在黑洞开始后 6.1 秒,broker 日志出现 missed heartbeats from client, timeout: 2s,随后连接从 list_connections 里消失。也就是说检测需要的时间大约是超时的 3 倍,不是 1 倍。", t=tl(S(3)), mark=lidx(S(3), '黑洞开始后'), done=lidx(S(3), 'list_connections 此时'), kv=KV([['heartbeat', '2 s'], ['检测时间', '6.1 s(约 3 倍超时)'], ['broker 日志', 'missed heartbeats from client']], ['检测时间'])),
    step("不开心跳(heartbeat=0)的黑洞:代理停止转发 25 秒之后,list_connections 里这条连接仍然是 running、timeout=0——broker 完全发现不了,连接和它的 channel、消费者都还占着。只有 TCP 层的保活(这里没有测)才可能发现;这就是生产上不要把 heartbeat 设成 0 的原因。", t=tl(S(4)), mark=lidx(S(4), 'heartbeat=0,黑洞 25 秒后'), done=lidx(S(4), 'heartbeat=0,黑洞 25 秒后'), kv=KV([['heartbeat=0', '黑洞 25 s 后连接仍 running'], ['占用', '连接、channel、消费者都还在'], ['建议', '不要关闭心跳']], ['heartbeat=0'])),
    step("最常见的坑:pika 的 BlockingConnection 只有在调用 process_data_events(或别的收发操作)时才会发心跳。heartbeat=2,让客户端线程忙 8 秒不收发:broker 日志里新增 1 行 missed heartbeats,连接被关掉,list_connections 里没有了;客户端醒来再发命令得到 StreamLostError(BrokenPipeError)。耗时任务应放到别的线程,或者拆开并穿插 process_data_events,或者适当调大 heartbeat(检测对端宕机也会变慢)。", t=tl(S(5)), mark=lidx(S(5), 'StreamLostError', '8 秒后 broker 日志'), done=lidx(S(5), '解决办法'), kv=KV([['线程忙 8 s(heartbeat=2)', 'broker 判定心跳丢失,关连接'], ['客户端再发', 'StreamLostError'], ['办法', '别阻塞收发线程']], ['线程忙 8 s(heartbeat=2)'])),
]
A = mkartq('q22', 22, 'RabbitMQ,心跳,heartbeat,连接断开检测,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测心跳:默认 60 秒,客户端请求 0/5/30/120 都被采用;heartbeat=2 时双方每秒各发一个 8 字节的 Heartbeat 帧;网络黑洞下 broker 约 6.1 秒(3 倍超时)才发现;heartbeat=0 的黑洞 25 秒后连接仍在;pika 的 BlockingConnection 线程忙 8 秒就会被 broker 踢掉。',
    '心跳是发现“连接其实已经死了”的唯一办法。它怎么协商、线上长什么样、发现一个悄悄消失的对端要多久?关掉心跳会怎样?为什么一个“耗时任务”会让连接莫名其妙断开?这篇用代理做黑洞,一项项量。',
    [('6.1 s', 'heartbeat=2 的连接遇到网络黑洞后,broker 记下 missed heartbeats 的时间(约 3 倍超时)'), ('8 字节', '一个 Heartbeat 帧的大小,每半个超时发一次'), ('0', 'heartbeat=0 时黑洞 25 秒后 broker 对连接的处理:什么都不做,连接仍是 running')],
    [('协商', '<p>broker 在 Connection.Tune 里给出默认 60 秒,客户端 TuneOk 回自己的值,实测客户端请求的 0、5、30、120 都被采用。</p>'),
     ('帧', '<p>Heartbeat 帧只有 8 字节,双方各自每 timeout/2 发一次;连接上有别的数据时同样算“活着”。</p>'),
     ('发现死连接', '<p>对端消失(黑洞)时,broker 约在超时的 3 倍(6.1 s)后记 missed heartbeats 并关闭连接。</p>'),
     ('关掉心跳', '<p>heartbeat=0 时黑洞 25 秒后连接仍然是 running,broker 发现不了,连接和它的 channel、消费者都还占着。</p>'),
     ('线程被阻塞', '<p>BlockingConnection 不在后台线程里发心跳,只在收发调用里处理。线程忙于别的事超过两个心跳间隔,连接就会被 broker 关闭,下一次操作得到 StreamLostError。</p>')],
    steps,
    [ENV_Q + '。第二、三、四节经过自己写的 TCP 代理(hole=True 时停止转发但不断开 TCP);协商结果来自 rabbitmqctl list_connections timeout;“missed heartbeats”来自 broker 日志;第五节客户端 time.sleep 8 秒模拟忙',
     '没有验证:TCP keepalive 对 heartbeat=0 的补救作用;多次测量 “3 倍超时” 的分布(只测了 2 次,6.0 与 6.1 秒);TLS 连接上的心跳;客户端库自己实现后台心跳线程(如 aio-pika / Java 客户端)的行为;非常大的 heartbeat 值;服务器端 heartbeat 默认值的修改'],
    '心跳')
