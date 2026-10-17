from lib import *
import re
S = SS('u94')
R = J('u94')
got = re.search(r'实际 (\d+)', R['racy']).group(1); sold = re.search(r'卖出了 (\d+) 件;库存值 = (-?\d+)', R['logic'])
steps = [
    step("两个线程同时可变地修改同一个 counter:error[E0499]: cannot borrow `counter` as mutable more than once at a time。数据竞争在编译期就被借用规则挡住了。", t=tl(S(1)), mark=lidx(S(1), 'error[E0499]'), kv=KV([['两个线程各 &mut counter', 'E0499']], ['两个线程各 &mut counter'])),
    step("一个线程读 v、一个线程 v.push(4):error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable。数据竞争 = 至少一个写 + 没有同步 + 同时访问;借用规则(可以有多个 &,或者一个 &mut)恰好把这种情形全部排除。", t=tl(S(2)), mark=lidx(S(2), 'error[E0502]'), kv=KV([['一读一写', 'E0502']], ['一读一写'])),
    step("合法的并发写法:多个线程同时只读 &v(合计 21);或者用 chunks_mut 把 Vec 切成互不重叠的 &mut 切片,每个线程一份,结果 [1, 1, 2, 2, 3, 3]。", t=tl(S(3)), done=lidx(S(3), '只读', '不重叠'), kv=KV([['多个 &T', '随便共享'], ['不重叠的 &mut', '各管各的']], ['不重叠的 &mut'])),
    step("static mut 也不是后门:2024 edition 里 let r = &COUNTER 报 error: creating a shared reference to mutable static(deny 级别的 static_mut_refs),help 建议用 &raw const。", t=tl(S(4)), mark=lidx(S(4), 'error: creating a shared reference'), kv=KV([['&static mut', 'deny:static_mut_refs']], ['&static mut'])),
    step("即使手写 unsafe impl Sync for Racy,闭包里直接写 c.0 仍被拒绝:error[E0277]: `UnsafeCell<u64>` cannot be shared between threads safely —— 2021 起闭包只捕获用到的字段 c.0(一个 UnsafeCell),而不是整个 c,Racy 的 Sync 承诺没有被用上。", t=tl(S(5)), mark=lidx(S(5), 'error[E0277]'), kv=KV([['闭包捕获', '只捕获 c.0']], ['闭包捕获'])),
    step(f"改成通过 &self 方法访问(闭包捕获整个 c)才能编译。4 个线程各 +1 一百万次,期望 4000000,实际只有 {got} —— 没有同步的并发写丢失了大量更新。这是未定义行为,只在 unsafe 里才能写出来。", t=tl(S(6)), mark=lidx(S(6), '期望 4000000'), kv=KV([['unsafe 里的竞争', f'4000000 → {got}']], ['unsafe 里的竞争'])),
    step(f"竞态条件(race condition)不等于数据竞争:全部用安全代码和 Mutex,「检查库存 → 睡一会 → 扣减」仍然可以出错。库存 1 件,4 个线程各自检查到「有货」后都扣减,卖出 {sold.group(1)} 件,库存变成 {sold.group(2)}。Rust 保证没有数据竞争,不保证没有逻辑竞态。", t=tl(S(7)), mark=lidx(S(7), '卖出了'), kv=KV([['数据竞争', 'Rust 的类型系统排除'], ['逻辑竞态', '要自己用锁覆盖整个「检查+操作」']], ['逻辑竞态'])),
]
A = mkart('u94', 94, 'Rust,数据竞争,借用检查,并发安全,真实验证,动画演示',
    f'用真实编译验证数据竞争为什么无法通过编译:两个线程 &mut 同一变量 E0499、一读一写 E0502;合法的共享只读与不重叠 &mut 切片;static mut 引用 deny;闭包只捕获字段导致 unsafe impl Sync 也被拒绝;unsafe 里的真实数据竞争 4000000 → {got};安全代码里的逻辑竞态卖出 {sold.group(1)} 件。',
    '“数据竞争无法通过编译”是 Rust 的招牌。这篇用能编译失败的真实例子逐条验证,再用 unsafe 故意造一个数据竞争看后果,最后说明它没有解决的另一类问题:逻辑上的竞态条件。',
    [('E0499 / E0502', '两个线程同时修改、或一读一写时的借用错误码'), (f'4000000 → {got}', 'unsafe 里没有同步的 4 线程 +1:期望与实际'), (f'{sold.group(1)} 件', '库存只有 1 件时,安全代码里的「检查-再-操作」竞态卖出的件数')],
    [('两个线程同时可变地修改', None), ('一读一写', None), ('合法的并发写法', '<p>Send 与 Sync 的规则见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>'), ('static mut', None), ('unsafe impl Sync 与闭包捕获', None), ('真实的数据竞争', '<p>这是未定义行为,结果只是这台机器、这次运行的现象。</p>'), ('竞态条件', '<p>原子类型与内存序见<a href="rust-atomics-memory-ordering.html">原子类型与内存序</a>。</p>')],
    steps, [ENV_U, '没有验证:Miri 或 ThreadSanitizer 对 unsafe 竞争的检测(需要 nightly)、跨 FFI 的竞争、死锁(Rust 不阻止)、unsafe 数据竞争在 debug 构建下的表现'], '数据竞争')
