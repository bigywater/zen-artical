from lib import *
S = SS('k44')
F1 = [['web-3', '+6.7 s'], ['web-2', '+11.7 s'], ['web-1', '+16.1 s'], ['web-0', '+21.7 s']]
F2 = [['partition=2', 'web-0、web-1 保持 v1'], ['web-2、web-3', '换成 v2'], ['partition → 0', '其余也更新'], ['currentRevision', '最终 = updateRevision']]
F3 = [['OnDelete', '改模板 8 秒后全是 v1'], ['手动删 web-1', '重建的是 v2'], ['updatedReplicas', '1']]
F4 = [['坏模板', 'web-3 起不来'], ['更新卡住', 'web-2/1/0 仍是 v1'], ['改回好模板', 'web-3 仍是 bad'], ['手动删 web-3', '17 秒内全部 v3']]
PANELS = [('f', 'flow', 'StatefulSet 更新'), ('t', 'term', '实测输出'), ('b', 'bars', '被替换并 Ready 的时刻(秒)'), ('kv', 'kv', '要点')]
PANELS_NB = [('f', 'flow', 'StatefulSet 更新'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("4 个副本,改 env V=v2 触发 RollingUpdate:被替换并 Ready 的时刻 web-3 +6.7 秒、web-2 +11.7 秒、web-1 +16.1 秒、web-0 +21.7 秒——从最大序号开始,一次一个,每个 Ready 之后才换下一个。revision(controller-revision-hash)从 567bd6 全部变成 75f475,status 里 currentRevision 与 updateRevision 都是 75f475。", f=fl(F1, cur=[0, 1, 2, 3]), t=tl(S(1), mark=lidx(S(1), 'web-3 +6.7s'), done=lidx(S(1), '更新后')), b=bars([['web-3', 6.7, '6.7'], ['web-2', 11.7, '11.7'], ['web-1', 16.1, '16.1'], ['web-0', 21.7, '21.7']], 21.7, done=[0, 1, 2, 3]), kv=KV([['更新顺序', '从大序号到小序号'], ['每次一个', '前一个 Ready 才换下一个'], ['revision', 'controller-revision-hash 标签标记每个 Pod 的版本']], ['更新顺序'])),
    step("partition=2、改 env V=v2:只有 web-2、web-3 被替换成 v2,web-0、web-1 保持 v1;status:currentRevision=567bd6、updateRevision=75f475、currentReplicas=2、updatedReplicas=2。把 partition 改成 0 之后其余也更新,最终四个都是 v2,currentRevision=75f475。partition 就是“只更新序号 ≥ partition 的 Pod”,用来做金丝雀。", f=fl(F2, cur=[1], done=[0, 2, 3]), t=tl(S(2), mark=lidx(S(2), 'partition=2', '把 partition 改成 0')), kv=KV([['partition', '序号小于它的 Pod 不更新'], ['金丝雀', '先更新最后几个,观察后再放开'], ['currentRevision', '还有 Pod 没更新时仍指向旧版本']], ['partition'])),
    step("OnDelete:改了模板 8 秒后四个 Pod 仍是 v1(updatedReplicas 为空);手动删掉 web-1,重建出来的 web-1 是 v2(updatedReplicas=1),其余 v1。", f=fl(F3, cur=[1], done=[2], mark=[0]), t=tl(S(3), mark=lidx(S(3), '改 env V=v2 后 8 秒'), done=lidx(S(3), '手动删掉 web-1')), kv=KV([['OnDelete', '控制器永远不主动更新'], ['适合', '需要人工控制升级顺序的有状态应用'], ['删一个换一个', '只有被删的那个换成新模板']], ['OnDelete'])),
    step("更新到一个就绪探针永远失败的坏模板:20 秒后 web-3 是 bad 且不 Ready,更新停在这里,web-2、web-1、web-0 仍是 v1,ready 只有 3 个。把模板改回好的(V=v3)25 秒后,web-3 仍然是 bad——StatefulSet 控制器不会替换一个不健康的 Pod,更新也没继续。手动删掉 web-3 之后 17 秒,新建的 web-3 是 v3,更新继续往 web-0 推进,最终四个都是 v3。", f=fl(F4, cur=[1, 2], mark=[0], done=[3]), t=tl(S(4), mark=lidx(S(4), '仍然是坏的 bad', '20 秒后'), done=lidx(S(4), '手动删掉 web-3 之后')), kv=KV([['不健康的 Pod', '不会被自动替换,哪怕模板已修好'], ['处理', 'kubectl delete pod 那个坏的 Pod'], ['教训', '先在小范围(partition)验证,别让坏版本卡住整个集合']], ['不健康的 Pod'])),
]
A = mkartk('k44', 44, 'Kubernetes,StatefulSet,滚动更新,partition,OnDelete,updateStrategy,真实验证,动画演示',
    '在 5 节点 kind 集群里实测 StatefulSet 更新:RollingUpdate 从最大序号开始一次换一个(web-3 +6.7 秒、web-2 +11.7 秒、web-1 +16.1 秒、web-0 +21.7 秒);partition=2 只更新 web-2、web-3,currentRevision 与 updateRevision 不同,改成 0 后其余更新;OnDelete 改模板后 Pod 全不动,删一个才换一个;更新到坏模板后卡在 web-3,即使把模板改回好的,不健康的 web-3 也不会被自动替换,必须手动删除。',
    'StatefulSet 的滚动更新和 Deployment 有什么不同?partition 怎么做金丝雀?更新到一半卡住了怎么办?这篇用 4 个副本的 StatefulSet 把更新顺序、partition、OnDelete 和“坏版本卡住后怎么救”都实测了一遍。',
    [('web-3 → web-0', '滚动更新的顺序:从最大序号开始,耗时 +6.7 / +11.7 / +16.1 / +21.7 秒'), ('2 个 v2 + 2 个 v1', 'partition=2 时更新后的版本分布'), ('web-3 仍是 bad', '把模板改回好的 25 秒后,坏掉的 web-3 依然没被替换')],
    [('逆序、一次一个', '<p>改环境变量触发更新:<code>web-3</code> +6.7 秒换完并 Ready,<code>web-2</code> +11.7 秒,<code>web-1</code> +16.1 秒,<code>web-0</code> +21.7 秒——从最大序号开始,前一个 Ready 才换下一个。每个 Pod 的 <code>controller-revision-hash</code> 标签标记它属于哪个版本,<code>status.currentRevision</code>/<code>updateRevision</code> 在更新结束后合一。</p>'),
     ('partition 做金丝雀', '<p><code>updateStrategy.rollingUpdate.partition: 2</code>:只有序号 ≥ 2 的 <code>web-2</code>、<code>web-3</code> 被更新成 v2,<code>web-0</code>、<code>web-1</code> 保持 v1;<code>currentRevision</code>(旧)与 <code>updateRevision</code>(新)并存,<code>updatedReplicas=2</code>。观察一段时间没问题,再把 partition 改成 0,其余的就接着更新。</p>'),
     ('OnDelete', '<p><code>updateStrategy.type: OnDelete</code> 下改了模板 8 秒,四个 Pod 全是 v1,<code>updatedReplicas</code> 为空;手动 <code>kubectl delete pod web-1</code>,重建出来的 web-1 才是 v2。适合必须由人来决定升级顺序和时机的有状态应用。</p>'),
     ('坏版本卡住', '<p>更新到一个就绪探针永远失败的模板:<code>web-3</code> 起不来,更新停在这里,<code>web-2</code>、<code>web-1</code>、<code>web-0</code> 仍是旧版本。这时把模板改回好的,25 秒后 <code>web-3</code> 依然是坏的——StatefulSet 控制器不会替换不健康的 Pod。<b>手动删掉 web-3</b> 之后,新建的 web-3 用的是好模板,更新才继续往 web-0 推进,17 秒全部完成。这是 StatefulSet 与 Deployment 一个重要的差别:Deployment 会按最新模板继续滚动,StatefulSet 会等你亲自处理坏 Pod。</p>')],
    steps,
    [ENV_K + '。独立的 5 节点 kind 集群 kx-sched(Kubernetes v1.37.0);StatefulSet 是 busybox:1.36 sleep,环境变量 V 用来改变 Pod 模板,就绪探针 initialDelaySeconds=2,terminationGracePeriodSeconds=1;被替换的时刻由 0.2 秒间隔轮询 Pod 的 uid 变化并 Ready 得到;版本取 controller-revision-hash 标签的后 6 位;坏模板的就绪探针是 exit 1;每种情形各一次',
     '没有验证:maxUnavailable 与 podManagementPolicy: Parallel 下的更新(特性较新);PVC 在更新中的行为;minReadySeconds;kubectl rollout undo 对 StatefulSet 的作用;revisionHistoryLimit 与 ControllerRevision 对象;partition 大于副本数时的行为;更新期间 Pod 被驱逐或节点故障的情形'],
    'StatefulSet 更新', PANELS)
