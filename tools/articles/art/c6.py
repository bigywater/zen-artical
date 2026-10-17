from lib import *
S = SS('c6')
steps = [
    step("docker stop -t 3 对不同写法的容器。app.sh 捕获 SIGTERM、打印后 exit 0。exec 形式 ENTRYPOINT [\"/app.sh\"]:用时 0.10 秒,退出码 0,日志有“收到 SIGTERM”,PID=1;shell 形式、单条命令 ENTRYPOINT /app.sh:0.08 秒,退出码 0,PID=1(sh 把它 exec 了);shell 形式、复合命令 ENTRYPOINT /app.sh && echo done:用时 3.13 秒(等满了 -t 3),退出码 137,日志只有“app 启动,PID=7”,没有收到信号;改成 ENTRYPOINT exec /app.sh:0.13 秒,退出码 0。没有信号处理的 sleep 300 作为 PID 1(exec 形式):3.16 秒,退出码 137;同样加 docker run --init:0.13 秒,退出码 143。", t=tl(S(1)), done=lidx(S(1), 'exec 形式 ENTRYPOINT ["/app.sh"]', '单条命令', 'exec 接管', '--init'), mark=lidx(S(1), '复合命令 ENTRYPOINT /app.sh && echo done', '没有信号处理'), b=bars([['exec 形式:docker stop 用时 (秒)', 0.10, '0.10'], ['shell 复合命令', 3.13, '3.13'], ['sleep 作 PID 1 无处理', 3.16, '3.16'], ['同上加 --init', 0.13, '0.13']], 3.16, done=[0, 3], mark=[1, 2]), kv=KV([['exec 形式 / 单条命令 / exec 接管', '信号送到程序,0.1 秒内干净退出'], ['复合 shell 命令', 'PID 1 是 sh,不转发 SIGTERM,等满超时后 137'], ['没有信号处理的 PID 1', '同样等满超时后 137'], ['--init', '0.13 秒,退出码 143']], ['复合 shell 命令'])),
    step("PID 1 的特殊性:容器内对 PID 1(sleep 300,没有信号处理)发 kill -TERM 1,1 秒后 ps 里它还在(1 sleep 300);同一个容器里另起一个 sleep 300(PID 不是 1),对它发 kill -TERM,退出码 143(128 + 15,被 SIGTERM 终止)。", t=tl(S(2)), mark=lidx(S(2), '1 sleep 300'), done=lidx(S(2), '退出码 143'), kv=KV([['PID 1,无处理函数', 'SIGTERM 不会终止它'], ['非 PID 1', '默认动作终止,退出码 143']], ['PID 1,无处理函数'])),
    step("从宿主机发信号也是一样:docker kill --signal TERM(sleep 300 作为 PID 1,没有信号处理),1 秒后容器状态仍是 running;接着 docker stop -t 2:用时 2.13 秒,退出码 137。", t=tl(S(3)), mark=lidx(S(3), 'running', '137'), kv=KV([['docker kill --signal TERM', '1 秒后仍在运行'], ['docker stop -t 2', '等满 2 秒后 SIGKILL,退出码 137']], ['docker stop -t 2'])),
]
A = mkartc('c6', 6, 'Docker,PID 1,信号,exec形式,shell形式,docker stop,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测信号能不能传到你的程序:exec 形式、单条 shell 命令和 exec 接管都能在 0.1 秒内收到 SIGTERM 并退出(退出码 0);复合 shell 命令让 PID 1 变成 sh,docker stop 等满超时 3.13 秒后以 137 结束;没有信号处理的程序当 PID 1 会忽略 SIGTERM(3.16 秒,137),加 --init 后 0.13 秒、退出码 143。',
    '“为什么我的容器 docker stop 要等那么久?”(默认的等待时间随环境配置而不同,这台 Docker Desktop 是 3 秒,见 c30)几乎总是因为 SIGTERM 没有到达你的程序,或者你的程序作为 PID 1 没有处理函数。这篇把几种写法并排跑一遍,测 docker stop 的用时和退出码,再验证 PID 1 对 SIGTERM 的特殊对待。',
    [('3.13 秒 / 137', '复合 shell 命令的 ENTRYPOINT:PID 1 是 sh,docker stop -t 3 等满超时后被 SIGKILL'), ('0.10 秒 / 0', 'exec 形式的 ENTRYPOINT:信号直达程序,干净退出'), ('--init:0.13 秒 / 143', '没有信号处理的 sleep 加 --init 后,docker stop 立刻结束')],
    [('谁是 PID 1', '<p>exec 形式和 <code>exec /app.sh</code> 接管后,程序自己就是 PID 1,<code>docker stop</code> 发的 SIGTERM 它能收到;复合 shell 命令(<code>/app.sh &amp;&amp; echo done</code>)让 <code>/bin/sh</code> 当 PID 1,程序成了 PID 7 的子进程,sh 不转发信号,日志里程序根本没收到 SIGTERM,等满超时后被强杀(137)。</p>'),
     ('PID 1 不会被默认动作杀死', '<p>容器里对 PID 1 发 <code>kill -TERM 1</code>,没有信号处理函数的 <code>sleep 300</code> 1 秒后还在;同一个容器里另一个 <code>sleep 300</code>(PID 不是 1)被同样的信号杀死(退出码 143)。内核对 PID 1 的默认信号动作做了保护。我没有读内核源码,这是现象。</p>'),
     ('docker kill 与 docker stop', '<p>从宿主机用 <code>docker kill --signal TERM</code> 发信号,PID 1 的 <code>sleep</code> 1 秒后仍是 running;<code>docker stop -t 2</code> 等满 2 秒后发 SIGKILL,退出码 137。加 <code>--init</code>(容器里多一个 init 进程负责转发信号并回收子进程)后,同样的 <code>sleep</code> 在 0.13 秒内以 143 退出。</p>')],
    steps,
    [ENV_C + '。app.sh 是一个 trap 了 SIGTERM 的 sh 脚本;docker stop -t 3(或 -t 2)的用时用 Python time.time 测;退出码取 docker inspect 的 State.ExitCode;日志取 docker logs;每种写法只运行一次;实验后已删除所有镜像和容器',
     '没有验证:bash / dash 作为 PID 1 的差别、Python / Node / Java 程序作为 PID 1 时的默认信号行为、tini 与 docker run --init 的内部差异(后面有专门一篇)、docker stop --signal / STOPSIGNAL 指令(后面也有专门一篇)、子进程孤儿的回收'],
    'exec 与 shell 形式')
