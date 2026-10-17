from lib import *
S = SS('c87')
steps = [
    step("镜像:debian:12-slim 加 apt-get install systemd procps(首次从网络安装花了约 10 分钟,这次构建命中缓存只要 1 秒),CMD 是 /lib/systemd/systemd,STOPSIGNAL SIGRTMIN+3。各种启动选项的结果(cgroup v2):什么都不加 → 退出码 255,控制台 Failed to mount API filesystems,Exiting PID 1;只加 --tmpfs /run --tmpfs /tmp → 255,同样的错误;再加 --tmpfs /run/lock → 255,错误变成 Failed to allocate manager object;--cap-add SYS_ADMIN、再加 seccomp=unconfined、再加三个 tmpfs → 都是 255,Failed to allocate manager object;只有 --privileged 启动成功:Status=running,systemctl is-system-running = running。", t=tl(S(1)), done=lidx(S(1), '--privileged:running'), mark=lidx(S(1), '默认(什么选项都不加)', '--tmpfs /run --tmpfs /tmp', '--cap-add SYS_ADMIN:'), b=bars([['能启动的配置数', 1, '1'], ['试过的配置数', 7, '7']], 7, done=[0]), kv=KV([['默认', '255:挂载 /run 的 tmpfs 失败'], ['--tmpfs + --cap-add SYS_ADMIN', '255:Failed to allocate manager object'], ['--privileged', '启动成功']], ['--privileged'])),
    step("能启动的 --privileged 容器里:PID 1 是 systemd;systemctl is-system-running = running;运行中的服务有 console-getty、getty@tty1 到 tty6、systemd-journald;进程里有 systemd、systemd-journald 和 7 个 agetty;docker top 看到 9 个进程。普通的应用容器通常只有一两个进程。", t=tl(S(2)), done=lidx(S(2), 'PID 1 的名字', 'systemctl is-system-running'), mark=lidx(S(2), '运行中的服务', 'docker top'), kv=KV([['PID 1', 'systemd'], ['服务', 'journald + 一组 getty'], ['进程数', 'docker top 看到 9 个']], ['进程数'])),
    step("怎么停:镜像里设了 STOPSIGNAL SIGRTMIN+3,docker stop -t 10 只用 0.2 秒,ExitCode=130(没有深究为什么是 130);改成 --stop-signal SIGTERM,docker stop 等满 10.2 秒,ExitCode=137——systemd 当 PID 1 时 SIGTERM 不会让它关机,只能等超时后被 SIGKILL。", t=tl(S(3)), done=lidx(S(3), '镜像里 STOPSIGNAL'), mark=lidx(S(3), '--stop-signal SIGTERM'), b=bars([['SIGRTMIN+3:docker stop (秒)', 0.2, '0.2'], ['SIGTERM:docker stop (秒)', 10.2, '10.2']], 10.2, done=[0], mark=[1]), kv=KV([['SIGRTMIN+3', '0.2 秒,ExitCode 130'], ['SIGTERM', '等满 10.2 秒,137']], ['SIGRTMIN+3'])),
    step("开销:从 docker run 到 systemctl is-system-running 返回 running 用了 0.5 秒;docker stats 的 MemUsage 是 15.25MiB,PIDs = 9。", t=tl(S(4)), done=lidx(S(4), '0.5 秒', 'docker stats'), kv=KV([['启动', '0.5 秒到 running'], ['内存', '15.25MiB(空闲)'], ['进程', '9 个']], ['内存'])),
]
A = mkartc('c87', 87, 'Docker,systemd,init系统,特权容器,STOPSIGNAL,真实验证,动画演示',
    '在 Docker Engine 29.8.2(cgroup v2)里实测让 systemd 当 PID 1:什么都不加、只加 tmpfs、加 --cap-add SYS_ADMIN 与 seccomp=unconfined 都以 255 退出,只有 --privileged 能启动(0.5 秒到 running,空闲 15.25MiB、9 个进程);STOPSIGNAL SIGRTMIN+3 下 docker stop 0.2 秒,SIGTERM 下等满 10.2 秒后 137。',
    '能不能在容器里跑完整的 systemd?它需要什么条件、启动后有多重、怎么停?这篇用 debian:12-slim 装上 systemd,逐种选项试能不能启动,并量停止信号的差别。',
    [('只有 1 种能启动', '试过的 7 种选项配置里,只有 --privileged 能让 systemd 在容器里跑起来'), ('255', '没有足够权限时 systemd 当 PID 1 的退出码'), ('0.2 秒 对 10.2 秒', 'SIGRTMIN+3 与 SIGTERM 下 docker stop 的用时')],
    [('条件', '<p>systemd 当 PID 1 要挂载 /run、/run/lock 等 tmpfs、管理 cgroup。非特权容器里这些操作被拒绝,结果是 255 退出;我试的 --cap-add SYS_ADMIN 加 seccomp=unconfined 加 tmpfs 都还是 <code>Failed to allocate manager object</code>。另一种常被提到的做法是让 cgroup 以可写方式挂入(<code>-v /sys/fs/cgroup:/sys/fs/cgroup:rw --cgroupns=host</code>);我最初探索时带这些选项的 docker run 没有成功创建出容器(原因没有看),所以没有纳入最终的矩阵,不能下结论。</p>'),
     ('跑起来之后', '<p>systemd 容器像一台小机器:journald、getty 一组服务,9 个进程。这和「一个容器一个进程」的惯例相反,通常只在需要测试 systemd 服务单元的场景里用。</p>'),
     ('怎么停', '<p>systemd 通过 SIGRTMIN+3 关机(这也是 jrei/systemd-debian 这类镜像设 STOPSIGNAL 的原因),SIGTERM 对它无效,docker stop 就会等满宽限期再 SIGKILL。</p>'),
     ('开销', '<p>空闲时 15.25MiB、0.5 秒到 running。服务多了会更重,没有测。</p>')],
    steps,
    [ENV_C + '。镜像在本机构建(debian:12-slim 经 dpull.py 下载,apt-get 通过容器网络安装 systemd、procps);所有启动选项各试一次,用 -t 让 systemd 的控制台输出进 docker logs;is-system-running 由 docker exec 查询;实验后已删除容器和镜像',
     '没有验证:cgroup 可写挂载方式(--cgroupns=host + 可写 /sys/fs/cgroup)是否让非特权容器启动(在 -t 的最终矩阵里没有包含)、systemd 的 user 实例、在 systemd 里运行真实服务、cgroup v1 的情形、Podman 的 systemd 支持、journald 日志与 docker logs 的关系'],
    '容器里的 systemd')
