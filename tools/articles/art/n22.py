from lib import *
S = SS('n22')
steps = [
    step("原始 TCP 连接发请求,200 ms 时直接关闭。GET /wait:handler 在 201 ms 看到 Request.Context() 被取消(context canceled)。POST 声明 Content-Length 1000 却只发 10 字节:如果 handler 不读 body(/nobody),等满 2000 ms 也始终没有收到取消;如果 handler 在读 body(/readbody),读到 10 字节后在 201 ms 返回 unexpected EOF,此时 Request.Context() 已是 canceled。", t=tl(S(1)), mark=lidx(S(1), '等满 2000 ms', 'unexpected EOF'), done=lidx(S(1), '201 ms 时看到 Request.Context() 取消'), b=bars([['GET:感知断开', 201, '201 ms'], ['POST 读 body:感知断开', 201, '201 ms'], ['POST 不读 body:感知断开', 2000, '没有感知(等满 2000 ms)']], 2000, done=[0, 1], mark=[2]), kv=KV([['GET', '201 ms 感知到'], ['POST 且读 body', '读不到更多数据时 unexpected EOF,201 ms'], ['POST 不读 body', '2 秒都感知不到']], ['POST 不读 body'])),
    step("断开之后继续写:客户端 100 ms 断开,handler 睡到 300 ms 后每次写 64 KB 并 Flush。这次运行第 2 次写(累计 68 KB)返回 write: broken pipe,此时 c.Request.Context().Err() 是 context canceled;另一次运行里第 1 次写(56 KB)就失败——先写进内核缓冲区的字节数取决于 TCP 栈,所以不是固定的第几次,但都在几十 KB 之内。", t=tl(S(2)), mark=lidx(S(2), 'broken pipe'), done=lidx(S(2), '客户端 100ms 时断开'), kv=KV([['写错误', 'write: broken pipe'], ['时机', '断开后写的第 1~2 个 64 KB 内'], ['此时 Context', 'Request.Context().Err() = context canceled']], ['时机'])),
    step("断开之后 c.Done() 与 Request.Context() 的状态:ContextWithFallback=false 时,c.Request.Context().Done() 在 151 ms 触发,c.Done() 为 nil、100 ms 内没有触发;true 时 c.Request.Context().Done() 在 152 ms 触发,c.Done() 也已触发。", t=tl(S(3)), mark=lidx(S(3), 'ContextWithFallback=false'), done=lidx(S(3), 'ContextWithFallback=true'), kv=KV([['false', 'c.Done()==nil,要用 Request.Context()'], ['true', '两者同时触发'], ['延迟', '都约等于断开后的 1~2 ms']], ['false'])),
    step("原因在 net/http 服务器:它为每个请求启动一个后台读 goroutine 来发现客户端关闭连接,但源码注释写明:请求带 body 时,要等到整个 body 被读完(bodyRemains 为假)才启动后台读(registerOnHitEOF(startBackgroundRead))。不读 body 的 POST,断开就没人发现,Request.Context() 不会被取消。", t=tl(S(4)), mark=lidx(S(4), 'start the background read only after the entire body has been consumed', 'registerOnHitEOF'), done=lidx(S(4), 'startBackgroundRead()'), kv=KV([['无 body', '请求一开始就后台读'], ['有 body', '读完 body 才后台读'], ['后果', '没读 body 的 handler 看不到客户端断开']], ['后果'])),
]
A = mkartn('n22', 22, 'Gin,客户端断开,Request.Context,net/http,Go,真实验证,动画演示',
    '在 Gin v1.12.0 + Go 1.27.1 的真实服务上实测客户端断开:GET 请求 201 ms 后 handler 感知到 Request.Context() 取消;带 body 的 POST 如果 handler 不读 body,2 秒都感知不到(net/http 读完 body 才启动后台读);断开后写入几十 KB 内收到 broken pipe。',
    '客户端关掉浏览器标签,服务端的 handler 什么时候才知道?这篇用原始 TCP 连接模拟断开,量出 GET 和 POST 的感知时间,看断开之后写响应会怎样,并从 net/http 的源码解释为什么不读 body 的 POST 感知不到。',
    [('201 ms', 'GET 请求客户端 200 ms 断开后,handler 感知到的时间'), ('2000 ms', '不读 body 的 POST 在客户端断开后,等满 2 秒仍没有收到取消'), ('68 KB', '断开后继续 Flush 64 KB 的块,这次运行在第 2 次写(累计 68 KB)收到 broken pipe')],
    [('GET 与读 body 的 POST', '<p>没有 body 的请求,net/http 在请求一开始就启动后台读 goroutine 监测连接,断开后 1~2 ms 内 <code>Request.Context()</code> 就被取消。有 body 的请求在 handler 读 body 时,读到连接关闭会返回 <code>unexpected EOF</code>,同时 context 也被取消。</p>'),
     ('断开之后写响应', '<p>断开之后往连接里写,前几 KB 会被内核缓冲区吸收而不报错,继续写才会返回 <code>write: broken pipe</code>。具体是第几次写失败取决于 TCP 缓冲区,所以不能指望“写一次就知道客户端走了”,要靠 context。</p>'),
     ('c.Done() 的区别', '<p>断开后 <code>c.Request.Context().Done()</code> 总是会触发;<code>c.Done()</code> 只有在 <code>ContextWithFallback</code> 打开时才会触发,否则是 nil 通道,<code>select</code> 在上面永远不会命中。</p>'),
     ('不读 body 的 POST', '<p>net/http 的服务器代码里写着:请求带 body 时,要等整个 body 读完才启动后台读。所以只处理 header、不读 body 的 handler(比如先鉴权再拒绝)看不到客户端断开,<code>Request.Context()</code> 不会被取消,耗时的下游调用也不会被取消。需要及时取消时,应当先把 body 读掉(或者用 <code>http.MaxBytesReader</code> 之类限制后读掉)。</p>')],
    steps,
    [ENV_N_GIN + '。服务端是 httptest.NewServer 起的真实 net/http 服务器,客户端用 net.Dial 的原始 TCP 连接手写 HTTP/1.1 请求并在指定时刻 Close;源码引用来自 Go 1.27.1 的标准库;每种情形各一次(断开后写入的第几次失败在两次运行里不同,见正文)',
     '没有验证:HTTP/2 下的取消行为(RST_STREAM);经过反向代理(nginx 等)时断开的传播;keep-alive 连接复用时的行为;大 body 且已经读完时的情形;“读完 body 再等”的手法是否在所有情形下都能及时取消(只验证了读不到更多数据时的 unexpected EOF)'],
    '客户端断开')
