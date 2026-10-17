from lib import *
S = SS('g96')
steps = [
    step("测一个 TTL 一小时的缓存。TestRealTTL(真实时钟,TTL 只能设 300 ms):通过,测试自己报告耗时 0.35 秒;TestFakeTTL(synctest.Test,TTL 是 1 小时):通过,耗时 0.00 秒;测试里 time.Since(start) 是 1h0m1s,起点是 2000-01-01 08:00:00 CST(即 UTC 的 2000-01-01 00:00:00)。", t=tl(S(1)), mark=lidx(S(1), 'TestRealTTL:'), done=lidx(S(1), 'TestFakeTTL:'), b=bars([['真实时钟:TTL 300 ms,耗时 (秒)', 0.35, '0.35'], ['假时钟:TTL 1 小时,耗时', 0.0, '0.00']], 0.35, mark=[0], done=[1]), kv=KV([['真实时钟', 'TTL 只能缩到 300 ms 来测,耗时 0.35 秒'], ['synctest', 'TTL 1 小时,耗时 0.00 秒'], ['起点', '2000-01-01 00:00:00 UTC']], ['synctest'])),
    step("轮询次数是确定的:每秒轮询一次、超时 10.001 秒的 Poll,在 synctest 里调用了 10 次,TestFakePoll 通过(0.00s);同一个测试连续重复 50 次(-count=50)通过 50 次、失败 0 次。真实时钟下这类测试的次数可能受调度抖动影响(我没有统计过具体偏差),通常需要放宽断言。", t=tl(S(2)), mark=lidx(S(2), '调用了 10 次', '重复 50 次'), kv=KV([['调用次数', '10,每次都一样'], ['原因', '假时钟只在所有 goroutine 阻塞时才推进']], ['原因'])),
    step("synctest.Wait() 等所有其它 goroutine 都“持久阻塞”或结束:启动一个 goroutine 加锁并设 done = true,调用 synctest.Wait() 之后读到 done = true。", t=tl(S(3)), mark=lidx(S(3), 'done=true'), kv=KV([['Wait', '等其它 goroutine 都阻塞或结束'], ['结果', 'done=true,确定无疑']], ['结果'])),
    step("死锁检测:bubble 里所有 goroutine 都阻塞(<-ch)又没有定时器可推进:退出码 1,panic: deadlock: all goroutines in bubble are blocked。", t=tl(S(4)), mark=lidx(S(4), 'deadlock: all goroutines in bubble are blocked'), kv=KV([['全部阻塞且无定时器', 'panic: deadlock'], ['含义', 'synctest 能发现测试里的永久阻塞']], ['含义'])),
    step("根 goroutine 退出时还有 goroutine 没结束:启动一个 select {} 的 goroutine 后测试函数返回:退出码 1,panic: deadlock: main bubble goroutine has exited but blocked goroutines remain——泄漏的 goroutine 会让测试失败。", t=tl(S(5)), mark=lidx(S(5), 'main bubble goroutine has exited'), kv=KV([['根 goroutine 退出', '还有阻塞的 goroutine → panic'], ['含义', '测试结束时不允许泄漏']], ['含义'])),
    step("文档里“持久阻塞”的清单:在 bubble 内创建的 channel 上的阻塞发送或接收;每个 case 都是 bubble 内 channel 的阻塞 select;sync.Cond.Wait;sync.WaitGroup.Wait(且 Add 在 bubble 内调用);time.Sleep。不在清单里的操作不算持久阻塞,因为它们可能被 bubble 外的事件唤醒(例如网络、外部进程)。", t=tl(S(6)), done=lidx(S(6), 'durably block a goroutine'), mark=lidx(S(6), 'Operations not in the above list'), kv=KV([['算持久阻塞', 'bubble 内的 channel、select、Cond、WaitGroup、Sleep'], ['不算', '可能被 bubble 外唤醒的操作(网络、外部进程等)']], ['不算'])),
]
A = mkartg('g96', 96, 'Go,testing/synctest,假时钟,并发测试,死锁检测,真实验证,动画演示',
    '在 Go 1.27.1 里实测 testing/synctest:TTL 一小时的缓存,测试里过了 1h0m1s 却耗时 0.00 秒(真实时钟的 300 ms TTL 版本要 0.35 秒);每秒一次的轮询在超时 10.001 秒内确定地调用 10 次;synctest.Wait 确保后台 goroutine 已执行完;所有 goroutine 阻塞又没有定时器时报 deadlock,根 goroutine 退出时有泄漏的 goroutine 也会 panic。',
    '测试超时、重试、定时器这类依赖时间的并发代码,以前只能真的睡;或者把时间抽象成接口再注入假时钟。testing/synctest 让 time 包在一个“气泡”里用假时钟,所有 goroutine 都阻塞时时间才快进。这篇用一个 TTL 一小时的缓存和一个轮询函数实测它,并验证死锁检测和泄漏检测。',
    [('0.00 vs 0.35 秒', '测 1 小时 TTL 的缓存用 synctest 与测 300 ms TTL 的缓存用真实时钟的耗时'), ('10 次', '每秒轮询、超时 10.001 秒的函数在假时钟下的确定调用次数'), ('2000-01-01', 'synctest 气泡里时钟的起点(UTC 午夜)')],
    [('时间被快进', '<p>气泡里的 <code>time.Sleep(59*time.Minute + 59*time.Second)</code> 瞬间完成,<code>time.Since(start)</code> 报告 1h0m1s,测试本身耗时 0.00 秒。真实时钟版本为了不让测试太慢,只能把 TTL 缩到 300 ms 去测——测的就不是生产参数了。</p>'),
     ('次数是确定的', '<p>假时钟只在气泡里所有 goroutine 都阻塞时才推进,所以每秒一次、10.001 秒超时的轮询,调用次数永远是 10,没有调度抖动的影响。真实时钟下的同类测试通常要放宽断言(本文没有统计真实时钟下的偏差)。</p>'),
     ('Wait', '<p><code>synctest.Wait()</code> 等其它 goroutine 都“持久阻塞”或结束再返回,所以不需要靠 <code>time.Sleep</code> 去猜后台 goroutine 跑完没有。</p>'),
     ('死锁与泄漏检测', '<p>气泡里所有 goroutine 都阻塞且没有定时器可推进,<code>synctest.Test</code> 直接 panic <code>deadlock: all goroutines in bubble are blocked</code>;根 goroutine 退出时还有阻塞的 goroutine,panic <code>main bubble goroutine has exited but blocked goroutines remain</code>。副作用是测试必须把自己启动的 goroutine 都收拾干净。</p>'),
     ('什么算“持久阻塞”', '<p>文档的清单是:气泡内创建的 channel 上的阻塞操作、<code>sync.Cond.Wait</code>、<code>WaitGroup.Wait</code>(<code>Add</code> 在气泡内)和 <code>time.Sleep</code>。网络、外部进程、不在气泡内创建的 channel 等不算,所以文档建议测试自包含、避免真实网络。我没有试 <code>sync.Mutex</code> 之类不在清单里的操作的实际表现。</p>'),
     ('文档', '<p>文档建议每个测试自包含:不与气泡外的 goroutine 交互、不用网络(用假网络)、不依赖外部进程、不泄漏 goroutine。</p>')],
    steps,
    [ENV_G + '。测试代码是自己写的:带 TTL 的 Cache 和用 Ticker 的 Poll;真实时钟与 synctest 版本各运行一次;死锁与泄漏的测试故意写成会失败的,取其 panic 信息;读过的文档:go doc testing/synctest(Time、Blocking 两节和持久阻塞清单)',
     '没有验证:testing/synctest 引入的 Go 版本(本机文档没有写)、与 net/http 的 httptest.NewTestServer(内存网络)配合的写法、Mutex 等不在清单里的阻塞操作的表现、气泡与 context 的更多交互、对 time.AfterFunc 的支持细节'],
    'testing/synctest')
