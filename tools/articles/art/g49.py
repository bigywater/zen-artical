from lib import *
S = SS('g49')
steps = [
    step("只有 1 个 P(GOMAXPROCS=1),一个 goroutine 在没有任何函数调用的死循环里,main 想 time.Sleep(10ms) 后醒来,共 30 次。默认设置下每次实际耗时:最小 25.2 ms / 中位 30.0 ms / 最大 30.1 ms——比 10 ms 慢,但每次都醒来了(为什么是 25–30 ms 而不是 10 ms,我没有查)。加上 GODEBUG=asyncpreemptoff=1 关掉信号抢占后,15 秒内程序没有结束,被我杀掉:main 的 Sleep 到期后拿不到 P。", t=tl(S(1)), done=lidx(S(1), '中位 30.0'), mark=lidx(S(1), '超时:15 s'), b=bars([['请求的睡眠', 10, '10 ms'], ['默认:最小', 25.2, '25.2 ms'], ['默认:中位', 30.0, '30.0 ms'], ['默认:最大', 30.1, '30.1 ms']], 30.1, done=[1, 2, 3], mark=[0]), kv=KV([['默认', '30 次都醒来,中位 30.0 ms'], ['asyncpreemptoff=1', '15 s 内没有结束(被杀)'], ['含义', '没有函数调用的循环靠信号才能被打断']], ['含义'])),
    step("GC 要停下所有 goroutine:GOMAXPROCS=2,一个死循环 goroutine 在跑,main 调用 runtime.GC()。默认设置下耗时 0.2 ms;加上 GODEBUG=asyncpreemptoff=1,4 秒内没有返回,被我杀掉。", t=tl(S(2)), done=lidx(S(2), '耗时 0.2 ms'), mark=lidx(S(2), '超时:4 s'), kv=KV([['默认', 'runtime.GC() 耗时 0.2 ms'], ['asyncpreemptoff=1', '4 s 内没有返回(被杀)'], ['含义', '停不下死循环,GC 就一直等']], ['含义'])),
    step("抢占靠的是 SIGURG 信号:订阅 SIGURG,让一个死循环 goroutine 占着唯一的 P 约 1 秒,os/signal 一共收到 19 次 SIGURG(默认设置)。关掉 asyncpreemptoff 的那次,4 秒内同样没有结束(main 的 Sleep 一直没醒)。19 次是否都是抢占信号、为什么大约每 50 ms 一次,我没有进一步查。", t=tl(S(3)), done=lidx(S(3), '收到 SIGURG 19 次'), mark=lidx(S(3), '超时:4 s'), kv=KV([['约 1 秒内', '收到 SIGURG 19 次'], ['asyncpreemptoff=1', '4 s 内没有结束(被杀)']], ['约 1 秒内'])),
    step("看汇编:spinNoCall 的循环体只有 ADD、TST、BNE,以及偶尔读一下原子变量(LDARW、CBZW)。整个函数 LEAF|NOFRAME、48 字节,CALL 指令个数为 0,也没有栈检查的序言——没有一个可以主动检查“要不要让出”的函数入口。", t=tl(S(4)), done=lidx(S(4), 'ADD', 'TST', 'BNE'), mark=lidx(S(4), 'LDARW', 'CALL 指令的个数'), kv=KV([['函数大小', '48 字节,LEAF|NOFRAME'], ['CALL 指令', '0 个'], ['栈检查序言', '没有']], ['CALL 指令'])),
    step("运行时源码(runtime/preempt.go 开头的注释):goroutine 可以在任何安全点被抢占,安全点有三类——阻塞时的安全点、同步安全点(运行中的 goroutine 检查抢占请求)、异步安全点(用户代码里任意一条指令,运行时可以用信号停住它)。proc.go 里 forcePreemptNS 是 10 ms,注释写着“给 G 的时间片”。extern.go 对 asyncpreemptoff 的描述:disables signal-based asynchronous goroutine preemption,并说这会让某些循环长时间不可抢占,可能延迟 GC。signal_unix.go 里 sigPreempt 注释为“非协作式抢占使用的信号”。", t=tl(S(5)), done=lidx(S(5), 'Synchronous safe-points', 'forcePreemptNS'), mark=lidx(S(5), 'Asynchronous safe-points', 'asyncpreemptoff: asyncpreemptoff=1', 'sigPreempt is the signal'), kv=KV([['同步安全点', '函数序言里的栈检查'], ['异步安全点', '用信号停住线程,检查它是否在安全的指令上'], ['时间片', 'forcePreemptNS = 10 ms'], ['关闭开关', 'GODEBUG=asyncpreemptoff=1']], ['异步安全点'])),
]
A = mkartg('g49', 49, 'Go,调度器,异步抢占,SIGURG,GC,真实验证,动画演示',
    '在 Go 1.27.1(arm64 macOS)里验证异步抢占:只有 1 个 P、一个没有函数调用的死循环 goroutine 占着它时,main 的 time.Sleep(10ms) 实际 25–30 ms 醒来;GOMAXPROCS=2 时 runtime.GC() 只要 0.2 ms;而 GODEBUG=asyncpreemptoff=1 下这些程序都不结束。并看汇编(循环里 0 个 CALL)和运行时源码里关于安全点与 SIGURG 的说明。',
    '一个没有任何函数调用的死循环,调度器怎么把它打断?老版本的 Go 打不断,整个程序会被一个循环卡死。这篇关掉信号抢占做对照,量出默认设置下被打断需要多久、GC 会不会被拖住,并读源码里的安全点说明。',
    [('25–30 ms', '死循环占着唯一的 P 时,main 的 Sleep(10ms) 实际醒来的时间'), ('0.2 ms', '死循环在跑时 runtime.GC() 的耗时(GOMAXPROCS=2)'), ('0 个 CALL', '死循环函数汇编里的调用指令个数,没有可以主动让出的入口')],
    [('没有函数调用就没有主动让出的机会', '<p>同步抢占靠函数序言里的栈检查:运行时把 goroutine 的栈边界改成一个必定失败的值,下次进函数就会发现“该让出了”。但上面这个循环的汇编里没有任何调用、也没有栈检查,它从来不会走进那段代码。</p>'),
     ('关掉信号抢占:程序不再往前走', '<p>加上 <code>GODEBUG=asyncpreemptoff=1</code> 后,main 的 <code>Sleep</code> 到期也拿不到唯一的 P,程序 15 秒内没有结束;GC 的情形里 <code>runtime.GC()</code> 4 秒内没有返回。我杀掉了它们,所以只能说“超过这个时间都没结束”,不是证明永远不结束。</p>'),
     ('默认设置下靠信号打断', '<p>默认情况下运行时会给占着线程的死循环发信号(<code>SIGURG</code>),在一条安全的指令上把它停住。实验里一个死循环占着 P 约 1 秒,订阅 <code>SIGURG</code> 的 <code>os/signal</code> 收到 19 次;main 的 10 ms 睡眠实际 25–30 ms 才醒——比 10 ms 慢,但不会被卡死。慢多少、为什么是这个数,我没有深查,源码里能确认的只有每个 G 有 10 ms 的时间片。</p>'),
     ('GC 也依赖它', '<p>GC 的停顿阶段要让所有 goroutine 停下来。默认设置下死循环在跑时 <code>runtime.GC()</code> 只花了 0.2 ms;关掉信号抢占就等不到。源码里 <code>asyncpreemptoff</code> 的说明也提到这会让某些循环长时间不可抢占、可能延迟 GC。</p>'),
     ('读源码的结论', '<p><code>preempt.go</code> 开头把安全点分成三类:阻塞、同步(函数序言)、异步(用户代码任意指令,用信号停住并检查这条指令是否安全)。异步抢占补上了前两类够不到的地方。具体“哪些指令算安全”的判断我没有读。</p>')],
    steps,
    [ENV_G + '。死循环函数 spinNoCall 只做自增,每 2^28 次读一次原子变量;“被杀”的程序是由我的脚本在 15 秒或 4 秒后 kill 的;SIGURG 次数用 os/signal.Notify 统计;汇编来自 go build -gcflags=-S;读过的源码:runtime/preempt.go 开头注释、proc.go 的 forcePreemptNS、extern.go 的 asyncpreemptoff 说明、signal_unix.go 的 sigPreempt 注释',
     '没有验证:Linux 上的信号行为、25–30 ms 的原因、19 次信号的构成、哪些指令是异步安全点、Windows 上的实现、asyncpreemptoff 下“永远不结束”(只测到超时)、GOMAXPROCS 更大时的情形'],
    '异步抢占')
