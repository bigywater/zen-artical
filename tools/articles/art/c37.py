from lib import *
S = SS('c37')
steps = [
    step("--memory 32m、--memory-swap 32m,python 不停分配内存:docker run 退出码 137,State.OOMKilled=True、ExitCode=137。docker events 的序列是 create → attach → start → oom → die——die 之前多了一个 oom 事件。进到虚拟机看内核日志(dmesg),有形如“Memory cgroup out of memory: Killed process 74249 (python) total-vm:41996kB, anon-rss:32104kB … oom_score_adj:0”的行,anon-rss 约 32 MB,正是容器的内存上限。", t=tl(S(1)), done=lidx(S(1), 'docker events', 'docker run 退出码'), mark=lidx(S(1), '虚拟机内核日志'), kv=KV([['docker', 'OOMKilled=True,ExitCode 137,events 里有 oom'], ['内核日志', 'Memory cgroup out of memory: Killed process … (python)'], ['被杀进程的 anon-rss', '约 32104 kB(≈ 内存上限)']], ['内核日志'])),
    step("容器里有多个进程时:--memory 48m,sh 起了 sleep 600 加一个吃内存的 python。python 被杀(日志:子进程 python 结束 状态 137 | Killed),但容器 5 秒后 Status=running,OOMKilled=True——内核只杀了最吃内存的那个进程,其它进程(两个 sleep)还活着。容器没有因此退出,OOMKilled 标志却已经是 True。", t=tl(S(2)), done=lidx(S(2), '容器里还活着的进程'), mark=lidx(S(2), '5 秒后容器'), kv=KV([['被杀的进程', '吃内存的 python,状态 137'], ['容器', 'Status=running,但 OOMKilled=True'], ['别的进程', '两个 sleep 还活着']], ['容器'])),
    step("cgroup 的 memory.events:max 37(碰到上限 37 次)、oom 1、oom_kill 1、oom_group_kill 0;memory.events.local 里 oom_kill 1。碰到上限不等于被杀:先回收内存,回收不了才触发 OOM(oom_kill 计数加一)。", t=tl(S(3)), done=lidx(S(3), 'memory.events:'), mark=lidx(S(3), 'oom_kill'), b=bars([['max(碰到上限)', 37, '37'], ['oom', 1, '1'], ['oom_kill', 1, '1']], 37, done=[0], mark=[1, 2]), kv=KV([['max', '37 次碰到上限'], ['oom / oom_kill', '各 1 次'], ['oom_group_kill', '0']], ['oom / oom_kill'])),
    step("--oom-kill-disable 在这台 cgroup v2 的 Docker Desktop 上没有生效:docker run 输出 WARNING: Your kernel does not support OomKillDisable. OomKillDisable discarded.;4 秒后容器 Status=exited、OOMKilled=True,HostConfig.OomKillDisable 是空——照样被杀。", t=tl(S(4)), done=lidx(S(4), 'WARNING'), mark=lidx(S(4), '4 秒后'), kv=KV([['--oom-kill-disable', '被丢弃,打印 WARNING'], ['结果', '容器照样被 OOM 杀死']], ['结果'])),
]
A = mkartc('c37', 37, 'Docker,OOM,oom killer,OOMKilled,memory.events,dmesg,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测容器 OOM:退出码 137、OOMKilled=True,docker events 里 die 前有 oom 事件,虚拟机内核日志有 “Memory cgroup out of memory: Killed process … (python)”;多进程容器里只杀吃内存的进程,容器仍 running 但 OOMKilled 已是 True;cgroup 的 memory.events 里 max 37、oom_kill 1;--oom-kill-disable 在 cgroup v2 上被丢弃。',
    '容器因为内存不足被杀,到底留下哪些证据?谁被杀、容器退不退出、怎么在 docker 和内核两边查到?这篇逐项复现:退出码、OOMKilled 标志、docker events、dmesg、cgroup 的 memory.events,以及 --oom-kill-disable 的下场。',
    [('oom → die', 'docker events 里 OOM 的容器,die 之前会多出一个 oom 事件'), ('running 且 OOMKilled=True', '多进程容器里只有吃内存的进程被杀,容器没退出,标志已经是 True'), ('max 37 / oom_kill 1', 'memory.events:碰到上限 37 次,真正触发 OOM 杀进程 1 次')],
    [('三处证据', '<p>docker 这边:退出码 137、<code>State.OOMKilled=True</code>、events 里有 <code>oom</code>。内核这边:虚拟机的 dmesg 里有 <code>Memory cgroup out of memory: Killed process … (python)</code>,anon-rss 约 32 MB,与容器的上限吻合。cgroup 这边:<code>memory.events</code> 的 oom_kill 计数。</p>'),
     ('多进程容器', '<p>内核杀的是进程,不是容器。容器里有 sleep 和吃内存的 python,只有 python 被杀,容器还在运行,但 OOMKilled 已经是 True。如果被杀的恰好是 PID 1,容器才会退出。看到 OOMKilled=True 不代表容器已经停了(我没有测被杀的是 PID 1 以外且容器继续服务的情形对应用的实际影响)。</p>'),
     ('memory.events', '<p><code>max</code> 是碰到上限的次数(37 次),不代表被杀;按我的理解,内核会先尝试回收内存,回收不了才 OOM,最终 <code>oom_kill</code> 为 1(回收的过程我没有观察)。</p>'),
     ('--oom-kill-disable', '<p>这个环境(cgroup v2)下 <code>--oom-kill-disable</code> 会被丢弃,docker 打印 WARNING,容器照样被杀。cgroup v1 的行为我没有测。</p>')],
    steps,
    [ENV_C + '。吃内存的程序是 python 的循环分配 5 MiB 并写入;内核日志取自虚拟机里的 dmesg(特权容器加 nsenter,方法见 c19),dmesg 里还有此前其它实验的 OOM 记录,文中只引用本次对应的那一行;memory.events 取自容器 cgroup;每种情形运行一次;实验后已删除容器',
     '没有验证:cgroup v1、oom_score_adj 对杀谁的影响、memory.oom.group(整组杀)、宿主机整体内存耗尽时的全局 OOM、PID 1 被杀时容器的退出、应用对 OOM 的感知与恢复'],
    'OOM 杀手')
