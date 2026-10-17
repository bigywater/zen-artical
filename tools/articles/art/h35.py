from lib import *
S = SS('h35')
steps = [
    step("客户端开了服务端流,收了第一条就不管了(没取消 ctx、没读到结束、也没保留引用):开 200 个流之后,服务端在运行的 handler 是 200 个,进程 goroutine 比基线多 405(客户端和服务端在同一个进程里,合计每个流约 2 个);把所有引用丢掉并 runtime.GC() 3 次,仍是 200 个 handler、405 个 goroutine——GC 不会回收没结束的流;直到 conn.Close() 之后 handler 才降到 0。所以一个流只有三种结束方式:读到服务端结束(EOF/错误)、取消 ctx、关闭连接;“不管它了”不是其中之一。", t=tl(S(1)), done=lidx(S(1), 'conn.Close() 之后'), mark=lidx(S(1), '开了 200 个流'), b=bars([['开 200 个流后服务端 handler', 200, '200'], ['丢弃引用 + GC 3 次之后', 200, '200'], ['conn.Close() 之后', 0, '0']], 210, mark=[0, 1], done=[2]), kv=KV([['泄漏的流', '服务端 handler 一直在'], ['GC', '不会回收'], ['conn.Close()', '才全部结束']], ['GC'])),
    step("泄漏的流占着名额,别的调用也被拖死:服务端 MaxConcurrentStreams(10),先泄漏 10 个流,再发一个 Unary(deadline 1 秒):1002.1 ms 后返回 DeadlineExceeded——这次调用根本没有发出去,在客户端排队等名额(第 13 篇)。cancel 掉泄漏的流以后,同样的 Unary 调用 0.7 ms 就成功,服务端 handler 降到 0。流的泄漏不只是内存问题,它占的是并发名额。", t=tl(S(2)), done=lidx(S(2), 'cancel 掉泄漏的流之后'), mark=lidx(S(2), '10 个流被泄漏'), b=bars([['名额被占满时 Unary 用时 ms', 1002.1, '1002.1'], ['释放之后 Unary 用时 ms', 0.7, '0.7']], 1050, mark=[0], done=[1]), kv=KV([['名额被占满', 'Unary 排队到 deadline'], ['cancel 之后', '0.7 ms 成功'], ['教训', '流泄漏会拖死同一条连接上的所有调用']], ['教训'])),
    step("怎样才算“释放”了一个服务端流:只调用 CloseSend()(只是告诉服务端“我不再发了”):服务端 handler 还在(1 个);再开一个并 cancel ctx:新的这个释放了,服务端仍只有最早那个 1 个;再开一个会自己结束的流并读到 EOF:服务端 handler 还是只有那一个;conn.Close() 之后降到 0。结论:服务端流要么读到结束、要么取消 ctx;CloseSend 只管发送方向。最稳妥的写法:ctx, cancel := context.WithCancel(…); defer cancel()。", t=tl(S(3)), done=lidx(S(3), 'conn.Close() 之后'), mark=lidx(S(3), '只调用 CloseSend'), b=bars([['只 CloseSend:handler 仍在', 1, '1'], ['cancel ctx:新流已释放', 0, '0'], ['读到 EOF:已释放', 0, '0']], 1.3, mark=[0], done=[1, 2]), kv=KV([['CloseSend()', '不释放服务端流'], ['cancel ctx', '释放'], ['读到 EOF', '释放']], ['CloseSend()'])),
    step("客户端流忘记 CloseAndRecv:发了 3 条消息就没了下文,服务端 handler 还在 Recv 里等(1 个);调用 CloseAndRecv() 之后:成功,服务端数到 3 条,handler 降到 0。服务端是靠收到 EOF 才知道客户端发完了,所以客户端流必须 CloseSend(或 CloseAndRecv)。", t=tl(S(4)), done=lidx(S(4), '调用 CloseAndRecv'), mark=lidx(S(4), '发了 3 条之后'), b=bars([['未 CloseAndRecv:服务端 handler', 1, '1'], ['CloseAndRecv 之后', 0, '0']], 1.3, mark=[0], done=[1]), kv=KV([['不关闭', '服务端一直在 Recv 里等 EOF'], ['CloseAndRecv()', '服务端数到 3 条并返回'], ['规则', '客户端流必须关发送方向']], ['规则'])),
    step("泄漏的流让连接永远“不空闲”:服务端设 MaxConnectionIdle = 300 ms。没有任何在途的流时,1.5 秒内服务端发出了 1 个 GOAWAY(空闲到期,关闭连接);有一个泄漏的流时,1.5 秒内 0 个 GOAWAY,连接一直保持;cancel 之后再过 0.8 秒,GOAWAY 共 1 个。所以一个泄漏的流可以让连接永远不被空闲超时回收,连接上的资源也不释放。", t=tl(S(5)), done=lidx(S(5), '没有任何在途的流'), mark=lidx(S(5), '有一个泄漏的流'), b=bars([['有泄漏的流:1.5 秒内 GOAWAY', 0, '0'], ['没有流:1.5 秒内 GOAWAY', 1, '1']], 1.3, mark=[0], done=[1]), kv=KV([['MaxConnectionIdle 300 ms', '没有流 → 1.5 秒内发 GOAWAY'], ['有泄漏的流', '不发,连接不被回收'], ['cancel 之后', '随即发 GOAWAY']], ['有泄漏的流'])),
]
A = mkarth('h35', 35, 'gRPC,流,泄漏,取消,CloseSend,MaxConcurrentStreams,MaxConnectionIdle,Go,真实验证,动画演示',
    '实测 gRPC 流泄漏:没读完也没取消的流在服务端一直存在,GC 回收不了;泄漏的流占满 MaxConcurrentStreams 会拖死同一连接上的其它调用;CloseSend 不释放服务端流,cancel 或读到 EOF 才算;客户端流必须 CloseAndRecv;泄漏的流让连接永远不空闲。',
    '忘记关闭的流会怎么样?GC 管不管?它会不会拖累别的请求?CloseSend、cancel、读到 EOF 到底哪个才算结束?这篇用服务端 handler 计数器和抓包代理逐个验证。',
    [('200 个 handler', '丢弃引用并 GC 之后,200 个泄漏的流在服务端仍然全部存在'), ('1002.1 ms → 0.7 ms', '流泄漏占满名额时 Unary 的耗时,与 cancel 之后的耗时'), ('GOAWAY 0 个', '有泄漏的流时,MaxConnectionIdle 到期后服务端仍没有关闭连接')],
    [('流需要明确结束', '<p>一个流只有读到服务端结束、取消 ctx 或关闭连接才会结束。不再引用它、等 GC,服务端 handler 不会因此退出。</p>'),
     ('占着名额', '<p>每个未结束的流占一个并发名额(MaxConcurrentStreams),泄漏的流足够多时,同一连接上别的调用也会排队到超时。</p>'),
     ('哪些算结束', '<p>服务端流:读到 EOF 或取消 ctx,CloseSend 不算。客户端流:CloseSend 或 CloseAndRecv,让服务端读到 EOF。最稳妥是为每个流使用 context.WithCancel 并 defer cancel()。</p>'),
     ('连接保持', '<p>泄漏的流让连接一直有在途的流,MaxConnectionIdle 这类空闲超时永远不触发。</p>'),
     ('排查', '<p>服务端在运行的 handler 数、goroutine 数持续上涨是泄漏的信号。</p>')],
    steps,
    [ENV_H + '。handler 数用服务端 handler 里的原子计数器;goroutine 数用 runtime.NumGoroutine(客户端和服务端在同一个进程,所以是合计);GOAWAY 来自抓包代理;时间是本机测量',
     '没有验证:双向流泄漏的表现(只测了服务端流和客户端流);客户端 ctx 的 deadline 到期是否同样释放(预期会,没有单独测);泄漏对服务端内存的实际增长(第 31 篇给了每个调用的开销);keepalive 对泄漏流的影响;其它语言的客户端是否有终结器会清理未结束的流'],
    '流的泄漏')
