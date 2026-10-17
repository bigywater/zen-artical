from lib import *
S = SS('c41')
steps = [
    step("镜像里放一份 setuid root 的 Python(/pysuid,权限 -rwsr-xr-x,属主 root)和一份普通的 /pynormal,以 uid 1000 运行并打印 uid / euid / 状态。默认:/pysuid 得到 uid=1000 euid=0,CapEff=a80425fb(14 个 capability 全拿到),NoNewPrivs=0——普通用户靠 setuid 变成了 root;/pynormal 是 euid=1000、CapEff=0。加 --security-opt no-new-privileges:/pysuid 的 euid 仍是 1000、CapEff=0,NoNewPrivs=1,setuid 位不起作用。no-new-privileges=false 与默认相同。", t=tl(S(1)), done=lidx(S(1), '--security-opt no-new-privileges:', 'setuid 的 /pysuid → uid=1000 euid=1000'), mark=lidx(S(1), '默认:', 'setuid 的 /pysuid → uid=1000 euid=0'), kv=KV([['默认', 'setuid 程序 euid=0,CapEff=a80425fb'], ['no-new-privileges', 'euid 仍是 1000,CapEff=0,NoNewPrivs=1'], ['普通程序', '两种情况都是 euid=1000']], ['no-new-privileges'])),
    step("no-new-privileges 不影响已经是 root 的进程:--user 默认 root 的容器里,uid=0 euid=0,CapEff 仍是 a80425fb,只是 NoNewPrivs=1。docker exec 进入一个 no-new-privileges 的容器,运行 /pysuid 仍是 euid=1000(exec 出来的进程同样带着 NoNewPrivs=1);docker exec --user 0 进去的进程是 root,NoNewPrivs=1。docker inspect 里 HostConfig.SecurityOpt = [no-new-privileges]。", t=tl(S(2)), done=lidx(S(2), 'root 用户 + no-new-privileges', 'docker exec --user 0'), mark=lidx(S(2), 'docker exec 进入'), kv=KV([['root 进程', '不受影响,capability 照旧'], ['docker exec 的进程', '同样 NoNewPrivs=1'], ['setuid 位', '对非 root 用户失效']], ['docker exec 的进程'])),
]
A = mkartc('c41', 41, 'Docker,no-new-privileges,setuid,权限提升,安全,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 no-new-privileges:镜像里一份 setuid root 的程序,uid 1000 默认运行得到 euid=0 和全部 14 个 capability;加 --security-opt no-new-privileges 后 euid 仍是 1000、CapEff=0、NoNewPrivs=1;已经是 root 的进程不受影响,docker exec 进去的进程也带着这个标志。',
    '容器里一个 setuid 程序能把普通用户变成 root 吗?no-new-privileges 到底挡住了什么、又没挡住什么?这篇用一份 setuid root 的 Python 在两种设置下对比,并验证 docker exec 进去的进程。',
    [('euid=0 → 1000', 'setuid root 程序由 uid 1000 运行,默认 euid 是 0;加 no-new-privileges 后仍是 1000'), ('NoNewPrivs=1', '/proc/self/status 里表示进程及其后代不能通过 execve 获得新权限'), ('root 不受影响', '已经是 root 的进程有同样的 capability,只多了 NoNewPrivs=1')],
    [('setuid 失效', '<p>默认情况下,普通用户运行镜像里 setuid root 的程序,得到 euid=0 和全部 14 个 capability。加了 <code>--security-opt no-new-privileges</code> 后,setuid 位被忽略,euid 仍是 1000。我是自己制造了一份 setuid 的 Python;镜像里本来就有的 setuid 程序(如 su、ping)没有逐个测。</p>'),
     ('范围', '<p>这个标志不降低已经是 root 的进程的权限;docker exec 进入这个容器的进程同样带着 NoNewPrivs=1。它防止的是「通过 execve 获得比父进程更多的权限」,所以常和 <code>--cap-drop ALL</code> 一起用(见 c40)。</p>')],
    steps,
    [ENV_C + '。setuid 程序是构建时把 python 解释器复制成 /pysuid 并 chmod 4755;以 uid 1000 运行并打印 os.getuid / os.geteuid 与 /proc/self/status 的 NoNewPrivs、CapEff;每种配置运行一次;实验后已删除容器和镜像',
     '没有验证:真实镜像里 su / sudo / ping 的行为、文件 capability(setcap)是否同样被忽略、与 AppArmor / SELinux 的交互、Kubernetes 的 allowPrivilegeEscalation 对应关系'],
    'no-new-privileges')
