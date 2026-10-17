from lib import *
S = SS('c30')
steps = [
    step("PID 1 是 python 并安装了 SIGTERM/SIGINT/SIGQUIT/SIGHUP/SIGUSR1 的处理程序(打印收到的信号名,可选地睡几秒再退出)。默认 docker stop:日志是“启动,PID 1 | 收到信号 SIGTERM | 清理完成,退出”,用时 147 ms,ExitCode=0——docker stop 默认发的是 SIGTERM。", t=tl(S(1)), done=lidx(S(1), '默认:docker stop'), kv=KV([['docker stop 默认信号', 'SIGTERM'], ['用时 / 退出码', '147 ms / 0']], ['docker stop 默认信号'])),
    step("换信号有两处:docker run --stop-signal SIGINT → 日志里收到 SIGINT;Dockerfile 里写 STOPSIGNAL SIGQUIT → 收到 SIGQUIT,镜像里记录的 StopSignal 是 SIGQUIT;Dockerfile 是 SIGQUIT 而运行时 --stop-signal SIGUSR1 → 收到 SIGUSR1,运行时的设置覆盖 Dockerfile。四种情况 ExitCode 都是 0,用时约 100~150 ms。", t=tl(S(2)), done=lidx(S(2), 'STOPSIGNAL SIGQUIT:', 'docker run --stop-signal SIGINT'), mark=lidx(S(2), '运行时覆盖为 SIGUSR1', '镜像里记录的 StopSignal'), kv=KV([['--stop-signal SIGINT', '收到 SIGINT'], ['STOPSIGNAL SIGQUIT', '收到 SIGQUIT'], ['两者都有', '运行时的优先(SIGUSR1)']], ['两者都有'])),
    step("清理需要 3 秒的程序:docker stop -t 5 → 用时 3112 ms,ExitCode=0,日志有“清理完成,退出”;docker stop -t 1 → 用时 1131 ms,ExitCode=137,日志停在“收到信号 SIGTERM”,清理没做完就被 SIGKILL 了。宽限期要比清理时间长。", t=tl(S(3)), done=lidx(S(3), '-t 5'), mark=lidx(S(3), '-t 1'), b=bars([['-t 5:docker stop 用时 (ms)', 3112, '3112'], ['-t 1:docker stop 用时 (ms)', 1131, '1131']], 3112, done=[0], mark=[1]), kv=KV([['-t 5(清理 3 秒)', '3112 ms,ExitCode 0'], ['-t 1(清理 3 秒)', '1131 ms,ExitCode 137,清理被打断']], ['-t 1(清理 3 秒)'])),
    step("不带 -t 的 docker stop 等多久?这个 Docker Desktop 的守护进程配置(虚拟机里的 /run/config/docker/daemon.json)里有 \"default-stop-timeout\": 3,容器的 Config.StopTimeout 是空,所以清理要 15 秒的程序,docker stop 用了 3149 ms,ExitCode=137——这里的默认宽限期是 3 秒,不是常说的 10 秒。docker run --stop-timeout 2:Config.StopTimeout = 2,docker stop 用时 2123 ms;--stop-timeout 2 再加 docker stop -t 4 → 4188 ms,命令行参数优先。", t=tl(S(4)), done=lidx(S(4), 'default-stop-timeout', '--stop-timeout 2 的 Config.StopTimeout'), mark=lidx(S(4), 'docker stop(不带 -t):用时 3149', '再加 docker stop -t 4'), b=bars([['不带 -t (ms)', 3149, '3149'], ['--stop-timeout 2 (ms)', 2123, '2123'], ['--stop-timeout 2 + -t 4 (ms)', 4188, '4188']], 4188, done=[1], mark=[0, 2]), kv=KV([['守护进程默认', 'default-stop-timeout: 3(本机)'], ['--stop-timeout 2', '2 秒'], ['docker stop -t N', '覆盖前两者']], ['守护进程默认'])),
]
A = mkartc('c30', 30, 'Docker,STOPSIGNAL,stop-signal,stop-timeout,docker stop,优雅退出,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测停止信号与宽限期:docker stop 默认发 SIGTERM,--stop-signal 和 Dockerfile 的 STOPSIGNAL 可以换信号且运行时优先;清理要 3 秒的程序 -t 5 能干净退出(0)、-t 1 被打断(137);这台 Docker Desktop 的守护进程默认宽限期是 3 秒(default-stop-timeout),--stop-timeout 与 docker stop -t 依次覆盖它。',
    'docker stop 到底发什么信号、等多久?怎么让优雅退出的程序收到它认识的信号?这篇用一个会打印信号名、可以模拟清理耗时的 Python 程序实测,并发现这台 Docker Desktop 的默认宽限期并不是 10 秒。',
    [('3 秒', '这台 Docker Desktop 的守护进程默认宽限期(default-stop-timeout),不带 -t 的 docker stop 最长等这么久'), ('SIGQUIT / SIGUSR1', 'Dockerfile 的 STOPSIGNAL 与运行时 --stop-signal,后者覆盖前者'), ('3112 ms / 0 vs 1131 ms / 137', '清理要 3 秒时 -t 5 与 -t 1 的结果')],
    [('默认信号', '<p>docker stop 默认发 SIGTERM,装了处理程序的 PID 1 能收到并干净退出(ExitCode 0)。没装处理程序的 PID 1 收不到,见 c6。</p>'),
     ('改信号', '<p>在 Dockerfile 里用 <code>STOPSIGNAL</code>,或运行时用 <code>--stop-signal</code>;两者同时存在时运行时的优先。需要某个信号才能优雅关闭的程序(比如 nginx 的 SIGQUIT)就要设。我这里用的是自己写的小程序,没有测真实的 nginx。</p>'),
     ('宽限期要够长', '<p>清理要 3 秒的程序,宽限期 5 秒能干净退出,宽限期 1 秒则被 SIGKILL 打断(ExitCode 137,清理没做完)。</p>'),
     ('默认宽限期', '<p>常说 docker stop 默认等 10 秒,但这台 Docker Desktop 的守护进程配置里 <code>"default-stop-timeout": 3</code>,不带 <code>-t</code> 就是 3 秒(实测 3149 ms 后被杀,ExitCode 137)。优先级依次是 <code>docker stop -t</code>、<code>--stop-timeout</code>、守护进程的默认值;没有这个配置时的默认值是多少,我没有测。</p>')],
    steps,
    [ENV_C + '。测试程序是 python:3.12-alpine 里的小脚本(PID 1,python -u,信号处理程序里 sleep WORK 秒再退出);用时用 Python time.time 测 docker stop 命令;守护进程配置是在虚拟机里只读查看 /run/config/docker/daemon.json(没有修改);实验后已删除容器和镜像',
     '没有验证:真实服务(nginx、postgres 等)的停止信号、Docker Desktop 以外的 Linux 宿主机默认宽限期、docker compose stop 的宽限期、Kubernetes 的 terminationGracePeriodSeconds、Windows 容器'],
    '停止信号与宽限期')
