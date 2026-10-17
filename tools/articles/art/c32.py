from lib import *
S = SS('c32')
steps = [
    step("docker run --init alpine sleep 600:容器里 /proc/1/cmdline 是“/sbin/docker-init -- sleep 600”,进程列表里 PID 1 是 docker-init,sleep 600 变成 PID 7,父进程是 1。/sbin/docker-init --version 输出 tini version 0.19.0 - git.de40ad0——Docker 的 --init 用的就是 tini。这个文件 601296 字节、权限 -rwxr-xr-x,不是镜像里的:不加 --init 的同一个镜像里没有 /sbin/docker-init(No such file);mountinfo 里它是从宿主(虚拟机)的 /usr/libexec/docker/docker-init 只读挂载进来的。PID 1 的 VmRSS 是 508 kB。HostConfig.Init = true。", t=tl(S(1)), done=lidx(S(1), 'tini version', '/proc/1/cmdline', '进程列表'), mark=lidx(S(1), 'mountinfo', '不加 --init'), kv=KV([['PID 1', '/sbin/docker-init(tini 0.19.0),VmRSS 508 kB'], ['你的程序', 'PID 7,父进程 1'], ['docker-init 来源', '运行时从虚拟机只读挂载,不在镜像里']], ['docker-init 来源'])),
    step("退出码穿过 init:子进程 exit 3 → docker run 退出码 3(不用 --init 也是 3);子进程 kill -9 自己 → 137;子进程 kill -TERM 自己 → 143(128 加信号编号)。对比不用 --init、PID 1 是 sh 的情形,kill -TERM $$ 的结果是 0——sh 作为 PID 1 忽略了对自己的 SIGTERM。", t=tl(S(2)), done=lidx(S(2), '子进程 exit 3:', '子进程被 SIGKILL', '子进程被 SIGTERM(kill -TERM $$):docker run 退出码 143'), mark=lidx(S(2), '不用 --init,PID 1 是 sh'), kv=KV([['exit 3', 'init 透传 3'], ['被 SIGKILL', '137'], ['被 SIGTERM', '143'], ['不用 --init,PID 1 是 sh', '对自己的 TERM 被忽略,退出码 0']], ['被 SIGTERM'])),
    step("信号转发:程序(python,装了 SIGUSR1 处理程序)在 --init 下,docker kill -s USR1 后日志出现“子进程收到 SIGUSR1”,ExitCode=0;不用 --init(python 自己是 PID 1)结果完全一样。能自己处理信号的程序,有没有 init 差别不大;init 的价值在不会处理信号的程序和孤儿进程(见 c6、c31)。", t=tl(S(3)), done=lidx(S(3), '--init:日志', '不用 --init:日志'), kv=KV([['--init', '子进程收到 SIGUSR1'], ['不用 --init', '同样收到'], ['结论', '程序自己处理信号时没有差别']], ['结论'])),
    step("启动开销:docker run --rm alpine true 各 10 次,不用 --init 中位数 170 ms(最小 164、最大 191),--init 中位数 175 ms(最小 167、最大 208)。差别在测量的抖动范围内。", t=tl(S(4)), done=lidx(S(4), '不用 --init:中位数'), mark=lidx(S(4), '--init:中位数'), b=bars([['不用 --init (ms)', 170, '170'], ['--init (ms)', 175, '175']], 175, done=[0], mark=[1]), kv=KV([['不用 --init', '中位数 170 ms'], ['--init', '中位数 175 ms']], ['--init'])),
]
A = mkartc('c32', 32, 'Docker,tini,--init,docker-init,PID 1,信号转发,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 --init:PID 1 变成 /sbin/docker-init(tini 0.19.0,601296 字节,VmRSS 508 kB,运行时从虚拟机只读挂载进容器,不在镜像里),你的程序是 PID 7;子进程的退出码(3、137、143)原样穿过;能自己处理信号的程序有没有 init 都收到 SIGUSR1;启动开销中位数 175 ms 对 170 ms,在抖动范围内。',
    'docker run --init 到底往容器里放了什么?它是镜像的一部分吗,占多少内存,退出码和信号怎么穿过它,启动会慢多少?这篇逐项实测。',
    [('tini 0.19.0', 'docker run --init 放进容器的 PID 1(/sbin/docker-init),大小 601296 字节'), ('508 kB', 'PID 1 的内存常驻(VmRSS)'), ('175 vs 170 ms', 'docker run --rm alpine true 在 --init 与不用 --init 时的启动用时中位数')],
    [('放进去的是什么', '<p><code>--init</code> 让 PID 1 变成 <code>/sbin/docker-init -- 你的命令</code>,它是 tini 0.19.0。这个文件不在镜像里,运行时从 Docker Desktop 虚拟机的 <code>/usr/libexec/docker/docker-init</code> 只读挂载进来,所以任何镜像都能用,也不改变镜像内容。你的程序变成 PID 7,父进程是 1。</p>'),
     ('退出码', '<p>子进程 exit 3,docker run 的退出码就是 3;被信号杀死则是 128 加信号编号(137、143)。</p>'),
     ('信号', '<p>程序自己装了信号处理程序时,有没有 init 都能收到信号。init 的价值在没有处理程序的程序(c6)和孤儿进程收尸(c31)。</p>'),
     ('开销', '<p>PID 1 的 VmRSS 只有 508 kB,启动用时中位数 175 ms 对 170 ms,各 10 次,差别在抖动范围内。</p>')],
    steps,
    [ENV_C + '。docker-init 信息取自容器内 /proc 与 mountinfo;退出码和信号各情形运行一次;启动用时是 docker CLI 的整次调用,各 10 次取中位数;实验后已删除容器',
     '没有验证:自己用 apk / apt 安装的 tini 与 docker-init 的差别、tini 的 -g(进程组转发)和 -s 参数、compose 的 init: true、dumb-init、Linux 宿主机上 docker-init 的位置'],
    'tini 与 --init')
