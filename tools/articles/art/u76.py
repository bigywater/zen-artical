from lib import *
S = SS('u76')
steps = [
    step("catch_unwind 把 panic 变成 Result:没有 panic 时返回 Ok(2);有 panic 时返回 Err(payload),程序继续运行。载荷的类型取决于 panic! 怎么写:panic!(\"字面量\") 的载荷是 &str(downcast_ref::<&str>() 得 Some(\"固定字符串\"),String 得 None);带格式参数的 panic!(\"带参数 {}\", n) 的载荷是 String;panic_any(42i32) 的载荷就是 i32。", t=tl(S(1)), done=lidx(S(1), '没有 panic', '字面量', '带 {}', 'panic_any', '程序继续运行'), kv=KV([['panic!(\"字面量\")', '&str'], ['panic!(\"{}\", x)', 'String'], ['panic_any(v)', 'v 的类型']], ['panic!(\"{}\", x)'])),
    step("闭包里有 &mut 捕获时,catch_unwind 报 error[E0277]: the type `&mut i32` may not be safely transferred across an unwind boundary;note 说 `UnwindSafe` 对 &i32 实现了、对 &mut i32 没有。", t=tl(S(2)), mark=lidx(S(2), 'error[E0277]', 'UnwindSafe'), kv=KV([['闭包捕获 &mut', 'E0277:不是 UnwindSafe']], ['闭包捕获 &mut'])),
    step("包一层 AssertUnwindSafe 就能通过(程序员保证 panic 后状态仍可用):is_err = true,而 panic 之前对 count 的修改仍然可见,count = 1。", t=tl(S(2)), done=lidx(S(2), 'is_err = true'), kv=KV([['AssertUnwindSafe', '由你保证 panic 后状态一致']], ['AssertUnwindSafe'])),
    step("持锁时 panic:Mutex 被毒化,is_poisoned = true;之后 m.lock() 返回 Err(PoisonError),但 into_inner() 仍能取出数据 [1,2,3,4](panic 前的 push(4) 已经生效);clear_poison() 之后恢复为 false。", t=tl(S(3)), mark=lidx(S(3), 'is_poisoned = true'), done=lidx(S(3), 'lock 返回', 'clear_poison'), kv=KV([['panic 时持锁', '毒化'], ['数据', '仍可通过 into_inner 取出']], ['panic 时持锁'])),
    step("resume_unwind 重新抛出捕获到的 panic:第一次 panic 触发了自定义 hook(打印一次「hook 被调用: 原始 panic」),resume_unwind 再被 catch_unwind 捕获时 is_err = true,hook 没有再被调用。", t=tl(S(4)), done=lidx(S(4), 'hook 被调用', '第一次捕获后继续', 'resume_unwind'), kv=KV([['resume_unwind', '不触发 hook']], ['resume_unwind'])),
    step("panic = \"abort\" 时 catch_unwind 没有用:进程直接被信号 6(SIGABRT)终止,stdout 是空的,catch_unwind 根本没机会返回。", t=tl(S(4)), mark=lidx(S(4), 'panic = "abort"'), kv=KV([['panic = abort', 'catch_unwind 抓不到']], ['panic = abort'])),
    step("Drop 里在展开期间再 panic 会直接 abort:先打印「主函数先 panic」「Bomb::drop 里 panic」,stderr 依次是第一个 panic、drop 里的 panic,最后「panic in a destructor during cleanup / thread caused non-unwinding panic. aborting.」,进程被信号 6 终止。", t=tl(S(5)), mark=lidx(S(5), 'panic in a destructor', 'aborting'), done=lidx(S(5), 'stdout'), kv=KV([['展开中再 panic', 'abort(信号 6)']], ['展开中再 panic'])),
]
A = mkart('u76', 76, 'Rust,catch_unwind,panic,UnwindSafe,真实验证,动画演示',
    '用真实运行验证 catch_unwind:panic 变成 Err(载荷是 &str / String / 任意类型);闭包捕获 &mut 需要 AssertUnwindSafe(否则 E0277);持锁 panic 毒化 Mutex,into_inner 仍可取数据;resume_unwind 不再触发 hook;panic = "abort" 下抓不到;Drop 里再 panic 直接 abort。',
    'catch_unwind 能让 panic 不拖垮整个程序,但它不是 try/catch。这篇验证它能抓什么、载荷怎么还原、为什么要 UnwindSafe、毒化 Mutex 是怎么回事,以及哪些情况下它完全没用。',
    [('3 种', '载荷类型:&str(字面量)、String(带格式)、panic_any 的任意类型'), ('E0277', '闭包捕获 &mut 时不是 UnwindSafe'), ('SIGABRT', 'panic = "abort" 或展开中再 panic 时进程的终止信号')],
    [('载荷与捕获', '<p>panic 本身的行为见<a href="rust-panic-unwrap-expect.html">panic!、unwrap 与 expect</a>。</p>'), ('UnwindSafe', None), ('Mutex 毒化', '<p>Mutex 的基础见<a href="rust-mutex-interior-mutability.html">Mutex&lt;T&gt; 与内部可变性</a>。</p>'), ('resume_unwind 与 abort', None), ('Drop 里再 panic', None)],
    steps, [ENV_U + '。panic = "abort" 通过 cargo profile.dev 设置', '没有验证:跨 FFI 边界的 panic(extern "C" 里的展开行为)、catch_unwind 的性能开销、其它非 Rust 异常、线程里 catch_unwind 与 join 的组合'], 'catch_unwind')
