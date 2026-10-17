from lib import *
S = SS('k45')
F1 = [['默认 25%/25%', '峰值 8,谷值 5,7.9 s'], ['surge 1 / unavail 0', '峰值 7,谷值 6,23.9 s'], ['surge 0 / unavail 1', '峰值 6,谷值 5,24.0 s'], ['surge 100% / unavail 0', '峰值 12,谷值 6,4.0 s']]
F2 = [['+0.2 s', '总数 8 / Ready 5 / 旧 5 / 新 3'], ['+3.8 s', '8 / 7 / 4 / 4'], ['+4.0 s', '8 / 5 / 2 / 6'], ['+7.9 s', '6 / 6 / 0 / 6']]
F3 = [['+0.2 s', '旧 Pod 全部停掉'], ['+2.3 s', '6 个新 Pod 已创建,Ready=0'], ['+6.0 s', '全部 Ready'], ['不可用窗口', '约 6 秒']]
F4 = [['minReadySeconds=0', '15.9 s'], ['minReadySeconds=5', '31.9 s']]
PANELS = [('f', 'flow', '滚动更新'), ('t', 'term', '实测输出'), ('b', 'bars', '耗时(秒)'), ('kv', 'kv', '要点')]
PANELS2 = [('f', 'flow', '滚动更新'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("6 个副本改环境变量触发更新(就绪探针延迟 3 秒)。默认 25%/25%:Pod 总数峰值 8、Ready 最低 5、用了 7.9 秒——maxSurge 25% 向上取整 ceil(1.5)=2,maxUnavailable 25% 向下取整 floor(1.5)=1;maxSurge 1 / maxUnavailable 0:峰值 7、谷值 6、23.9 秒(一次只加一个,没有不可用);maxSurge 0 / maxUnavailable 1:峰值 6、谷值 5、24.0 秒;maxSurge 100% / maxUnavailable 0:峰值 12、谷值 6、4.0 秒。", f=fl(F1, cur=[0, 1, 2, 3]), t=tl(S(1), mark=lidx(S(1), '默认(25% / 25%)'), done=lidx(S(1), 'maxSurge 100%')), b=bars([['默认 25%/25%', 7.9, '7.9'], ['surge 1 / unavail 0', 23.9, '23.9'], ['surge 0 / unavail 1', 24.0, '24.0'], ['surge 100% / unavail 0', 4.0, '4.0']], 24.0, mark=[1, 2], done=[0, 3]), kv=KV([['maxSurge', '最多比期望多几个(百分比向上取整)'], ['maxUnavailable', '最多少几个可用(百分比向下取整)'], ['速度与风险', '两个都小 = 慢但稳,surge 100% = 快但临时翻倍资源']], ['maxSurge'])),
    step("默认参数下一次更新的时间线(总数, Ready, 旧, 新):+0.2 秒 8/5/5/3 → +3.8 秒 8/7/4/4 → +4.0 秒 8/5/2/6 → +7.9 秒 6/6/0/6;更新后有两个 ReplicaSet:旧的(revision 1)replicas=0,新的(revision 2)replicas=6。", f=fl(F2, cur=[0, 1, 2], done=[3]), t=tl(S(2), mark=lidx(S(2), '总数=8'), done=lidx(S(2), '总数=6 Ready=6', '更新后的 ReplicaSet')), kv=KV([['新旧 ReplicaSet', '一边扩一边缩'], ['先多后少', '总数先到 8,新 Pod Ready 之后才缩旧的'], ['旧 ReplicaSet', '缩到 0 但保留,用于回滚']], ['新旧 ReplicaSet'])),
    step("Recreate:+0.2 秒旧 Pod 已经全部停掉(总数 0),+2.3 秒 6 个新 Pod 创建出来但 Ready=0,+6.0 秒全部 Ready——有大约 6 秒完全没有可用的 Pod,总数从不超过 6。", f=fl(F3, cur=[1], mark=[3], done=[2]), t=tl(S(3), mark=lidx(S(3), 'Ready 最低值 0'), done=lidx(S(3), '时间线')), kv=KV([['Recreate', '先全停再全起,有完全不可用的窗口'], ['适用', '不能新旧版本同时运行(如独占的卷、数据库迁移)'], ['代价', '停机时间 = 停止 + 启动 + 就绪']], ['Recreate'])),
    step("minReadySeconds:新 Pod Ready 之后还要连续 Ready 这么久才算 available。4 个副本、maxSurge 1 / maxUnavailable 0:minReadySeconds=0 用了 15.9 秒,minReadySeconds=5 用了 31.9 秒——每换一个 Pod 多等 5 秒,4 个就是 16 秒。", f=fl(F4, cur=[0, 1]), t=tl(S(4), mark=lidx(S(4), 'minReadySeconds=5'), done=lidx(S(4), 'minReadySeconds=0')), b=bars([['minReadySeconds=0', 15.9, '15.9'], ['minReadySeconds=5', 31.9, '31.9']], 31.9, done=[0], mark=[1]), kv=KV([['minReadySeconds', '防止“刚 Ready 又崩”的新 Pod 被当成可用'], ['代价', '每个批次都多等这么久'], ['配合 maxUnavailable: 0', '新 Pod 稳定了才会杀旧的']], ['minReadySeconds'])),
]
A = mkartk('k45', 45, 'Kubernetes,Deployment,滚动更新,maxSurge,maxUnavailable,Recreate,minReadySeconds,真实验证,动画演示',
    '在 kind 集群里实测 Deployment 滚动更新:6 个副本下默认 25%/25% 峰值 8 个 Pod、最低 5 个 Ready(maxSurge 向上取整、maxUnavailable 向下取整),用时 7.9 秒;maxSurge 1 / maxUnavailable 0 与 maxSurge 0 / maxUnavailable 1 都要约 24 秒,maxSurge 100% 只要 4.0 秒但峰值 12 个;Recreate 有约 6 秒完全不可用;minReadySeconds=5 让 4 个副本的更新从 15.9 秒变成 31.9 秒。',
    '滚动更新时到底会多出几个 Pod、最少剩几个可用?百分比是怎么取整的?Recreate 的停机有多长?minReadySeconds 又拖慢多少?这篇用同一个 Deployment 换四组参数,把 Pod 总数的峰值、可用数的谷值和耗时全部量了出来。',
    [('8 / 5', '6 个副本、默认 25%/25% 时更新过程中 Pod 总数的峰值与 Ready 数的谷值'), ('7.9 秒 vs 23.9 秒', '默认参数与 maxSurge 1 / maxUnavailable 0 的更新耗时'), ('15.9 → 31.9 秒', '4 个副本把 minReadySeconds 从 0 改成 5 之后的更新耗时')],
    [('参数怎么算', '<p><code>maxSurge</code> 与 <code>maxUnavailable</code> 的百分比取整方向相反:6 个副本的 25%,<code>maxSurge</code> 向上取整得 2,<code>maxUnavailable</code> 向下取整得 1,所以默认更新时 Pod 总数最多 8 个、Ready 最少 5 个,7.9 秒完成。<code>maxSurge 1 / maxUnavailable 0</code>(一次只加一个、不允许少)用时 23.9 秒但始终保持 6 个 Ready;<code>maxSurge 0 / maxUnavailable 1</code>(不多起、一次停一个)24.0 秒;<code>maxSurge 100%</code> 一次性把新版本全起来,只要 4.0 秒,代价是 Pod 总数翻到 12。</p>'),
     ('一次更新的过程', '<p>默认参数:+0.2 秒新旧 Pod 并存(8 个,5 个 Ready,旧 5 个新 3 个),+3.8 秒 7 个 Ready,+4.0 秒旧的缩到 2 个,+7.9 秒 6 个全是新的。两个 ReplicaSet 一边扩一边缩;更新完后旧 ReplicaSet(revision 1)<code>replicas=0</code> 但保留着,为回滚留下记录(下一篇)。</p>'),
     ('Recreate', '<p><code>strategy.type: Recreate</code> 先把旧 Pod 全部停掉(+0.2 秒总数为 0),再创建 6 个新 Pod(+2.3 秒,Ready=0),+6.0 秒全部 Ready。大约 6 秒里一个可用的 Pod 都没有,总数则从不超过 6。只有“新旧版本绝不能同时运行”时才值得用。</p>'),
     ('minReadySeconds', '<p>新 Pod Ready 之后还要连续 Ready <code>minReadySeconds</code> 秒才算 available,才会继续杀旧的。4 个副本、<code>maxSurge 1 / maxUnavailable 0</code>:<code>minReadySeconds=0</code> 用了 15.9 秒,<code>=5</code> 用了 31.9 秒——每个批次多等 5 秒。用它可以挡住“刚 Ready 就崩”的坏版本把旧副本全换光。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);Pod 是 busybox:1.36 sleep,就绪探针 initialDelaySeconds=3,terminationGracePeriodSeconds=2,环境变量 V 从 v1 改成 v2 触发更新;每 0.15 秒轮询一次 Pod 列表统计(总数、Ready、旧、新),时间线在计数变化时记录,峰值与谷值取自这些记录(可能漏掉不足 0.15 秒的瞬时状态);每组参数各一次;“Recreate 窗口约 6 秒”取自时间线中 Ready=0 的区间',
     '没有验证:progressDeadlineSeconds 与更新卡住时的 Progressing 条件;kubectl rollout status 的输出;百分比为小数时 maxSurge 与 maxUnavailable 同时为 0 的校验(会被拒绝);HPA 与滚动更新同时发生时的副本数;PodDisruptionBudget 与滚动更新的关系(本文没有测 PDB 是否影响 Deployment 控制器缩旧 ReplicaSet);Deployment 暂停(pause)'],
    '滚动更新', PANELS)
