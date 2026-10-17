from lib import *
S = SS('c73')
steps = [
    step("虚拟机的 /sys/fs/cgroup 是 cgroup2fs(cgroup v2)。容器主进程的 /proc/<pid>/cgroup 是 0::/../<容器ID>(相对于读取者自己的 cgroup 命名空间);在虚拟机里能找到真实目录 /sys/fs/cgroup/docker/<容器ID>。这个目录有 86 个文件,cgroup.controllers = cpuset cpu io memory hugetlb pids rdma——每个容器就是 docker 这个 cgroup 下的一个子目录。", t=tl(S(1)), done=lidx(S(1), 'cgroup2fs', '86 个文件'), mark=lidx(S(1), '找到的目录', '/proc/<pid>/cgroup'), b=bars([['容器 cgroup 目录里的文件数', 86, '86']], 86, done=[0]), kv=KV([['文件系统', 'cgroup2fs(cgroup v2)'], ['位置', '/sys/fs/cgroup/docker/<容器ID>'], ['可用控制器', 'cpuset cpu io memory hugetlb pids rdma']], ['位置'])),
    step("启动参数变成了文件里的值:--cpus 0.5 → cpu.max = 50000 100000;--cpu-shares 512 → cpu.weight = 59;--memory 100m → memory.max = 104857600;--memory-swap 100m → memory.swap.max = 0;--pids-limit 50 → pids.max = 50;--cpuset-cpus 0-1 → cpuset.cpus = 0-1(cpuset.cpus.effective 也是 0-1);--device-write-bps /dev/vda:1mb → io.max = 254:0 rbps=max wbps=1048576 riops=max wiops=max。docker 的资源限制就是往这些文件里写数字。", t=tl(S(2)), done=lidx(S(2), 'cpu.max', 'memory.max', 'pids.max', 'io.max'), mark=lidx(S(2), 'cpu.weight', 'memory.swap.max', 'cpuset.cpus '), kv=KV([['--cpus 0.5', 'cpu.max = 50000 100000'], ['--memory 100m', 'memory.max = 104857600'], ['--pids-limit 50', 'pids.max = 50'], ['--device-write-bps vda:1mb', 'io.max = 254:0 … wbps=1048576']], ['--cpus 0.5'])),
    step("cgroup.procs 里是 59365,docker top 的 PID 列也是 59365,两者一致(True)——docker top 看的就是这个 cgroup 里的进程。cgroup.type = domain,memory.current = 0.5 MiB,pids.current = 1。", t=tl(S(3)), done=lidx(S(3), 'cgroup.procs', 'cgroup.type'), kv=KV([['cgroup.procs', '与 docker top 的 PID 一致'], ['memory.current', '0.5 MiB'], ['pids.current', '1']], ['cgroup.procs'])),
    step("docker pause 对应 cgroup.freeze:暂停前 cgroup.freeze = 0、cgroup.events 是 populated 1 frozen 0;docker pause 后 cgroup.freeze = 1、cgroup.events 是 populated 1 frozen 1;unpause 后又回到 0。暂停用的是 cgroup 的冻结功能。", t=tl(S(4)), done=lidx(S(4), 'docker pause 后', 'unpause 后'), mark=lidx(S(4), '暂停前'), kv=KV([['暂停前', 'freeze 0 / frozen 0'], ['docker pause', 'freeze 1 / frozen 1'], ['unpause', 'freeze 0']], ['docker pause'])),
    step("docker stop 之后,这个 cgroup 目录已删除。cgroup 的生命周期和容器进程一致。", t=tl(S(5)), done=lidx(S(5), '已删除'), kv=KV([['容器停止', 'cgroup 目录被删除']], ['容器停止'])),
]
A = mkartc('c73', 73, 'Docker,cgroup v2,cpu.max,memory.max,pids.max,io.max,cgroup.freeze,真实验证,动画演示',
    '进入 Docker Desktop 虚拟机读容器的 cgroup v2 目录:/sys/fs/cgroup/docker/容器ID(86 个文件);--cpus 0.5 是 cpu.max = 50000 100000、--cpu-shares 512 是 cpu.weight = 59、--memory 100m 是 memory.max = 104857600、--pids-limit 50 是 pids.max = 50、--device-write-bps 变成 io.max;cgroup.procs 与 docker top 一致;docker pause 就是 cgroup.freeze = 1。',
    'docker run 的资源限制参数最后落在哪里?这篇直接读容器的 cgroup v2 目录,把每个参数对应的文件和数值一一列出来,还看了 docker pause 在 cgroup 里是什么样子。',
    [('86 个文件', '一个容器的 cgroup v2 目录里的文件数'), ('50000 100000', '--cpus 0.5 在 cpu.max 里的内容'), ('cgroup.freeze = 1', 'docker pause 之后 cgroup 里的冻结标志')],
    [('位置', '<p>这台虚拟机用 cgroup v2,每个容器在 <code>/sys/fs/cgroup/docker/&lt;容器ID&gt;</code>。读 <code>/proc/&lt;pid&gt;/cgroup</code> 得到的是相对读取者自己 cgroup 命名空间的路径(这次是 <code>../&lt;容器ID&gt;</code>),所以我是在虚拟机的 /sys/fs/cgroup 下按容器 ID 找到真实目录的;容器内部看到的路径,我没有单独验证。</p>'),
     ('参数与文件', '<p>--cpus 对应 cpu.max;--cpu-shares 被换算成 cpu.weight(512 → 59,见 c34);--memory 与 --memory-swap 对应 memory.max 和 memory.swap.max(swap 是总和减内存,见 c36);--pids-limit 对应 pids.max(c38);--cpuset-cpus 对应 cpuset.cpus;--device-write-bps 对应 io.max,按设备号(254:0 是虚拟机的 vda)。</p>'),
     ('进程与统计', '<p>cgroup.procs 列出的进程就是 docker top 看到的进程;memory.current、pids.current 等是运行时统计,docker stats 读的就是它们(见 c70)。</p>'),
     ('暂停', '<p>docker pause 把 <code>cgroup.freeze</code> 写成 1,<code>cgroup.events</code> 里 frozen 变成 1;unpause 写回 0。按我的理解进程没有收到信号,只是被内核冻住,这一点没有专门验证。</p>'),
     ('生命周期', '<p>容器停止后,这个 cgroup 目录随之删除。</p>')],
    steps,
    [ENV_C + '。cgroup 目录在虚拟机里用特权容器加 nsenter 读取(方法见 c19),目录用 find 按容器 ID 定位;容器参数:--cpus 0.5 --memory 100m --memory-swap 100m --pids-limit 50 --cpu-shares 512 --cpuset-cpus 0-1 --device-write-bps /dev/vda:1mb;PID 与容器 ID 每次运行不同;实验后已删除容器',
     '没有验证:cgroup v1 的目录结构、memory.high / memory.low 的行为(c36 里 --memory-reservation 对应 memory.low)、io.weight、hugetlb 与 rdma 控制器、嵌套 cgroup(容器里再建子 cgroup)、cgroup 的 BPF 设备过滤(见 c45)'],
    'cgroup 文件')
