from lib import *
S = SS('c79')
steps = [
    step("为了不影响 Docker Desktop 真正的守护进程,实验在一个特权的 docker:dind 容器里单独起一个嵌套的 dockerd 29.9.0(存储驱动 vfs),反复停止、重启它。默认(没有 live-restore,docker info 的 LiveRestoreEnabled = false):容器 tc 的主进程在嵌套环境里是 PID 695;给 dockerd 发 SIGTERM,等它退出用了 10.3 秒(容器里是 sleep 作为 PID 1,不处理 SIGTERM,要等满默认的 10 秒宽限期后被杀),此时容器的主进程已不在;重新启动 dockerd 后容器 Status=exited、Pid=0、ExitCode=137,docker ps 里没有运行的容器。", t=tl(S(1)), done=lidx(S(1), '给 dockerd 发 SIGTERM', '重新启动 dockerd 后'), mark=lidx(S(1), 'LiveRestoreEnabled = false'), kv=KV([['停 dockerd', '先停掉所有容器,等了 10.3 秒'], ['重启后的容器', 'exited,ExitCode 137']], ['停 dockerd'])),
    step("--live-restore(LiveRestoreEnabled = true):容器主进程 PID 1824。给 dockerd 发 SIGTERM,只用了 0.1 秒就退出了,容器的主进程 1824 还活着;重新启动 dockerd 后容器 Status=running、Pid=1824、ExitCode=0,StartedAt 与重启前相同,docker ps 里的 tc 是 Up——守护进程重启,容器没有被打断。", t=tl(S(2)), done=lidx(S(2), '给 dockerd 发 SIGTERM', '重新启动 dockerd 后'), mark=lidx(S(2), 'LiveRestoreEnabled = true'), b=bars([['无 live-restore:停 dockerd (秒)', 10.3, '10.3'], ['live-restore:停 dockerd (秒)', 0.1, '0.1']], 10.3, done=[1], mark=[0]), kv=KV([['--live-restore 停 dockerd', '0.1 秒退出,容器继续跑'], ['重启后', '同一个 PID、同一个 StartedAt']], ['--live-restore 停 dockerd'])),
    step("模拟崩溃:--live-restore 下给 dockerd 发 SIGKILL(kill -9),容器的主进程 2621 还活着;清掉遗留的 pid 文件后重新启动 dockerd,容器 Status=running、Pid=2621、StartedAt 相同,docker ps 里仍是 Up。", t=tl(S(3)), done=lidx(S(3), 'SIGKILL', '重新启动 dockerd 后'), kv=KV([['kill -9 dockerd', '容器进程仍在运行'], ['重新启动后', '重新接管,同一个 PID']], ['kill -9 dockerd'])),
    step("live-restore 的限制:dockerd 停着的时候,容器的 sleep 进程仍在运行(pgrep 找到 PID),但 docker ps 报 failed to connect to the docker API,退出码 1——你管不了这些容器,也看不到它们的状态。重新启动 dockerd 后 docker logs tc 能读到停机前输出的 tick。Docker Desktop 自己的 daemon.json 里没有 live-restore(0 处),也就是默认关闭。", t=tl(S(4)), done=lidx(S(4), '重启后 docker logs tc'), mark=lidx(S(4), 'dockerd 停着时', 'daemon.json 里有 live-restore'), kv=KV([['dockerd 停着', '容器在跑,但 docker 命令全部失败'], ['重启后', '日志仍可读'], ['Docker Desktop', 'daemon.json 里没有 live-restore']], ['dockerd 停着'])),
]
A = mkartc('c79', 79, 'Docker,live-restore,dockerd重启,容器存活,docker-in-docker,真实验证,动画演示',
    '在一个嵌套的 dockerd 里实测 live-restore:默认停 dockerd 要先停掉所有容器(10.3 秒),重启后容器 exited(137);--live-restore 下停 dockerd 只要 0.1 秒,容器主进程继续运行,重启后同一个 PID、同一个 StartedAt 被重新接管;kill -9 dockerd 同样不影响;dockerd 停着时 docker 命令全部失败。Docker Desktop 默认没有开启。',
    '重启 Docker 守护进程会不会把所有容器带走?live-restore 能不能让容器活下来?为了不动真实的 Docker Desktop,这篇在一个嵌套的 dockerd 里反复停止和重启,对比默认与 live-restore 的表现。',
    [('exited 137 对 running', '重启 dockerd 之后,默认与 --live-restore 下容器的状态'), ('10.3 秒 对 0.1 秒', '给 dockerd 发 SIGTERM 到它退出,默认与 --live-restore 的用时'), ('同一个 PID', 'live-restore 重启后,容器主进程的 PID 和 StartedAt 都没变')],
    [('默认', '<p>停止 dockerd 会先把所有容器停掉(SIGTERM,等宽限期后再 SIGKILL);这个嵌套的 dockerd 没有 Docker Desktop 的 3 秒默认值,所以等了 10 秒。重启后容器是 exited,退出码 137。</p>'),
     ('live-restore', '<p>开启 <code>--live-restore</code>(或 daemon.json 里的 <code>"live-restore": true</code>)后,停 dockerd 不再停容器;dockerd 重新启动时重新接管它们,PID 和 StartedAt 都没变。</p>'),
     ('崩溃', '<p>kill -9 dockerd 也一样。我清除了遗留的 pid 文件才重启(没有清理时会不会失败,我没有测)。</p>'),
     ('限制', '<p>dockerd 停着的时候容器还在跑,但你什么 docker 命令都用不了,也无法修改容器的配置。据我所知 live-restore 与 Swarm 模式不兼容,但这一点我没有查文档也没有验证。在真正的 Docker Desktop 上我没有重启守护进程,因为会中断其它正在运行的容器。</p>')],
    steps,
    [ENV_C + '。实验在 docker:dind 镜像(Docker 29.9.0)的特权容器里单独起的 dockerd 上完成,存储驱动 vfs,里面只有一个 alpine:3.20 镜像和一个 sleep 600 容器;没有重启 Docker Desktop 的守护进程;停止是否完成用 ps 判断 dockerd 进程是否消失;实验后已删除嵌套环境',
     '没有验证:Docker Desktop 的守护进程开启 live-restore(需要改配置并重启,会中断其它容器)、live-restore 与网络(端口映射、userland-proxy)的关系、重启期间容器输出日志的去向、dockerd 版本升级时的 live-restore、kill -9 后不清理 pid 文件会怎样'],
    'live-restore')
