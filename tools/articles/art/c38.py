from lib import *
S = SS('c38')
steps = [
    step("--pids-limit 在容器的 cgroup 里是 pids.max:不限制 → max;--pids-limit 100 → 100;--pids-limit -1 → max。刚启动的容器 pids.current=2(sh 和读文件的 cat)。", t=tl(S(1)), done=lidx(S(1), '--pids-limit 100'), mark=lidx(S(1), '不限制', '-1'), kv=KV([['不限制 / -1', 'pids.max = max'], ['--pids-limit 100', 'pids.max = 100']], ['--pids-limit 100'])),
    step("线程也占进程数:--pids-limit 50,Python 不停创建线程,创建了 49 个后失败(can't start new thread),此时 pids.current = 50(49 个线程加主线程)。", t=tl(S(2)), done=lidx(S(2), '创建了 49 个线程'), b=bars([['创建成功的线程', 49, '49'], ['pids.current', 50, '50'], ['--pids-limit', 50, '50']], 50, done=[0, 1], mark=[2]), kv=KV([['--pids-limit 50', '线程也计数'], ['创建失败', "can't start new thread"]], ['--pids-limit 50'])),
    step("在 --pids-limit 64、--memory 128m、--cpus 1 的容器里跑 fork 炸弹(bomb() { bomb | bomb & }; bomb),3 秒后:pids.current 读到 65、pids.events 里 max 35(35 次 fork 因为到上限而失败);docker stats 显示 64 个进程,内存 1.391MiB / 128MiB;docker stop -t 2 退出码 0,用时 2151 ms;docker ps 正常——炸弹被关在容器的进程数上限里,没有影响到虚拟机里的 docker。pids.current 读到的 65 比上限 64 多 1,可能是 docker exec 进来读文件的那个进程,我没有查。", t=tl(S(3)), done=lidx(S(3), 'docker stats', 'docker ps'), mark=lidx(S(3), 'pids.events', 'docker stop -t 2'), b=bars([['--pids-limit', 64, '64'], ['docker stats 的 PIDS', 64, '64'], ['pids.events max(fork 失败次数)', 35, '35']], 64, done=[1], mark=[2]), kv=KV([['进程数', '64(上限),pids.events max 35 次'], ['内存', '1.391MiB / 128MiB'], ['docker stop', '2151 ms,docker ps 正常']], ['进程数'])),
]
A = mkartc('c38', 38, 'Docker,pids-limit,fork炸弹,cgroup,pids.max,线程,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 --pids-limit:对应 cgroup 的 pids.max(不限制是 max);线程也算进程数(limit 50 创建了 49 个线程后失败);--pids-limit 64 的容器里跑 fork 炸弹,进程数停在 64、pids.events 里 35 次 fork 失败,docker stop 与 docker ps 都正常。',
    '容器里的 fork 炸弹会不会拖垮整台机器?--pids-limit 到底限制什么,线程算不算?这篇在受限的容器里实测:cgroup 的 pids.max、线程计数、fork 炸弹被关在多大的范围内。',
    [('49 个线程', '--pids-limit 50 的容器里,Python 能再创建的线程数(线程也占 pid)'), ('pids.events max 35', 'fork 炸弹被 --pids-limit 64 挡住时,cgroup 记录的 fork 失败次数'), ('2151 ms', '被炸弹占满进程数的容器 docker stop -t 2 的用时(退出码 0)')],
    [('cgroup 里的值', '<p><code>--pids-limit 100</code> 对应 <code>pids.max = 100</code>;不设置或设 -1 就是 <code>max</code>。Docker 默认不限制进程数。</p>'),
     ('线程也算', '<p>--pids-limit 50 下创建线程,到第 50 个(含主线程)就失败了,报 <code>can\'t start new thread</code>。线程多的程序(Java、Go 的大量线程)设置过小的 pids-limit 会遇到这种错误。</p>'),
     ('fork 炸弹', '<p>--pids-limit 64 把炸弹限制在 64 个进程里,cgroup 的 <code>pids.events</code> 记录了 35 次因上限失败的 fork;docker stats 显示 64 个进程、内存仅 1.391MiB,docker stop 和 docker ps 都正常。我同时加了 128m 内存和 1 个 CPU 的限制作为保险,所以这个实验没有单独验证「只靠 pids-limit」能保护多少资源,也没有在没有限制的容器里跑炸弹(那样会危险)。</p>')],
    steps,
    [ENV_C + '。fork 炸弹是 sh 函数 bomb() { bomb | bomb & },只在 --pids-limit 64 --memory 128m --cpus 1 的容器里运行,3 秒后检查并停止;线程测试用 Python threading;pids.max、pids.current、pids.events 取自容器 cgroup;每种情形运行一次;实验后已删除容器',
     '没有验证:不设 pids-limit 的 fork 炸弹(不做)、Docker Desktop 虚拟机整体的 pid 上限、cgroup v1 的行为、pids-limit 与 ulimit nproc 的相互作用(nproc 见 c33)、pids.current 比上限多 1 的原因'],
    '进程数限制')
