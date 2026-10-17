from lib import *
S = SS('u20')
steps = [
    step("任意多个 &T 可以同时存在:a、b、c 都是对同一个 Vec 的只读引用(std::ptr::eq 比较为 true),各自读到 len = 3;c = a 只是复制了一个引用 —— &T 本身实现了 Copy(is_copy(&a) 编译通过)。", t=tl(S(1)), done=lidx(S(1), 'true', 'len:'), kv=KV([['多个 &T', '可以同时存在'], ['&T', '是 Copy']], ['&T'])),
    step("多个线程同时读同一份数据是安全的:用 thread::scope 起 4 个线程,每个读 Vec 的一个 25 万元素的切片(共享同一份数据),总和 500000500000,与期望值 1_000_000 × 1_000_001 / 2 一致。只读共享不需要锁。", t=tl(S(2)), done=lidx(S(2), '总和'), kv=KV([['4 线程并发读', '无锁,结果正确']], ['4 线程并发读'])),
    step("共享的同时能修改就是数据竞争的温床:两个线程都 c.set(c.get() + 1) 共享一个 Cell,编译不过 —— error[E0277]: `Cell<i32>` cannot be shared between threads safely(Cell 没有实现 Sync,&Cell<i32> 因此不是 Send),并建议改用 RwLock 或原子类型。可变共享被类型系统挡在了线程之外。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]'), kv=KV([['&Cell 跨线程', 'E0277(不是 Sync)']], ['&Cell 跨线程'])),
    step("同一线程里也一样:已经有 r1、r2 两个只读引用,再 v.push(4) 报 error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable。读者还活着时,写者被拒绝 —— 多个读者共存的前提是没有人在写。", t=tl(S(4)), mark=lidx(S(4), 'error[E0502]'), kv=KV([['读者在场时 push', 'E0502']], ['读者在场时 push'])),
]
A = mkart('u20', 20, 'Rust,借用,共享,Sync,线程,真实验证,动画演示',
    '用真实编译与运行验证为什么多个不可变借用可以共存:多个 &T 指向同一份数据且 &T 是 Copy;4 个线程用 thread::scope 并发只读同一个 Vec 结果正确;&Cell 跨线程被 Sync 拒绝(E0277);读者在场时写者被拒绝(E0502)。',
    '「可以有任意多个 &T」这条规则背后的原因是:只读不会互相干扰。这篇从三个角度验证它:引用本身是 Copy、多线程并发读真的能跑出正确结果、以及一旦引入「共享 + 修改」(Cell),编译器马上用 Sync 把它拦住。',
    [('Copy', '&T 本身是 Copy,可以随便复制'), ('500000500000', '4 个线程共享读一个 Vec 得到的总和(正确)'), ('E0277', '&Cell<i32> 跨线程:Cell 不是 Sync')],
    [('多个 &T', None), ('多线程只读', '<p>Send 与 Sync 的定义见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>'), ('共享加修改', '<p>需要「共享 + 修改」时用 Mutex、RwLock 或原子类型,见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>。</p>'), ('读者在场时写者被拒绝', None)],
    steps, [ENV_U + '。多线程求和用 release 构建;没有对比与单线程的耗时', '没有验证:并行读的加速比、伪共享(false sharing)对只读共享的影响、Arc<T> 共享所有权(见其它文章)'], '共享借用')
