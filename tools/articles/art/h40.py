from lib import *
S = SS('h40')
steps = [
    step("到期时线上发生什么:MaxConnectionAge = 1 秒(宽限默认 = 无限),连接上有一个已完成的调用。抓包代理看到:1.053 秒(1 秒 + 抖动)服务端发出 GOAWAY,最后流 ID 2147483647(最大值,意思是“还在接受新流,但要关了”),错误码 NO_ERROR,附加数据 “max_age”;此时连接上没有在途的流,所以只看到这一个 GOAWAY,TCP 连接 1 条,客户端状态变成 IDLE(下一次调用才重新建连,第 39 篇)。附加数据里的 max_age 说明这是年龄到期触发的,idle 到期时是 max_idle(读源码)。", t=tl(S(1)), done=lidx(S(1), 'TCP 连接数'), mark=lidx(S(1), 'GOAWAY 最后流'), b=bars([['MaxConnectionAge 设置 s', 1.0, '1.0'], ['GOAWAY 实际到达 s', 1.053, '1.053']], 1.2, mark=[1], done=[0]), kv=KV([['GOAWAY', '最后流 2147483647,NO_ERROR,max_age'], ['到达时刻', '1.053 秒(1 秒 + 抖动)'], ['之后', '客户端 IDLE,下次调用重连']], ['GOAWAY'])),
    step("抖动:MaxConnectionAge = 2 秒,新建 30 条连接,第一个 GOAWAY 到达的时刻:最早 1.87 秒、最晚 2.21 秒、平均 2.05 秒。读源码(http2_server.go):服务端给 MaxConnectionAge 加了 ±10% 的随机抖动,避免所有连接在同一时刻一起断开重连;观察到的范围与 1.8~2.2 秒基本吻合(多出来的零点几十毫秒是调度和测量误差)。", t=tl(S(2)), done=lidx(S(2), '观察到 30 个连接'), mark=lidx(S(2), '观察到 30 个连接'), b=bars([['最早 s', 1.87, '1.87'], ['平均 s', 2.05, '2.05'], ['最晚 s', 2.21, '2.21']], 2.3, done=[0, 1, 2]), kv=KV([['设置值', '2 秒'], ['实测范围', '1.87 ~ 2.21 秒'], ['原因', '±10% 随机抖动(读源码)']], ['原因'])),
    step("到期时还有长调用:服务端流(一共 4 秒,每 500 ms 发一条),MaxConnectionAge = 1 秒。宽限默认(无限):流一直跑到 4.02 秒自己结束,收到 8 条消息,结束时是 io.EOF(状态 OK),服务端发送一直成功——到期只是不再接受新流,在途的流不受影响;宽限 1 秒:服务端第一次发送失败在 2.50 秒(约 1 秒 + 1 秒宽限之后连接被关闭),客户端在 3.07 秒时收到 Unavailable(“closing transport due to: connection error: …error reading from server: EOF”),已收到 5 条;客户端发现的时刻比服务端发送失败的时刻晚约 0.6 秒,原因我没有查。长流超过“年龄 + 宽限”就会被打断,客户端要能重新发起。", t=tl(S(3)), done=lidx(S(3), '宽限 1 秒'), mark=lidx(S(3), '宽限默认'), b=bars([['宽限默认:流持续 s(跑完)', 4.02, '4.02'], ['宽限 1 秒:服务端发送失败 s', 2.5, '2.50'], ['宽限 1 秒:客户端出错 s', 3.07, '3.07']], 4.2, mark=[1, 2], done=[0]), kv=KV([['宽限默认(无限)', '长流跑完 4.02 秒,8 条'], ['宽限 1 秒', '约 2.5 秒后被打断,客户端 Unavailable'], ['含义', '长流必须能重连续传']], ['含义'])),
    step("持续负载下的连接更替:8 个 goroutine 连续调用 4 秒。没有设置:总调用 142588,失败 0,TCP 连接 1 条,p50 210 µs、p99 418 µs;MaxConnectionAge 500 ms(宽限 1 秒):总调用 144272,失败 0,TCP 连接 8 条(大约每 0.5 秒换一条),p50 209 µs、p99 395 µs。连接频繁更替,在这个本机回环的测试里没有失败的调用,延迟也没有可见的变差(p99 甚至略低,在噪声内)。代价在真实网络里是每次重建连接的握手(TLS)和新连接的拥塞窗口起步。", t=tl(S(4)), done=lidx(S(4), 'MaxConnectionAge 500 ms'), mark=lidx(S(4), '没有设置'), b=bars([['没有设置:TCP 连接数', 1, '1'], ['MaxConnectionAge 500 ms:TCP 连接数', 8, '8'], ['两者失败调用数', 0, '0']], 9, mark=[1], done=[0, 2]), kv=KV([['没有设置', '142588 次,1 条连接,失败 0'], ['年龄 500 ms', '144272 次,8 条连接,失败 0'], ['延迟', 'p99 418 µs vs 395 µs,没有变差']], ['延迟'])),
    step("MaxConnectionIdle(只回收空闲连接)与 MaxConnectionAge 的区别:每秒调用一次,持续 4 秒。MaxConnectionIdle = 300 ms:每次调用之间连接都空闲超过 300 ms 而被回收,4 次调用建立了 4 条 TCP 连接;MaxConnectionAge = 1.5 秒:4 秒里建立了 2 条连接。两者失败都是 0——客户端遇到 GOAWAY 后会在下一次调用时重新建连。Idle 适合清理长期不用的连接,Age 适合让忙连接也定期更换(做重新负载均衡、换证书,第 16、25 篇)。", t=tl(S(5)), done=lidx(S(5), 'MaxConnectionAge = 1.5 秒'), mark=lidx(S(5), 'MaxConnectionIdle = 300 ms'), b=bars([['MaxConnectionIdle 300 ms:TCP 连接数', 4, '4'], ['MaxConnectionAge 1.5 秒:TCP 连接数', 2, '2']], 5, mark=[0], done=[1]), kv=KV([['MaxConnectionIdle', '空闲就回收,每次调用重连'], ['MaxConnectionAge', '到期就换,不管忙闲'], ['失败调用', '两者都是 0']], ['MaxConnectionAge'])),
]
A = mkarth('h40', 40, 'gRPC,MaxConnectionAge,MaxConnectionIdle,GOAWAY,连接更替,抖动,Go,真实验证,动画演示',
    '实测服务端 MaxConnectionAge:到期发 GOAWAY(最后流 2147483647,附加数据 max_age);±10% 抖动(2 秒设置下 1.87~2.21 秒);宽限默认无限时长流不受影响、宽限 1 秒时长流被打断;持续负载下换连接没有失败调用;与 MaxConnectionIdle 的区别。',
    '让服务端定期结束长连接有什么好处?到期时线上发生什么?在途的长流会怎样?会不会引起失败或延迟抖动?这篇用抓包代理和持续负载把它们都看一遍。',
    [('1.87 ~ 2.21 秒', 'MaxConnectionAge = 2 秒时,30 条连接第一个 GOAWAY 到达的时刻范围'), ('失败 0 / 8 条连接', '年龄 500 ms 的持续负载 4 秒里,失败调用数与建立的连接数'), ('4.02 秒 vs 2.50 秒', '宽限默认(无限)时长流跑完;宽限 1 秒时服务端第一次发送失败的时刻')],
    [('机制', '<p>年龄到期时服务端发 GOAWAY(附加数据 max_age),不再接受新流;客户端之后遇到调用会重新建连,而不是继续用这条连接。</p>'),
     ('抖动', '<p>服务端给年龄加 ±10% 的随机抖动,避免所有连接同时重建。</p>'),
     ('在途的流', '<p>宽限(MaxConnectionAgeGrace)默认是无限,在途的流不受影响;设了宽限,到期加宽限之后连接被强制关闭,长流会被打断。</p>'),
     ('代价', '<p>本机回环上频繁更换连接没有造成失败或可见的延迟变差;真实网络里要加上重建连接的握手成本。</p>'),
     ('Idle 与 Age', '<p>MaxConnectionIdle 只回收空闲连接,MaxConnectionAge 不管忙闲都定期更换,常用来重新做负载均衡、让新证书或新后端生效。</p>')],
    steps,
    [ENV_H + '。GOAWAY 的时刻和内容来自抓包代理;连接数是代理接受的 TCP 连接数;抖动范围、max_age/max_idle 附加数据读自 internal/transport/http2_server.go;长流那一节只跑了一次,时刻有数十毫秒的误差',
     '没有验证:真实负载均衡器(如 Kubernetes Service、Envoy)在连接更替时的行为;TLS 下重建连接的成本;客户端使用 pick_first 与 round_robin 时更替后的后端分布(第 16 篇有一部分);为什么长流的客户端比服务端的发送失败晚约 0.6 秒才报错(没有查);MaxConnectionAge 与 keepalive 的相互作用',],
    '主动断开长连接')
