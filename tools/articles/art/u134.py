from lib import *
import re
S = SS('u134')
R = J('u134')
lim = re.search(r'软限制 = (\d+)', R['limit']).group(1); fail = re.search(r'第 (\d+) 次 open 失败', R['limit']).group(1); okn = re.search(r'一共成功打开 (\d+) 个', R['limit']).group(1)
steps = [
    step("文件描述符(fd)是 File 里的一个整数,File 被 drop 时才关闭。用 /dev/fd 数进程里打开的 fd:起始 4 个(stdin/stdout/stderr 加上 /dev/fd 目录自己);打开一个文件得到 fd = 3,数量变 5;再开一个 fd = 4,数量 6;drop(f1) 后数量回到 5;再开一个文件拿到 fd = 3 —— 刚释放的编号被复用。", t=tl(S(1)), done=lidx(S(1), '打开 1 个文件', '再打开 1 个', 'drop(f1)', '再开一个'), kv=KV([['打开', 'fd 数 +1'], ['drop', 'fd 数 -1,编号可被复用']], ['drop'])),
    step("作用域结束就自动关闭:块内再开一个文件,数量 7;块结束(自动 drop)之后回到 6。不需要手写 close,这就是「用所有权管理资源」。", t=tl(S(1)), done=lidx(S(1), '块内再开一个', '块结束'), kv=KV([['块内', '7'], ['块结束', '6(自动 drop)']], ['块结束'])),
    step(f"fd 有上限:不 drop 地一直打开同一个文件,第 {fail} 次 open 失败:kind = TooManyOpenFiles,os_error = Some(24),Too many open files (os error 24);一共成功打开 {okn} 个。getrlimit 报告的软限制是 {lim},但实际失败发生在 {fail} 处 —— 内核里还有别的上限,本文没有查明是哪一个。释放 10 个之后再 open 就成功了。", t=tl(S(2)), mark=lidx(S(2), '次 open 失败', 'os_error'), done=lidx(S(2), '释放 10 个'), kv=KV([['成功打开', okn], ['失败', 'TooManyOpenFiles / os error 24'], ['释放 10 个后', '又能 open']], ['失败'])),
    step("泄漏对比:每轮函数结束时 File 被自动 drop,处理 1000 个文件,结束后 fd 数还是 4;而 mem::forget(f) 让 1000 个 fd 全部泄漏,结束后 fd 数是 1004 —— 一个都没有回收。长期运行的服务里泄漏 fd 迟早触发上一步的错误。", t=tl(S(3)), done=lidx(S(3), '每轮函数结束时'), mark=lidx(S(3), 'mem::forget'), b=bars([['自动 drop 后 fd 数', 4, '4'], ['mem::forget 后 fd 数', 1004, '1004']], 1004, cur=[1], done=[0]), kv=KV([['自动 drop', 'fd 数不变(4)'], ['mem::forget ×1000', 'fd 数 1004']], ['mem::forget ×1000'])),
    step("try_clone 得到独立的 fd(类似 dup):原 fd = 3、克隆 fd = 4,数量 2,原 File drop 后克隆仍然可读(\"hello\")。into_raw_fd 消耗 File 但不关闭 fd(fd 仍然打开,数量 2),Rust 不再负责关闭;手动 close 第一次返回 0,第二次返回 -1(EBADF,已经关过了)—— 重复关闭是 fd 管理里的典型 bug,而 Rust 的所有权让 File 与 OwnedFd 不可能 drop 两次。OwnedFd::from_raw_fd 把 fd 重新交给 Rust 管理,drop 后数量回落。", t=tl(S(4)), done=lidx(S(4), 'try_clone', 'into_raw_fd', 'OwnedFd'), mark=lidx(S(4), '手动 close 两次'), kv=KV([['try_clone', '新 fd,可独立关闭'], ['into_raw_fd', '放弃管理,自己 close'], ['close 两次', '0 然后 -1(EBADF)']], ['close 两次'])),
    step("fd 默认不会泄漏到子进程:父进程的 File 持有 fd 3,spawn 一个 sh 子进程检查 /dev/fd/3,子进程里没有这个 fd(not inherited)。避免了子进程意外持有文件、让父进程以为已关闭的文件仍被占用。这里只验证了现象,没有读标准库源码确认机制。", t=tl(S(5)), done=lidx(S(5), 'child has no fd'), kv=KV([['子进程', '看不到父进程的 File fd']], ['子进程'])),
]
A = mkart('u134', 134, 'Rust,文件描述符,资源释放,fd,真实验证,动画演示',
    f'用 /dev/fd 与真实文件验证文件描述符:打开 +1、drop −1、编号被复用;不 drop 地打开到第 {fail} 次出现 Too many open files(os error 24);mem::forget 1000 次让 fd 数从 4 涨到 1004;try_clone / into_raw_fd / OwnedFd 与重复 close 返回 EBADF;子进程不继承 File 的 fd。',
    'Rust 用所有权管理文件描述符:drop 就关闭。这篇用真实的 fd 计数验证每一种情形 —— 正常释放、泄漏、上限、克隆、移交给裸 fd、重复关闭,以及子进程继承。',
    [(f'第 {fail} 次', '不 drop 地打开文件时,open 开始失败(Too many open files)的位置'), ('4 → 1004', 'mem::forget 1000 个 File 后进程的 fd 数'), ('-1(EBADF)', '对同一个 fd 手动 close 第二次的返回值')],
    [('drop 就关闭(含作用域结束的自动释放)', '<p>Drop 的规则见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>;文件读写见<a href="rust-std-fs.html">std::fs 文件读写</a>。</p>'), ('fd 的上限', '<p>上限在不同系统与配置下不同;这里 getrlimit 返回的值与实际失败点不一致,原因没有深究。</p>'), ('泄漏', None), ('克隆与移交', '<p>裸指针的类似 into_raw / from_raw 见<a href="rust-raw-pointer-deref.html">原始指针解引用</a>。</p>'), ('子进程', '<p>子进程见<a href="rust-subprocess-command.html">子进程与 Command</a>。</p>')],
    steps, [ENV_U + '。/dev/fd 统计方式在 macOS 上适用', '没有验证:Linux 上 /proc/self/fd 的统计、fd 上限的具体来源(getrlimit 与实际不一致)、把 fd 传给子进程(Stdio::from)、socket fd 的 SO_LINGER、重复 close 在多线程下误关别人 fd 的后果、O_CLOEXEC 的实现细节'], '文件描述符与资源释放')
