from lib import *
S = SS('c90')
steps = [
    step("虚拟机里的值:net.ipv4.ip_forward=1、net.core.somaxconn=4096、net.ipv4.ip_local_port_range=55000 65535、kernel.shmmax=18446744073692774399;默认容器里:ip_forward=1、somaxconn=4096、ip_local_port_range=32768 60999(与虚拟机不同——网络命名空间有自己的默认值)、shmmax 同虚拟机。用 --sysctl 设 ip_forward=1、somaxconn=1024、ip_local_port_range=\"40000 40100\"、shmmax=1048576,退出码 0,容器里读到的就是这些新值;同一时刻虚拟机里的值一个都没变。", t=tl(S(1)), done=lidx(S(1), '同一时刻虚拟机里的值', '--sysctl net.ipv4.ip_forward=1'), mark=lidx(S(1), '默认容器里的值', '虚拟机里的当前值'), kv=KV([['容器里', 'somaxconn=1024,端口范围 40000 40100,shmmax=1048576'], ['虚拟机里', '4096 / 55000 65535 / 原值,没变']], ['容器里'])),
    step("不在独立命名空间里的 sysctl 被拒绝:vm.swappiness、kernel.panic、fs.file-max、kernel.pid_max 都是退出码 125,报 sysctl '…' is not allowed——这些是整台机器共享的参数,容器不能改。", t=tl(S(2)), done=lidx(S(2), '--sysctl vm.swappiness=10', '--sysctl kernel.panic=1'), mark=lidx(S(2), 'fs.file-max', 'kernel.pid_max'), kv=KV([['net.* / kernel.shm*', '命名空间级,允许'], ['vm.* / fs.file-max / kernel.panic / kernel.pid_max', '全局,拒绝(125)']], ['vm.* / fs.file-max / kernel.panic / kernel.pid_max'])),
    step("共享命名空间时也不能设:--network host 加 net.ipv4.ip_forward → 退出码 125,sysctl \"net.ipv4.ip_forward\" not allowed in host network namespace;--ipc host 加 kernel.shmmax → 125,sysctl \"kernel.shmmax\" is not allowed in the hosts ipc namespace;--network none 加 net.core.somaxconn=512 → 退出码 0,读到 512。", t=tl(S(3)), done=lidx(S(3), '--network none'), mark=lidx(S(3), '--network host', '--ipc host'), kv=KV([['--network host', 'net.* 不允许(会改到虚拟机的)'], ['--ipc host', 'kernel.shm* 不允许'], ['--network none', '允许,仍是自己的命名空间']], ['--network host'])),
    step("在容器里直接写 /proc/sys 也不行:echo 1 > /proc/sys/net/ipv4/ip_forward 和 echo 20 > /proc/sys/vm/swappiness 都报 Read-only file system,退出码 1;/proc/sys 是单独的只读挂载(选项 ro)。要改只能在容器启动时用 --sysctl。", t=tl(S(4)), done=lidx(S(4), '默认容器里'), kv=KV([['/proc/sys', '只读挂载'], ['写入', 'Read-only file system']], ['/proc/sys'])),
]
A = mkartc('c90', 90, 'Docker,sysctl,内核参数,命名空间,--sysctl,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 --sysctl:net.core.somaxconn、net.ipv4.ip_local_port_range、kernel.shmmax 等属于命名空间的参数只改容器内的值,虚拟机里的值不变;vm.swappiness、kernel.panic、fs.file-max、kernel.pid_max 被拒绝(125);--network host 或 --ipc host 时对应的参数也被拒绝;容器里直接写 /proc/sys 是只读的。',
    '容器能调内核参数吗?哪些参数只影响自己、哪些根本不让设?这篇逐项实测 --sysctl 的规则,并确认虚拟机里的值没有被改动。',
    [('4096 对 1024', '虚拟机与设了 --sysctl net.core.somaxconn=1024 的容器里的 somaxconn,虚拟机不变'), ('125', '--sysctl vm.swappiness=10 之类全局参数时 docker run 的退出码'), ('只读', '容器里 /proc/sys 的挂载选项,直接写会报 Read-only file system')],
    [('命名空间级的参数', '<p>网络(net.*)和 IPC(kernel.shm*、kernel.msg*、kernel.sem、fs.mqueue.*)是各命名空间自己的,<code>--sysctl</code> 只改容器里的值,虚拟机的值不动。容器的网络命名空间默认值也和虚拟机不同(端口范围 32768 60999 对 55000 65535)。</p>'),
     ('全局参数', '<p>vm.swappiness、kernel.panic、fs.file-max、kernel.pid_max 不是命名空间级的,docker 直接拒绝(我只试了这四个,没有穷举白名单)。</p>'),
     ('共享命名空间', '<p>用了 <code>--network host</code> 或 <code>--ipc host</code>,容器和虚拟机共用命名空间,改了就会改到虚拟机的,所以同样被拒绝。</p>'),
     ('/proc/sys', '<p>/proc/sys 在容器里是只读的(c44 里 --privileged 才会变成可写),想调参数必须在启动时声明。</p>')],
    steps,
    [ENV_C + '。只用 --sysctl 在容器内设置命名空间级参数,没有修改虚拟机里的任何参数(每次都对比了虚拟机里的值);全局参数的尝试都被 docker 拒绝;值通过读取 /proc/sys 得到;实验后已删除容器',
     '没有验证:Linux 宿主机上同样的结果、net.ipv4.ping_group_range 等其它命名空间级参数、--sysctl 与 Kubernetes 的 safe / unsafe sysctl 清单对应关系、--privileged 容器写 /proc/sys 的影响(会改动虚拟机,不做)'],
    '容器的 sysctl')
