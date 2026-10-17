from lib import *
S = SS('n17')
steps = [
    step("Context 里有一把 sync.RWMutex(mu)和一个导出的 Keys map[any]any。Set 先 c.mu.Lock(),Keys 为 nil 就 make,再写;Get 用 c.mu.RLock() 读。所以只要通过 Set / Get(以及 GetString 等包装)访问,就是并发安全的;而 Keys 是导出字段,绕过锁直接读写它不受保护。", t=tl(S(1)), mark=lidx(S(1), 'c.mu.Lock()', 'c.mu.RLock()', 'Keys map[any]any'), done=lidx(S(1), 'mu sync.RWMutex', 'c.Keys = make(map[any]any)'), kv=KV([['Set', 'Lock,Keys 为 nil 时才 make'], ['Get', 'RLock'], ['c.Keys', '导出字段,没有锁']], ['c.Keys'])),
    step("50 个 goroutine 各对同一个 Context 做 200 次 Set + Get(用 -race 编译):最终 Keys 里正好 10000 个键,读回不一致 0 次,竞态检测器报告 0 个,退出码 0。", t=tl(S(2)), mark=lidx(S(2), '竞态检测器报告个数: 0'), done=lidx(S(2), '10000 个键'), kv=KV([['10000 个键', '没有丢失'], ['读回不一致', '0 次'], ['-race 报告', '0 个']], ['-race 报告'])),
    step("绕过 Set,8 个 goroutine 直接对 c.Keys[...] 各写 10 万次:连续 3 次运行都以 fatal error: concurrent map writes 崩溃(退出码 2),这个检查是 Go 运行时的,不需要 -race;-race 版本则报告了 Write at … / Previous write at …,两个访问都在 main.main.func1.1(也是退出码 2)。", t=tl(S(3)), mark=lidx(S(3), 'fatal error: concurrent map writes', 'Previous write at'), done=lidx(S(3), '第 1 次运行', '第 2 次运行', '第 3 次运行', 'Write at'), kv=KV([['直接写 c.Keys', '3 次全崩:concurrent map writes'], ['退出码', '2(进程直接退出,Recovery 拦不住)'], ['检测', 'Go 运行时自带,不用 -race']], ['退出码'])),
    step("Keys 在第一次 Set 之前是 nil:进入 handler 时 c.Keys == nil 为真,读 c.Keys[\"a\"] 得到 nil 没问题;直接 c.Keys[\"a\"] = 1 会 panic(assignment to entry in nil map);c.Set 之后 Keys 才有内容。v1.12 的 Keys 是 map[any]any,结构体和整数都可以做键。", t=tl(S(4)), mark=lidx(S(4), 'panic: assignment to entry in nil map'), done=lidx(S(4), '进入时 c.Keys == nil: true', 'c.Set 之后', 'map[any]any'), kv=KV([['Keys 初始', 'nil,第一次 Set 才创建'], ['直接写', 'panic: assignment to entry in nil map'], ['键类型', 'any(v1.12)']], ['Keys 初始'])),
    step("互斥锁的开销(单 goroutine、无竞争,9 轮中位数):c.Get 16.1 ns,直接读 map[any]any 12.8 ns;c.Set 29.8 ns,直接写 23.7 ns。锁带来的额外开销是几纳秒,远小于一次请求里别的开销。", t=tl(S(5)), mark=lidx(S(5), 'c.Get', 'c.Set'), done=lidx(S(5), '直接读', '直接写'), b=bars([['c.Get', 16.1, '16.1 ns'], ['map 直接读', 12.8, '12.8 ns'], ['c.Set', 29.8, '29.8 ns'], ['map 直接写', 23.7, '23.7 ns']], 29.8, mark=[0, 2], done=[1, 3]), kv=KV([['读', '多约 3.3 ns'], ['写', '多约 6.1 ns'], ['结论', '锁的开销可以忽略']], ['结论'])),
]
A = mkartn('n17', 17, 'Gin,Context,Keys,并发安全,RWMutex,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 c.Keys 的并发安全:Set / Get 有读写锁,50 个 goroutine 同时操作无竞态、不丢数据;绕过 Set 直接写 c.Keys 会以 fatal error: concurrent map writes 崩溃;Keys 初始为 nil;锁的开销是几纳秒。',
    'c.Set 和 c.Get 是并发安全的,但 c.Keys 是个导出的 map。这篇用 -race 和多个 goroutine 验证 Set/Get 到底安全到什么程度,再把绕过锁直接写 Keys 的后果、nil map 的坑和锁本身的开销一一量出来。',
    [('10000 个键', '50 个 goroutine 同时 Set+Get,没有丢失,-race 报告 0 个'), ('3 / 3', '直接并发写 c.Keys 时崩溃的次数(concurrent map writes)'), ('+3.3 ns', 'c.Get 比直接读 map 多出的耗时(16.1 vs 12.8 ns)')],
    [('锁在哪里', '<p><code>Set</code> 持写锁,<code>Get</code> 持读锁,所以通过它们(以及基于它们的 <code>GetString</code>、<code>GetInt</code> 等)并发访问同一个 Context 是安全的。但 <code>Keys</code> 本身是个导出的字段,源码里没有任何东西阻止你绕过锁直接读写。</p>'),
     ('Set / Get 的安全性', '<p>50 个 goroutine、每个 200 次 Set+Get,最后 10000 个键一个不少,读回的值全部一致,<code>-race</code> 没有任何报告。注意这是对“同一个 Context”并发访问的结果;跨请求持有 Context 的问题见上一篇。</p>'),
     ('绕过 Set 的后果', '<p>直接并发写 <code>c.Keys</code>,Go 运行时会检测并发写 map 并让整个进程以 <code>fatal error: concurrent map writes</code> 退出(退出码 2)。这是 <code>fatal error</code> 而不是普通 panic,<code>Recovery</code> 中间件拦不住,服务会直接挂掉。</p>'),
     ('nil map', '<p><code>Keys</code> 是懒创建的:进入 handler 时是 nil,读取没有问题,但直接 <code>c.Keys["a"] = 1</code> 会 panic。v1.12 的键类型是 <code>any</code>,可以用自定义类型做键来避免不同包之间的键冲突。</p>'),
     ('开销', '<p>读写锁在无竞争时的开销是几个纳秒:读多 3.3 ns,写多 6.1 ns。相对于 handler 里的任何 I/O 都可以忽略,不需要为了省这点开销而绕过 Set / Get。</p>')],
    steps,
    [ENV_N_GIN + '。并发实验用真实的 httptest.NewServer;-race 版本用 go build -race;崩溃实验重复 3 次(每次一个新进程);基准是 testing.Benchmark,9 轮中位数,用 gin.CreateTestContext 创建的 Context,单 goroutine',
     '没有验证:读写混合且有争用时的锁开销;sync.Map 或分片锁是否更合适;Get 系列包装函数(GetString 等)的类型断言开销;在 c.Copy() 之后跨 goroutine 访问副本 Keys 的行为(副本的 Keys 是独立的 map)'],
    'Keys 并发')
