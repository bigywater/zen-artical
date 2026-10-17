from lib import *
S = SS('u32')
steps = [
    step("RefCell<T> 把借用检查推迟到运行期:let c = RefCell::new(vec![1, 2, 3]) 虽然 c 不是 mut,c.borrow_mut().push(4) 照样能修改(这叫内部可变性),打印得 [1, 2, 3, 4];同时持有两个 borrow() 也可以(多个只读)。", t=tl(S(1)), done=lidx(S(1), '[1, 2, 3, 4]', '同时两个'), kv=KV([['不需要 mut', '通过 & 也能修改'], ['检查时机', '运行期']], ['检查时机'])),
    step("违反借用规则在运行时才被发现:持有 borrow() 时再 borrow_mut(),panic:RefCell already borrowed,退出码 101。不想 panic 就用 try_borrow / try_borrow_mut,已有可变借用时它们返回 Err(is_err() 为 true)。", t=tl(S(2)), mark=lidx(S(2), 'panicked', 'already borrowed'), done=lidx(S(2), 'try_borrow'), kv=KV([['borrow_mut 冲突', 'panic(退出码 101)'], ['try_borrow_mut', '返回 Err']], ['borrow_mut 冲突'])),
    step("对比:同样的「读时写」错误用普通引用写,编译期就被拒绝:error[E0502]: cannot borrow `x` as mutable because it is also borrowed as immutable。RefCell 的代价就是把这类错误从编译期挪到了运行期 —— 能用普通借用就不要用 RefCell。", t=tl(S(3)), mark=lidx(S(3), 'error[E0502]'), kv=KV([['普通引用', '编译期报错'], ['RefCell', '运行期 panic']], ['普通引用'])),
    step("典型用途是 Rc<RefCell<T>>:共享所有权 + 可修改。两个所有者各自 push 一次,共享的 Vec 是 [1, 2]。空间成本:RefCell<u64> 比 u64 大一倍(16 字节 vs 8 字节),多出来的是借用标志;RefCell<u8> 是 16 字节(u8 只有 1 字节)。(运行时的耗时开销我没有可靠地量出来,所以这里不给数字。)", t=tl(S(4)), done=lidx(S(4), '[1, 2]'), mark=lidx(S(4), 'size_of'), kv=KV([['Rc<RefCell<T>>', '共享 + 可变'], ['RefCell<u64>', '16 字节(u64 是 8)']], ['Rc<RefCell<T>>'])),
]
A = mkart('u32', 32, 'Rust,RefCell,内部可变性,借用检查,真实验证,动画演示',
    '用真实运行验证 RefCell<T>:不需要 mut 也能通过 borrow_mut 修改;多个 borrow() 共存;借用规则被违反时运行期 panic(RefCell already borrowed),try_borrow 返回 Err;对照编译期 E0502;Rc<RefCell<T>> 共享修改;空间上多一个借用标志(RefCell<u64> 16 字节)。',
    'RefCell 是「内部可变性」的代表:借用规则不变,只是检查从编译期搬到了运行期。这篇验证它能做什么、违反规则时会怎样、与编译期借用的对照,以及典型的 Rc<RefCell<T>> 组合。',
    [('panic', '运行期违反借用规则:RefCell already borrowed(退出码 101)'), ('16 字节', 'RefCell<u64> 的大小(u64 是 8)'), ('Rc<RefCell<T>>', '共享所有权 + 可修改的惯用组合')],
    [('内部可变性', None), ('运行期检查', None), ('与编译期对照', '<p>编译期借用规则见<a href="rust-shared-vs-mut-borrow.html">不可变借用与可变借用</a>。</p>'), ('组合与成本', '<p>不借用而是直接替换值的轻量版本见<a href="rust-cell-interior-mutability.html">Cell&lt;T&gt;</a>;线程安全版本见<a href="rust-mutex-interior-mutability.html">Mutex&lt;T&gt;</a>。</p>')],
    steps, [ENV_U + '。我尝试用循环量 RefCell 的耗时开销,结果被编译器优化干扰、不可信,所以没有列出', '没有验证:RefCell 的运行期开销、Ref::map、借用标志的具体布局、在多线程里 RefCell 不是 Sync 的报错(见 Sync 一篇)'], 'RefCell')
