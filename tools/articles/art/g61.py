from lib import *
S = SS('g61')
steps = [
    step("同一个计数器 2000 万次加一,分给 G 个 goroutine(墙钟 ÷ 2000 万,每格 3 次中位数,GOMAXPROCS=8)。atomic.Add:G=1 4.1 ns / G=2 10.5 / G=4 26.9 / G=8 53.7;CAS 循环:7.5 / 24.1 / 77.4 / 254.9;Mutex(Lock;加一;Unlock):7.7 / 61.3 / 185.3 / 157.2。没有竞争(G=1)时 atomic 4.1 ns,Mutex 7.7 ns;争得越凶,每次操作越慢,CAS 循环最差。", t=tl(S(1)), done=lidx(S(1), 'atomic  G=1'), mark=lidx(S(1), 'cas     G=1', 'mutex   G=1'), b=bars([['atomic G=1 (ns)', 4.1, '4.1'], ['atomic G=8', 53.7, '53.7'], ['mutex G=8', 157.2, '157.2'], ['CAS 循环 G=8', 254.9, '254.9']], 254.9, done=[0, 1], mark=[2, 3]), kv=KV([['G=1', 'atomic 4.1,CAS 7.5,Mutex 7.7 ns'], ['G=8', 'atomic 53.7,Mutex 157.2,CAS 254.9 ns'], ['结论', '争同一个变量时,三者都随 goroutine 数变慢']], ['结论'])),
    step("成本下限:每个 goroutine 用自己的局部变量累加、最后才一次 atomic.Add:G=1 0.3 ns/次,G=8 0.1 ns/次(8 个并行)。共享同一个计数器时的 4.1–254.9 ns,差的是缓存一致性的代价,不是加法本身。", t=tl(S(2)), mark=lidx(S(2), '局部变量'), kv=KV([['局部变量累加', 'G=1 0.3 ns,G=8 0.1 ns'], ['共享原子计数器', 'G=8 时 53.7 ns']], ['共享原子计数器'])),
    step("伪共享:每个 goroutine 有自己的 atomic 计数器,互不共享。相邻放在一起(无填充):G=1 4.0 ns,G=8 57.1 ns;每个计数器占 128 字节:G=1 3.9 ns,G=8 0.8 ns。逻辑上没有共享,放在同一个缓存行里却慢了约 70 倍。", t=tl(S(3)), done=lidx(S(3), '各占 128 字节'), mark=lidx(S(3), '相邻放置'), b=bars([['相邻放置 G=8 (ns)', 57.1, '57.1'], ['各占 128 字节 G=8', 0.8, '0.8']], 57.1, mark=[0], done=[1]), kv=KV([['无填充', 'G=8:57.1 ns'], ['填充到 128 字节', 'G=8:0.8 ns'], ['G=1', '4.0 对 3.9 ns,没有区别']], ['无填充'])),
    step("编译结果(arm64):atomic.Int64.Add 先读 runtime.arm64HasATOMICS,为真则执行 LDADDALD(单条原子加指令),否则走另一段代码(我没有展开);CompareAndSwap 同样先检查 arm64HasATOMICS,为真则用 CASALD。", t=tl(S(4)), done=lidx(S(4), 'main.add:'), mark=lidx(S(4), 'main.cas:'), kv=KV([['Add', 'LDADDALD(有原子扩展时)'], ['CompareAndSwap', 'CASALD'], ['运行时检查', 'runtime.arm64HasATOMICS']], ['Add'])),
    step("sync/atomic 的包文档开头:这些函数需要非常小心地使用;除了特殊的低层应用,同步最好用 channel 或 sync 包。“Share memory by communicating; don't communicate by sharing memory.” 然后列出 Swap 和 CompareAndSwap 的等价写法。", t=tl(S(5)), done=lidx(S(5), 'great care', 'Share memory by communicating'), mark=lidx(S(5), 'swap operation', 'compare-and-swap'), kv=KV([['文档的态度', '谨慎使用,优先 channel 或 sync 包'], ['Swap / CAS', '文档给出等价的伪代码']], ['文档的态度'])),
]
A = mkartg('g61', 61, 'Go,sync/atomic,原子操作,Mutex,伪共享,真实验证,动画演示',
    '在 Go 1.27.1(arm64 macOS,8 个线程)里量原子操作与 Mutex 的边界:无竞争时 atomic.Add 4.1 ns、Mutex 7.7 ns;8 个 goroutine 争同一个计数器时 atomic 53.7 ns、Mutex 157.2 ns、CAS 循环 254.9 ns;互不共享的原子计数器相邻放置比隔开 128 字节慢约 70 倍(57.1 ns 对 0.8 ns);并看 arm64 上编译出的 LDADDALD 与 CASALD。',
    '“用 atomic 比 Mutex 快”只在一定条件下成立。这篇把同一个计数器在不同并发度下的耗时量出来,看 atomic、CAS 循环、Mutex 各自在哪里变慢,再用伪共享说明慢的真正原因是缓存行。',
    [('4.1 vs 7.7 ns', '无竞争时 atomic.Add 与 Mutex 保护的加一'), ('53.7 / 157.2 / 254.9 ns', '8 个 goroutine 争同一计数器时的 atomic、Mutex、CAS 循环'), ('57.1 vs 0.8 ns', '8 个 goroutine 各用自己的原子计数器:相邻放置对隔开 128 字节')],
    [('争的是同一个缓存行', '<p>无竞争时 atomic 比 Mutex 快一点(4.1 对 7.7 ns),差别不大。8 个 goroutine 争同一个计数器,atomic 慢到 53.7 ns,Mutex 157.2 ns,CAS 循环 254.9 ns——它失败了要重试。三者慢的根源都是这一个缓存行在核之间来回传递。</p>'),
     ('下限与伪共享', '<p>每个 goroutine 先在局部变量里累加,一次性汇总,每次只要 0.1–0.3 ns。更有意思的是伪共享:8 个 goroutine 各用自己的 atomic 变量,逻辑上互不相干,放在相邻内存里却是 57.1 ns,隔开 128 字节后只要 0.8 ns。慢的不是原子指令,是缓存行。</p>'),
     ('指令层面', '<p>arm64 上 <code>Add</code> 编译成 <code>LDADDALD</code>,<code>CompareAndSwap</code> 编译成 <code>CASALD</code>,前面各有一个对 <code>runtime.arm64HasATOMICS</code> 的检查。另一条分支(没有原子扩展时)我没有展开。</p>'),
     ('什么时候选哪个', '<p>计数这类单个变量用 atomic 比 Mutex 省;高并发下最好的办法是别共享——按 goroutine 分片、再汇总。包文档也建议优先用 channel 或 sync 包。以上是这台 8 线程 arm64 机器上的结论,别的核数、别的架构需要自己量。</p>'),
     ('读文档', '<p><code>sync/atomic</code> 文档开头就提醒这些函数要极其小心,除非是低层应用,同步最好用 channel 或 sync 包。</p>')],
    steps,
    [ENV_G + '。基准是自己写的:2000 万次操作平均分给 G 个 goroutine,用 close(start) 同时放行,墙钟时间 ÷ 2000 万,每格 3 次取中位数,GOMAXPROCS=8;伪共享用两种结构(无填充 / [120]byte 填充)的数组;汇编来自 go build -gcflags=-S;文档来自 go doc sync/atomic',
     '没有验证:x86 上的结果、缓存行大小(这里用 128 字节填充,没有单独测 64 字节是否够)、runtime.arm64HasATOMICS 为假时的路径、Mutex 在饥饿模式下的行为、更多/更少核数时的曲线、LDADDALD 的内存序语义细节'],
    '原子操作与 Mutex')
