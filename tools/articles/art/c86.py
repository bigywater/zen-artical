from lib import *
S = SS('c86')
steps = [
    step("Docker-in-Docker:在一个 --privileged 的 docker:dind 容器里直接起 dockerd(不指定存储驱动),0.3 秒就绪,版本 29.9.0,存储驱动 overlayfs,cgroup v2,containers=0、images=0。外层 Docker 有 8 个容器,嵌套的 docker ps 看到 0 个——看不到外层任何东西。嵌套的镜像库一开始是空的,需要 load/pull(load 之后有 alpine:3.20)。在嵌套里运行一个容器 inner1,外层 docker ps 看不到它;它的主进程在 dind 容器的进程列表里(PID 390,sleep 120)。", t=tl(S(1)), done=lidx(S(1), '0.3 秒后就绪', '外层 docker ps 能看到 inner1'), mark=lidx(S(1), '嵌套的 docker ps 看到的容器数', '嵌套的镜像库'), kv=KV([['嵌套 dockerd', '自己的镜像库、自己的容器,0.3 秒就绪'], ['看不到外层', '外层 8 个容器,里面 0 个'], ['inner1', '只存在于嵌套 dockerd 里']], ['看不到外层'])),
    step("Docker-outside-of-Docker:不加 --privileged,把 /var/run/docker.sock 挂进去(退出码 0)。容器里的 docker ps -q 看到 9 个容器,外层 docker ps -q 也是 9 个——同一个 dockerd,能看到所有容器(含 Docker Desktop 里别的项目的);docker info 的 Name = docker-desktop、29.8.2、overlayfs。在容器里 docker run 一个 sibling86,外层 docker ps 能看到它——是外层 dockerd 的兄弟容器,不是子容器。", t=tl(S(2)), done=lidx(S(2), 'docker ps -q 看到', '外层 docker ps 能看到 sibling86'), mark=lidx(S(2), 'docker info 的 Name'), b=bars([['容器里 docker ps -q', 9, '9'], ['外层 docker ps -q', 9, '9']], 9, done=[0, 1]), kv=KV([['挂 socket', '共用外层 dockerd'], ['docker ps', '看到全部 9 个容器'], ['docker run', '创建的是外层的兄弟容器']], ['挂 socket'])),
    step("不加 --privileged 起嵌套 dockerd:15 秒内没有就绪,日志里 iptables 报 Could not fetch rule set generation id: Permission denied (you must be root)——嵌套的 dockerd 需要特权去管理网络规则等。对比:DooD 不加 --privileged 就能用,DinD 加了 --privileged 后 0.3 秒就绪。", t=tl(S(3)), done=lidx(S(3), '对比'), mark=lidx(S(3), '不加 --privileged'), kv=KV([['DinD 不加 --privileged', 'dockerd 起不来 (iptables Permission denied)'], ['DooD', '不需要 --privileged']], ['DinD 不加 --privileged'])),
]
A = mkartc('c86', 86, 'Docker,Docker-in-Docker,DinD,docker.sock,DooD,特权,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里对比 Docker-in-Docker 和挂载 docker.sock:DinD(--privileged 的 docker:dind)里的嵌套 dockerd 0.3 秒就绪、镜像库是空的、看不到外层容器;挂载 socket(不需要 --privileged)则共用外层 dockerd,docker ps 看到全部 9 个容器,创建出来的是外层的兄弟容器;DinD 不加 --privileged 时 dockerd 因 iptables 权限起不来。',
    '在容器里用 docker 命令,是起一个嵌套的 dockerd 还是把宿主的 socket 挂进去?两种做法看到的东西、创建的容器、需要的权限各不相同。这篇用 docker:dind 镜像逐项实测。',
    [('0 对 9', '嵌套的 docker ps 看到的容器数,与挂载 socket 后容器里 docker ps 看到的容器数(外层也是 9)'), ('兄弟容器', '通过挂载的 socket 创建的容器,出现在外层 docker ps 里'), ('iptables Permission denied', '不加 --privileged 起 dind 的 dockerd 时的报错')],
    [('DinD', '<p>容器里起一个独立的 dockerd,有自己的镜像库和容器,和外层互不可见;镜像要重新 pull 或 load。需要 <code>--privileged</code>,否则 iptables 等操作被拒绝。镜像是 docker:dind(29.9.0),存储驱动在这里是 overlayfs。</p>'),
     ('DooD(挂 socket)', '<p>把宿主的 <code>/var/run/docker.sock</code> 挂进去,容器里的 docker 命令就是在操作外层的 dockerd:看到所有容器,创建的是外层的兄弟容器,共享镜像缓存。不需要 --privileged,但这个容器等于拥有了控制整个 Docker 的能力——它能列出甚至操作别的项目的容器。这里我只做了 ps 和创建删除一个带标签的容器。</p>'),
     ('取舍', '<p>要隔离(CI 里每个任务一个干净的 Docker)用 DinD,代价是特权和冷缓存;要共享缓存、轻量用 DooD,代价是权限过大且容器互相可见。哪种适合,取决于你信任里面的代码到什么程度(本文没有做更多的安全测试)。</p>')],
    steps,
    [ENV_C + '。嵌套的 dockerd 来自 docker:dind 镜像(Docker 29.9.0),用特权容器启动,启动耗时从 dockerd 进程拉起到 docker info 成功;DooD 部分挂载的是 Docker Desktop 虚拟机里的 /var/run/docker.sock;只创建和删除了带 bwlab 标签的容器;实验后已删除这些容器',
     '没有验证:DinD 的数据持久化与卷、DinD 里的网络与端口映射、rootless DinD、sysbox 之类的运行时、通过 socket 能做的破坏性操作(不做)、CI 里的实际性能差别'],
    'Docker in Docker')
