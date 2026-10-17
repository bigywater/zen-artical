from lib import *
S = SS('g83')
steps = [
    step("不 Wait 会留下僵尸进程:Start 之后不调用 Wait,子进程已经退出 200 ms,ps 显示 pid 54033 的状态是 Z、命令名 <defunct>;调用 cmd.Wait() 之后,进程表里已经没有这个 pid。", t=tl(S(1)), mark=lidx(S(1), 'Z    <defunct>'), done=lidx(S(1), '进程表里已经没有'), kv=KV([['不 Wait', 'ps 状态 Z(<defunct>)'], ['Wait 之后', '进程表项被回收']], ['不 Wait'])),
    step("StdoutPipe 必须在 Wait 之前读完:先 Wait 再读 StdoutPipe,读到 \"\",err = read |0: file already closed;先读完 StdoutPipe 再 Wait,读到 \"hello\\nworld\\n\",读 err 和 Wait err 都是 nil。", t=tl(S(2)), mark=lidx(S(2), '先 Wait 再读'), done=lidx(S(2), '先读完 StdoutPipe 再 Wait'), kv=KV([['先 Wait', '管道已被关,读到空,file already closed'], ['先读完再 Wait', '正常']], ['先 Wait'])),
    step("管道写满了没人读:子进程写 200000 字节,父进程不读管道,1.5 秒后 Wait 仍然没有返回(ps 看到子进程 head 还在,状态 S 即睡眠)。", t=tl(S(3)), mark=lidx(S(3), '1.5 秒后 Wait 仍然没有返回'), kv=KV([['子进程输出', '200000 字节,超过管道缓冲'], ['父进程', '不读,Wait 一直等'], ['结果', '互相等待']], ['结果'])),
    step("孙进程抱着管道:sh 立刻退出,但留下一个后台 sleep 1 抱着 stdout,cmd.Output() 用了 1009 ms 才返回,输出 \"hi\\n\"。同样的命令设 cmd.WaitDelay = 200 ms:206 ms 返回,输出 \"hi\\n\",err = exec: WaitDelay expired before I/O complete(errors.Is(err, exec.ErrWaitDelay) 为 true)。", t=tl(S(4)), mark=lidx(S(4), 'cmd.Output() 用了 1009 ms'), done=lidx(S(4), 'WaitDelay = 200 ms'), b=bars([['不设 WaitDelay:返回用时 (ms)', 1009, '1009'], ['WaitDelay = 200ms', 206, '206']], 1009, mark=[0], done=[1]), kv=KV([['默认', '等孙进程关掉管道:1009 ms'], ['WaitDelay = 200ms', '206 ms 返回,err = ErrWaitDelay']], ['WaitDelay = 200ms'])),
    step("CommandContext 只杀直接的子进程:超时 200 ms,sh -c 'sleep 2; echo done':2017 ms 后返回,输出 \"\",err = signal: killed;sh -c 'sleep 2 & wait':2015 ms 后返回,err 同样是 signal: killed。sh 在 200 ms 时被杀了,但孙进程 sleep 还抱着 stdout,Output 一直等到约 2 秒。", t=tl(S(5)), mark=lidx(S(5), 'sleep 2; echo done', 'sleep 2 & wait'), b=bars([['设定超时 (ms)', 200, '200'], ['实际返回(第一种)', 2017, '2017'], ['实际返回(第二种)', 2015, '2015']], 2017, done=[0], mark=[1, 2]), kv=KV([['超时', '200 ms'], ['实际返回', '约 2 秒'], ['原因', '孙进程仍抱着管道,需要 WaitDelay / 杀进程组']], ['原因'])),
    step("启动一个进程要多久:exec.Command(\"/usr/bin/true\").Run() 50 次:最小 1.5 ms / 中位 2.1 ms / 最大 5.8 ms。", t=tl(S(6)), mark=lidx(S(6), 'exec.Command'), b=bars([['最小 (ms)', 1.5, '1.5'], ['中位', 2.1, '2.1'], ['最大', 5.8, '5.8']], 5.8, done=[0, 1, 2]), kv=KV([['中位', '2.1 ms'], ['含义', '启动子进程的代价是毫秒级,不要放在热路径里']], ['含义'])),
    step("文档:StdoutPipe 会在 Wait 看到命令退出后关闭管道,所以在读完之前调用 Wait 是错误的;同样的原因,使用 StdoutPipe 时调用 Cmd.Run 也是错的。WaitDelay 非零时,限制 Wait 里两种意外延迟的时间:Context 取消后子进程不退出,以及子进程退出但留下没关的 I/O 管道;WaitDelay 为零(默认)时,I/O 管道会一直读到 EOF,这可能要等到被遗弃的子进程也关闭它们的描述符。", t=tl(S(7)), done=lidx(S(7), 'StdoutPipe returns a pipe', 'If WaitDelay is non-zero'), mark=lidx(S(7), 'If WaitDelay is zero'), kv=KV([['StdoutPipe', 'Wait 之前必须读完'], ['WaitDelay 非零', '限制两类意外延迟'], ['WaitDelay 为零', '等到所有持有管道的进程都关掉']], ['WaitDelay 非零'])),
]
A = mkartg('g83', 83, 'Go,os/exec,僵尸进程,WaitDelay,管道,真实验证,动画演示',
    '在 Go 1.27.1(macOS)里实测 os/exec 的陷阱:不 Wait 会留下状态 Z 的僵尸进程;先 Wait 再读 StdoutPipe 报 file already closed;管道写满且没人读时 Wait 一直不返回;孙进程抱着 stdout 会让 Output 多等约 1 秒,设 WaitDelay 200 ms 后 206 ms 返回(ErrWaitDelay);CommandContext 的 200 ms 超时只杀直接子进程,实际约 2 秒后才返回;启动一个进程约 2.1 ms。',
    '用 os/exec 调外部命令,最容易出问题的不是启动,而是收尾:不 Wait 会留下僵尸进程,管道没读完就 Wait 会丢数据或卡死,子进程的子进程会让 Output 迟迟不返回,Context 超时也杀不干净。这篇把这些情形一个个跑出来,并验证 WaitDelay 能不能兜底。',
    [('Z', '不调用 Wait 时,已退出的子进程在 ps 里的状态'), ('1009 → 206 ms', '孙进程抱着 stdout 时,cmd.Output() 不设与设 WaitDelay = 200 ms 的返回用时'), ('200 ms → 约 2 秒', 'CommandContext 设了 200 ms 超时,实际返回的时间(孙进程仍抱着管道)')],
    [('僵尸进程', '<p>子进程退出后,内核保留它的退出状态,等父进程来取。不调用 <code>Wait</code>,<code>ps</code> 里就是状态 <code>Z</code>(&lt;defunct&gt;);调用后进程表项消失。长期运行的服务里反复 <code>Start</code> 而不 <code>Wait</code>,僵尸会越积越多。</p>'),
     ('StdoutPipe 的顺序', '<p>文档写明:<code>Wait</code> 会在看到命令退出后关闭管道,所以必须先读完再 <code>Wait</code>。先 <code>Wait</code> 的实验读到空和 “file already closed”;使用 <code>StdoutPipe</code> 时也不能调用 <code>Run</code>。</p>'),
     ('管道写满', '<p>管道有缓冲上限,子进程写 200000 字节而父进程不读,子进程阻塞,<code>Wait</code> 也就一直不返回。要么及时读,要么把输出交给 <code>cmd.Stdout</code>(由 os/exec 起 goroutine 去读)。</p>'),
     ('孙进程抱着管道', '<p><code>sh</code> 已经退出,但它留下的后台 <code>sleep 1</code> 还持有 stdout 的写端,<code>Output</code> 要等到 EOF 才返回(1009 ms)。给 <code>cmd.WaitDelay</code> 设 200 ms 后 206 ms 返回,同时返回 <code>ErrWaitDelay</code>(输出仍是 hi)。</p>'),
     ('CommandContext 杀不干净', '<p>200 ms 超时到了,<code>CommandContext</code> 只给直接的子进程(这里是 sh)发 Kill,sh 的孙进程 <code>sleep 2</code> 仍然活着、抱着管道,所以 <code>Output</code> 一直等到约 2 秒(2017 ms)才返回,错误是 signal: killed。配合 <code>WaitDelay</code>,或者让子进程自成进程组再整体杀掉,才能真正按超时返回(进程组的做法本文没有实验)。</p>'),
     ('成本', '<p>启动并等待一个什么都不做的进程,中位数 2.1 ms。批量调用外部命令时,这个固定成本要算进去。</p>'),
     ('文档', '<p>文档对 <code>WaitDelay</code> 的描述和实验吻合:默认零值会一直读到所有持有管道的进程关闭它们的描述符。</p>')],
    steps,
    [ENV_G + '。僵尸状态用 ps -o pid=,stat=,comm= 观察;孙进程场景用 sh -c 启动后台 sleep;计时用 time.Since;启动成本 50 次;读过的文档:go doc os/exec.Cmd.StdoutPipe / Cmd 的 WaitDelay 注释',
     '没有验证:Linux 上的行为差异、进程组(Setpgid)杀整组的写法、Cmd.Cancel 自定义、僵尸进程在容器 PID 1 下的收养问题、stderr 管道的同类问题、Windows 行为'],
    'os/exec')
