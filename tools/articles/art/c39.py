from lib import *
S = SS('c39')
steps = [
    step("docker info 的 SecurityOptions:[name=seccomp,profile=builtin name=cgroupns]——守护进程用的是内置的默认 seccomp 配置。容器里的 /proc/self/status:默认 Seccomp=2(filter 模式)、Seccomp_filters=1;--security-opt seccomp=unconfined → Seccomp=0、Seccomp_filters=0。", t=tl(S(1)), done=lidx(S(1), '默认:/proc/self/status'), mark=lidx(S(1), 'seccomp=unconfined', 'SecurityOptions'), kv=KV([['默认', 'Seccomp=2,1 个 filter'], ['seccomp=unconfined', 'Seccomp=0,没有 filter'], ['守护进程', 'profile=builtin']], ['默认'])),
    step("用 ctypes 直接发 13 个系统调用,默认 seccomp 对 unconfined。被默认配置挡掉的(默认 EPERM,unconfined 能到达内核):add_key(成功返回 key 编号)、keyctl(EINVAL)、unshare(CLONE_NEWUSER)(成功)、userfaultfd(ENOSYS)、perf_event_open(EFAULT)、bpf(EINVAL)、kcmp(ESRCH)、personality(成功)、clock_settime(EFAULT)。两边都 EPERM 的:mount、swapon——它们被 capability(没有 CAP_SYS_ADMIN)挡住,不是 seccomp。getpid、ptrace(PTRACE_TRACEME) 两边都成功。", t=tl(S(2)), done=lidx(S(2), 'getpid', 'ptrace(PTRACE_TRACEME)'), mark=lidx(S(2), 'add_key', 'unshare(CLONE_NEWUSER)', 'bpf', 'clock_settime', 'mount', 'swapon'), b=bars([['默认配置挡掉(EPERM,unconfined 不同)', 9, '9'], ['两边都 EPERM(capability)', 2, '2'], ['两边都成功', 2, '2']], 13, done=[2], mark=[0, 1]), kv=KV([['seccomp 挡的', 'add_key、keyctl、unshare 用户命名空间、bpf、userfaultfd 等'], ['capability 挡的', 'mount、swapon(unconfined 下仍 EPERM)'], ['都放行', 'getpid、ptrace(TRACEME)']], ['seccomp 挡的'])),
    step("--privileged:Seccomp=0、Seccomp_filters=0——特权模式同时关掉了 seccomp;--security-opt no-new-privileges:NoNewPrivs=1,Seccomp 仍是 2、1 个 filter,两个选项互不相关。", t=tl(S(3)), done=lidx(S(3), '--security-opt no-new-privileges'), mark=lidx(S(3), '--privileged'), kv=KV([['--privileged', 'Seccomp=0'], ['no-new-privileges', 'NoNewPrivs=1,seccomp 仍启用']], ['--privileged'])),
]
A = mkartc('c39', 39, 'Docker,seccomp,系统调用,capability,安全,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测默认 seccomp 配置:容器 /proc/self/status 显示 Seccomp=2(unconfined 和 --privileged 是 0);用 ctypes 发 13 个系统调用,add_key、keyctl、unshare(CLONE_NEWUSER)、bpf、userfaultfd 等 9 个在默认配置下 EPERM、unconfined 下能到达内核,mount 和 swapon 两边都是 EPERM(靠 capability 挡住)。',
    '默认的 seccomp 配置到底挡了什么?怎么区分一个 EPERM 是 seccomp 挡的还是 capability 挡的?这篇在默认和 unconfined 下发同一批系统调用,逐个对比结果。',
    [('9 个', '13 个系统调用里,默认 seccomp 返回 EPERM 而 unconfined 能进入内核的个数'), ('Seccomp=2', '容器进程的 seccomp 模式(filter);unconfined 与 --privileged 为 0'), ('mount 仍 EPERM', '关掉 seccomp 之后仍被拒绝,说明那是 capability 的限制')],
    [('状态', '<p>/proc/self/status 里的 <code>Seccomp</code>:2 是 filter 模式;<code>--security-opt seccomp=unconfined</code> 和 <code>--privileged</code> 都是 0。</p>'),
     ('哪些被挡', '<p>默认配置下,add_key、keyctl、unshare(CLONE_NEWUSER)、userfaultfd、perf_event_open、bpf、kcmp、personality、clock_settime 都返回 EPERM;关掉 seccomp 后它们到达内核,返回别的 errno(参数故意给得不合法的会得到 EINVAL、EFAULT 等,这说明过滤器不再拦截)或者成功。mount 和 swapon 在两种配置下都是 EPERM:需要 CAP_SYS_ADMIN,和 seccomp 无关。判断一个 EPERM 来自哪里,最直接的办法就是把 seccomp 关掉再试一次。这批系统调用号是 arm64 的,amd64 不同;只测了这 13 个,不是完整的黑名单。</p>'),
     ('与其它选项的关系', '<p>--privileged 会把 seccomp 一起关掉;no-new-privileges 只设置 NoNewPrivs=1,seccomp 照常启用。</p>')],
    steps,
    [ENV_C + '。系统调用用 Python ctypes 的 syscall(),号码是 linux/arm64 的(getpid 172、add_key 217、keyctl 219、unshare 97、userfaultfd 282、perf_event_open 241、bpf 280、kcmp 272、personality 92、mount 40、ptrace 117、clock_settime 112、swapon 224);参数多数是故意不合法或无害的,只用来看 errno;每种配置运行一次;实验后已删除容器和镜像',
     '没有验证:默认 profile 的完整 JSON 内容、自定义 seccomp profile 的写法与效果、amd64 上的差异、与 capability 同时放开时哪些调用才可用、seccomp 的性能开销、Docker Desktop 以外的内核版本'],
    '默认 seccomp')
