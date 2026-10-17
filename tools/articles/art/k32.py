from lib import *
S = SS('k32')
F1 = [['limits.cpu 200m', 'cpu.max = 20000 100000'], ['每个 100ms 周期', '最多跑 20ms'], ['超过', 'throttled'], ['结果', '10.3 秒只用 2.06 秒 CPU']]
F2 = [['无 limit', '4 个死循环 → 3.99 核'], ['limit 1 核', '4 个死循环 → 1.00 核'], ['被限流的周期', '0% / 100%']]
F3 = [['requests 100m', 'cpu.weight 17'], ['requests 400m', 'cpu.weight 49'], ['同一节点吃满核', '28.9 : 89.2 秒 = 1 : 3.08']]
F4 = [['没有 limit', '4.3 秒'], ['limit 500m', '8.4 秒'], ['limit 100m', '54.8 秒']]
PANELS = [('f', 'flow', 'CPU requests 与 limits'), ('t', 'term', '实测输出'), ('b', 'bars', '对比'), ('kv', 'kv', '要点')]
steps = [
    step("limit 200m、requests 100m 的容器里跑一个死循环:cgroup 里 cpu.max=20000 100000(每 100000 微秒的周期最多 20000 微秒),cpu.weight=17。10.3 秒的窗口内只用掉 2.06 秒 CPU(20% 个核);nr_periods=102,其中 nr_throttled=79(77% 的周期被限流),throttled_usec=4.64 秒——想继续跑却被停住的总时间。", f=fl(F1, cur=[2], mark=[3], done=[0, 1]), t=tl(S(1), mark=lidx(S(1), '用掉 CPU 2.06 秒'), done=lidx(S(1), 'cpu.max=')), b=bars([['用掉的 CPU(秒)', 2.06, '2.06'], ['被限流停住的时间(秒)', 4.64, '4.64']], 4.64, mark=[1], done=[0]), kv=KV([['limits.cpu', '变成 cpu.max:每 100ms 周期的配额'], ['nr_throttled', '用完配额被停住的周期数'], ['想跑的 vs 能跑的', '一个死循环想要 100%,只让给 20%']], ['limits.cpu'])),
    step("同样 4 个死循环:没有 limit 的 free4 平均用了 3.99 个核,被限流的周期 0%;limit 1 核的 lim1 平均只有 1.00 个核,被限流的周期占 100%。没有 limit 的容器可以用到节点上空闲的所有核,limit 才是上限。", f=fl(F2, cur=[0, 1]), t=tl(S(2), mark=lidx(S(2), 'free4', 'lim1')), b=bars([['无 limit', 3.99, '3.99 核'], ['limit 1 核', 1.00, '1.00 核']], 3.99, done=[0], mark=[1]), kv=KV([['没有 limit', '可以用到所有空闲的核'], ['有 limit', '再空闲也不让多跑'], ['被限流的周期', '无 limit 为 0,limit 1 核为 100%']], ['没有 limit'])),
    step("只有 requests、没有 limit:在同一节点上各跑 12 个死循环、把核吃满。small(requests 100m)cpu.weight=17,big(requests 400m)cpu.weight=49;同一次读取里量 12 秒:small 用了 28.9 秒 CPU,big 用了 89.2 秒,比例 3.08(权重比 2.88);合计约 9.8 个核(节点共 10 个核)。竞争时按 requests 的比例分,没竞争时谁都能多用。", f=fl(F3, cur=[2], done=[0, 1]), t=tl(S(3), mark=lidx(S(3), '比例 big/small'), done=lidx(S(3), 'cpu.weight=17')), b=bars([['small(100m)', 28.9, '28.9 s'], ['big(400m)', 89.2, '89.2 s']], 89.2, mark=[0], done=[1]), kv=KV([['requests.cpu', '变成 cpu.weight,只在竞争时起作用'], ['比例', '3.08 ≈ 权重比 2.88'], ['不竞争时', 'requests 不限制用量']], ['requests.cpu'])),
    step("限流让同一件事变慢:awk 做 2000 万次加法,没有 limit 4.3 秒,limit 500m 8.4 秒,limit 100m 54.8 秒——limit 越小,CPU 密集的程序越慢;墙钟时间会远大于它真正占用 CPU 的时间。", f=fl(F4, cur=[1, 2]), t=tl(S(4), mark=lidx(S(4), 'w-100', 'w-500'), done=lidx(S(4), 'w-free')), b=bars([['无 limit', 4.3, '4.3 s'], ['500m', 8.4, '8.4 s'], ['100m', 54.8, '54.8 s']], 54.8, done=[0], cur=[1], mark=[2]), kv=KV([['限流 = 等待', '延迟随 limit 变小而变大'], ['突发请求', '短时间需要很多 CPU 的服务最容易被限流'], ['诊断', '看 nr_throttled / throttled_usec,不只是平均 CPU 使用率']], ['限流 = 等待'])),
]
A = mkartk('k32', 32, 'Kubernetes,CPU limit,限流,throttling,cgroup,cpu.max,cpu.weight,真实验证,动画演示',
    '在 kind 节点的 cgroup v2 里实测 requests 与 limits 对 CPU 的影响:limit 200m 的死循环 10.3 秒只用 2.06 秒 CPU,79 个周期被限流;没有 limit 的容器用到 3.99 个核而 limit 1 核的只有 1.00 个核;只有 requests 时竞争按 cpu.weight 分(100m:400m 的实测用量比 1:3.08);同样的计算在无 limit、500m、100m 下分别花 4.3、8.4、54.8 秒。',
    'CPU limit 到底是怎么限制容器的?requests 又在什么时候起作用?这篇直接读 cgroup 的 cpu.max、cpu.weight 和 cpu.stat,用死循环做对照,把限流的计数、没有 limit 的容器能用多少核、竞争时按什么比例分都量出来。',
    [('2.06 秒 / 10.3 秒', 'limit 200m 的死循环在窗口内用掉的 CPU 时间,以及窗口长度'), ('1 : 3.08', 'requests 100m 与 400m 的两个容器在同一节点吃满核时的 CPU 用量比(权重比 2.88)'), ('4.3 → 54.8 秒', '同样的计算在没有 limit 与 limit 100m 下的墙钟时间')],
    [('limit 是每个周期的配额', '<p>limit 200m 在 cgroup 里变成 <code>cpu.max=20000 100000</code>:每 100 毫秒周期里最多跑 20 毫秒。一个死循环想用满整个核,10.3 秒的窗口里只用掉 2.06 秒 CPU(20%);102 个周期里有 79 个用完了配额被停住(<code>nr_throttled</code>),<code>throttled_usec</code> 累计 4.64 秒就是被迫等待的时间。<code>requests</code> 变成 <code>cpu.weight=17</code>,和限流无关。</p>'),
     ('没有 limit 就是自由的', '<p>同样 4 个死循环:没有 limit 的容器平均用了 3.99 个核,被限流周期 0%;limit 1 核的只有 1.00 个核,被限流周期 100%。没有 limit 的容器能用到节点上所有空闲的核,所以“requests 设得很小、不设 limit”并不会限制它用多少 CPU。</p>'),
     ('requests 只在竞争时起作用', '<p>在同一个节点上各跑 12 个死循环,把 10 个核吃满:requests 100m 的容器 <code>cpu.weight=17</code>,400m 的 <code>cpu.weight=49</code>;同一次读取里量 12 秒,用量分别是 28.9 秒和 89.2 秒,比例 3.08,接近权重比 2.88,合计约 9.8 个核。没有竞争时 requests 不限制任何东西,有竞争时按它的比例分。</p>'),
     ('限流就是变慢', '<p>awk 做 2000 万次加法:没有 limit 4.3 秒,limit 500m 8.4 秒,limit 100m 54.8 秒。CPU 密集的程序在 limit 下的墙钟时间远大于它真正占用 CPU 的时间。排查延迟毛刺时要看 <code>nr_throttled</code> 与 <code>throttled_usec</code>,只看平均 CPU 使用率会误以为还有余量。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0,每个节点 10 个核,cgroup v2);死循环是 busybox sh 的 (while :; do :; done) &;cpu.max、cpu.weight、cpu.stat 直接用 docker exec 从节点的 /sys/fs/cgroup/kubelet.slice/… 读出,窗口前后各读一次(第 3 节在同一次 docker exec 里同时读两个容器,避免读取先后造成的误差——最初分别读取得到了超过 10 个核的假结果);第 4 节的计算是 awk BEGIN{for(i=0;i<20000000;i++)x+=i};每种情形各一次',
     '没有验证:cpu.max.burst(突发配额);CPU Manager static 策略下 Guaranteed Pod 的独占核不受限流;cpuset 与 limit 的关系;内核 CFS 带宽控制的已知问题(多线程应用的限流放大);cpu limit 在不同内核版本上的行为差异;kubectl top 的数字(本集群没有 metrics-server)'],
    'CPU requests 与 limits', PANELS)
