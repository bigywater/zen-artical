from lib import *
S = SS('k26')
F1 = [['i1', '0.00 → 2.00 s'], ['i2', '2.96 → 4.96 s'], ['i3', '5.74 → 7.75 s'], ['app', '8.75 s 才启动']]
F2 = [['init 容器 exit 1', 'Init:Error'], ['退避', 'Init:CrashLoopBackOff'], ['第 3 次成功', 'PodInitializing'], ['app', 'Running(+14.1s)']]
F3 = [['init 请求 10m', '调度到 worker2'], ['init 请求 100 核', 'Unschedulable'], ['每节点', 'allocatable 10 核']]
F4 = [['init setup', '运行 1 次'], ['app', '崩溃重启 2 次'], ['共享卷日志', 'setup-ran ×1,app-start ×3']]
PANELS = [('f', 'flow', 'init 容器'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("三个 init 容器各睡 2 秒,按顺序执行:i1 0.00→2.00 秒,i2 2.96→4.96 秒,i3 5.74→7.75 秒,应用容器 app 在 8.75 秒才启动——每个容器之间有约 1 秒的启动间隔。kubectl get 的 STATUS:Init:0/3(+0.1s)→ Init:1/3(+3.5s)→ Init:2/3(+6.6s)→ Running(+9.4s);三个 init 容器都 terminated(exitCode=0),Initialized=True。", f=fl(F1, cur=[0, 1, 2], done=[3]), t=tl(S(1), mark=lidx(S(1), 'Init:0/3', 'i1   start', 'app  start'), done=lidx(S(1), 'initContainerStatuses')), kv=KV([['顺序执行', '前一个 exit 0 才启动下一个'], ['STATUS', 'Init:N/M 表示完成了 N 个'], ['应用容器', '要等所有 init 容器结束']], ['顺序执行'])),
    step("init 容器失败:前两次 exit 1、第三次成功,STATUS 依次是 Init:0/1 → Init:Error(+1.8s)→ Init:CrashLoopBackOff(+12.8s)→ Init:0/1(+13.3s)→ PodInitializing(+13.7s)→ Running(+14.1s),initContainerStatuses.restartCount=2,应用容器全程没有启动;restartPolicy=Never 的 Pod,init 容器 exit 1 → phase=Failed,STATUS=Init:Error,应用容器 waiting(从未启动)。", f=fl(F2, cur=[1], mark=[0], done=[2, 3]), t=tl(S(2), mark=lidx(S(2), 'Init:Error', 'restartPolicy=Never'), done=lidx(S(2), 'restartCount=2')), kv=KV([['失败', 'init 容器按 restartPolicy 重试,同样有退避'], ['Never', 'init 失败 = Pod Failed'], ['应用容器', '一次都不会启动']], ['失败'])),
    step("init 容器的资源请求也参与调度:init 10m + 应用 100m 的 Pod 正常调度到 kx-main-worker2;init 请求 100 核、应用只要 100m 的 Pod 保持 Pending,PodScheduled=False reason=Unschedulable,message “0/3 nodes are available: … 2 Insufficient cpu”(每个节点 allocatable cpu=10 核)。", f=fl(F3, cur=[1], done=[0]), t=tl(S(3), mark=lidx(S(3), 'req-init-big'), done=lidx(S(3), 'req-app')), kv=KV([['有效请求', 'max(最大的 init 容器, 全部应用容器之和)'], ['init 容器很“重”', '会让整个 Pod 调度不上'], ['init 结束后', '它的资源就释放了,但调度时已经按它算']], ['有效请求'])),
    step("init 容器只在 Pod 启动时运行一次:应用容器 2 秒后 exit 1,28 秒内重启了 2 次;共享卷日志里 setup-ran 出现 1 次、app-start 出现 3 次(每次启动应用容器都追加一行),init 容器 setup 的 restartCount=0——应用容器重启不会重新运行 init 容器。", f=fl(F4, cur=[1], done=[0, 2]), t=tl(S(4), mark=lidx(S(4), 'setup-ran 出现 1 次')), kv=KV([['init 容器', '一次性,只为 Pod 启动做准备'], ['应用容器崩溃重启', '不会重新执行 init'], ['想让它重做', '要重建 Pod']], ['init 容器'])),
]
A = mkartk('k26', 26, 'Kubernetes,init 容器,Init:CrashLoopBackOff,Initialized,调度资源,真实验证,动画演示',
    '在 kind 集群里实测 init 容器:三个各睡 2 秒的 init 容器顺序执行(每个之间约 1 秒启动间隔),应用容器在 8.75 秒才启动,STATUS 依次 Init:0/3 → Init:1/3 → Init:2/3 → Running;失败的 init 容器按 restartPolicy 重试并经过 Init:Error 与 Init:CrashLoopBackOff,restartPolicy=Never 时 Pod 直接 Failed;init 容器的资源请求参与调度(请求 100 核导致 Unschedulable);应用容器重启不会重新运行 init 容器。',
    'init 容器怎么保证先于应用容器运行?失败了会怎样?它们的资源请求算不算?应用容器崩溃重启时会不会再来一遍?这篇用带时间戳的共享卷、STATUS 变化和调度结果,把这些问题一一量出来。',
    [('8.75 s', '三个各睡 2 秒的 init 容器之后,应用容器真正启动的时刻(init 结束于 7.75 秒)'), ('Init:CrashLoopBackOff', 'init 容器失败后的 STATUS;restartCount=2、第三次成功后 14.1 秒进入 Running'), ('setup ×1、app ×3', '应用容器重启 2 次后共享卷日志里 init 与应用各自的运行次数')],
    [('按顺序、一个接一个', '<p>三个 init 容器各睡 2 秒,往共享的 emptyDir 里写带时间的日志:i1 在 0.00~2.00 秒、i2 在 2.96~4.96 秒、i3 在 5.74~7.75 秒,应用容器 8.75 秒才启动。每个容器之间还有约 1 秒的启动开销。<code>kubectl get</code> 的 STATUS 显示 <code>Init:0/3</code> → <code>Init:1/3</code> → <code>Init:2/3</code> → <code>Running</code>,三个 init 容器都以 <code>exitCode=0</code> 结束,<code>Initialized</code> 条件为 True。</p>'),
     ('失败了就重试', '<p>一个前两次 <code>exit 1</code>、第三次成功的 init 容器:STATUS 经过 <code>Init:Error</code>、<code>Init:CrashLoopBackOff</code>,等退避结束再重试,第三次成功后 <code>PodInitializing</code> → <code>Running</code>,<code>restartCount=2</code>,应用容器全程没有启动。<code>restartPolicy: Never</code> 的 Pod 里 init 容器失败一次,整个 Pod 就是 <code>Failed</code>(STATUS <code>Init:Error</code>),应用容器从未启动。</p>'),
     ('资源请求也算', '<p>调度器按“所有 init 容器里最大的请求”和“所有应用容器请求之和”两者的较大值来算 Pod 的有效请求。init 容器 10m、应用 100m 的 Pod 正常调度;init 容器请求 100 核、应用只要 100m 的 Pod 保持 <code>Pending</code>,reason <code>Unschedulable</code>,message 里 <code>2 Insufficient cpu</code>(每个节点 10 核)——尽管 init 容器很快就会退出。</p>'),
     ('只运行一次', '<p>应用容器 2 秒后 <code>exit 1</code> 反复重启(28 秒内 2 次),共享卷日志里 <code>setup-ran</code> 只有 1 行、<code>app-start</code> 有 3 行,init 容器 <code>setup</code> 的 <code>restartCount</code> 仍是 0。init 容器是给 Pod 启动做准备的一次性步骤,应用容器重启不会重新运行它们;要让它们重做只能重建 Pod。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);容器之间用 emptyDir 共享日志文件,时间戳取自 /proc/uptime(同一节点上的容器共享内核,可以直接比较,busybox 的 date 不支持 %N);STATUS 取自 kubectl get pod 的第 3 列,每 0.3 秒轮询;失败重试用 emptyDir 里的计数文件实现“前两次失败第三次成功”;每个节点 allocatable cpu 为 10 核;每种情形各一次',
     '没有验证:原生 sidecar(restartPolicy: Always 的 init 容器,后面有专门的文章);init 容器的 securityContext 与镜像拉取失败时的 Init:ImagePullBackOff;activeDeadlineSeconds 对 init 阶段的限制;Pod 重建、节点重启(沙箱被重建)时 init 容器是否重跑;init 容器日志的保留;有效请求在 describe node 的 Allocated resources 里的体现'],
    'init 容器', PANELS)
