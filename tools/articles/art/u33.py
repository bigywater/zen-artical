from lib import *
S = SS('u33')
steps = [
    step("Cell<T> 通过共享引用整体替换里面的值,从不借出引用:c 不是 mut,c.set(20) 照样可以;replace(30) 返回旧值 20,现在的值是 30;take() 取出 30 并留下默认值 0,之后 get() = 0。", t=tl(S(1)), done=lidx(S(1), 'replace', 'take'), kv=KV([['set / replace / take', '整体替换,不借出引用']], ['set / replace / take'])),
    step("get() 只对 Copy 类型可用:Cell<String> 的 get() 报 error[E0599]: the method `get` exists for struct `Cell<String>`, but its trait bounds were not satisfied(`String: Copy`)。非 Copy 类型用 replace / take / swap,把整个值换出来:replace(new) 得到旧值 hi,之后 take() 得到 new。", t=tl(S(2)), mark=lidx(S(2), 'error[E0599]'), done=lidx(S(2), '旧值 hi'), kv=KV([['Cell<T>::get', '要求 T: Copy'], ['非 Copy', 'replace / take']], ['Cell<T>::get'])),
    step("Cell 没有运行时借用标志:size_of::<Cell<u32>>() = 4,与 u32 一样大;Cell<String> 与 String 都是 24 字节。对比上一篇的 RefCell<u32> 是 16 字节。也因此 Cell 永远不会 panic。", t=tl(S(3)), mark=lidx(S(3), 'Cell<u32>'), kv=KV([['Cell<u32>', '4 字节'], ['RefCell<u32>', '16 字节']], ['Cell<u32>'])),
    step("典型用途:在 &self 方法里更新计数器或缓存。lookup(&self, ...) 里 self.hits.set(self.hits.get() + 1),通过两个共享引用 r1、r2 共调用 3 次,hits = 3 —— 不需要把方法改成 &mut self。", t=tl(S(4)), done=lidx(S(4), 'hits = 3'), kv=KV([['&self 方法里更新', 'Cell<u32> 计数器']], ['&self 方法里更新'])),
    step("Cell 不是 Sync:两个线程共享 &Cell 报 error[E0277]: `Cell<i32>` cannot be shared between threads safely,并建议改用 RwLock 或 AtomicI32。线程之间要改共享数据,用原子类型或锁。", t=tl(S(5)), mark=lidx(S(5), 'error[E0277]'), kv=KV([['&Cell 跨线程', 'E0277(不是 Sync)']], ['&Cell 跨线程'])),
]
A = mkart('u33', 33, 'Rust,Cell,内部可变性,真实验证,动画演示',
    '用真实编译验证 Cell<T>:不需要 mut 也能 set / replace / take;get() 要求 T: Copy(E0599),非 Copy 用 replace / take;大小与 T 相同(Cell<u32> 4 字节,RefCell<u32> 16 字节);在 &self 方法里更新计数器;Cell 不是 Sync(E0277)。',
    'Cell 是内部可变性里最轻的一种:它不借出引用,只能整体读出或整体替换,所以不需要任何运行时检查。这篇验证它的 API、对 T 的要求、内存开销、典型用途,以及为什么它不能跨线程。',
    [('4 字节', 'Cell<u32> 的大小,与 u32 相同(RefCell<u32> 是 16 字节)'), ('E0599', 'Cell<String>::get 要求 String: Copy'), ('E0277', 'Cell 不是 Sync,不能跨线程共享')],
    [('set、replace、take', None), ('不借出引用', None), ('大小', '<p>RefCell 见<a href="rust-refcell-runtime-borrow.html">RefCell&lt;T&gt; 运行时借用检查</a>。</p>'), ('&self 方法里更新状态', None), ('不能跨线程', '<p>线程安全的内部可变性见<a href="rust-mutex-interior-mutability.html">Mutex&lt;T&gt;</a>与<a href="rust-atomics-memory-ordering.html">原子类型</a>。</p>')],
    steps, [ENV_U, '没有验证:OnceCell / LazyCell、Cell<[T]> 与 as_slice_of_cells、UnsafeCell 作为所有内部可变性的基础、Cell 在优化后的汇编(是否和直接读写内存相同)'], 'Cell<T>')
