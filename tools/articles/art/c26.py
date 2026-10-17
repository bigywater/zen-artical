from lib import *
S = SS('c26')
steps = [
    step("docker create 之后:Status=created、Running=False、Pid=0、ExitCode=0,StartedAt 和 FinishedAt 都是零值;docker ps(不带 -a)里没有它,docker ps -a 的 STATUS 是 Created;网络里还没有 IP。docker start 之后:Status=running、Running=True、Pid>0,StartedAt 有值,docker ps -a 的 STATUS 是 Up Less than a second,有了 IP。", t=tl(S(1)), done=lidx(S(1), 'docker start 之后'), mark=lidx(S(1), 'docker create 之后', 'docker ps(不带 -a)'), kv=KV([['create 之后', 'Status=created,Pid=0,没有 IP'], ['start 之后', 'Status=running,Pid>0,有 IP'], ['docker ps', 'created 的容器要 -a 才看得到']], ['create 之后'])),
    step("docker pause:Status=paused,Running 仍是 True、Paused=True,Pid 还在。unpause 后回到 running。docker stop -t 1(sh 是 PID 1,没有处理信号):耗时约 1.1 秒,Status=exited、ExitCode=137、FinishedAt 有值。对已停止的容器 docker exec,退出码 1,报错;再 docker start,Status=running,之前写进 /f 的内容 hi 还在,RestartCount=0(手动 start 不计入)。", t=tl(S(2)), done=lidx(S(2), 'docker unpause', '再 docker start'), mark=lidx(S(2), 'docker pause', 'docker stop -t 1'), kv=KV([['pause', 'Status=paused,Running 仍为 True'], ['stop', 'exited,ExitCode=137'], ['再 start', '可写层的文件还在']], ['再 start'])),
    step("docker rm 对运行中的容器退出码 1,报 cannot remove container(…)必须先停止或用 -f;docker rm -f 退出码 0。", t=tl(S(3)), done=lidx(S(3), 'docker rm -f'), mark=lidx(S(3), '运行中的容器'), kv=KV([['docker rm 运行中的容器', '退出码 1'], ['docker rm -f', '退出码 0']], ['docker rm -f'])),
    step("用 docker events 看事件序列:docker run --rm 一套是 create → attach → start → die → destroy。分步做 create、start、stop、rm 是 create → start → kill(信号 15) → kill(信号 9) → stop → die → destroy——docker stop 先发 15,等超时后再发 9。", t=tl(S(4)), done=lidx(S(4), 'create → attach'), mark=lidx(S(4), 'kill(信号 15)'), kv=KV([['docker run --rm', 'create → attach → start → die → destroy'], ['stop 的 kill', '先 15,再 9']], ['stop 的 kill'])),
    step("各步骤用时(5 次中位数):docker create 76 ms、docker start -a(运行 true 并退出)168 ms、docker rm 52 ms,docker run --rm alpine true 整套 243 ms。第一次通常更慢。", t=tl(S(5)), done=lidx(S(5), 'run --rm true'), mark=lidx(S(5), 'start:'), b=bars([['create (ms)', 76, '76'], ['start -a (ms)', 168, '168'], ['rm (ms)', 52, '52'], ['run --rm 整套 (ms)', 243, '243']], 243, done=[0, 2], mark=[1, 3]), kv=KV([['create', '76 ms'], ['start', '168 ms'], ['rm', '52 ms'], ['run --rm 整套', '243 ms']], ['run --rm 整套'])),
]
A = mkartc('c26', 26, 'Docker,容器生命周期,docker run,状态机,docker events,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测容器的状态机:created(Pid=0、没有 IP)→ running → paused → exited(stop -t 1 后 ExitCode 137)→ 再 start 可写层仍在;docker run --rm 的事件是 create → attach → start → die → destroy,docker stop 会先后发出信号 15 和 9;一次 docker run --rm true 约 243 ms。',
    'docker run 一条命令背后是 create 加 start,容器还有 created、paused、exited 这些状态。这篇逐个状态读 docker inspect,再用 docker events 看完整事件序列,并量一下各步骤的用时。',
    [('created / Pid=0', 'docker create 之后:没有进程、没有 IP,docker ps 不带 -a 看不见'), ('信号 15 → 9', 'docker stop 在 docker events 里依次出现的两个 kill 事件'), ('243 ms', 'docker run --rm alpine true 整套的中位数(create 76 + start 168 左右)')],
    [('create 之后', '<p><code>docker create</code> 之后容器处于 <code>created</code>:没有进程(Pid=0),StartedAt 是零值,没有 IP,<code>docker ps</code> 不加 <code>-a</code> 看不到它。<code>docker start</code> 之后才有进程和网络。</p>'),
     ('暂停与停止', '<p>pause 的容器 Running 仍是 True,Paused 是 True;stop 之后 exited,可写层的文件在,再 start 同一个容器可以继续用(RestartCount 仍是 0,只有重启策略触发的才计数,这一点我只验证了手动 start 的情形)。本文里 sh 是 PID 1、不处理 SIGTERM,所以 <code>-t 1</code> 等满 1 秒才被杀(ExitCode 137,见后面的退出码一篇)。</p>'),
     ('删除', '<p>运行中的容器必须 <code>docker rm -f</code> 才能删。</p>'),
     ('事件序列', '<p>docker events 里,run --rm 是 create → attach → start → die → destroy;stop 会产生两个 kill 事件,信号分别是 15 和 9,然后是 stop、die。</p>'),
     ('耗时', '<p>create 约 76 ms,start 约 168 ms,rm 约 52 ms,run --rm 整套约 243 ms(5 次中位数,波动明显)。这些数字包含 docker CLI 进程启动的开销。</p>')],
    steps,
    [ENV_C + '。状态取自 docker inspect 的 State;事件取自 docker events --since/--until 并按容器名过滤(过滤后没有网络事件);耗时用 Python time.time 测 docker CLI 调用,5 次取中位数;实验后已删除容器',
     '没有验证:restarting 与 dead 状态、重启策略下的 RestartCount(见后面的重启策略一篇)、docker kill 与 stop 的差别、容器内进程树(见 containerd shim 一篇)、docker events 里的网络事件'],
    '容器生命周期')
