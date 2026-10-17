from lib import *
S = SS('k28')
F1 = [['T0 删除', 'deletionTimestamp'], ['+0.15 s', '端点 ready=false, terminating'], ['preStop', '+0.13 → +5.13 s'], ['SIGTERM', '+5.15 s'], ['应用退出', '+6.15 s'], ['端点消失', '+6.32 s']]
F2 = [['T0 删除', ''], ['preStop(true)', '瞬间结束'], ['SIGTERM', '+0.07 s'], ['应用退出', '+1.08 s']]
F3 = [['preStop 睡 10 秒', '+0.07 s 开始'], ['宽限期 6 秒到', '钩子被截断'], ['SIGTERM', '+6.07 s'], ['再给 2 秒', '+8.1 s SIGKILL'], ['Pod 消失', '+8.5 s']]
F4 = [['preStop exit 1', '+0.11 s'], ['SIGTERM', '+0.12 s'], ['事件', 'FailedPreStopHook'], ['应用退出', '+1.12 s']]
PANELS = [('f', 'flow', '删除 Pod 的时间线'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("preStop 睡 5 秒、应用收到 SIGTERM 后再睡 1 秒才退出。以 kubectl delete 的发出时刻为 T0:+0.13 秒 preStop 开始,+5.13 秒结束,SIGTERM 在 +5.15 秒才到,+6.15 秒应用退出;kubectl delete 一共等了 7.2 秒。同时 EndpointSlice 里端点在 +0.15 秒就变成 (ready=false, serving=true, terminating=true),流量在 preStop 开始时就被摘掉,端点在 +6.32 秒才消失。", f=fl(F1, cur=[2, 3], done=[0, 1, 4, 5]), t=tl(S(1), mark=lidx(S(1), 'prestop-start', 'prestop-end', 'sigterm', '(False, True, True)'), done=lidx(S(1), 'exit', '(没有端点)')), kv=KV([['顺序', 'preStop 先于 SIGTERM'], ['端点', '删除时立刻摘掉,不等 preStop'], ['preStop 睡一会儿', '给负载均衡留下摘除的时间']], ['顺序'])),
    step("对照:preStop 是空命令 true:SIGTERM 在 +0.07 秒就到,+1.08 秒退出,kubectl delete 用了 1.5 秒;端点同样在 +0.08 秒变成 terminating。", f=fl(F2, cur=[2], done=[0, 1, 3]), t=tl(S(2), mark=lidx(S(2), 'sigterm'), done=lidx(S(2), 'exit')), kv=KV([['没有 preStop', 'SIGTERM 几乎立刻到'], ['端点摘除与 SIGTERM', '几乎同时,存在短暂的流量竞争']], ['没有 preStop'])),
    step("preStop 睡 10 秒、terminationGracePeriodSeconds=6、应用收到 SIGTERM 后要 5 秒才肯退出:+0.07 秒 preStop 开始;+6.07 秒宽限期用完,钩子被截断,SIGTERM 才送达;应用没来得及退出(日志里没有 exit),Pod 在 +8.5 秒消失——SIGTERM 之后又被额外给了约 2 秒才 SIGKILL;事件有 FailedPreStopHook: PreStopHook failed。", f=fl(F3, cur=[1, 2], mark=[3], done=[0, 4]), t=tl(S(3), mark=lidx(S(3), 'sigterm', '用了 8.5 秒'), done=lidx(S(3), 'prestop-start', 'FailedPreStopHook')), kv=KV([['preStop 占用宽限期', '它和应用退出共用同一份预算'], ['超出', '钩子被截断,SIGTERM 才发'], ['最后的 2 秒', 'kubelet 在宽限期用完后还会多给 2 秒']], ['preStop 占用宽限期'])),
    step("preStop 执行 exit 1:+0.11 秒钩子失败,SIGTERM 紧接着在 +0.12 秒到,+1.12 秒应用退出,kubectl delete 用了 1.6 秒;事件 FailedPreStopHook: PreStopHook failed。钩子失败不会阻止终止。", f=fl(F4, cur=[0], done=[1, 3], mark=[2]), t=tl(S(4), mark=lidx(S(4), 'prestop-fail', 'FailedPreStopHook'), done=lidx(S(4), 'sigterm', 'exit')), kv=KV([['preStop 失败', '记事件,终止照常进行'], ['不能靠 preStop 保证一定做完', '它可能被截断或失败']], ['preStop 失败'])),
]
A = mkartk('k28', 28, 'Kubernetes,preStop,优雅终止,SIGTERM,terminationGracePeriodSeconds,EndpointSlice,真实验证,动画演示',
    '在 kind 集群里量出删除 Pod 的时间线:preStop 睡 5 秒时 SIGTERM 在 +5.15 秒才到、应用 +6.15 秒退出,而 EndpointSlice 里端点在 +0.15 秒就变成 terminating(ready=false);没有 preStop 时 SIGTERM 在 +0.07 秒到;preStop 比宽限期还长时钩子被截断,SIGTERM 在 +6.07 秒送达、SIGKILL 约在 +8.1 秒,Pod 8.5 秒后消失;preStop 失败只产生 FailedPreStopHook 事件,终止照常进行。',
    '优雅退出的时序到底是什么?preStop 睡一会儿真的能让负载均衡有时间摘除吗?宽限期是怎么被 preStop 和应用退出分掉的?这篇用节点上的 /proc/uptime 时间戳和 EndpointSlice 的状态变化,把删除一个 Pod 的每一步都对到同一条时间轴上。',
    [('+0.15 s vs +5.15 s', '端点被标记 terminating 的时刻,与 preStop 睡 5 秒之后 SIGTERM 送达的时刻'), ('+6.07 s', 'preStop 比宽限期(6 秒)还长时,SIGTERM 终于送达的时刻——钩子被截断'), ('8.5 秒', '宽限期 6 秒、应用 5 秒才肯退出时,kubectl delete 到 Pod 消失的耗时(SIGTERM 后又多给了约 2 秒)')],
    [('preStop 在 SIGTERM 之前', '<p>以 <code>kubectl delete</code> 发出的时刻为 T0:+0.13 秒 preStop 开始,+5.13 秒结束,SIGTERM 在 +5.15 秒才到,+6.15 秒应用退出,<code>kubectl delete</code> 一共等了 7.2 秒。EndpointSlice 里这个端点在 +0.15 秒就变成 <code>(ready=false, serving=true, terminating=true)</code>:从被删除那一刻起 Service 就不再把新流量发给它,不用等 preStop。常见的 <code>preStop: sleep 5</code> 就是利用这段时间,让负载均衡、kube-proxy 有机会把它摘掉,再收到 SIGTERM。</p>'),
     ('没有 preStop 的对照', '<p>preStop 是空命令时 SIGTERM 在 +0.07 秒就到,端点在 +0.08 秒变成 terminating,两件事几乎同时发生——如果负载均衡摘除得慢,就有新请求被送到一个已经开始关闭的进程。这是为什么要用 preStop 睡一会儿。</p>'),
     ('钩子与宽限期共用预算', '<p>preStop 睡 10 秒但 <code>terminationGracePeriodSeconds</code> 只有 6 秒:+6.07 秒宽限期用完,钩子被截断(事件 <code>FailedPreStopHook</code>),SIGTERM 这时才送达;应用要 5 秒才肯退出,来不及了,Pod 在 +8.5 秒消失——SIGTERM 之后又被额外给了约 2 秒才被 SIGKILL,日志里没有应用的 <code>exit</code>。所以 preStop 的时间要计入宽限期,宽限期要设得比 preStop 加应用退出时间更大。</p>'),
     ('preStop 失败', '<p>钩子 <code>exit 1</code>:事件 <code>FailedPreStopHook: PreStopHook failed</code>,但终止照常进行——SIGTERM 紧接着在 +0.12 秒到,应用 +1.12 秒退出。preStop 不能当作“一定会执行完的清理步骤”;重要的清理要写在应用自己处理 SIGTERM 的代码里。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);应用是 busybox sh,trap TERM 后写日志、睡指定秒数、写日志、退出,日志写在 hostPath 卷里,时间取自 /proc/uptime,T0 取删除前一刻节点的 uptime;EndpointSlice 每 50 毫秒轮询一次(宿主机时钟),两种时钟之间有几十毫秒误差;Service 没有 readinessProbe;每种情形各一次,Pod 消失用时包含 kubectl 的开销',
     '没有验证:真实的流量(没有用客户端持续请求去观察丢包);kube-proxy 在各节点上摘除规则的延迟;preStop 用 httpGet 与 sleep 类型(sleep 钩子)的差别;terminationGracePeriodSeconds 被 kubectl delete --grace-period 覆盖的情形(下一篇);ingress / 云负载均衡的摘除时间;多容器 Pod 的终止顺序'],
    '删除时间线', PANELS)
