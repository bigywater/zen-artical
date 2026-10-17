from lib import *
S = SS('q6')
steps = [
    step("mandatory=True 发一条路由不到的消息(exchange x.d、key nomatch,带 message_id、content_type、自定义 header 和 delivery_mode=2)。线上是 Basic.Publish → ContentHeader → ContentBody 发出去,再收到 Basic.Return → ContentHeader → ContentBody 退回来:reply-code=312、reply-text='NO_ROUTE',还带着原来的 exchange 和 routing key,属性(message_id=id-42、content_type、headers、delivery_mode)和消息体 b'hello-return' 一字不改。退回的是一条完整的消息,发布方可以直接重发或记日志。", t=tl(S(1)), mark=lidx(S(1), 'Basic.Return: reply-code=312', '线上帧'), done=lidx(S(1), '退回的属性'), kv=KV([['reply-code', '312 NO_ROUTE'], ['退回内容', 'exchange、routing key、属性、消息体原样'], ['帧', 'Basic.Return + ContentHeader + ContentBody']], ['reply-code'])),
    step("没开 confirm 时 Return 是异步的:连发 1000 条路由不到的 mandatory 消息,这些发布调用本身花了 120 ms,返回时一个 Return 回调都还没处理;再处理 1 秒的网络事件之后收到 1000 个,顺序和发布顺序一致。所以发布方要有专门处理 Return 的回调,并且保证事件循环在转;只“发完就关连接”会丢掉这些 Return。", t=tl(S(2)), mark=lidx(S(2), '这时已处理的 Return 回调 0 个'), done=lidx(S(2), '1000 条发布调用'), kv=KV([['Return', '异步,从 broker 推回来'], ['发布调用', '不等 Return,立刻返回'], ['顺序', '与发布顺序一致'], ['风险', '发完就关连接 → 收不到 Return']], ['Return'])),
    step("哪些算“不可路由”:direct 的 key 不匹配、没有任何绑定的 fanout、topic 不匹配、headers 不匹配,都是退回 312;匹配的三种(direct、topic、headers)都已路由、没有退回。exchange 本身不存在时不是 Return,而是 channel 被 broker 关掉(出错的是 channel,不是 Return)。", t=tl(S(3)), mark=lidx(S(3), '退回 312', 'channel 被关'), done=lidx(S(3), '已路由'), kv=KV([['key / 头不匹配', '312 NO_ROUTE'], ['fanout 无绑定', '312 NO_ROUTE'], ['exchange 不存在', 'channel 级错误,不是 Return']], ['exchange 不存在'])),
    step("备用交换机(alternate-exchange)是另一条出路:x.main 设置 alternate-exchange=x.ae,发 5 条 mandatory(2 条 key 能路由、3 条不能):q.main 收到 2 条,q.ae 收到那 3 条(stray1、2、3),被退回 0 条——转给备用交换机算路由成功,mandatory 不再触发。若备用交换机也路由不到(x.main2 → 没有绑定的 x.ae2),才退回 312。", t=tl(S(4)), mark=lidx(S(4), '被退回 1 条', '被退回 0 条'), done=lidx(S(4), 'q.ae 里的消息'), b=bars([['q.main', 2, '2 条'], ['q.ae', 3, '3 条'], ['被退回', 0, '0 条']], 3, mark=[2], done=[0, 1]), kv=KV([['alternate-exchange', '路由不到时的兜底'], ['有备用且能路由', '不触发 Return'], ['备用也路由不到', '才退回 312']], ['alternate-exchange'])),
    step("代价:向可路由的队列发 20000 条,mandatory=False 与 True 交替 7 轮取中位数,分别是 526 ms 和 523 ms,最小值 512 与 517 ms——在可路由的情况下 mandatory 没有可测的开销(broker 只在路由不到时才需要多发一次)。", t=tl(S(5)), mark=lidx(S(5), 'mandatory=False 中位数'), done=lidx(S(5), 'mandatory=False 中位数'), b=bars([['mandatory=False', 526, '526 ms'], ['mandatory=True', 523, '523 ms']], 526, mark=[1], done=[0]), kv=KV([['可路由时', '无可测开销'], ['不可路由时', '多一次 Return 往返']], ['可路由时'])),
]
A = mkartq('q6', 6, 'RabbitMQ,mandatory,Basic.Return,alternate-exchange,NO_ROUTE,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测 mandatory:路由不到的消息会以 312 NO_ROUTE 连同属性和消息体原样退回,Return 是异步的;direct、fanout、topic、headers 的不匹配都算不可路由,exchange 不存在则是 channel 错误;备用交换机能接住时不触发 Return;可路由时 mandatory 开销不可测。',
    '消息发出去没人要,默认是悄悄丢掉。mandatory 标志让 broker 把它退回来,但退回来的是什么、什么时候到、什么情形才算“不可路由”?有备用交换机时又怎样?这篇用 TCP 代理看线上帧,并逐种情形验证。',
    [('312', '路由不到的 mandatory 消息收到的 reply-code(NO_ROUTE)'), ('1000 / 1000', '无 confirm 时连发 1000 条不可路由消息,最终收到的 Return 数,顺序不变'), ('0 条', '设了备用交换机且它能接住时,被退回的消息数')],
    [('Basic.Return', '<p>发布时 <code>mandatory=True</code> 且消息无法路由到任何队列,broker 会发回 <code>Basic.Return</code>(后面跟内容头和内容体),带 reply-code 312 NO_ROUTE,以及原来的 exchange、routing key、属性和消息体。</p>'),
     ('异步', '<p>Return 不是发布调用的返回值,而是 broker 之后推回来的一个帧。发布方要注册回调并保持事件循环运行;如果同时开了 confirm,Return 一定先于该条的 Ack。</p>'),
     ('不可路由的定义', '<p>direct/topic/headers 不匹配、没有任何绑定的 fanout 都算不可路由;exchange 不存在不是 Return,而是 channel 错误(channel 被关闭)。</p>'),
     ('备用交换机', '<p>给 exchange 设置 <code>alternate-exchange</code> 参数后,路由不到的消息转给它;转成功就算路由成功。只有备用交换机也路由不到才会退回。</p>'),
     ('开销', '<p>可路由时 mandatory 没有可测的额外开销(526 ms 对 523 ms)。</p>')],
    steps,
    [ENV_Q + '。第一、二、三、四节经过自己写的 TCP 代理(第一节看线上帧);第五节直连 broker,不经过代理,mandatory 交替 7 轮取中位数,不开 confirm',
     '没有验证:与 publisher confirm 同时开启时 Return / Ack 的顺序在高并发下的表现(第 5 篇只在单条上看到先 Return 后 Ack);quorum / stream 队列;immediate 标志(3.0 起已去掉);集群中跨节点路由失败;备用交换机链很长时的行为'],
    'mandatory 与 return')
