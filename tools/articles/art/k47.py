from lib import *
S = SS('k47')
F1 = [['裸 Pod stray', '标签 app=r,没有所有者'], ['创建 rs-a(replicas=2)', 'selector app=r'], ['收养 stray', 'ownerReferences 加上 rs-a'], ['再新建 1 个', '共 2 个']]
F2 = [['改标签 app=other', 'Pod 脱离,成孤儿'], ['ReplicaSet', '立刻补一个新的'], ['标签改回 app=r', '又被收养'], ['3 个匹配', '删掉多余的 1 个']]
F3 = [['delete rs-a --cascade=orphan', 'Pod 的所有者被摘掉'], ['创建 rs-b(同 selector)', '接管'], ['uid', '全部没变']]
F4 = [['rs-x、rs-y selector 相同', '各 2 个,共 4 个'], ['各管各的', 'status.replicas 都是 2'], ['新的裸 Pod stray2', '被 rs-y 收养'], ['随即删除', 'SuccessfulDelete']]
PANELS = [('f', 'flow', 'ReplicaSet 与 Pod 的归属'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("先有一个标签 app=r 的裸 Pod stray(没有所有者),再创建 replicas=2、selector app=r 的 rs-a:stray 被“收养”(ownerReferences 指向 ReplicaSet/rs-a、controller=True),uid 没变,ReplicaSet 只再新建了 1 个,总共 2 个 Pod,status.replicas=2、readyReplicas=2。", f=fl(F1, cur=[2], done=[0, 1, 3]), t=tl(S(1), mark=lidx(S(1), '创建 rs-a', 'stray 的 uid 没变'), done=lidx(S(1), '裸 Pod stray')), kv=KV([['selector', 'ReplicaSet 靠它找自己的 Pod'], ['收养', '没有控制器所有者的匹配 Pod 会被接管'], ['Pod 不重建', 'uid 不变']], ['收养'])),
    step("改标签:把其中一个 Pod 的 app 改成 other,它的所有者被摘掉成了孤儿、仍在运行,ReplicaSet 立刻补了一个新的;再把标签改回 app=r,这个孤儿又被收养,此时有 3 个匹配的 Pod,ReplicaSet 删掉了多余的一个(较新的那个)。改标签是把 Pod 从 ReplicaSet 里“拿出来”做隔离排查的常用办法。", f=fl(F2, cur=[0, 1], done=[2, 3]), t=tl(S(2), mark=lidx(S(2), '标签 app 改成 other', '再把标签改回'), done=lidx(S(2), '现在:(没有所有者)', '删掉了多余的')), kv=KV([['改掉标签', 'Pod 脱离 ReplicaSet,不再被管理'], ['ReplicaSet', '看到少了一个就补一个'], ['想隔离出问题的 Pod', '改标签,保留现场']], ['改掉标签'])),
    step("kubectl delete rs rs-a --cascade=orphan:Pod 还在,ownerReferences 被摘掉(没有所有者);创建 selector 相同的 rs-b:两个 Pod 立刻被 rs-b 接管,uid 全都没变,没有重建。这是“换 ReplicaSet 而不动 Pod”的办法。", f=fl(F3, cur=[1], done=[0, 2]), t=tl(S(3), mark=lidx(S(3), '删除 rs-a(orphan)', '创建 rs-b'), done=[]), kv=KV([['orphan 删除', '只删 ReplicaSet,保留 Pod'], ['接管', '同 selector 的新 ReplicaSet 会收养它们'], ['用途', '迁移控制器、改 ReplicaSet 的配置']], ['orphan 删除'])),
    step("已经有控制器所有者的 Pod 不会被另一个 ReplicaSet 收养:rs-x、rs-y 都是 replicas=2、selector app=r,各管各的,共 4 个 Pod,status.replicas 各自是 2。再创建一个标签匹配的裸 Pod stray2——两个 ReplicaSet 都已满足,它被 rs-y 收养后立刻作为“多余的”删掉(事件 rs-y SuccessfulDelete: Deleted pod: stray2),0.0 秒内就查不到了,总数仍是 4。", f=fl(F4, cur=[2], done=[0, 1, 3]), t=tl(S(4), mark=lidx(S(4), 'stray2', 'SuccessfulDelete'), done=lidx(S(4), 'status.replicas')), kv=KV([['controllerRef', '一个 Pod 只能有一个控制器所有者'], ['selector 重叠', '各 ReplicaSet 只数自己所有的 Pod'], ['新的裸 Pod 标签匹配', '可能被收养后立刻删掉']], ['controllerRef'])),
]
A = mkartk('k47', 47, 'Kubernetes,ReplicaSet,收养,ownerReferences,selector,orphan,真实验证,动画演示',
    '在 kind 集群里实测 ReplicaSet 的收养:先有标签匹配的裸 Pod 再创建 replicas=2 的 ReplicaSet,裸 Pod 被收养(ownerReferences、uid 不变)只再新建 1 个;改标签的 Pod 脱离 ReplicaSet、ReplicaSet 补新的,标签改回后又被收养并删掉多余的;--cascade=orphan 删除后同 selector 的新 ReplicaSet 接管全部 Pod(uid 不变);两个 selector 相同的 ReplicaSet 各管各的,新来的匹配裸 Pod 被收养后立刻作为多余的删掉。',
    '标签匹配的 Pod 会被谁接管?改个标签会怎样?两个 selector 一样的 ReplicaSet 会不会打架?这篇用裸 Pod、改标签、orphan 删除和两个重叠的 ReplicaSet,把 ReplicaSet 收养 Pod 的规则一条条跑出来。',
    [('uid 不变', '裸 Pod 被收养、以及 orphan 之后被新 ReplicaSet 接管时,Pod 都没有重建'), ('SuccessfulDelete: stray2', '新建的匹配裸 Pod 被已满足的 ReplicaSet 收养后立即被删除的事件'), ('4 个 Pod', '两个 selector 相同、replicas 都是 2 的 ReplicaSet 各管各的,总共的 Pod 数')],
    [('收养裸 Pod', '<p>先创建一个标签 <code>app=r</code> 的裸 Pod <code>stray</code>,再创建 <code>replicas: 2</code>、<code>selector: app=r</code> 的 ReplicaSet。<code>stray</code> 的 <code>ownerReferences</code> 立刻多了一条指向这个 ReplicaSet 的、<code>controller: true</code> 的记录——被收养了;<code>uid</code> 没变(没有重建),ReplicaSet 只再新建了 1 个,总共 2 个。缩到 1 个副本时删掉哪个由 ReplicaSet 按规则挑,不一定是被收养的那个。</p>'),
     ('改标签', '<p>把一个 Pod 的 <code>app</code> 标签改成 <code>other</code>,它不再匹配 selector,所有者被摘掉成了孤儿、继续运行,ReplicaSet 看到少了一个就补一个新的。再改回 <code>app=r</code>,它又被收养,此时有 3 个匹配的 Pod,ReplicaSet 删掉多余的一个(较新的那个)。排查线上出问题的 Pod 时,改标签把它“拿出来”保留现场、同时让 ReplicaSet 补上新的,是常用办法。</p>'),
     ('orphan 与接管', '<p><code>kubectl delete rs --cascade=orphan</code> 只删 ReplicaSet,Pod 的所有者被摘掉但仍在运行;创建 selector 相同的新 ReplicaSet 后,两个 Pod 立刻被接管,<code>uid</code> 全部没变。想换 ReplicaSet 的配置又不想重建 Pod,就用这个。</p>'),
     ('只收养没有控制器的 Pod', '<p>两个 selector 完全相同的 ReplicaSet(<code>rs-x</code>、<code>rs-y</code>,各 <code>replicas: 2</code>)并不会互相抢:每个 Pod 只有一个控制器所有者,两边各管各的 2 个,<code>status.replicas</code> 都是 2,共 4 个 Pod。但此后新建的、标签匹配的裸 Pod <code>stray2</code> 没有所有者,会被其中一个(这次是 <code>rs-y</code>)收养,而它们已经满足副本数,于是立刻被当作多余的删掉:事件 <code>SuccessfulDelete: Deleted pod: stray2</code>,0.0 秒内就查不到了。这也是不要让 selector 重叠的原因。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);Pod 是 busybox:1.36 sleep;所有者信息取自每个 Pod 的 metadata.ownerReferences;每次操作后等 3~5 秒再读取(第 4 节的 stray2 用 0.1 秒轮询,第一次查询就已 NotFound,所以靠事件确认它被收养后又被删除);每种情形各一次,Pod 名字后缀每次运行不同',
     '没有验证:Deployment 与 ReplicaSet 的收养关系(pod-template-hash 标签如何防止多个 ReplicaSet 互相收养);selector 与 Pod 模板标签不匹配时 ReplicaSet 创建被拒绝;ReplicaSet 缩容时选哪个 Pod 删除的完整排序规则(未就绪、较新、所在节点上同类更多的优先);Pod 的 controller=false 的 ownerReference 不阻止收养;垃圾回收对孤儿 Pod 的处理(见垃圾回收一篇)'],
    'ReplicaSet 收养', PANELS)
