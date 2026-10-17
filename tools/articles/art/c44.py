from lib import *
S = SS('c44')
steps = [
    step("默认容器 与 --privileged 对比。默认:capability 14 个(不含 sys_admin、sys_module、sys_rawio)、Seccomp: 2、/dev 里 15 个条目(0 个块设备)、/proc/sys 是单独的只读挂载(ro)、/sys 是 ro、mount -t tmpfs 退出码 1(permission denied)。--privileged:capability 41 个(含 sys_admin、sys_module、sys_rawio)、Seccomp: 0、/dev 里 169 个条目(12 个块设备)、/proc/sys 没有单独的只读挂载(随 /proc 为 rw)、/sys 是 rw、mount -t tmpfs 成功。", t=tl(S(1)), done=lidx(S(1), '默认:', 'capability 14 个'), mark=lidx(S(1), '--privileged:', 'capability 41 个', '/dev 条目数 169'), b=bars([['capability(默认)', 14, '14'], ['capability(--privileged)', 41, '41'], ['/dev 条目(默认)', 15, '15'], ['/dev 条目(--privileged)', 169, '169']], 169, done=[0, 2], mark=[1, 3]), kv=KV([['capability', '14 → 41'], ['seccomp', '2 → 0'], ['/dev 条目', '15 → 169'], ['/proc/sys、/sys', '只读 → 可写']], ['capability'])),
    step("不必用整个 --privileged:只 --cap-add SYS_ADMIN,capability 变成 15 个(含 sys_admin,仍不含 sys_module、sys_rawio),Seccomp 仍是 2,/dev 仍是 15 个,/proc/sys 与 /sys 仍是 ro,但 mount -t tmpfs 已经成功。只加这一个 capability 就能 mount,SYS_ADMIN 本身就很大(但比 --privileged 小得多)。", t=tl(S(2)), done=lidx(S(2), '--cap-add SYS_ADMIN:', 'capability 15 个'), mark=lidx(S(2), 'mount -t tmpfs 退出码 0'), kv=KV([['--cap-add SYS_ADMIN', '15 个 capability,mount 成功'], ['其它限制', 'seccomp、/dev、/proc/sys 都还在']], ['--cap-add SYS_ADMIN'])),
    step("特权容器能看到虚拟机的磁盘设备:/dev/vd* 有 vda、vda1、vdb;读 /dev/vda1 偏移 1080 处的 2 个字节是 53 ef(ext4 超级块魔数)。默认容器里没有 /dev/vd*,/dev/vda1 不存在。这里只读了 2 个字节,没有挂载也没有写。", t=tl(S(3)), done=lidx(S(3), '--privileged:/dev/vd*'), mark=lidx(S(3), '默认:/dev/vd*'), kv=KV([['--privileged', '看得到 vda、vda1、vdb,读到 ext4 魔数 53 ef'], ['默认', '/dev/vda1 不存在']], ['--privileged'])),
    step("docker inspect:HostConfig.Privileged = true,CapAdd 是空(特权不是靠一个个 CapAdd 实现的),SecurityOpt = [label=disable]。", t=tl(S(4)), done=lidx(S(4), 'HostConfig.Privileged'), kv=KV([['Privileged', 'true'], ['CapAdd', '[]'], ['SecurityOpt', '[label=disable]']], ['Privileged'])),
]
A = mkartc('c44', 44, 'Docker,privileged,特权容器,capability,/dev,安全,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 --privileged:capability 从 14 个变成 41 个、Seccomp 从 2 变成 0、/dev 条目从 15 个变成 169 个、/proc/sys 和 /sys 变成可写,能读虚拟机的 /dev/vda1;只 --cap-add SYS_ADMIN 就能 mount,但 seccomp 与 /dev 仍受限。',
    '--privileged 到底多“特权”?这篇把默认容器、--privileged 和只加 SYS_ADMIN 放在一起,对比 capability、seccomp、设备、/proc/sys 与 /sys 的挂载,并验证特权容器能读到虚拟机的磁盘设备。',
    [('14 → 41', '默认与 --privileged 的 capability 个数'), ('15 → 169', '/dev 里的条目数'), ('53 ef', '特权容器读 /dev/vda1 偏移 1080 处得到的 ext4 魔数(默认容器里这个设备不存在)')],
    [('整套放开', '<p>--privileged 同时放开多件事:全部 capability、关掉 seccomp、把宿主的设备都放进 /dev、/proc/sys 与 /sys 变成可写,<code>docker inspect</code> 里还多了 <code>label=disable</code>。我没有逐项测 AppArmor / SELinux。</p>'),
     ('更小的授权', '<p>只加 SYS_ADMIN 就已经能 mount,但 seccomp、/dev、/proc/sys 的限制仍在。能用单个 capability 或 <code>--device</code> 解决的需求,不要上 --privileged。</p>'),
     ('能碰到宿主', '<p>特权容器里能看到虚拟机的磁盘设备,读到了 ext4 的魔数。我只读了 2 个字节;至于在特权容器里能对虚拟机做多少事,我没有做更多实验。我在这个系列里用它的唯一目的是读取虚拟机里的信息,没有改动任何东西。</p>'),
     ('inspect 里的样子', '<p><code>HostConfig.Privileged</code> 是 true,而 <code>CapAdd</code> 是空的:特权不是靠一个个 CapAdd 实现的。</p>')],
    steps,
    [ENV_C + '。capability 来自 /proc/self/status 的 CapEff 解码(名字表同 c40);挂载和设备信息读自容器内的 /proc/mounts 与 /dev;读磁盘设备只读取偏移 1080 处的 2 个字节;每种配置运行一次;实验后已删除容器',
     '没有验证:AppArmor / SELinux 的差别、--device 单独放行设备、特权容器里挂载磁盘并读写(会修改虚拟机,不做)、Linux 宿主机上的 --privileged 范围、Docker-in-Docker(见后面的 DinD 一篇)'],
    '特权模式')
