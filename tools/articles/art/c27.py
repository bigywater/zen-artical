from lib import *
S = SS('c27')
steps = [
    step("起一个 sleep 600 的容器。docker inspect 的 State.Pid = 13063(这是 Docker Desktop 虚拟机里看到的 PID),/proc/13063/status 的 NSpid 是“13063 1”——容器里它是 PID 1。沿着父进程往上走:sleep 600(PID 13063)的 PPID 是 13039,那是 /usr/bin/containerd-shim-runc-v2 -namespace moby -id 837a27d7cb26… -address /run/containerd/containerd.sock;shim 的 PPID 是 1,即 /initd。shim 参数里的 -id 等于容器 ID。", t=tl(S(1)), done=lidx(S(1), 'NSpid', '容器进程的 PPID'), mark=lidx(S(1), '13063 13039 sleep 600', '13039     1', '      1     0 /initd'), kv=KV([['容器进程', 'PID 13063(容器内 PID 1),PPID 13039'], ['父进程', 'containerd-shim-runc-v2,-id = 容器 ID'], ['shim 的父进程', 'PID 1:/initd']], ['父进程'])),
    step("再起 3 个容器,虚拟机里 containerd-shim 进程从 20 个变成 23 个——每个容器一个 shim。容器运行期间连续 6 次查看,虚拟机里没有 runc 进程([0, 0, 0, 0, 0, 0])。dockerd(PID 283)和 containerd(PID 265)的父进程都是 146,两者是并列的两个进程,不是父子关系。", t=tl(S(2)), done=lidx(S(2), '起 3 个容器前后', '连续 6 次'), mark=lidx(S(2), 'dockerd 与 containerd'), b=bars([['shim 数(起 3 个容器前)', 20, '20'], ['shim 数(起 3 个容器后)', 23, '23']], 23, done=[0], mark=[1]), kv=KV([['3 个新容器', 'shim +3'], ['runc 进程', '6 次采样都是 0 个'], ['dockerd / containerd', '都是 PID 146 的子进程']], ['runc 进程'])),
    step("docker exec -d 起的 sleep 555:PID 14139,PPID 13039——同一个 shim(也就是容器主进程的父进程)。exec 进来的进程也挂在这个容器的 shim 下面。", t=tl(S(3)), done=lidx(S(3), 'sleep 555'), kv=KV([['exec 出来的进程', 'PID 14139'], ['它的父进程', '13039,同一个 shim']], ['它的父进程'])),
    step("从虚拟机里直接 kill -9 容器主进程 13063:docker inspect 随后是 Status=exited、ExitCode=137,对应的 shim 也不在了(False)。正常 docker stop 另一个容器后,它的 shim 同样消失。shim 的生命周期和容器一致。", t=tl(S(4)), done=lidx(S(4), 'kill -9 13063', 'docker stop 另一个容器'), kv=KV([['kill -9 主进程', 'exited,ExitCode 137,shim 消失'], ['docker stop', 'shim 也消失']], ['kill -9 主进程'])),
]
A = mkartc('c27', 27, 'Docker,containerd,containerd-shim,runc,进程树,PID,真实验证,动画演示',
    '进入 Docker Desktop 虚拟机实测容器进程的父进程链:容器里的 PID 1 在虚拟机里是 13063,它的父进程是 containerd-shim-runc-v2(-id 等于容器 ID),shim 的父进程是 /initd(PID 1);每个容器一个 shim,容器运行时没有 runc 进程;docker exec 的进程挂在同一个 shim 下;kill -9 主进程后容器 exited(137),shim 随之消失。',
    '容器进程的父进程到底是谁?是 dockerd、containerd 还是 runc?这篇进入 Docker Desktop 的虚拟机,从容器的主进程一路往上看,并验证 shim 的数量、runc 是否常驻,以及 exec 的进程挂在哪里。',
    [('containerd-shim', '容器主进程的父进程,命令行里的 -id 就是容器 ID'), ('shim +3', '多起 3 个容器,虚拟机里的 containerd-shim 进程数从 20 增加到 23'), ('6 次都是 0', '容器运行期间连续采样,虚拟机里 runc 进程的个数')],
    [('父进程链', '<p>容器里的 PID 1,在虚拟机里是另一个 PID(NSpid 显示 13063 和 1),它的父进程是 <code>containerd-shim-runc-v2</code>,shim 的命令行带着 <code>-namespace moby -id &lt;容器ID&gt;</code>;shim 的父进程是虚拟机的 PID 1(<code>/initd</code>),不是 dockerd 也不是 containerd。所以重启 dockerd 不会直接杀死容器进程(是否真的如此,我没有实验)。</p>'),
     ('一个容器一个 shim', '<p>多起 3 个容器,shim 进程从 20 个增加到 23 个。runc 只在创建容器时短暂出现,容器运行期间我连续采样 6 次,都没有 runc 进程;这个采样只能说明它没有常驻,不能证明启动瞬间的情形。</p>'),
     ('exec 的进程', '<p>docker exec -d 起的进程,父进程仍是该容器的 shim。</p>'),
     ('杀掉主进程', '<p>从虚拟机里直接 kill -9 容器的主进程,Docker 看到的是 exited、ExitCode 137,shim 也退出了。</p>')],
    steps,
    [ENV_C + '。进入虚拟机的方法见 c19(特权容器加 nsenter -t 1);进程信息用虚拟机里的 ps 和 /proc 读取;PID 每次运行不同,文中数字取自最后一次运行;虚拟机里还有其它容器在运行(shim 的基数是 20),所以只看变化量;实验后已删除容器',
     '没有验证:重启 dockerd/containerd 对容器的影响(见后面的 live-restore 一篇)、容器启动瞬间 runc 的进程、shim 的内存占用、其它 OCI 运行时(如 gVisor、crun)、Linux 宿主机上 shim 的父进程(这里是 Docker Desktop 自己的 /initd)'],
    'containerd-shim')
