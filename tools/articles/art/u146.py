from lib import *
S = SS('u146')
R = J('u146'); bf = R['buf']; k1, k2 = list(bf.values())
steps = [
    step("程序怎么知道自己连着终端:std::io::IsTerminal。stdout 接管道(| cat)、重定向到文件、stdin 来自 /dev/null,三种情形 stdin/stdout/stderr 都是 false;用 Python 的 pty 给它一个伪终端,三个都变成 true。所以 ls、git 这类程序才能「接终端时彩色、接管道时纯文本」。", t=tl(S(1)), done=lidx(S(1), '接管道', '重定向到文件', '/dev/null'), mark=lidx(S(1), '伪终端'), kv=KV([['管道 / 文件 / /dev/null', 'is_terminal = false'], ['pty', 'is_terminal = true']], ['pty'])),
    step("读 stdin 对来源不敏感:printf \"a\\nb\\nc\\n\" | prog 数到 3 行;prog < 文件(内容 \"x y z\\nlast line no newline\",最后一行没有换行)数到 2 行 —— 最后一个没有换行符的片段也算一行;read_to_string 读到 13 字节 3 个单词;< /dev/null 是 0 行。", t=tl(S(2)), done=lidx(S(2), 'echo 管道', '文件重定向', 'read_to_string', '空输入'), kv=KV([['管道 / 文件', '读法相同'], ['最后一行无换行', '也算一行'], ['空输入', '0 行']], ['最后一行无换行'])),
    step("stdout 与 stderr 是两个独立的流:默认两者都有输出;2>/dev/null 只剩 stdout 的「这行写到 stdout」;1>/dev/null 只剩 stderr 的「这行写到 stderr」;2>&1 | cat 合并后两行都在管道的 stdout 里。", t=tl(S(3)), done=lidx(S(3), '默认', '2>/dev/null', '1>/dev/null', '2>&1'), kv=KV([['2>/dev/null', '只剩 stdout'], ['1>/dev/null', '只剩 stderr'], ['2>&1', '合并成一个流']], ['2>&1'])),
    step("合并到同一个管道时的顺序:println! 与 eprintln! 交替写 3 次,2>&1 | cat 之后看到的顺序是 out0、err0、out1、err1、out2、err2 —— 与代码里的顺序一致。(这里每行都有换行,所以顺序与代码一致;没有换行的 print! 的顺序没有测。)", t=tl(S(4)), done=lidx(S(4), '合并后的行顺序'), kv=KV([['交替写 3 次', 'out0 err0 out1 err1 out2 err2']], ['交替写 3 次'])),
    step(f"stdout 接管道时的缓冲(读者记录每个数据块的到达时刻):print! 之后显式 flush,读者在 0.0 s 就收到「先写半行」,0.6 s 再收到「(换行)\\n」;不 flush、没有换行的 print!,读者要到 0.6 s 换行时才一次收到「没有换行的输出\\n」。结论:没有换行的输出,不 flush 就不会及时出现 —— 进度条之类的输出要手动 flush。", t=tl(S(5)), done=lidx(S(5), 'print! + 显式 flush'), mark=lidx(S(5), 'print! 不 flush'), kv=KV([['print! + flush', '0.0 s 就到达'], ['print! 不 flush、无换行', '到换行(0.6 s)才到达']], ['print! 不 flush、无换行'])),
    step("stdout 出错时:stdout 被关闭(>&-)时 println! 静默忽略,退出码 0,stderr 没有任何输出;但写入真正失败 —— stdout 接到已经关闭的管道(prog | true)—— println! 会 panic:failed printing to stdout: Broken pipe (os error 32)。需要处理时用 writeln!(stdout, …) 并检查 Result。", t=tl(S(6)), mark=lidx(S(6), '| true'), done=lidx(S(6), '>&-'), kv=KV([['stdout 关闭 >&-', '静默忽略'], ['写入失败(Broken pipe)', 'println! panic']], ['写入失败(Broken pipe)'])),
]
A = mkart('u146', 146, 'Rust,标准输入输出,重定向,IsTerminal,真实验证,动画演示',
    '用管道、文件重定向与 pty 验证标准输入输出:IsTerminal 在管道/文件/pty 下的值;stdin 来自管道、文件、空输入的读法;stdout 与 stderr 分开重定向与 2>&1 的顺序;print! 不 flush 无换行时读者要等到换行;stdout 关闭时静默忽略而管道断开时 println! panic(Broken pipe)。',
    '命令行程序最常被忽略的是输入输出的「环境」:是不是终端?stdout 和 stderr 怎么分?缓冲什么时候刷新?stdout 坏了会怎样?这篇用 shell 的重定向和一个伪终端逐项验证。',
    [('4 个值', '管道/文件/ /dev/null / pty 四种环境下 is_terminal 的结果(前三个 false,pty true)'), ('0.0 对 0.6 s', 'print! 有 flush 与无 flush(无换行)时读者收到数据的时刻'), ('Broken pipe', 'println! 写入已关闭的管道时的 panic 信息')],
    [('IsTerminal', '<p>子进程的 stdio 配置见<a href="rust-subprocess-command.html">子进程与 Command</a>;SIGPIPE 的处理见<a href="rust-binary-startup.html">Rust 二进制启动过程</a>。</p>'), ('读 stdin', '<p>缓冲读取见<a href="rust-bufreader.html">BufReader 与缓冲读取</a>。</p>'), ('stdout 与 stderr', None), ('合并的顺序', None), ('缓冲', '<p>写入侧的缓冲见<a href="rust-bufwriter.html">BufWriter 与批量写入</a>。</p>'), ('出错', None)],
    steps, [ENV_U + '。伪终端由 Python 的 pty 模块创建', '没有验证:stdin 是终端时的行编辑与回显、Windows 控制台的 UTF-16 处理、eprintln! 在 stderr 被关闭时的行为、tty 下 stdout 的缓冲(没有对比 isatty 与否的差别)、termios 原始模式'], '标准输入输出')
