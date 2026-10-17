from lib import *
S = SS('u26')
steps = [
    step("'static 引用的来源:字符串字面量(lit() 返回 \"字面量\")、static 变量(GLOBAL)、以及 Box::leak —— leaked() 把一个 Vec 放到堆上后「泄漏」,得到 &'static mut Vec<i32>,可以修改(push(4) 得到 [1, 2, 3, 4])并在函数返回后继续使用。", t=tl(S(1)), done=lidx(S(1), '全局', 'Box::leak'), kv=KV([["&'static 的来源", '字面量、static、Box::leak']], ["&'static 的来源"])),
    step("T: 'static 的意思是「T 里不含非 'static 的引用」,并不是「永远活着」:拥有数据的 String、整数 5、&'static str 都满足 needs_static<T: 'static>,输出「收到 \"owned\"」等;但 needs_static(&s)(s 是局部变量)报 error[E0597]: `s` does not live long enough,note 指出要求 T 的生命周期超过 'static。", t=tl(S(2)), mark=lidx(S(2), 'error[E0597]'), done=lidx(S(2), '收到'), kv=KV([["拥有数据(String)", "满足 'static"], ['&局部变量', "不满足"]], ["拥有数据(String)"])),
    step("thread::spawn 要求闭包满足 'static(线程可能比当前函数活得久):闭包借用局部变量 v 报 error[E0373]: closure may outlive the current function, but it borrows `v`,并建议加 move。三种解法都能跑:① move 把 v 的所有权交给线程;② Arc 共享;③ thread::scope 的作用域线程保证在作用域结束前 join,所以允许借用局部变量。", t=tl(S(3)), mark=lidx(S(3), 'error[E0373]'), done=lidx(S(3), '解法', 'move 之后'), kv=KV([['借用局部变量', 'E0373'], ['解法', 'move / Arc / thread::scope']], ['借用局部变量'])),
    step("Box::leak 真的不释放:用计数分配器统计,1000 个 Box 正常 drop 是 alloc +1000、dealloc +1000;1000 个 Box::leak 是 alloc +1000、dealloc +0 —— 内存直到进程结束都不会归还。'static 引用要付出的代价就是这块内存永远不释放。", t=tl(S(4)), mark=lidx(S(4), 'Box::leak'), b=bars([['正常 drop 的 dealloc', 1000, '1000'], ['Box::leak 的 dealloc', 0, '0']], 1000, mark=[1], done=[0]), kv=KV([['Box 正常 drop', 'dealloc +1000'], ['Box::leak', 'dealloc +0']], ['Box::leak'])),
]
A = mkart('u26', 26, "Rust,生命周期,'static,thread::spawn,Box::leak,真实验证,动画演示",
    "用真实编译与计数分配器验证 'static:来源(字面量、static、Box::leak);T: 'static 只意味着不含非 'static 的引用(拥有数据的 String 满足、&局部变量不满足 E0597);thread::spawn 的 E0373 与 move/Arc/thread::scope 三种解法;Box::leak 1000 次 alloc 而 dealloc 为 0。",
    "'static 经常被误解成「永远活着」。这篇用真实的编译器行为纠正它:什么样的值满足 'static 约束、thread::spawn 为什么要求它、有哪些绕开办法,以及 Box::leak 得到 &'static 的真实成本。",
    [("T: 'static", '不含非 \'static 引用(String 满足),不是「永远活着」'), ('E0373', 'thread::spawn 的闭包借用局部变量'), ('dealloc +0', '1000 次 Box::leak 之后的释放次数')],
    [("&'static 的来源", None), ("T: 'static 约束", None), ('thread::spawn', '<p>spawn 与线程的更多内容见<a href="rust-thread-spawn-join.html">线程创建与 Join</a>;异步里的 spawn 与 \'static 见<a href="rust-spawn-static.html">spawn 与 \'static</a>。</p>'), ('Box::leak', None)],
    steps, [ENV_U + '。计数分配器在 release 构建下统计', "没有验证:&'static 与 const 提升(rvalue static promotion)、泄漏的内存是否被 Miri 之类工具报告、lazy_static / OnceLock 的实现、'static 与 Send 的关系"], "'static")
