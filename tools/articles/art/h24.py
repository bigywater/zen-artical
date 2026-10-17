from lib import *
S = SS('h24')
steps = [
    step("服务端默认的接收上限是 4 MiB = 4194304 字节(读源码 server.go:defaultServerMaxReceiveMessageSize)。二分找到最大能通过的 payload 是 4194299 字节——序列化后的整条消息正好 4194304 字节(payload 外还有 5 字节的字段头);再多 1 字节的 payload(4194300),消息 4194305 字节,被拒绝:code=ResourceExhausted,message=“grpc: received message larger than max (4194305 vs. 4194304)”。限制比的是 protobuf 序列化之后的字节数,不是你以为的“数据”的大小。", t=tl(S(1)), done=lidx(S(1), '再多一字节时的错误'), mark=lidx(S(1), '最大能通过的 payload'), b=bars([['最大能通过的消息字节数', 4194304, '4194304'], ['再多 1 字节被拒绝(消息字节数)', 4194305, '4194305']], 4194400, mark=[1], done=[0]), kv=KV([['上限', '4194304 字节(4 MiB)'], ['比较的是', '序列化后的整条消息'], ['超过时', 'ResourceExhausted']], ['比较的是'])),
    step("三个方向的限制和各自的错误:服务端收 5 MiB 的请求,ResourceExhausted“grpc: received message larger than max (5242885 vs. 4194304)”;客户端收 5 MiB 的响应(服务端发的),错误完全一样(客户端接收的默认上限同样是 4 MiB);客户端自己设了 MaxCallSendMsgSize(1 MiB) 后发 2 MiB,ResourceExhausted“trying to send message larger than max (2097157 vs. 1048576)”,线上客户端只发出 1 个 HEADERS——这是发送前在客户端本地检查。注意:服务端发送默认上限是 MaxInt32,基本不限,所以大响应是被客户端拒绝的。", t=tl(S(2)), done=lidx(S(2), '客户端 MaxCallSendMsgSize'), mark=lidx(S(2), '服务端收 5 MiB'), b=bars([['三种限制报错的 code 都是 ResourceExhausted', 3, '3 种']], 4, done=[0]), kv=KV([['服务端收请求', 'received message larger than max'], ['客户端收响应', '同样的消息(客户端默认也是 4 MiB)'], ['客户端发请求', 'trying to send message larger than max,本地拒绝']], ['客户端发请求'])),
    step("服务端拒绝一个 64 MiB 的请求之前,线上传了多少字节:ResourceExhausted“received message larger than max (67108869 vs. 4194304)”,耗时 14.7 ms,客户端→服务端的线上字节只有 65670(0.06 MiB,占消息的 0.1%)。服务端读到消息长度前缀就判定超限、立刻结束这个流,不会等整条消息传完。传出去的 65670 字节与初始流控窗口 65535 字节接近(第 10 篇测过窗口),这个对应关系是我的推断,没有单独验证。", t=tl(S(3)), done=lidx(S(3), '64 MiB 的请求'), mark=lidx(S(3), '64 MiB 的请求'), b=bars([['线上实际传出的字节', 65670, '65670'], ['消息总字节(64 MiB)', 67108869, '67108869']], 67200000, mark=[0], done=[1]), kv=KV([['消息大小', '67108869 字节'], ['拒绝前线上字节', '65670(占 0.1%)'], ['耗时', '14.7 ms']], ['拒绝前线上字节'])),
    step("限制是“每条消息”的,不是每个流的:客户端流里发 10 条 3 MiB 的消息(一共 30 MiB),服务端数到 10 条,最终成功;先发一条 1 MiB、再发一条 5 MiB,第二条被拒绝,ResourceExhausted“received message larger than max (5242885 vs. 4194304)”。要传大量数据,把它拆成多条小消息放在流里,不需要调大限制。", t=tl(S(4)), done=lidx(S(4), '先 1 MiB 再 5 MiB'), mark=lidx(S(4), '10 条 3 MiB'), b=bars([['10 条 3 MiB 服务端数到', 10, '10'], ['先 1 MiB 再 5 MiB:通过的消息数', 1, '1']], 11, mark=[1], done=[0]), kv=KV([['10 × 3 MiB', '全部通过(共 30 MiB)'], ['1 MiB + 5 MiB', '第二条被拒绝'], ['含义', '限制按单条消息算']], ['含义'])),
    step("压缩后的大小不算,解压后的大小才算:客户端用 gzip 发 100 MiB 的零,压缩后线上只有 205887 字节(约 201 KiB),服务端默认上限 4 MiB:ResourceExhausted“grpc: received message after decompression larger than max 4194304”;服务端把上限提到 128 MiB 后,同样的请求成功,线上 205917 字节。所以压缩没办法绕过大小限制——这也是对“压缩炸弹”的保护。", t=tl(S(5)), done=lidx(S(5), 'MaxRecvMsgSize(128 MiB)'), mark=lidx(S(5), '默认上限 4 MiB'), b=bars([['线上字节', 205887, '205887'], ['解压后字节(100 MiB)', 104857600, '104857600']], 105000000, mark=[0], done=[1]), kv=KV([['线上', '约 201 KiB'], ['默认上限 4 MiB', '解压后超限被拒绝'], ['提到 128 MiB', '成功']], ['默认上限 4 MiB'])),
    step("调大上限:服务端 MaxRecvMsgSize(64 MiB) 和 MaxSendMsgSize(64 MiB),客户端 MaxCallRecvMsgSize 和 MaxCallSendMsgSize 也设 64 MiB,往返 32 MiB:发 32 MiB 请求成功(29.4 ms),收 32 MiB 响应成功(21.8 ms)(本机回环的耗时)。调大要两头都改,并且要注意内存——一条消息要整条放进内存(第 32 篇讨论大消息的拷贝)。", t=tl(S(6)), done=lidx(S(6), '发 32 MiB 请求'), mark=lidx(S(6), '发 32 MiB 请求'), b=bars([['发 32 MiB 请求 ms', 29.4, '29.4'], ['收 32 MiB 响应 ms', 21.8, '21.8']], 32, done=[0, 1]), kv=KV([['服务端', 'MaxRecvMsgSize / MaxSendMsgSize'], ['客户端', 'MaxCallRecvMsgSize / MaxCallSendMsgSize'], ['成本', '整条消息都在内存里']], ['成本'])),
]
A = mkarth('h24', 24, 'gRPC,消息大小,MaxRecvMsgSize,ResourceExhausted,4MiB,压缩炸弹,Go,真实验证,动画演示',
    '实测 gRPC 的消息大小限制:默认接收上限 4194304 字节比的是序列化后的整条消息;服务端、客户端各自的报错;拒绝 64 MiB 请求前线上只传了约 64 KiB;限制按单条消息而不是流;压缩后不算、解压后才算;怎么调大。',
    'gRPC 单条消息默认最大多少?超了是什么错?在哪一端检查?压缩能不能绕过?这篇用二分查出精确的临界点,并看了拒绝之前线上传了多少数据。',
    [('4194304 字节', '默认接收上限,比的是序列化后的整条消息;payload 最多 4194299 字节'), ('0.1%', '服务端拒绝 64 MiB 请求之前,线上只传了消息的这个比例(65670 字节)'), ('201 KiB → 100 MiB', 'gzip 线上只有 201 KiB,但解压后超限,仍被拒绝')],
    [('默认值', '<p>服务端和客户端接收的默认上限都是 4 MiB;发送的默认上限是 MaxInt32(基本不限)。比较的是序列化后的整条消息。</p>'),
     ('错误', '<p>超限一律是 ResourceExhausted。服务端拒绝请求、客户端拒绝响应、客户端本地拒绝发送,消息文字不同。</p>'),
     ('拒绝得很早', '<p>接收方读到 5 字节的消息前缀就知道长度,超限立刻结束这个流,不会等整条消息传完。</p>'),
     ('按消息计', '<p>限制是单条消息的,流里可以发很多条,总量不受限制。</p>'),
     ('压缩', '<p>压缩后的大小不算,解压后的大小才算,压缩不能绕过限制。</p>'),
     ('调大', '<p>服务端 MaxRecvMsgSize/MaxSendMsgSize,客户端 MaxCallRecvMsgSize/MaxCallSendMsgSize,要两头都设。内存占用随之上升。</p>')],
    steps,
    [ENV_H + '。临界点用二分得到,线上字节来自抓包代理,耗时是本机回环;默认值读自 clientconn.go、server.go;“拒绝前传了 65670 字节与流控窗口接近”是推断',
     '没有验证:服务端发送上限 MaxSendMsgSize 超限时的错误;WithDefaultCallOptions 与单次 CallOption 的优先级;大消息对内存和 GC 的影响(第 32 篇);经过网关或代理(Envoy、nginx)时它们自己的大小限制;流式 RPC 里服务端发送过大消息时客户端的表现'],
    '消息大小限制')
