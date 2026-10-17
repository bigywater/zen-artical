from lib import *
S = SS('c65')
steps = [
    step("容器 sleep 4 秒后才创建 /tmp/ready,健康检查 test -f /tmp/ready(interval 1s、timeout 1s、retries 3)。状态变化:starting(0.0s)→ unhealthy(3.2s)→ healthy(4.2s)——文件还没出现时连续失败了 3 次,先变成 unhealthy,文件出现后第一次检查通过就变回 healthy。Health 对象有 FailingStreak、Log、Status 三个字段;最后一次日志 ExitCode=0、Output 为空;docker ps 的 STATUS 是 Up 4 seconds (healthy)。", t=tl(S(1)), done=lidx(S(1), '状态变化 starting(0.0s) → unhealthy(3.2s) → healthy(4.2s)', 'docker ps'), mark=lidx(S(1), 'Health 对象'), b=bars([['变成 unhealthy (秒)', 3.2, '3.2'], ['变成 healthy (秒)', 4.2, '4.2']], 4.2, done=[1], mark=[0]), kv=KV([['starting', '初始状态'], ['连续失败 retries 次', '变成 unhealthy'], ['检查通过', '立刻变回 healthy']], ['连续失败 retries 次'])),
    step("一直失败的检查(exit 1、interval 1s、retries 3):starting(0.0s)→ unhealthy(3.1s);FailingStreak=3,Log 里 3 条;容器 Status 仍是 running——unhealthy 只是一个标记,容器照样运行。", t=tl(S(2)), done=lidx(S(2), '状态变化', 'FailingStreak=3'), kv=KV([['3 次连续失败', 'unhealthy 约 3.1 秒'], ['容器', '仍是 running']], ['容器'])),
    step("检查命令超时:--health-cmd \"sleep 5\" --health-timeout 1s retries=1:starting(0.1s)→ unhealthy(2.1s);日志里 ExitCode=-1、Output='Health check exceeded timeout (1s)'。超时的检查按失败计算,退出码记作 -1。", t=tl(S(3)), done=lidx(S(3), '状态变化', '日志:ExitCode=-1'), kv=KV([['超时', 'ExitCode=-1'], ['Output', 'Health check exceeded timeout (1s)']], ['超时'])),
    step("--health-start-period:一直失败的检查(retries 2),start-period=0s 时 unhealthy(2.2s);start-period=6s 时要等到 unhealthy(7.1s)。start-period 内的失败不计入重试次数,宽限了启动慢的程序。", t=tl(S(4)), done=lidx(S(4), 'start-period=0s'), mark=lidx(S(4), 'start-period=6s'), b=bars([['start-period=0s:变成 unhealthy (秒)', 2.2, '2.2'], ['start-period=6s:变成 unhealthy (秒)', 7.1, '7.1']], 7.1, done=[0], mark=[1]), kv=KV([['start-period=0s', '2.2 秒后 unhealthy'], ['start-period=6s', '7.1 秒后 unhealthy']], ['start-period=6s'])),
    step("--restart always 加一直失败的健康检查:RestartCount=0、Status=running;docker events 是 create → start → health_status: unhealthy。docker 本身不会因为 unhealthy 重启容器,健康状态只是给编排工具、depends_on(见 c58)用的信号。", t=tl(S(5)), done=lidx(S(5), 'RestartCount=0'), kv=KV([['--restart always + unhealthy', 'RestartCount=0,不重启'], ['events', 'health_status: unhealthy']], ['--restart always + unhealthy'])),
]
A = mkartc('c65', 65, 'Docker,healthcheck,健康检查,start-period,unhealthy,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测健康检查:interval 1s、retries 3 时一直失败约 3 秒变成 unhealthy,检查通过立刻变回 healthy;慢启动的程序在没有 start-period 时会先变成 unhealthy 再变回 healthy;超时的检查记 ExitCode -1;start-period=6s 把变成 unhealthy 推迟到 7.1 秒;unhealthy 的容器不会被 --restart always 重启。',
    'HEALTHCHECK 的各个参数到底怎么起作用?为什么启动慢的程序会闪一下 unhealthy?unhealthy 的容器会被自动重启吗?这篇用可控的检查命令实测状态变化的时间点。',
    [('3.2 → 4.2 秒', '启动慢的程序:先 unhealthy(3.2 秒),文件出现后变回 healthy(4.2 秒)'), ('7.1 秒', 'start-period=6s 时,一直失败的检查变成 unhealthy 的时间(无 start-period 时 2.2 秒)'), ('ExitCode=-1', '健康检查命令超时时记录的退出码')],
    [('状态机与慢启动', '<p>刚启动是 <code>starting</code>;连续失败 retries 次变成 <code>unhealthy</code>;任何一次成功就回到 <code>healthy</code>。<code>docker inspect</code> 的 <code>State.Health</code> 有 Status、FailingStreak 和最近几次的 Log。程序要 4 秒才就绪、检查每秒一次重试 3 次时,容器会在第 3 秒先变成 unhealthy,再在第 4 秒变回 healthy。</p>'),
     ('一直失败', '<p>连续失败 3 次后约 3.1 秒变成 unhealthy,FailingStreak 记录连续失败次数。容器的 Status 仍是 running,unhealthy 只是标记。</p>'),
     ('超时', '<p>超过 <code>--health-timeout</code> 的检查按失败计,日志里 ExitCode=-1,Output 是 <code>Health check exceeded timeout (1s)</code>。</p>'),
     ('start-period', '<p>用 <code>--health-start-period</code> 让启动阶段的失败不计数:一直失败的检查,start-period 为 0 时 2.2 秒变成 unhealthy,为 6s 时推迟到 7.1 秒。给启动慢的程序设置它,可以避免先闪一下 unhealthy。</p>'),
     ('不会重启', '<p>docker 不会因为 unhealthy 重启容器,即便设了 <code>--restart always</code>。它的作用是被 <code>docker compose</code> 的 <code>depends_on</code> 或外部编排消费。</p>')],
    steps,
    [ENV_C + '。检查命令用 test -f、exit 1、sleep 5 等可控的命令;状态变化时间用 Python 每 0.2 秒轮询 docker inspect 记录,误差约 ±0.3 秒;每种配置运行一次;实验后已删除容器',
     '没有验证:Dockerfile 里的 HEALTHCHECK 指令(与 --health-cmd 等价的部分未对比)、--health-start-interval、真实服务的 HTTP 检查、健康检查本身的 CPU 开销、docker events 里 health_status: healthy 的细节'],
    '健康检查')
