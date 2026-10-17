import re
from lib import *
S = SS('u30')
t = '\n'.join(S(4)); rc, arc1 = [float(x) for x in re.findall(r'每次约 ([\d.]+) ns', t)]; sh_, sp_ = [float(x) for x in re.findall(r'墙钟 (\d+) ms', t)]
steps = [
    step("Arc<T> 是原子引用计数的 Rc:4 个线程各持有一个 Arc::clone 共享同一个 Vec,各自求和得到 3、7、11、15;所有线程结束后 strong_count 回到 1。", t=tl(S(1)), done=lidx(S(1), '线程', 'strong_count'), kv=KV([['Arc', '跨线程共享所有权'], ['结束后', 'strong_count = 1']], ['Arc'])),
    step("Arc 只给共享所有权、不给可变性:*a += 1 报 error[E0594]: cannot assign to data in an `Arc`。要修改就配合 Mutex:Arc<Mutex<u64>>,4 个线程各加 10000 次,counter = 40000,与期望一致。", t=tl(S(2)), mark=lidx(S(2), 'error[E0594]'), done=lidx(S(2), 'counter = 40000'), kv=KV([['Arc<i32> 修改', 'E0594'], ['Arc<Mutex<T>>', '40000 / 40000']], ['Arc<Mutex<T>>'])),
    step("Arc<T> 要求 T: Send + Sync:Arc<Cell<i32>> 交给 thread::spawn 报 error[E0277]: `Cell<i32>` cannot be shared between threads safely(Cell 不是 Sync),并说明 Arc<Cell<i32>> 因此不是 Send。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]'), kv=KV([['Arc<Cell<i32>>', 'E0277']], ['Arc<Cell<i32>>'])),
    step(f"克隆的代价:单线程里 Rc::clone + drop 与 Arc::clone + drop 在这台机器上差不多(约 {rc:.2f} ns 与 {arc1:.2f} ns;没有争用时原子操作的额外代价很小)。真正的代价来自争用:4 个线程各克隆 200 万次,共用同一个 Arc 时墙钟 {sh_:.0f} ms,各用自己的 Arc 只要 {sp_:.0f} ms —— 慢约 {sh_/sp_:.0f} 倍。(我的推断:同一个计数器所在的缓存行在核之间来回传递,没有用性能计数器验证。)", t=tl(S(4)), mark=lidx(S(4), '共用同一个'), b=bars([['4 线程共用一个 Arc', sh_, f'{sh_:.0f} ms'], ['4 线程各用自己的 Arc', sp_, f'{sp_:.0f} ms']], sh_, mark=[0], done=[1]), kv=KV([['无争用', f'Rc ≈ Arc ≈ {arc1:.1f} ns'], ['共用计数器', f'慢 {sh_/sp_:.0f} 倍']], ['共用计数器'])),
]
A = mkart('u30', 30, 'Rust,Arc,原子引用计数,多线程,真实验证,动画演示',
    f'用真实编译与计时验证 Arc<T>:4 个线程共享一个 Vec;Arc 不可变(E0594),配合 Mutex 得到 40000/40000;Arc<Cell> 因 Cell 非 Sync 报 E0277;无争用时 Arc 与 Rc 克隆都约 {arc1:.1f} ns,4 线程共用同一个 Arc 克隆比各用各的慢约 {sh_/sp_:.0f} 倍。',
    '上一篇的 Rc 不能跨线程,Arc 就是它的线程安全版本。这篇验证 Arc 能做什么、不能做什么、对 T 有什么要求,并量一量「原子计数」到底贵不贵 —— 结果是:不争用时几乎不贵,争用时非常贵。',
    [('E0594', 'Arc 里的数据不可变,要修改得配合 Mutex'), ('40000', '4 线程 × 10000 次,Arc<Mutex<u64>> 的最终值'), (f'≈ {sh_/sp_:.0f} 倍', '4 线程共用一个 Arc 克隆与各用各的相比的慢速倍数')],
    [('跨线程共享', None), ('Arc 与 Mutex', '<p>Mutex 的细节见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>。</p>'), ('Send + Sync 要求', None), ('克隆的代价', '<p>原子操作与内存顺序见<a href="rust-atomics-memory-ordering.html">原子类型与内存顺序</a>。</p>')],
    steps, [ENV_U + '。计时为 release 构建的单次运行,机器为 Apple 芯片(原子操作的代价在其它 CPU 上可能不同)', '没有验证:Arc 在 x86 上无争用的开销、Arc::make_mut / get_mut / try_unwrap、Arc<str>、克隆后立即 drop 是否会被编译器优化掉(使用了 black_box)、争用慢速的硬件原因'], 'Arc<T>')
