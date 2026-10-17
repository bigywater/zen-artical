from lib import *
S = SS('c84')
steps = [
    step("用同一个会打印信号、收到 SIGTERM 后清理 0.5 秒再退出的 Python 应用,换四种入口脚本,docker stop -t 5:A(sh 脚本里直接 python,不 exec)用时 5.2 秒、ExitCode=137,日志里应用从没收到信号(应用是 PID 7,sh 是 PID 1);B(exec python)0.7 秒、ExitCode=0,应用是 PID 1,收到 SIGTERM 并完成清理;C1(trap 转发 TERM,但只 wait 一次)0.1 秒、ExitCode=143,应用收到 SIGTERM 却没来得及打印“清理完成”——第一次 wait 被信号打断后立刻返回 143,脚本就退出了;C2(被打断后再 wait 一次)0.6 秒、ExitCode=0,应用收到信号、清理完成,脚本打印“python 退出码 0”。", t=tl(S(1)), done=lidx(S(1), 'B exec python', 'C2 trap'), mark=lidx(S(1), 'A 不用 exec', 'C1 trap'), b=bars([['A 不 exec (秒)', 5.2, '5.2'], ['B exec (秒)', 0.7, '0.7'], ['C1 只 wait 一次 (秒)', 0.1, '0.1'], ['C2 再 wait 一次 (秒)', 0.6, '0.6']], 5.2, done=[1, 3], mark=[0, 2]), kv=KV([['A 不 exec', '应用收不到信号,等满 5 秒后 137'], ['B exec', '应用是 PID 1,优雅退出'], ['C1 trap,只 wait 一次', '脚本提前退出 143,应用来不及清理'], ['C2 再 wait 一次', '转发成功,优雅退出']], ['C1 trap,只 wait 一次'])),
    step("加 --init 的效果:A + --init(sh 脚本不 exec)docker stop -t 5 只用 0.1 秒、ExitCode=143,但日志里应用没有“收到信号”——tini 把 TERM 转给 sh,sh 立刻被杀,python 是被连带终止的,没有机会清理;B + --init(exec python)0.6 秒、ExitCode=0,应用收到信号并清理完成。--init 解决不了入口脚本不转发信号的问题。", t=tl(S(2)), done=lidx(S(2), 'B + --init'), mark=lidx(S(2), 'A + --init'), kv=KV([['脚本不 exec + --init', '快速结束,但应用没机会清理 (143)'], ['exec + --init', '应用收到信号,优雅退出']], ['脚本不 exec + --init'])),
    step("docker kill -s HUP(比如通知应用重新加载配置):A(不 exec)日志里只有启动信息,应用没收到 HUP;B(exec python)日志出现“收到信号 SIGHUP”,容器仍在运行;C2(只转发 TERM / INT 的 trap)应用也没收到 HUP。入口脚本要转发哪些信号,得自己明确列出来。", t=tl(S(3)), done=lidx(S(3), 'B exec python,发 HUP'), mark=lidx(S(3), 'A 不用 exec,发 HUP', 'C2 trap'), kv=KV([['不 exec', 'HUP 到不了应用'], ['exec', 'HUP 直达应用,容器继续运行'], ['trap 只列 TERM INT', 'HUP 没被转发']], ['exec'])),
]
A = mkartc('c84', 84, 'Docker,信号转发,entrypoint,exec,trap,docker stop,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测入口脚本的信号转发:sh 里直接 python(不 exec)时应用收不到 SIGTERM,docker stop -t 5 等满 5.2 秒后 137;exec python 0.7 秒优雅退出;trap 转发时只 wait 一次会让脚本在应用清理完之前退出(143),被打断后再 wait 一次才正确;--init 不能替脚本转发;HUP 等其它信号要自己转发。',
    '入口脚本里到底该写 exec 还是 trap?为什么 docker stop 总要等满超时?这篇用同一个会打印信号的 Python 应用,对比不 exec、exec、两种 trap 写法和 --init,并看 HUP 这类非 TERM 信号怎么到达应用。',
    [('5.2 秒 / 137', '入口脚本不 exec 时 docker stop -t 5 的用时和退出码'), ('只 wait 一次 = 143', 'trap 转发信号后,脚本因第一次 wait 被信号打断而提前退出'), ('HUP 到不了', '只转发 TERM / INT 的 trap 脚本,收不到 docker kill -s HUP')],
    [('exec 与 trap', '<p>入口脚本最后一行写 <code>exec 应用</code>,应用取代 sh 成为 PID 1,收到 SIGTERM 直接处理;前提是应用自己处理信号(PID 1 没有默认动作,见 c6)。要保留脚本时用 trap 转发:但 <code>wait</code> 被信号打断时立刻返回 128+信号编号,必须再 <code>wait</code> 一次才能拿到子进程的真正退出码并等它清理完;只写一次 wait 的脚本会比应用先退出,应用被容器终止时直接杀掉(C1)。</p>'),
     ('--init', '<p>--init 让 tini 当 PID 1,它把信号转给它的子进程(这里是 sh);sh 没装 trap,TERM 的默认动作就是退出,孙子进程 python 没有机会清理。--init 的价值在收尸和 PID 1 的特殊信号语义(c31、c32),不能代替入口脚本去转发。</p>'),
     ('其它信号', '<p>热加载常用的 HUP:exec 形式直达;trap 脚本要把 HUP 也写进 trap 列表才会转发。</p>')],
    steps,
    [ENV_C + '。应用是 python:3.12-alpine 里的小脚本(收到 TERM / INT 后睡 0.5 秒再退出,收到 HUP 只打印);入口脚本通过 --entrypoint 切换;docker stop 的用时用 Python time.time 测;每种情形运行一次;实验后已删除容器和镜像',
     '没有验证:dumb-init、s6 等其它 init 的转发行为、进程组信号(kill -- -PGID)、docker compose 的 stop_signal、应用是 Go / Java 时的信号处理差别、trap 脚本里多个子进程的处理'],
    '信号转发')
