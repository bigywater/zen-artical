from lib import *
S = SS('u13')
steps = [
    step("const LIMIT: u32 = 100 是编译期常量;static GREETING 与 static TABLE 是程序里一个固定的内存位置:对 TABLE 两次取地址相同(true),地址在可执行文件的数据段,与 main 函数所在的代码段、栈上的局部变量是三个不同的区域(地址数值每次运行都不同,栈地址远大于另外两个)。", t=tl(S(1)), done=lidx(S(1), 'static TABLE', 'main 函数', '栈上'), kv=KV([['static', '固定地址,在数据段'], ['代码 / 栈', '不同的区域']], ['static'])),
    step("const fn 在编译期求值:const FIB20: u64 = fib(20),get() 返回它,-O 汇编只有 mov w0, #6765 ; ret —— 20 次迭代的循环在编译期就算完了,6765 直接写进指令。同样的循环放在普通函数里(runtime(n) 的 n 是运行时参数),汇编有 16 条指令,带循环与分支。", t=tl(S(2)), mark=lidx(S(2), 'mov\tw0, #6765', 'mov	w0, #6765'), kv=KV([['const 求值', 'mov w0, #6765'], ['运行时求值', '16 条指令的循环']], ['const 求值'])),
    step("static mut 可以修改,但每次访问都要 unsafe:COUNTER += 1; 与 println!(\"{}\", COUNTER) 各报一个 error[E0133]: use of mutable static is unsafe and requires unsafe block(note:mutable statics can be mutated by multiple threads)。放进 unsafe 块后,2024 edition 里 println! 对它隐式取了共享引用,又触发 deny 级别的 lint:error: creating a shared reference to mutable static(static_mut_refs)。", t=tl(S(3)), mark=lidx(S(3), 'error[E0133]', 'static_mut_refs'), kv=KV([['访问 static mut', 'E0133,需要 unsafe'], ['对它取引用', '2024 里 deny 级 lint']], ['访问 static mut'])),
    step("安全的可变全局用原子类型:static COUNTER: AtomicUsize,4 个线程各 fetch_add 1000 次,最终 COUNTER = 4000。static 要求类型实现 Sync:static C: Cell<i32> 报 error[E0277]: `Cell<i32>` cannot be shared between threads safely,并建议改用 RwLock 或原子类型。", t=tl(S(4)), done=lidx(S(4), 'COUNTER = 4000'), mark=lidx(S(4), 'error[E0277]'), kv=KV([['AtomicUsize', '4 线程 × 1000 = 4000'], ['static Cell', 'E0277(不是 Sync)']], ['static Cell'])),
]
A = mkart('u13', 13, 'Rust,const,static,static mut,真实验证,动画演示',
    '用真实编译与汇编验证 const 与 static:static 有固定的数据段地址;const fn 在编译期求值(fib(20) 变成 mov w0, #6765);static mut 访问报 E0133,2024 edition 对其取引用还触发 deny 级 lint;原子类型是安全的可变全局,static Cell 因不是 Sync 报 E0277。',
    'const、static 与 static mut 常被混在一起讲。这篇逐个验证:它们在内存里的位置,const fn 能把计算提前到编译期的证据,static mut 为什么需要 unsafe、2024 edition 又加了什么限制,以及安全的可变全局应该怎么写。',
    [('mov w0, #6765', 'const FIB20 = fib(20) 在 -O 下编译成的整个函数体(加 ret)'), ('E0133', '访问 static mut 需要 unsafe'), ('Sync', 'static 的类型必须是 Sync(Cell 不行,原子类型可以)')],
    [('const 与 static', None), ('const fn 与编译期求值', '<p>编译期断言就是这个机制的应用,见<a href="rust-compile-time-assert.html">编译期断言</a>。</p>'), ('static mut', None), ('安全的可变全局', '<p>原子类型与内存顺序见<a href="rust-atomics-memory-ordering.html">原子类型与内存顺序</a>;Sync 的含义见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>')],
    steps, [ENV_U + '。汇编用 --emit=asm -O 生成,目标 aarch64-apple-darwin;地址是单次运行的数字', '没有验证:const 在每个使用处被内联(按 Rust 参考手册的说法,没有逐处验证)、static 的初始化表达式的限制、thread_local!、OnceLock / LazyLock、const 泛型'], 'const 与 static')
