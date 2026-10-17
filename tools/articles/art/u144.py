from lib import *
S = SS('u144')
R = J('u144')
steps = [
    step("默认行为:一个持有 Guard(实现了 Drop)的子进程在 sleep,外部发 SIGTERM,进程立刻被信号 15 终止,Python 看到退出码 -15,输出里只有开头那行,没有「Guard 被 drop」—— 被信号终止时不会运行任何 Drop,栈上的清理代码都没有机会执行。", t=tl(S(1)), mark=lidx(S(1), '退出码 -15'), done=lidx(S(1), '子进程输出'), kv=KV([['默认的 SIGTERM', '进程被终止,退出码 -15'], ['Drop', '不运行']], ['Drop'])),
    step("优雅退出:用 libc 的 sigaction 给 SIGTERM 安装处理函数(返回 0),处理函数里只设置一个原子标志并计数(信号处理函数里能做的事非常有限,按惯例只做原子操作)。主循环每 20 ms 检查标志,收到 SIGTERM 后「处理函数被调用 1 次」,主循环正常退出,Guard 被 drop(清理代码运行),退出码 0。", t=tl(S(2)), done=lidx(S(2), 'installed sigaction', '处理函数被调用 1 次', 'Guard(优雅退出) 被 drop'), mark=lidx(S(2), '退出码 0'), kv=KV([['处理函数', '只设原子标志'], ['主循环', '发现标志后正常返回'], ['结果', 'Drop 运行,退出码 0']], ['结果'])),
    step("标准信号不排队:不阻塞时对自己连续发 100 次 SIGUSR1,处理函数被调用 100 次(每次发送都立即处理);用 pthread_sigmask 阻塞 SIGUSR1 后再发 100 次,解除阻塞前处理函数调用 0 次,解除阻塞后总共只调用 1 次 —— 100 个信号被合并成一个待处理信号。所以信号不能当计数器,只能当「有事发生」的通知。", t=tl(S(3)), done=lidx(S(3), '不阻塞', '阻塞期间发 100 次'), mark=lidx(S(3), '解除阻塞后'), kv=KV([['不阻塞', '100 次 → 调用 100 次'], ['阻塞期间 100 次', '解除后只调用 1 次']], ['阻塞期间 100 次'])),
    step("SIGKILL 不能被捕获:对 SIGKILL 调用 sigaction 返回 -1,errno = 22(EINVAL);对 SIGTERM 返回 0。SIGKILL 与 SIGSTOP 是系统保证能终止/暂停进程的最后手段,不能被忽略或自定义。", t=tl(S(4)), done=lidx(S(4), '对 SIGKILL', 'errno'), kv=KV([['sigaction(SIGKILL)', '-1,errno 22'], ['sigaction(SIGTERM)', '0']], ['sigaction(SIGKILL)'])),
    step("查询当前各信号的处理方式:SIGPIPE 已经是 SIG_IGN(忽略)—— Rust 运行时在 main 之前设好的(前面「二进制启动」一篇里用管道行为验证过);SIGINT、SIGTERM、SIGUSR1 是 SIG_DFL(默认)。程序没有安装处理函数时,Ctrl-C 与 kill 都按默认直接终止。", t=tl(S(5)), done=lidx(S(5), 'SIGPIPE', 'SIGINT', 'SIGTERM', 'SIGUSR1'), kv=KV([['SIGPIPE', 'SIG_IGN'], ['SIGINT / SIGTERM / SIGUSR1', 'SIG_DFL']], ['SIGPIPE'])),
]
A = mkart('u144', 144, 'Rust,信号,SIGTERM,sigaction,真实验证,动画演示',
    '用 libc 的 sigaction 与真实进程验证信号处理:默认 SIGTERM 终止进程且不运行 Drop(退出码 -15);安装处理函数设置原子标志后主循环正常退出,Drop 运行、退出码 0;阻塞期间的 100 个 SIGUSR1 合并成 1 次;SIGKILL 不能被捕获(EINVAL);Rust 运行时已把 SIGPIPE 设为忽略。',
    '服务收到 SIGTERM 时怎么「优雅退出」?为什么 Drop 有时不运行?信号会排队吗?哪些信号不能捕获?这篇用真实的子进程和 libc 的 sigaction 逐条验证。',
    [('-15', '没有处理函数时 SIGTERM 终止进程的退出码(被信号 15 终止)'), ('100 → 1', '阻塞期间发 100 个 SIGUSR1,解除阻塞后处理函数的调用次数'), ('EINVAL', '对 SIGKILL 安装处理函数的错误')],
    [('默认行为', '<p>进程启动与 SIGPIPE 见<a href="rust-binary-startup.html">Rust 二进制启动过程</a>;Drop 见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>。</p>'), ('优雅退出', '<p>signal-hook、ctrlc 等 crate 把这个模式封装成安全接口,本文用的是直接的 libc 调用。</p>'), ('信号会合并', None), ('SIGKILL', None), ('当前的处理方式', '<p>子进程的发送与等待见<a href="rust-subprocess-command.html">子进程与 Command</a>。</p>')],
    steps, [ENV_U + '。macOS(信号编号 SIGUSR1 = 30,Linux 上是 10)', '没有验证:在处理函数里调用 println! 或分配内存的后果(不是 async-signal-safe,按惯例避免)、多线程下信号由哪个线程处理、SA_RESTART 与被中断的系统调用(EINTR)、signal-hook crate 的行为、Windows 的 Ctrl-C 处理'], '信号处理')
