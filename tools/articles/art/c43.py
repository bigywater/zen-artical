from lib import *
S = SS('c43')
steps = [
    step("这台 Docker 没有开 userns-remap(我也不会改守护进程配置):docker info 的 SecurityOptions 只有 seccomp 和 cgroupns。容器里的 /proc/self/uid_map 与 gid_map 都是“0 0 4294967295”——容器里的 uid 0 就是虚拟机里的 uid 0,没有重映射。在虚拟机里看这个容器的主进程(PID 17650):用户是 root、uid 0;它的 /proc/17650/uid_map 同样是“0 0 4294967295”。", t=tl(S(1)), done=lidx(S(1), '/proc/self/uid_map', '虚拟机里看这个容器的主进程'), mark=lidx(S(1), 'SecurityOptions'), kv=KV([['SecurityOptions', 'seccomp、cgroupns,没有 userns'], ['uid_map', '0 0 4294967295(恒等映射)'], ['虚拟机里的主进程', 'root(uid 0)']], ['uid_map'])),
    step("要看映射是怎么起作用的,可以手动建一个用户命名空间:uid 1000 的容器进程(需要 seccomp=unconfined,默认 seccomp 不允许,见 c39)。unshare(CLONE_NEWUSER) 之后、还没写映射时,它看自己是 uid=65534(nobody);写入 uid 映射“0 1000 1”和 gid 映射“0 0 1”后,uid=0。这时 /etc/hosts 和 /etc/passwd(真实属主是 root)显示成 65534,自己创建的 /tmp/f 显示成 0;chown /tmp/f 0 0 成功,chown /tmp/f 5 5 失败(5 没有映射,Invalid argument);CapEff 是 000001ffffffffff(命名空间里的全部 capability)。在虚拟机里看同一个进程:用户 1000、uid 1000——容器里的“root”在外面其实是 uid 1000。", t=tl(S(2)), done=lidx(S(2), '写入 uid 映射', 'chown /tmp/f 0 0'), mark=lidx(S(2), '虚拟机里看这个进程', 'chown /tmp/f 5 5', 'CapEff'), kv=KV([['映射前', '看自己是 65534(nobody)'], ['映射 0 → 1000', '里面是 uid 0,外面是 uid 1000'], ['没映射的 uid', '文件显示成 65534,chown 它返回 EINVAL']], ['映射 0 → 1000'])),
]
A = mkartc('c43', 43, 'Docker,用户命名空间,userns,uid_map,root映射,真实验证,动画演示',
    '实测 Docker 里的 uid 映射:这台 Docker Desktop 没开 userns-remap,容器里 uid 0 就是虚拟机里的 root(uid_map 是恒等的“0 0 4294967295”);手动 unshare 出一个用户命名空间并写入“0 1000 1”后,命名空间里是 uid 0、虚拟机里看是 uid 1000,未映射的文件显示成 65534,chown 到未映射的 uid 返回 EINVAL。',
    '容器里的 root 在宿主机上是谁?userns-remap 想解决什么问题?我不能修改这台 Docker 的守护进程配置,所以这篇没有测 userns-remap 本身,而是读 uid_map、再手动建一个用户命名空间,把「里面的 root、外面的普通用户」这件事的机制测出来。',
    [('0 0 4294967295', '默认容器的 uid_map:没有重映射,容器 root 就是虚拟机的 root'), ('65534', '用户命名空间里没有映射的 uid(包括真实属主 root 的文件)显示成的 uid'), ('0 → 1000', '命名空间里的 uid 0 在外面的真实 uid')],
    [('默认没有重映射', '<p>docker info 里没有 userns,容器里 <code>/proc/self/uid_map</code> 是恒等映射 <code>0 0 4294967295</code>,在虚拟机里看容器的主进程就是 root。所以默认情况下,逃出容器的 root 进程在虚拟机里仍然是 root(这句话是对恒等映射的直接推论,我没有做逃逸实验)。</p>'),
     ('映射的机制', '<p>手动建的用户命名空间展示了 userns-remap 背后的机制:里面的 uid 0 对应外面的普通 uid(这里是 1000),外面没映射的 uid(如 root 的文件)在里面是 65534,不能 chown 到未映射的 uid,命名空间里有的 capability 只对命名空间自己管辖的资源有效。Docker 的 userns-remap 需要在守护进程配置里打开(<code>userns-remap</code>),它会为容器统一分配一段 subuid 范围,具体的行为和对 volume、镜像存储的影响,我没有验证。</p>')],
    steps,
    [ENV_C + '。没有修改守护进程配置,也没有启用 userns-remap;手动用户命名空间用 Python 3.12 的 os.unshare(CLONE_NEWUSER) 并写 /proc/self/{setgroups,uid_map,gid_map};容器需要 --security-opt seccomp=unconfined 才能 unshare;宿主侧(虚拟机)的进程信息用特权容器加 nsenter 读取(方法见 c19);实验后已删除容器',
     '没有验证:真正的 userns-remap(守护进程配置、subuid / subgid 范围、镜像和卷的属主变化、与 --privileged 和 --net=host 的冲突)、rootless Docker、Kubernetes 的 user namespace、多个 uid 范围的映射'],
    '用户命名空间')
