from lib import *
S = SS('g84')
steps = [
    step("不处理信号:客户端发出一个要处理 2 秒的 /slow 请求,0.5 秒后给服务进程发 SIGTERM。客户端的这个请求在 0.51 秒后失败(RemoteDisconnected: Remote end closed connection without response);SIGTERM 之后新发的请求立刻 Connection refused;服务进程退出码 −15(被信号杀死)。", t=tl(S(1)), mark=lidx(S(1), '0.51 秒后失败', '退出码 -15'), done=lidx(S(1), '新发的请求'), kv=KV([['在途请求', '0.51 秒后连接被断,没有响应'], ['新请求', 'Connection refused'], ['进程', '被 SIGTERM 杀死(−15)']], ['在途请求'])),
    step("signal.NotifyContext + srv.Shutdown(10 秒超时):同样的场景,客户端的 /slow 请求 2.00 秒后收到 200 \"slow done\";SIGTERM 之后新发的请求 Connection refused;服务进程退出码 0,发信号后 1.63 秒退出。服务进程日志:+755 ms 收到信号并调用 srv.Shutdown,+2360 ms Shutdown 返回 nil。", t=tl(S(2)), done=lidx(S(2), '2.00 秒后收到 200', 'Shutdown 返回:<nil>'), mark=lidx(S(2), '收到信号,调用 srv.Shutdown', '新发的请求'), kv=KV([['在途请求', '正常完成,200 slow done'], ['新请求', '被拒绝(监听已关)'], ['退出', '等请求结束后以 0 退出,约 1.6 秒']], ['在途请求'])),
    step("Shutdown 的超时比请求短(500 ms 对 2 秒的请求):客户端的请求 1.01 秒后失败(RemoteDisconnected);服务进程在 +750 ms 开始 Shutdown,+1251 ms 返回 context deadline exceeded,发信号后 0.50 秒退出。超时一到就不再等,请求被截断。", t=tl(S(3)), mark=lidx(S(3), '1.01 秒后失败', 'context deadline exceeded'), kv=KV([['Shutdown 超时', '500 ms'], ['结果', '返回 context deadline exceeded,请求被截断'], ['提醒', '超时要和最长请求匹配']], ['结果'])),
    step("被 Hijack 的连接(WebSocket 一类)Shutdown 不会等:handler 劫持连接并在 2 秒后才写响应。收到信号后 Shutdown 立刻返回 nil(+755 ms 调用、+755 ms 返回),发信号后 0.20 秒进程退出,客户端 0.51 秒后失败(RemoteDisconnected)。", t=tl(S(4)), mark=lidx(S(4), '0.51 秒后失败', 'Shutdown 返回:<nil>'), kv=KV([['Shutdown', '立刻返回 nil,不管被劫持的连接'], ['进程', '随即退出,连接被断'], ['做法', '自己通知并等待长连接(RegisterOnShutdown)']], ['做法'])),
    step("文档(go doc net/http.Server.Shutdown):Shutdown 不打断任何活动连接地优雅关闭服务器:先关闭所有打开的监听器,再关闭所有空闲连接,然后无限期地等待连接回到空闲并关闭;如果传入的 context 在完成前过期,返回 context 的错误;调用后 Serve 等立即返回 ErrServerClosed,所以要确保程序不退出而是等待 Shutdown 返回;Shutdown 不会尝试关闭或等待被劫持的连接(如 WebSocket),调用者应另行通知这类长连接并等待它们关闭,可以用 Server.RegisterOnShutdown 注册通知。", t=tl(S(5)), done=lidx(S(5), 'Shutdown gracefully shuts down'), kv=KV([['步骤', '关监听 → 关空闲连接 → 等活动连接'], ['Serve 返回', 'ErrServerClosed 立即返回'], ['被劫持的连接', '不关也不等']], ['被劫持的连接'])),
]
A = mkartg('g84', 84, 'Go,优雅退出,os/signal,Shutdown,NotifyContext,真实验证,动画演示',
    '在 Go 1.27.1(macOS)里实测优雅退出:不处理 SIGTERM 时,2 秒的在途请求 0.51 秒后被断开;用 signal.NotifyContext + Server.Shutdown 时,在途请求 2.00 秒后正常完成、新连接被拒绝、进程 1.63 秒后以 0 退出;Shutdown 超时 500 ms 时请求被截断并返回 context deadline exceeded;被 Hijack 的连接 Shutdown 不会等。',
    'Kubernetes 一类系统停服务时先发 SIGTERM,服务如果不处理,正在处理的请求就会被直接掐掉。优雅退出的核心是 Shutdown,但它到底等什么、不等什么?这篇把服务做成单独的进程,用脚本发真实的 SIGTERM,看客户端和进程的结果。',
    [('0.51 秒 vs 2.00 秒', '不处理信号与优雅关闭时,2 秒的在途请求的结局:被断开 vs 正常完成'), ('1.63 秒', '优雅关闭时从发信号到进程退出的时间(等在途请求结束)'), ('不等 Hijack', 'Shutdown 不会等被劫持的连接,返回 nil 后进程立即退出')],
    [('不处理信号', '<p>SIGTERM 的默认行为就是终止进程。在途的 2 秒请求在 0.51 秒时被断开,客户端看到没有响应的连接关闭;新请求直接被拒绝(连接被拒)。</p>'),
     ('NotifyContext + Shutdown', '<p><code>signal.NotifyContext</code> 把信号变成 context 的取消;收到后调用 <code>srv.Shutdown</code>:先关监听(新请求被拒绝),再等在途请求完成。在途请求 2.00 秒后正常返回 200,进程在发信号后 1.63 秒以 0 退出。注意 <code>main</code> 要等 <code>Shutdown</code> 返回再退出。</p>'),
     ('Shutdown 的超时', '<p>给 <code>Shutdown</code> 的 context 设了 500 ms,而请求需要 2 秒:500 ms 一到它返回 <code>context deadline exceeded</code>,进程退出,请求被截断。超时要略大于最长请求,但也要小于编排系统给的强制杀死期限。</p>'),
     ('被 Hijack 的连接', '<p>WebSocket 之类被 <code>Hijack</code> 的连接不在 <code>Shutdown</code> 的管理范围内:它立刻返回 <code>nil</code>,随后进程退出,连接被断。需要自己通过 <code>RegisterOnShutdown</code> 通知这些连接并等待它们结束。</p>'),
     ('文档', '<p>文档的描述和实验一致:先关监听器,再关空闲连接,然后无限期等待活动连接;调用后 <code>Serve</code> 返回 <code>ErrServerClosed</code>,程序应等待 <code>Shutdown</code> 返回。</p>')],
    steps,
    [ENV_G + '。服务端是单独编译的 Go 程序,由 Python 脚本启动、用 os.kill 发 SIGTERM,并用 http.client 发请求;时间用 Python 的 time.time,精度约 10 ms;每种情形只运行一次;读过的文档:go doc net/http.Server.Shutdown',
     '没有验证:SIGINT/第二次信号处理(NotifyContext 的 stop 之后默认行为恢复)、Kubernetes 的 preStop 与 terminationGracePeriod、keep-alive 空闲连接的关闭细节、HTTP/2 下的 GOAWAY、Linux 上的差别、RegisterOnShutdown 的实际写法'],
    '优雅退出')
