from lib import *
S = SS('u100')
steps = [
    step("tokio::spawn 要求 Future 是 Send + 'static。借用局部变量的 async 块 tokio::spawn(async { println!(\"hello {}\", name); }) 报 error[E0373]: async block may outlive the current function, but it borrows `name`,note 说「async blocks are not executed immediately and must either take a reference or ownership of outside variables they use」,help 建议加 move。", t=tl(S(1)), mark=lidx(S(1), 'error[E0373]', 'async blocks are not executed'), kv=KV([['spawn 的 Future', "必须 'static"], ['借用 name', 'E0373']], ['借用 name'])),
    step("三种修法都可以:① async move 把 name 的一份克隆交给任务,任务拥有它;② Arc::clone 让 3 个任务共享同一个 Vec,收集结果 [10, 20, 30],全部结束后 strong_count 回到 1;③ 克隆之后原来的 name 仍然可用。", t=tl(S(2)), done=lidx(S(2), '①', '②', '③'), kv=KV([['move', '任务拥有数据'], ['Arc', '多个任务共享'], ['clone', '原变量继续可用']], ['Arc'])),
    step("不 spawn 就没有 'static 的限制:tokio::join! 在同一个任务里并发运行两个 async 块,它们可以借用局部的 name 和 data,结果 \"tokio 长度 5\" 与 6,之后 name 与 data 仍然可用。代价是它们共享同一个任务(不能跨线程并行)。", t=tl(S(3)), done=lidx(S(3), 'join!'), kv=KV([['join!', '同一任务内并发,可借用'], ['spawn', "独立任务,要求 'static"]], ['join!'])),
    step("'static 不是「活到程序结束的值」,而是「不含短生命周期借用」:拥有所有权的 String、字面量 &'static str、Box::leak 出来的 &'static mut 都满足 T: 'static;而 &local(借用局部变量 local)报 error[E0597]: `local` does not live long enough,note 写「argument requires that `local` is borrowed for `'static`」。", t=tl(S(4)), mark=lidx(S(4), 'error[E0597]', "'static"), kv=KV([['拥有的 String', "满足 'static"], ['字面量', "满足 'static"], ['&local', 'E0597']], ['&local'])),
    step("借用发生在任务内部就没问题:spawn 的任务里先创建 v,再 let r = &v 并跨 yield_now().await 使用,结果 10。限制的是「从任务外面借进来」,不是任务内部的借用。", t=tl(S(5)), done=lidx(S(5), '任务内部借用'), kv=KV([['任务内部借用自己的数据', '可以,跨 await 也行']], ['任务内部借用自己的数据'])),
]
A = mkart('u100', 100, 'Rust,tokio,spawn,生命周期,真实验证,动画演示',
    "真实验证 tokio::spawn 为什么要求 'static:借用局部变量的 async 块报 E0373;move、Arc、clone 三种修法;tokio::join! 在同一任务里并发可以借用;'static 的含义(拥有的值、字面量、Box::leak 都满足,&local 报 E0597);任务内部的借用不受限制。",
    "tokio::spawn(async { … name … }) 报「may outlive」是最常见的 async 编译错误。这篇从错误信息出发,验证三种修法,再说明 'static 到底限制什么、什么时候用 join! 就不用考虑它。",
    [("E0373", "spawn 里的 async 块借用局部变量的错误码"), ("3 种", "修法:move、Arc 共享、clone"), ("join!", "不要求 'static 的同任务并发方式")],
    [("spawn 为什么要 'static", '<p>线程的类似限制见<a href="rust-thread-spawn-join.html">线程创建与 Join</a>;调度见<a href="rust-tokio-scheduling.html">Tokio 任务调度</a>。</p>'), ('三种修法', None), ('join! 可以借用', None), ("'static 的真实含义", None), ('任务内部的借用', None)],
    steps, [ENV_U + '。tokio 1.x', '没有验证:tokio::task::LocalSet(也要求 \'static)、scoped 异步任务库(如 async-scoped)、FuturesUnordered 配合借用、Box::leak 的内存泄漏对长期运行程序的影响、Send 约束的错误(见 Send 与 Sync 一篇)'], "spawn 与 'static")
