from lib import *
S = SS('g63')
steps = [
    step("池里的对象能活过几次 GC?放入 100 个对象,runtime.GC() 之后再 Get 100 次(GOMAXPROCS=4):0 次 GC → 取到原来的 100 个;1 次 GC → 取到原来的 99 个、New 新造 1 个;2 次 GC → 原来的 0 个、新造 100 个;3 次 GC → 同样 0 个、新造 100 个。一次 GC 之后基本都还在,两次之后全没了(1 次 GC 后少的那 1 个,我没有查原因)。", t=tl(S(1)), done=lidx(S(1), 'GC() 0 次', 'GC() 1 次'), mark=lidx(S(1), 'GC() 2 次', 'GC() 3 次'), b=bars([['0 次 GC 后还在', 100, '100'], ['1 次 GC 后还在', 99, '99'], ['2 次 GC 后还在', 0, '0'], ['3 次 GC 后还在', 0, '0']], 100, done=[0, 1], mark=[2, 3]), kv=KV([['0 次 GC', '100 / 100 还在'], ['1 次 GC', '99 / 100 还在'], ['2 次及以上', '全部丢失'], ['未查', '1 次 GC 后少的 1 个']], ['2 次及以上'])),
    step("放进池里的是什么也有成本:Put([]byte)(把切片本身放进去)每次 1 次分配,因为切片头要装箱成 interface;Put(&s)(放指针)每次 0 次分配。", t=tl(S(2)), mark=lidx(S(2), 'Put([]byte)'), done=lidx(S(2), 'Put(&s)'), kv=KV([['Put(切片)', '1 次分配(装箱)'], ['Put(指针)', '0 次分配']], ['Put(切片)'])),
    step("复用 bytes.Buffer 值不值得(每次写约 2 KB):每次新建 bytes.Buffer(单 goroutine)714 ns/次、4032 B/次、6 次分配;sync.Pool 复用 192 ns/次、0 B、0 次分配。4 个 P 并行:每次新建 987 ns/次,复用 71 ns/次。", t=tl(S(3)), done=lidx(S(3), 'sync.Pool 复用'), mark=lidx(S(3), '每次新建'), b=bars([['新建(单) ns', 714, '714'], ['Pool(单)', 192, '192'], ['新建(4P 并行)', 987, '987'], ['Pool(4P 并行)', 71, '71']], 987, mark=[0, 2], done=[1, 3]), kv=KV([['单 goroutine', '714 → 192 ns,6 次分配 → 0'], ['4 个 P 并行', '987 → 71 ns'], ['内存', '4032 B/次 → 0 B/次']], ['4 个 P 并行'])),
    step("对 GC 的影响:200 万次借用 4 KiB 缓冲区。每次 make:GC 2611 次,累计分配 8192 MB;用 sync.Pool:GC 0 次,累计分配 0 MB。", t=tl(S(4)), mark=lidx(S(4), '每次 make'), done=lidx(S(4), '用 sync.Pool'), b=bars([['每次 make:GC 次数', 2611, '2611'], ['用 sync.Pool:GC 次数', 0, '0']], 2611, mark=[0], done=[1]), kv=KV([['每次 make', 'GC 2611 次,分配 8192 MB'], ['sync.Pool', 'GC 0 次,分配 0 MB']], ['sync.Pool'])),
    step("源码与文档:sync/pool.go 的 poolCleanup 在每次 GC 开头(世界停止时)调用:先丢掉所有池的 victim 缓存(p.victim = nil),再把主缓存移成 victim 缓存(p.victim = p.local),主缓存清空。所以对象第一次 GC 后只是从主缓存变成 victim 缓存,第二次 GC 才真被丢掉。文档:Pool 里的任何条目可能随时被自动移除,不另行通知。", t=tl(S(5)), done=lidx(S(5), 'Drop victim caches', 'p.victim = nil'), mark=lidx(S(5), 'Move primary cache to victim cache', 'p.victim = p.local', 'Any item stored in the Pool'), kv=KV([['第 1 次 GC', '主缓存 → victim'], ['第 2 次 GC', 'victim 被丢弃'], ['文档', '条目随时可能被移除']], ['第 2 次 GC'])),
]
A = mkartg('g63', 63, 'Go,sync.Pool,victim cache,对象复用,GC,真实验证,动画演示',
    '在 Go 1.27.1 里验证 sync.Pool:放入 100 个对象后,一次 GC 还能取回 99 个,两次 GC 全部丢失(对应 poolCleanup 里“主缓存→victim→丢弃”);Put 切片本身比 Put 指针多一次分配;复用 bytes.Buffer 从 714 ns/6 次分配降到 192 ns/0 次分配,4 核并行 987 ns 降到 71 ns;200 万次借用 4 KiB 缓冲区,GC 次数从 2611 降到 0。',
    'sync.Pool 的文档只说“可能随时被移除”,但具体活多久?值不值得用?这篇实测对象能活过几次 GC(答案对应源码里的 victim cache),并量复用对分配、耗时和 GC 次数的影响,以及一个常见的装箱坑。',
    [('99 → 0', '一次 GC 后还剩的对象数,两次 GC 后就是 0(放入 100 个)'), ('714 → 192 ns', '复用 bytes.Buffer 的单 goroutine 耗时,分配从 6 次降为 0'), ('2611 → 0', '200 万次借用 4 KiB 缓冲区的 GC 次数')],
    [('victim cache 是什么', '<p>每次 GC 开头,<code>poolCleanup</code> 先丢掉上一轮的 victim 缓存,再把当前的主缓存挪成 victim 缓存。对象因此要经过两次 GC 才会消失:实验里放入 100 个,一次 GC 后还能取回 99 个,两次后一个不剩。(一次 GC 少的那个,我没有查。)</p>'),
     ('放指针,别放值', '<p>往池里 <code>Put</code> 一个切片会因为装箱多一次分配,放它的指针就没有。这是用 Pool 时最常见的无意义开销。</p>'),
     ('复用的收益', '<p>每次写约 2 KB 的 <code>bytes.Buffer</code>,新建每次 714 ns、6 次分配、4032 B;用池复用后 192 ns、0 次分配。4 个 P 并行时 987 ns 对 71 ns。做这种测试时要把 Reset 的成本算进去(这里已经包含)。</p>'),
     ('对 GC 的影响', '<p>200 万次借用 4 KiB 缓冲区,每次 <code>make</code> 触发了 2611 次 GC、累计分配 8192 MB,用池复用时一次 GC 都没触发。这是一个理想化的循环,真实服务里池里的对象仍然会因为 GC 而丢失重建。</p>'),
     ('什么时候不该用', '<p>文档的建议:短寿命对象自己持有的空闲链表不适合用 Pool;Pool 适合在并发的独立使用者之间共享临时对象(fmt 的缓冲区就是例子)。本文没有测短寿命场景。</p>')],
    steps,
    [ENV_G + '。生存实验每组新建一个 Pool,GOMAXPROCS=4;基准用 testing.Benchmark 与 RunParallel;GC 次数来自 runtime.MemStats;读过的源码与文档:sync/pool.go 的 poolCleanup、go doc sync.Pool',
     '没有验证:一次 GC 后少的 1 个对象去了哪、Pool 的 per-P 结构(private/shared 链)细节、对象特别大或特别多时的表现、Pool 与 finalizer 的交互、短寿命场景下的收益、其它架构'],
    'sync.Pool')
