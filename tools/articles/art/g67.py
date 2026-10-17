from lib import *
S = SS('g67')
steps = [
    step("本文用的是 golang.org/x/sync v0.24.0(通过代理下载,errgroup 不在标准库里)。后面所有实验都基于这个版本。", t=tl(S(1)), mark=lidx(S(1), 'golang.org/x/sync v0.24.0'), kv=KV([['模块', 'golang.org/x/sync'], ['版本', 'v0.24.0'], ['来源', '不在标准库,需要 go get']], ['版本'])),
    step("第一个错误取消其他任务:5 个任务,任务 2 在 50 ms 出错,其它任务本来要做 200/400/600/800/1000 ms 之类。用 errgroup.WithContext:任务 1、3、4、5 都在 51 ms 发现 ctx 已取消(原因是“任务 2 失败”),g.Wait() 在 51 ms 返回“任务 2 失败”。只用 WaitGroup(没有取消)的对照:wg.Wait() 要等到 1001 ms 才返回。", t=tl(S(2)), done=lidx(S(2), '发现 ctx 已取消', 'g.Wait() 在 51 ms'), mark=lidx(S(2), '只用 WaitGroup'), b=bars([['errgroup:Wait 返回 (ms)', 51, '51'], ['WaitGroup:Wait 返回', 1001, '1001']], 1001, done=[0], mark=[1]), kv=KV([['errgroup', '51 ms 全部结束'], ['WaitGroup', '1001 ms 才返回'], ['前提', '任务要自己监听 ctx.Done()']], ['前提'])),
    step("多个错误只返回第一个:3 个任务先后在 20/40/60 ms 出错,g.Wait() 返回“错误 1”,另外两个错误被丢弃。", t=tl(S(3)), mark=lidx(S(3), '错误 1'), kv=KV([['3 个任务都出错', '只返回最先出错的一个'], ['其余', '被丢弃']], ['其余'])),
    step("SetLimit 限制并发数:SetLimit(3),12 个各 30 ms 的任务:同时运行的最大个数 = 3,总用时 124 ms,调用 g.Go 累计阻塞 93 ms(超过上限时 Go 会阻塞调用者)。SetLimit(1) 且已有一个任务在跑时,TryGo 立刻返回 false。", t=tl(S(4)), done=lidx(S(4), 'SetLimit(3)'), mark=lidx(S(4), 'TryGo'), b=bars([['同时运行最大个数', 3, '3'], ['总用时 (ms÷10)', 12.4, '124 ms'], ['g.Go 累计阻塞 (ms÷10)', 9.3, '93 ms']], 12.4, done=[0], mark=[1, 2]), kv=KV([['最大并发', '3'], ['总用时', '124 ms(12 个任务/3 并发×30 ms≈120 ms)'], ['TryGo', '满了就返回 false,不阻塞']], ['TryGo'])),
    step("任务里 panic:g.Go(func() error { panic(...) }),而 g.Wait() 所在的 goroutine 里写了 defer recover()——没有用:进程直接崩溃,退出码 2,栈里是 panic: 任务里 panic 了,以及 errgroup.go 里 Go 方法内的调用。panic 发生在任务的 goroutine 里,不会传到 Wait。", t=tl(S(5)), mark=lidx(S(5), '进程退出码 2', 'panic:'), kv=KV([['任务里 panic', '进程崩溃,退出码 2'], ['Wait 处的 recover', '捕获不到'], ['含义', '要在任务内部自己 recover']], ['含义'])),
    step("WithContext 的 ctx 什么时候取消:即使任务返回了错误,Wait 返回之后 ctx.Err() 是 context canceled;所有任务都成功时,Wait 返回之后 ctx.Err() 也是 context canceled。所以这个 ctx 在 Wait 返回后不能再拿来做别的事。", t=tl(S(6)), done=lidx(S(6), '所有任务都成功时'), mark=lidx(S(6), 'Wait 返回之后 ctx.Err()'), kv=KV([['有错误', 'ctx 被取消'], ['全部成功', 'Wait 返回后 ctx 也被取消'], ['含义', 'Wait 之后别再用这个 ctx']], ['含义'])),
    step("源码(errgroup.go):Group 结构体有 cancel、一个 sync.WaitGroup、用作信号量的 sem(chan token)、errOnce(sync.Once)和 err。Go 方法先 g.sem <- token{}(有上限时阻塞),再 wg.Add(1) 开 goroutine 执行 f;若返回非 nil,则 errOnce.Do 记下第一个错误并调用 cancel。源码里还有一段注释解释为什么不把 panic 传回 Wait:会延迟 panic、把栈变成一个值、可能死锁而隐藏 panic。", t=tl(S(7)), done=lidx(S(7), 'sem chan token', 'g.sem <- token{}', 'g.errOnce.Do', 'g.cancel(g.err)'), mark=lidx(S(7), 'It is tempting to propagate panics', 'delays panics arbitrarily', 'hiding it from crash-monitoring tools'), kv=KV([['第一个错误', 'errOnce.Do 只记第一个并 cancel'], ['并发上限', '容量固定的 channel 当信号量'], ['panic', '刻意不传播,注释列出 3 条理由']], ['panic'])),
]
A = mkartg('g67', 67, 'Go,errgroup,并发,取消,SetLimit,真实验证,动画演示',
    '用 golang.org/x/sync v0.24.0 实测 errgroup:一个任务出错 51 ms 后其余 4 个任务都因 ctx 取消结束(WaitGroup 要等 1001 ms);多个错误只返回第一个;SetLimit(3) 时最大并发恰好是 3、g.Go 会阻塞而 TryGo 返回 false;任务里 panic 会让整个进程崩溃(Wait 处 recover 不到);WithContext 的 ctx 在 Wait 返回后一定被取消;并读源码里的信号量与 errOnce。',
    'errgroup 是并发任务的常用工具:第一个错误取消其他任务、限制并发数。但它到底怎么做的、有哪些容易踩的坑?这篇用真实运行回答:取消要多久、丢了几个错误、panic 去哪了、ctx 什么时候被取消,再读一遍几十行的实现。',
    [('51 ms vs 1001 ms', '一个任务出错后,errgroup 与不带取消的 WaitGroup 的 Wait 返回时间'), ('3', 'SetLimit(3) 下同时运行的最大任务数,g.Go 累计阻塞 93 ms'), ('退出码 2', '任务里 panic 时进程崩溃,在 Wait 的 goroutine 里 recover 无效')],
    [('版本与来源', '<p>errgroup 在 <code>golang.org/x/sync</code> 里,不在标准库。本文所有结果来自 v0.24.0,不同版本的行为(尤其是 panic 的处理)可能不同。</p>'),
     ('取消靠 ctx,要任务自己配合', '<p>任务 2 出错后,其余任务在 51 ms 就看到了 <code>ctx.Done()</code>;同样的任务只用 <code>WaitGroup</code> 要 1001 ms。取消不是强杀,任务必须在 <code>select</code> 里监听 <code>ctx.Done()</code>。</p>'),
     ('错误只留第一个', '<p>3 个任务都出错,<code>Wait</code> 只返回最先出错的那个。如果后面的错误也需要记录,要在任务里自己打日志或收集。</p>'),
     ('SetLimit', '<p>上限 3 时同时运行的最大个数正好是 3,12 个 30 ms 的任务总用时 124 ms;超过上限时 <code>g.Go</code> 会阻塞调用者(累计阻塞 93 ms),要不阻塞就用 <code>TryGo</code>(返回 false)。</p>'),
     ('panic 不会传到 Wait', '<p>任务里的 panic 发生在任务自己的 goroutine,在 <code>Wait</code> 所在 goroutine 里 <code>defer recover()</code> 没有用,整个进程退出(退出码 2)。源码注释特意解释了不传播的理由。需要容错就在任务函数里自己 recover。</p>'),
     ('ctx 的生命周期', '<p><code>WithContext</code> 返回的 ctx 在第一个错误或 <code>Wait</code> 返回时被取消——实验里即使所有任务成功,<code>Wait</code> 返回后它也是 <code>context canceled</code>。不要在 <code>Wait</code> 之后继续用它。</p>'),
     ('实现很短', '<p>核心就是 WaitGroup、一个当信号量的 channel、一个 <code>sync.Once</code> 记录第一个错误并 cancel。读源码时那段关于 panic 的注释最值得看。</p>')],
    steps,
    [ENV_G + '。errgroup 为 golang.org/x/sync v0.24.0(通过本机代理下载);每个实验是一个单独的小程序;时间点用 time.Since 在任务内记录,精度到毫秒;源码摘自下载的 errgroup.go(Group 结构体与 Go 方法原文)',
     '没有验证:其它版本的 errgroup(尤其是 panic 与 Goexit 的处理是否变化)、WithCancelCause 的使用、g.Go 的阻塞行为在大量任务下的开销、TryGo 的竞态细节、errgroup 与 context.WithTimeout 联用时的表现'],
    'errgroup')
