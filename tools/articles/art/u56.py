from lib import *
S = SS('u56')
steps = [
    step("Vec::new() 不分配:len=0 cap=0。第 1 个 push 后 cap 变成 4,之后每次装满就翻倍:4→8→16→32→64→128→256→512→1024→2048,在第 5、9、17、33、65、129、257、513、1025 个元素处扩容。", t=tl(S(1)), done=lidx(S(1), 'new:', '1025'), kv=KV([['起点', 'cap 0 → 4'], ['之后', '装满就 ×2']], ['之后'])),
    step("最小非零容量取决于元素大小:u8 是 8;大小不超过 1024 字节的类型(u32、u64、128 字节、1000、1024 字节)是 4;1025 字节与 5000 字节的元素是 1。零大小类型 Vec<()> 的 capacity 直接是 usize::MAX,根本不分配。", t=tl(S(2)), done=lidx(S(2), 'u8 ', '1024 字节', '1025 字节', 'Vec<()>'), kv=KV([['1 字节', '8'], ['≤ 1024 字节', '4'], ['> 1024 字节', '1'], ['零大小', 'usize::MAX']], ['≤ 1024 字节'])),
    step("用全局分配器计数:Vec::new() 逐个 push 1000 个 u64,分配器收到 1 次 alloc + 8 次 realloc,最终 cap 1024;with_capacity(1000) 只有 1 次 alloc、0 次 realloc,cap 恰好 1000。", t=tl(S(3)), done=lidx(S(3), '逐个 push', 'with_capacity(1000)'), b=bars([['Vec::new() 的 realloc', 8, '8'], ['with_capacity 的 realloc', 0, '0']], 10, cur=[0], done=[1]), kv=KV([['Vec::new()', '1 alloc + 8 realloc'], ['with_capacity(1000)', '1 alloc']], ['with_capacity(1000)'])),
    step("reserve 与 reserve_exact 的区别:cap 8 已满再 reserve(1) 得 cap 16(摊还式翻倍),reserve_exact(1) 得 cap 9(只要刚好够);vec![1,2,3] 上 reserve(10) 与 reserve_exact(10) 都得 13(需求 13 已超过翻倍的 6)。shrink_to_fit 把 cap 100 缩到 10。", t=tl(S(3)), done=lidx(S(3), 'cap 8 已满', 'shrink_to_fit'), kv=KV([['reserve(1)(满 8)', '16'], ['reserve_exact(1)(满 8)', '9'], ['shrink_to_fit', '100 → 10']], ['reserve_exact(1)(满 8)'])),
    step("扩容会搬家:cap 4 装满再 push 第 5 个,cap 变 8,缓冲区地址变了;cap 8 里 push 第 5 个地址没变。所以编译器不允许持有 &v[0] 时 push:error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable。", t=tl(S(4)), mark=lidx(S(4), 'error[E0502]'), done=lidx(S(4), '地址变了', '地址没变'), kv=KV([['满了再 push', '缓冲区搬家'], ['持有 &v[0] 时 push', 'E0502']], ['持有 &v[0] 时 push'])),
]
A = mkart('u56', 56, 'Rust,Vec,扩容,内存分配,真实验证,动画演示',
    '用真实运行验证 Vec 的扩容:Vec::new 不分配,第一次 push 后 cap 为 4(u8 为 8,元素超过 1024 字节为 1),之后翻倍;逐个 push 1000 个 u64 要 1 次 alloc 加 8 次 realloc,with_capacity 只要 1 次;reserve 与 reserve_exact 的区别;扩容搬家导致 E0502。',
    '往 Vec 里 push 看起来是 O(1),背后其实是「装满就换更大的缓冲区」。这篇把容量变化序列、不同元素大小的起始容量、分配器真实收到的调用次数,以及搬家带来的借用限制都真实跑了一遍。',
    [('×2', '装满之后 Vec<u32> 的扩容倍数(4→8→…→2048)'), ('1 + 8', '逐个 push 1000 个 u64 的 alloc + realloc 次数'), ('1 + 0', 'with_capacity(1000) 的 alloc + realloc 次数')],
    [('容量怎么变', None), ('元素大小与起始容量', '<p>这些起始容量是在当前工具链(rustc 1.98.1)上量到的数字,标准库的实现细节可能随版本变化。</p>'), ('分配器看到的次数', '<p>Box 与堆分配的基础见<a href="rust-box-heap.html">Box&lt;T&gt; 与堆分配</a>。</p>'), ('搬家与借用', '<p>借用规则见<a href="rust-exclusive-mut-borrow.html">可变借用为什么不能同时存在</a>。</p>')],
    steps, [ENV_U + '。容量序列在 release 模式下记录;分配次数用 #[global_allocator] 包装 System 计数', '没有验证:其它版本标准库的增长策略、realloc 是否原地扩展(只量了地址变化,没区分系统是否原地)、Vec::shrink_to、try_reserve、大容量(接近 isize::MAX)的错误'], 'Vec 扩容')
