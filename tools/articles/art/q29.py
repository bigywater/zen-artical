from lib import *
S = SS('q29')
steps = [
    step("RPC 一次往返:客户端声明一个独占的回复队列(服务器生成的名字 amq.gen-…),发请求时带 reply_to=回复队列、correlation_id=一个 uuid;服务端处理后把响应经默认 exchange 发到 reply_to(routing key 就是队列名),带上同一个 correlation_id。实测收到响应 'resp:ping',correlation_id 一致,往返 0.5 ms。线上:客户端 Basic.Publish(26 字节)+ ContentHeader(90 字节,头里多了 reply_to 和 correlation_id),服务端那头 broker 给客户端 Basic.Deliver(92 字节)+ ContentHeader(59 字节)。", t=tl(S(1)), mark=lidx(S(1), 'correlation_id 是否一致', 'Basic.Deliver'), done=lidx(S(1), 'Basic.Publish', 'ContentHeader'), kv=KV([['reply_to', '回复队列名'], ['correlation_id', '把响应对回请求'], ['响应路由', '默认 exchange,key = reply_to']], ['correlation_id'])),
    step("correlation_id 的作用:同一个回复队列上有多个未完成的请求,响应可能乱序。两个服务端实例(一个慢 300 ms、一个快 10 ms)共同消费 rpc_queue,客户端连发 6 个请求 req-0~req-5,响应到达顺序是 req-0、req-2、req-3、req-4、req-5、req-1——慢实例拿到的 req-1 最后才回来。靠 correlation_id,每个响应都能对回自己的请求。", t=tl(S(2)), mark=lidx(S(2), '请求发送顺序'), done=lidx(S(2), '请求发送顺序'), b=bars([['req-0', 1, '第 1 个到'], ['req-2', 2, '第 2 个到'], ['req-5', 5, '第 5 个到'], ['req-1', 6, '第 6 个到(慢实例)']], 6, mark=[3], done=[0, 1, 2]), kv=KV([['响应顺序', '与请求顺序无关'], ['correlation_id', '唯一把响应对回请求的凭据'], ['6 个响应', '全部对得上']], ['correlation_id'])),
    step("回复队列的三种做法(各 2000 次顺序调用,服务端立即回复):每次请求新建一个独占队列,p50 3.317 ms、p99 5.261 ms,292 次/秒;复用一个独占回复队列 + correlation_id,p50 0.257 ms、p99 0.459 ms,3738 次/秒;direct reply-to(amq.rabbitmq.reply-to,伪队列,不用声明),p50 0.237 ms、p99 0.369 ms,4043 次/秒。每次新建队列慢了一个数量级(多了声明、订阅、删除三次往返),后两种几乎一样。", t=tl(S(3)), mark=lidx(S(3), '(a)'), done=lidx(S(3), '(b)', '(c)'), b=bars([['(a) 每次新建队列', 3.317, 'p50 3.317 ms'], ['(b) 复用回复队列', 0.257, 'p50 0.257 ms'], ['(c) direct reply-to', 0.237, 'p50 0.237 ms']], 3.317, mark=[0], done=[1, 2]), kv=KV([['每次新建', 'p50 3.317 ms,292 次/秒'], ['复用 / direct reply-to', 'p50 0.24~0.26 ms'], ['结论', '别为每个请求新建回复队列']], ['结论'])),
    step("服务端不在线时:没有服务端,客户端等了 3 秒收到的回复是 0 条——RPC 必须自己设超时。给请求加 expiration 也不一定能让它及时消失:发了两个请求,一个没有 expiration、一个 expiration=1000 ms,3.5 秒后 rpc_queue 里还剩 2 条——带 expiration 的那条排在没有 expiration 的后面,出不了队头(第 11 篇讲的队头阻塞),没有被丢掉。", t=tl(S(4)), mark=lidx(S(4), '剩 2 条'), done=lidx(S(4), '没有服务端'), kv=KV([['没有服务端', '客户端要自己超时'], ['expiration', '只在队头检查'], ['rpc_queue 里', '3.5 s 后仍有 2 条']], ['expiration'])),
]
A = mkartq('q29', 29, 'RabbitMQ,RPC,reply_to,correlation_id,direct reply-to,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测 RPC 模式:reply_to + correlation_id 的线上帧;两个速度不同的服务端使响应乱序到达,靠 correlation_id 对应;每次新建回复队列 p50 3.317 ms,复用回复队列 0.257 ms,direct reply-to 0.237 ms;服务端不在线时客户端要自己超时,带 expiration 的请求会被队头挡住。',
    '用消息队列做 RPC:请求怎么告诉服务端“把结果发到哪”,多个请求并发时怎么把响应对回去?回复队列怎么建才不拖慢?服务端挂了怎么办?这篇逐项在线上和延迟上量一遍。',
    [('3.317 vs 0.237 ms', '每次新建回复队列与 direct reply-to 的 p50 往返延迟'), ('req-1 最后到', '快慢两个服务端并发时,响应到达顺序与请求顺序不同,靠 correlation_id 对应'), ('2 条', '无服务端、一个带 expiration 的请求被队头挡住,3.5 秒后 rpc_queue 里剩的条数')],
    [('基本机制', '<p>请求带 <code>reply_to</code>(回复队列名)和 <code>correlation_id</code>(唯一标识)。服务端把响应发到默认 exchange、routing key=reply_to,并带回同一个 correlation_id。</p>'),
     ('乱序', '<p>多个请求并发时响应可能乱序到达(服务端实例的速度不同),只有 correlation_id 能把响应对回请求。</p>'),
     ('回复队列的做法', '<p>为每个请求新建回复队列最慢(p50 3.317 ms),复用一个回复队列(0.257 ms)和 direct reply-to(0.237 ms)快一个数量级。</p>'),
     ('服务端不在', '<p>RPC 没有天然的超时,客户端要自己设;请求的 <code>expiration</code> 受队头阻塞影响,不是一个可靠的清理手段。</p>')],
    steps,
    [ENV_Q + '。线上帧经自己写的 TCP 代理;往返延迟是 2000 次顺序调用(服务端立即回复),pika BlockingConnection;乱序实验用两个消费 rpc_queue 的服务端线程(慢 300 ms、快 10 ms,prefetch=1),响应顺序受调度影响,每次运行可能不同',
     '没有验证:direct reply-to 在服务端和客户端不同连接时的限制(必须同一 channel 上订阅);quorum 队列作为 rpc_queue;并发请求数很大时回复队列的吞吐;服务端崩溃时未回复请求的重投与重复响应;客户端的超时与重试策略的完整实现'],
    'RPC 模式')
