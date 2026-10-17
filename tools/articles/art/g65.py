from lib import *
S = SS('g65')
steps = [
    step("递归读锁:goroutine A 持有读锁,B 随后调 Lock 开始排队,A 再调一次 RLock。输出依次是 “B: 调用 Lock …”、“A: 已持有读锁,现在第二次 RLock …”,然后 fatal error: all goroutines are asleep - deadlock!——A 的第二次 RLock 被排队的写者挡住,B 又在等 A 的第一次读锁释放,互相等待。(这里是因为所有 goroutine 都睡了,运行时才报出来;在有别的 goroutine 在跑的服务里,它会悄无声息地卡住,这一点是我的推断,没有实验。)", t=tl(S(1)), done=lidx(S(1), 'B: 调用 Lock', 'A: 已持有读锁'), mark=lidx(S(1), 'deadlock'), kv=KV([['A', '持读锁后再 RLock'], ['B', '已在 Lock 排队'], ['结果', 'fatal error: all goroutines are asleep - deadlock!']], ['结果'])),
    step("写者排队时,新来的读者要等写者:R1 在 0 ms 拿到读锁并持有 100 ms;W 在 10 ms 请求写锁,在 101 ms 拿到(持有 20 ms);R2 在 20 ms 请求读锁,要等到 122 ms 才拿到——虽然 R1 只是读锁,R2 本可以与它并存,但排在写者后面。TryRLock 在“已有读者且有写者排队”时返回 false;只有读者、没有写者时返回 true。", t=tl(S(2)), done=lidx(S(2), '没有写者时'), mark=lidx(S(2), 'R1 在 0 ms', '有写者在排队时'), b=bars([['W 请求写锁(ms)', 10, '10'], ['R2 请求读锁', 20, '20'], ['W 拿到', 101, '101'], ['R2 拿到', 122, '122']], 122, done=[0, 1], mark=[2, 3]), kv=KV([['R2 的等待', '20 ms → 122 ms,共约 102 ms'], ['TryRLock(有写者排队)', 'false'], ['TryRLock(无写者)', 'true']], ['R2 的等待'])),
    step("读者不停地读,写者会不会饿死?8 个读者连续读(每次持锁约 1 ms),写者请求 30 次写锁,每次等待:最小 0.60 ms / 中位 0.91 ms / 最大 1.01 ms。每次最多等到当前读者放手(约 1 ms),不会被新读者无限推迟。", t=tl(S(3)), mark=lidx(S(3), '写者 30 次 Lock 的等待'), b=bars([['最小 (ms)', 0.60, '0.60'], ['中位', 0.91, '0.91'], ['最大', 1.01, '1.01']], 1.01, done=[0, 1, 2]), kv=KV([['读者持锁', '约 1 ms'], ['写者等待', '0.60 / 0.91 / 1.01 ms'], ['结论', '不会饿死']], ['结论'])),
    step("读写锁什么时候值得(8 个 goroutine 都只读,总耗时 RWMutex.RLock 对 Mutex.Lock):持有 0 ns:134.1 对 190.2 ms(160 万次);100 ns:227.8 对 578.2 ms(160 万次);1000 ns:3.1 对 18.8 ms(1.6 万次);100000 ns:204.9 对 1661.8 ms(1.6 万次)。临界区越长,RWMutex 的优势越大(100 µs 时约 8.1 倍);极短时只快一点(0 ns 时 1.4 倍)。", t=tl(S(4)), done=lidx(S(4), 'RWMutex.RLock'), mark=lidx(S(4), 'Mutex.Lock'), b=bars([['0 ns:Mutex/RWMutex 倍数', 1.4, '1.4×'], ['100 ns', 2.5, '2.5×'], ['1000 ns', 6.1, '6.1×'], ['100000 ns', 8.1, '8.1×']], 8.1, done=[3], mark=[0, 1, 2]), kv=KV([['持有 0 ns', 'RWMutex 134.1 ms,Mutex 190.2 ms'], ['持有 100 µs', 'RWMutex 204.9 ms,Mutex 1661.8 ms'], ['规律', '临界区越长,读写锁越划算']], ['规律'])),
    step("文档原文(go doc sync.RWMutex):如果有 goroutine 在锁已被一个或多个读者持有时调用 Lock,之后并发的 RLock 调用会阻塞,直到写者拿到并释放锁,以保证锁最终能让写者拿到;注意这禁止了递归读锁;RLock 不能升级成 Lock,Lock 也不能降级成 RLock。", t=tl(S(5)), done=lidx(S(5), 'will block until the writer'), mark=lidx(S(5), 'prohibits recursive read-locking'), kv=KV([['写者排队后', '新的 RLock 阻塞'], ['递归读锁', '被禁止'], ['升级 / 降级', '都不支持']], ['递归读锁'])),
]
A = mkartg('g65', 65, 'Go,RWMutex,读写锁,死锁,写者饥饿,真实验证,动画演示',
    '在 Go 1.27.1 里实测 RWMutex:持读锁时递归 RLock 遇上排队的写者会死锁(fatal error);写者排队后新读者要等(R2 在 20 ms 请求,122 ms 才拿到);8 个连续读的 goroutine 下写者每次只等 0.60–1.01 ms;8 个只读 goroutine 下,临界区 100 µs 时 RWMutex 比 Mutex 快约 8.1 倍,而几乎不持有时只快 1.4 倍。',
    'RWMutex 的文档里有一句不起眼的话:写者排队后,新的读者会阻塞。这意味着什么?这篇用实验复现递归读锁死锁,看写者排队的时间线,量写者会不会饿死,并测临界区多长读写锁才值得。',
    [('deadlock', '持读锁时递归 RLock、且有写者排队,运行时报 all goroutines are asleep'), ('0.60–1.01 ms', '8 个读者不停读时,写者每次 Lock 的等待范围'), ('8.1×', '100 µs 临界区、8 个只读 goroutine,Mutex 对 RWMutex 的总耗时倍数')],
    [('递归读锁是个坑', '<p>A 持有读锁、B 在 <code>Lock</code> 排队时,A 再 <code>RLock</code> 会被挡在写者后面,而 B 等着 A 的第一次读锁——典型死锁,运行时在所有 goroutine 都睡着时报 <code>fatal error</code>。文档明确说这禁止递归读锁。注意嵌套调用链里的“读锁函数调用读锁函数”。</p>'),
     ('写者排队后新读者要等', '<p>R1 持读锁 100 ms,W 在 10 ms 请求写锁,R2 在 20 ms 请求读锁:R2 直到 122 ms(W 拿到 101 ms 并持有 20 ms 之后)才拿到,尽管读锁本来可以并存。<code>TryRLock</code> 在这种情形下返回 false。</p>'),
     ('写者不会饿死', '<p>读者连续读(每次约 1 ms)时,写者 30 次请求的等待是 0.60–1.01 ms,正好是当前读者的持锁时间量级,没有被后来的读者无限推后。这是上面“排队后新读者阻塞”规则的直接结果。</p>'),
     ('读写锁什么时候值得', '<p>临界区几乎为空时,RWMutex 只比 Mutex 快 1.4 倍(134.1 对 190.2 ms);临界区 100 µs 时快约 8.1 倍(204.9 对 1661.8 ms)。再加上 RWMutex 本身更重,读很短的场景要先量。atomic.Value 那一篇里测过:8 个读者下 RWMutex.RLock 每次也要 78.8 ns。</p>'),
     ('读文档', '<p>文档那段话里有三个要点:写者排队后读者阻塞,所以递归读锁被禁止;RLock 不能升级为 Lock;Lock 也不能降级为 RLock。实验涉及了前两点,没有单独测“升级”会怎样(预期同样是死锁,没验证)。</p>')],
    steps,
    [ENV_G + '。递归读锁与时间线实验在 GOMAXPROCS=8 下运行一次,输出为运行时 fatal error 的第一行;写者等待用 8 个持锁约 1 ms 的读者(忙等待)和 30 次写锁请求;临界区对比用忙等待模拟持有时间,总次数 160 万(持有 1000 ns 以上为 1.6 万),单次测量;文档引自 go doc sync.RWMutex',
     '没有验证:RLock 升级为 Lock 的结果、读者数量更多时写者等待的上限、RWMutex 的内部实现(没有读源码)、TryLock 的更多情形、其它架构、有大量写者时的公平性'],
    'RWMutex')
