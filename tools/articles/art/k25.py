from lib import *
S = SS('k25')
F1 = [['崩溃 #1', '等 1 秒'], ['#2', '等 14 秒'], ['#3', '等 26 秒'], ['#4', '等 45 秒'], ['#5', '等 83 秒'], ['#6', '等 161 秒']]
F2 = [['good 容器', 'restartCount=0,running'], ['bad 容器', 'restartCount=6'], ['Pod', 'Running,READY 1/2'], ['STATUS', 'Error']]
F3 = [['restartPolicy: Never', ''], ['容器 exit 1', 'terminated'], ['phase', 'Failed'], ['没有重启', '没有 CrashLoopBackOff']]
F4 = [['删除 crash', ''], ['重新创建同名 Pod', ''], ['第 1 次重启', '等 0 秒'], ['第 2 次', '等 14 秒']]
PANELS = [('f', 'flow', '重启退避'), ('t', 'term', '实测输出'), ('b', 'bars', '每次重启前的等待(秒)'), ('kv', 'kv', '要点')]
steps = [
    step("容器 sleep 1 后 exit 1,restartPolicy 默认 Always,观察 345 秒:第 1 次重启等了 1 秒,之后每次崩溃后等待翻倍——14、26、45、83、161 秒(约 10、20、40、80、160 秒加上 1~5 秒的开销);第 6 次重启发生在 Pod 第一次启动后 336 秒,而每个容器实例都只运行 1 秒。kubectl get 的 STATUS 大部分时间是 Error,容器刚起来的 1 秒是 Running,CrashLoopBackOff 只在第 254~338 秒出现了一次;事件 BackOff 累计 count=8。", f=fl(F1, cur=[1, 2, 3, 4, 5], done=[0]), t=tl(S(1), mark=lidx(S(1), '第 2 次重启', '第 3 次重启', '第 4 次重启', '第 5 次重启', '第 6 次重启', 'CrashLoopBackOff(+254s)'), done=lidx(S(1), '第 1 次重启', '事件 BackOff')), b=bars([['#1', 1, '1'], ['#2', 14, '14'], ['#3', 26, '26'], ['#4', 45, '45'], ['#5', 83, '83'], ['#6', 161, '161']], 161, mark=[1, 2, 3, 4, 5], done=[0]), kv=KV([['退避', '10 秒起步,每次翻倍,上限 5 分钟'], ['第 1 次重启', '几乎立刻'], ['STATUS', 'Error 与 CrashLoopBackOff 交替,不总是显示后者']], ['退避'])),
    step("多容器 Pod mixed:good 一直运行,bad 立刻 exit 2。bad 的 restartCount=6、state=terminated、ready=False;good 的 restartCount=0、running、ready=True;Pod phase=Running,kubectl get 的 STATUS=Error、READY=1/2。每个容器各自退避,崩溃的容器不影响好的容器。", f=fl(F2, cur=[1], done=[0, 2], mark=[3]), t=tl(S(2), mark=lidx(S(2), '容器 bad'), done=lidx(S(2), '容器 good')), kv=KV([['每个容器独立', '各自的 restartCount 与退避'], ['READY 1/2', '只有崩溃的那个容器不就绪'], ['phase', '仍是 Running']], ['每个容器独立'])),
    step("restartPolicy=Never 的 Pod never:容器 exit 1 后 phase=Failed、restartCount=0、state=terminated(exitCode=1)、STATUS=Error——没有重启,所以也没有 CrashLoopBackOff。", f=fl(F3, cur=[2], done=[0, 1, 3]), t=tl(S(3), mark=lidx(S(3), 'Pod never')), kv=KV([['Never', '崩溃就结束,Pod 变 Failed'], ['没有重启', '也就没有退避']], ['Never'])),
    step("删除 crash 再创建同名的 Pod:前 50 秒里第 1 次重启前等了 0 秒、第 2 次 14 秒、第 3 次 27 秒——又从最短的等待开始,不是接着之前的 5 分钟。退避状态跟着 Pod 实例走,新 Pod 重新开始计时。", f=fl(F4, cur=[2, 3], done=[0, 1]), t=tl(S(4), mark=lidx(S(4), '重新创建的 Pod')), kv=KV([['重建 Pod', '退避重新开始'], ['想立刻重试', '删除 Pod 或改镜像,让它变成新的实例'], ['代价', '根因不修,新 Pod 只是重新走一遍']], ['重建 Pod'])),
]
A = mkartk('k25', 25, 'Kubernetes,CrashLoopBackOff,重启退避,restartPolicy,kubelet,真实验证,动画演示',
    '在 kind 集群里让一个容器每次运行 1 秒就崩溃,实测 CrashLoopBackOff 的退避时间序列:第 1 次重启几乎立刻,之后等待 14、26、45、83、161 秒(约 10 秒起步每次翻倍,含开销);STATUS 大部分时间是 Error,CrashLoopBackOff 只偶尔出现;多容器 Pod 中崩溃的容器各自退避,好容器不受影响;restartPolicy=Never 不重启因此没有退避;删除重建同名 Pod 后退避从头开始。',
    'CrashLoopBackOff 不是 Pod 的一种失败状态,而是 kubelet 在两次重启之间的等待。这篇让一个容器每秒崩溃一次,观察将近 6 分钟,把每次重启前真正等了多久量出来,再看 STATUS 列、多容器 Pod 和重建 Pod 时的表现。',
    [('14 → 26 → 45 → 83 → 161 秒', '第 2~6 次重启前实测的等待时间(约 10、20、40、80、160 秒加开销)'), ('336 秒', '第 6 次重启发生在 Pod 第一次启动后的时间'), ('0 → 14 秒', '删除重建同名 Pod 后,第 1、2 次重启前的等待:退避从头开始')],
    [('等待时间翻倍', '<p>容器 <code>sleep 1</code> 后 <code>exit 1</code>。第 1 次重启等了 1 秒(几乎立刻),之后每次崩溃等待翻倍:<code>14</code>、<code>26</code>、<code>45</code>、<code>83</code>、<code>161</code> 秒,约等于 10、20、40、80、160 秒再加 1~5 秒的启动与同步开销;第 6 次重启发生在 Pod 第一次启动后 336 秒,而每个容器实例只运行了 1 秒。再往后会封顶在 5 分钟。</p><p><code>kubectl get</code> 的 STATUS 大部分时间是 <code>Error</code>(上一个容器的终止原因),容器刚起来的那 1 秒是 <code>Running</code>,<code>CrashLoopBackOff</code> 只在第 254 到 338 秒出现了一次;事件 <code>BackOff</code> 的 <code>count</code> 累计到 8。所以别指望总能在 STATUS 里看到这几个字,判断崩溃循环要看 <code>restartCount</code>、<code>lastState</code> 和事件。</p>'),
     ('每个容器各管各的', '<p>多容器 Pod 里 <code>bad</code> 立刻崩溃(<code>restartCount=6</code>),<code>good</code> 一直 <code>running</code>(<code>restartCount=0</code>),Pod 的 <code>phase</code> 仍是 <code>Running</code>,<code>READY</code> 是 <code>1/2</code>,STATUS 显示 <code>Error</code>。退避是按容器计的。</p>'),
     ('Never 没有退避', '<p><code>restartPolicy: Never</code> 的 Pod 崩溃后 <code>phase=Failed</code>、<code>restartCount=0</code>,不会重启,所以不存在 CrashLoopBackOff;STATUS 只是 <code>Error</code>。</p>'),
     ('重建 Pod', '<p>删掉 <code>crash</code> 再创建同名 Pod:前 50 秒第 1 次重启等 0 秒,第 2 次 14 秒,第 3 次 27 秒——退避重新从最短开始,不是接着之前的 5 分钟。想让崩溃的容器立刻重试,把 Pod 重建一次就行;但根因不修,它只是把同样的退避重走一遍。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);容器 busybox:1.36,命令 sh -c "echo started; sleep 1; exit 1";每 1 秒读一次 Pod 状态,重启等待取自 lastState.terminated.finishedAt 到新容器 state.running.startedAt 的差,共观察 345 秒;STATUS 取自 kubectl get pod 的第 3 列;每种情形各一次(同一个脚本的另一次运行得到的等待是 12、26、48、84、164 秒)',
     '没有验证:5 分钟封顶(只观察到 161 秒这一档,下一档 320 会被封顶在 300 秒);容器连续运行 10 分钟后退避重置的规则;kubelet 的 CrashLoopBackOff 最大值参数(--crash-loop-back-off-max 一类的新特性);镜像拉取失败的退避(ImagePullBackOff,另一篇);init 容器的退避(上一篇里出现过 Init:CrashLoopBackOff);节点重启后退避状态是否保留'],
    '重启退避', PANELS)
