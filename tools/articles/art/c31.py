from lib import *
S = SS('c31')
steps = [
    step("容器的 PID 1 是一个创建 50 个马上退出的子进程、但不调用 wait 的 Python 程序:1 秒后容器里有 50 个僵尸进程(总进程数 51)。加 --init(PID 1 换成 docker 自带的 init,python 变成 PID 7)后,僵尸进程仍是 50 个(总进程数 52)——这些子进程的父进程是 python,还活着,init 无权替它收尸。", t=tl(S(1)), done=lidx(S(1), 'PID 1 创建 50 个子进程但不 wait'), mark=lidx(S(1), '加 --init'), b=bars([['PID 1 不 wait:僵尸数', 50, '50'], ['--init,父进程仍不 wait:僵尸数', 50, '50']], 50, done=[], mark=[0, 1]), kv=KV([['父进程活着且不 wait', '僵尸进程一直在'], ['--init', '帮不上忙']], ['--init'])),
    step("孤儿进程(子进程的父进程先退出,被重新挂到 PID 1 下):50 个孤儿,PID 1 是不 wait 的 python → 50 个僵尸(总进程数 51);同样的程序加 --init → 僵尸 0 个,总进程数只有 2。init 的职责就是给孤儿收尸。", t=tl(S(2)), done=lidx(S(2), '加 --init'), mark=lidx(S(2), 'PID 1 是 python 且不 wait'), b=bars([['PID 1 是 python:僵尸数', 50, '50'], ['--init:僵尸数', 0, '0']], 50, done=[1], mark=[0]), kv=KV([['孤儿进程 + PID 1 不 wait', '50 个僵尸'], ['孤儿进程 + --init', '0 个僵尸']], ['孤儿进程 + --init'])),
    step("僵尸进程占着进程号:--pids-limit 40,程序不停创建不 wait 的子进程:第 40 次创建失败,Resource temporarily unavailable,此时 39 个僵尸、总进程数 40。加 --init(python 是 PID 7,仍是父进程)也一样:第 39 次失败,38 个僵尸、总进程数 40。进程数上限到了,哪怕子进程早已退出。", t=tl(S(3)), done=lidx(S(3), '--pids-limit 40,不停创建'), mark=lidx(S(3), '加 --init'), kv=KV([['--pids-limit 40', '39 个僵尸后创建失败'], ['失败信息', 'Resource temporarily unavailable']], ['--pids-limit 40'])),
    step("docker top 看不到僵尸:PID 1 是 python、3 个子进程已退出但没被 wait 的容器,docker top 只列出 python(PID 38280,PPID 38256,STAT Ss);用 docker exec 进去跑 ps,看到 python(S)和 3 个 STAT 为 Z 的 true,PPID 都是 1。要查僵尸进程,别只看 docker top。", t=tl(S(4)), done=lidx(S(4), 'docker top'), mark=lidx(S(4), 'docker exec 里用 ps'), kv=KV([['docker top', '只列出 python'], ['容器里的 ps', '3 个 Z 状态的 true,PPID=1']], ['容器里的 ps'])),
]
A = mkartc('c31', 31, 'Docker,PID 1,僵尸进程,孤儿进程,--init,pids-limit,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测僵尸进程:不 wait 的 PID 1 留下 50 个僵尸;--init 只能收孤儿(孤儿 50 个 → 0 个僵尸),父进程还活着时僵尸照旧 50 个;僵尸占着进程号,--pids-limit 40 下 39 个僵尸后创建子进程失败;docker top 看不到僵尸,容器里的 ps 才看得到。',
    '容器里为什么会出现一堆 &lt;defunct&gt; 进程?--init 到底解决了什么、没解决什么?这篇用会故意不 wait 的 Python 程序复现僵尸进程和孤儿进程,验证 init 的作用边界,以及僵尸进程怎样把 --pids-limit 用光。',
    [('孤儿 50 → 0', '孤儿进程场景,PID 1 是 python 时 50 个僵尸,加 --init 后 0 个'), ('50 个僵尸还在', '父进程活着且不 wait 时,加 --init 也没用'), ('docker top 看不到', '僵尸进程用 docker top 看不见,容器里的 ps 才看得见')],
    [('僵尸是父进程的事', '<p>子进程退出后要由父进程 wait 才会消失。PID 1 创建了 50 个子进程但不 wait,就剩 50 个僵尸;加了 <code>--init</code> 后,python 变成 PID 7,仍是这些子进程的父进程,所以 50 个僵尸照旧。</p>'),
     ('孤儿才轮到 init', '<p>子进程的父进程退出后,孤儿进程被挂到 PID 1 下面。PID 1 是不 wait 的 python 时,这些孤儿退出后变成 50 个僵尸;换成 init(<code>--init</code>)就一个都不剩。这就是容器里需要一个会收尸的 PID 1 的原因。</p>'),
     ('进程数上限', '<p>僵尸进程仍占着进程号。<code>--pids-limit 40</code> 下,不停创建不 wait 的子进程,攒到 39 个僵尸就再也创建不出子进程了(Resource temporarily unavailable)。</p>'),
     ('怎么发现', '<p><code>docker top</code> 只显示了 python,看不到 3 个已退出的子进程;进入容器用 ps 才看到 STAT 为 Z 的 true。我没有查 docker top 为什么不显示它们。</p>')],
    steps,
    [ENV_C + '。测试程序是 python:3.12-alpine 里的小脚本:创建会立刻退出的 true 子进程,1 秒后读 /proc/*/stat 的状态字段统计 Z;--init 使用 Docker 内置的 init(PID 1,python 为 PID 7);每种情形运行一次(现象是确定性的);实验后已删除容器和镜像',
     '没有验证:tini 以外的 init(dumb-init、s6)、僵尸进程对宿主机的影响(进程表耗尽)、PID 1 是 sh 时的收尸行为、Kubernetes 的 shareProcessNamespace、docker top 不显示僵尸的原因'],
    '僵尸进程与 init')
