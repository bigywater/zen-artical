from lib import *
S = SS('g76')
steps = [
    step("一个连接的状态变化(用 Server.ConnState 回调记录):一个 TCP 连接上连续发 2 个请求再关闭,ConnState 依次是 new → active → idle → active → idle → closed。连接在请求之间是 idle,重新有请求时又变回 active——同一个连接服务了两个请求。", t=tl(S(1)), mark=lidx(S(1), 'new → active → idle → active → idle → closed'), kv=KV([['一个连接', '服务多个请求(keep-alive)'], ['状态', 'new → active → idle → active → idle → closed']], ['状态'])),
    step("每个连接一个 goroutine:500 个连接各有一个请求卡在 Handler 里,goroutine 数 2 → 1002(增加 1000,约每个连接 2.0 个);放行并关闭连接后回到 2。多出来的另一半见最后一节的源码。", t=tl(S(2)), mark=lidx(S(2), '2 → 1002'), done=lidx(S(2), '放行并关闭连接后'), b=bars([['500 个连接新增 goroutine', 1000, '1000'], ['放行后剩余', 2, '2']], 1000, mark=[0], done=[1]), kv=KV([['500 个连接', 'goroutine 2 → 1002'], ['每个连接', '约 2 个'], ['关闭后', '回到 2']], ['每个连接'])),
    step("响应头是自动生成的:Handler 写 100 字节的小响应:Content-Length: 100;Handler 里 Flush 过的响应:Transfer-Encoding: chunked(没有 Content-Length);写 10000 字节:也是 chunked;不设类型时 Content-Type 自动是 text/plain; charset=utf-8。WriteHeader(200) 之后再 WriteHeader(500):响应仍是 200,服务器错误日志是 “http: superfluous response.WriteHeader call from …”。", t=tl(S(3)), done=lidx(S(3), '/small', '/flush', '/big'), mark=lidx(S(3), '/twice'), kv=KV([['小响应', 'Content-Length 自动算'], ['Flush 过或较大', 'Transfer-Encoding: chunked'], ['重复 WriteHeader', '不生效,日志有 superfluous 提示']], ['重复 WriteHeader'])),
    step("Handler 里 panic:请求 /boom 时客户端收到 0 字节,读结束没有 HTTP 响应——连接被直接关掉了;之后再请求 /ok 仍正常返回 ok,进程没有崩溃;服务器日志第一行是 http: panic serving 127.0.0.1:…: handler 里 panic。", t=tl(S(4)), mark=lidx(S(4), '请求 /boom', 'panic serving'), done=lidx(S(4), '之后再请求 /ok'), kv=KV([['客户端', '0 字节,连接被关'], ['进程', '没有崩溃'], ['日志', 'http: panic serving …']], ['进程'])),
    step("客户端断开,Handler 怎么知道:客户端在请求发出 100 ms 后直接关闭连接,handler 里的 r.Context() 在 100 ms 后(也就是几乎立刻)被取消,错误是 context canceled。", t=tl(S(5)), mark=lidx(S(5), 'context canceled'), kv=KV([['客户端关闭连接', 'r.Context() 被取消'], ['延迟', '几乎立刻(100 ms 的测量粒度)']], ['客户端关闭连接'])),
    step("文档与源码:ConnState 表示客户端连接的状态,是可选的 Server.ConnState 钩子的参数;Serve 接受连接,为每个连接创建一个新的服务 goroutine,这些 goroutine 读请求再调用 s.Handler;Serve 总是返回非 nil 错误并关闭 l,Shutdown 或 Close 之后返回 ErrServerClosed。server.go 里 startBackgroundRead 函数(第 731 行)里有 go cr.backgroundRead()(第 742 行),在第 2126 行被调用——Handler 运行期间,另有一个 goroutine 在后台读连接,这也是客户端断开能被及时发现的原因,以及每个连接约 2 个 goroutine。", t=tl(S(6)), done=lidx(S(6), 'ConnState represents', 'creating a new service goroutine'), mark=lidx(S(6), 'server.go:731', 'server.go:742', 'server.go:2126'), kv=KV([['每个连接', '一个服务 goroutine'], ['Handler 运行期间', '多一个后台读 goroutine'], ['作用', '发现客户端断开,取消 r.Context()']], ['Handler 运行期间'])),
]
A = mkartg('g76', 76, 'Go,net/http,服务端,连接,goroutine,真实验证,动画演示',
    '在 Go 1.27.1 里实测 net/http 服务端:一个连接依次经历 new → active → idle → active → idle → closed;500 个连接让 goroutine 增加 1000(每个连接约 2 个,因为 Handler 运行期间还有后台读 goroutine);小响应自动带 Content-Length,Flush 或大响应用 chunked;Handler panic 只关闭当前连接、不会让进程崩溃;客户端断开会立即取消 r.Context()。',
    '一个 HTTP 请求从 Accept 到 Handler,中间发生了什么?这篇用原始 TCP 客户端和 ConnState 钩子,实测连接状态、goroutine 数、响应头的生成规则、panic 的处理和客户端断开的感知,并对着 server.go 的源码确认每个连接多出的那个 goroutine。',
    [('+1000', '500 个连接各有一个请求在 Handler 里时,goroutine 的增量(每个连接约 2 个)'), ('chunked', 'Flush 过或超过缓冲的响应用 Transfer-Encoding: chunked,小响应自动算 Content-Length'), ('0 字节', 'Handler panic 时客户端收到的响应:连接被关掉,进程不崩')],
    [('连接的生命周期', '<p>用 <code>ConnState</code> 钩子看到,一个 TCP 连接依次是 new → active → idle → active → idle → closed:keep-alive 让同一个连接服务多个请求,请求之间是 idle。</p>'),
     ('goroutine 数', '<p>500 个连接各有一个请求卡在 Handler 里,goroutine 增加 1000,即每个连接约 2 个;放行并关闭连接后回到基线。文档说 <code>Serve</code> 为每个连接创建一个服务 goroutine,多出来的那个是 Handler 运行期间的后台读 goroutine(<code>server.go</code> 里的 <code>startBackgroundRead</code>)。</p>'),
     ('响应头自动生成', '<p>100 字节的响应带 <code>Content-Length: 100</code>;Handler 里 Flush 过,或者响应较大(10000 字节),就是 <code>Transfer-Encoding: chunked</code>;没设类型时自动嗅探成 <code>text/plain; charset=utf-8</code>。重复调用 <code>WriteHeader</code> 不生效,服务器日志会出现 “superfluous response.WriteHeader call”。</p>'),
     ('Handler panic', '<p>服务器恢复这个 panic、记一行 <code>http: panic serving</code>、关掉这个连接:客户端读到 0 字节,其它请求不受影响,进程不崩。</p>'),
     ('客户端断开', '<p>客户端中途关闭连接:后台读发现连接关闭,<code>r.Context()</code> 被取消(实验里约 100 ms 的测量粒度内就取消了),Handler 应该监听 <code>ctx.Done()</code> 尽早收手。</p>'),
     ('源码位置', '<p>在本机的 <code>server.go</code> 里,<code>startBackgroundRead</code> 在 731 行,里面第 742 行启动后台 goroutine,第 2126 行调用它。行号只对 Go 1.27.1 有效。</p>')],
    steps,
    [ENV_G + '。服务端用 net/http.Server,客户端用原始 net.Dial 写 HTTP/1.1 请求并手工解析响应头;ConnState 钩子记录状态序列;goroutine 数用 runtime.NumGoroutine;读过的文档与源码:go doc net/http.ConnState / Server.Serve,src/net/http/server.go 的 startBackgroundRead',
     '没有验证:HTTP/2 的情形(单独一篇)、TLS 连接、请求体很大时的读取行为、Server.Shutdown 的等待逻辑、pipelining、响应头的完整生成规则(只看了 Content-Length、chunked、Content-Type)、Linux 上的差别'],
    'net/http 服务端')
