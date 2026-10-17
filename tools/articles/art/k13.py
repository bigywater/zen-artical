from lib import *
S = SS('k13')
F1 = [['delete owner1', '立即返回'], ['垃圾回收器', '发现 owner 没了'], ['child1 / child1b', '约 40 ms 后消失']]
F2 = [['delete --cascade=foreground', ''], ['owner2', 'foregroundDeletion'], ['slow (block=true)', '带 finalizer'], ['noblock (block=false)', '带 finalizer'], ['owner2 消失', '38 ms']]
F3 = [['owner3', '删除'], ['child3', '保留'], ['ownerReferences', '被摘掉']]
F4 = [['ownerRef → 不存在的 uid', ''], ['垃圾回收器', '按“没有所有者”处理'], ['ghost / child4', '约 40 ms 被删']]
PANELS = [('f', 'flow', '级联删除'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("child1、child1b 的 ownerReferences 指向 owner1 的 uid。kubectl delete cm owner1 --cascade=background(默认):40 毫秒返回,owner1 已经不存在;从属在 39 毫秒、39 毫秒后也被垃圾回收器删掉。", f=fl(F1, cur=[1], done=[0, 2]), t=tl(S(1), mark=lidx(S(1), '从属 child1'), done=lidx(S(1), 'owner1 还在吗')), kv=KV([['background', '所有者先没,从属随后被回收'], ['谁删的', 'kube-controller-manager 里的垃圾回收器'], ['依据', '从属的 ownerReferences']], ['background'])),
    step("--cascade=foreground:owner2 被标记删除但仍然存在(deletionTimestamp 已设置,finalizers=['foregroundDeletion']);无 finalizer 的 fast 已被删掉,带 finalizer 的 slow(blockOwnerDeletion=true)和 noblock(blockOwnerDeletion=false)还在。只摘掉 slow 的 finalizer,owner2 在 38 毫秒后消失,此时 noblock(finalizer 还在)仍然存在——只有 blockOwnerDeletion=true 的从属会阻塞所有者。", f=fl(F2, cur=[1], mark=[2], done=[4]), t=tl(S(2), mark=lidx(S(2), 'foregroundDeletion', '只摘掉 slow'), done=lidx(S(2), 'fast')), kv=KV([['foreground', '所有者要等从属先删完'], ['blockOwnerDeletion=true', '才会阻塞所有者'], ['所有者的 finalizer', 'foregroundDeletion']], ['blockOwnerDeletion=true'])),
    step("--cascade=orphan:删除前 child3 的 ownerReferences 指向 owner3;删除 owner3 之后 child3 还在,ownerReferences 变成 None——垃圾回收器把引用摘掉,从属成了孤儿。", f=fl(F3, cur=[2], done=[0, 1]), t=tl(S(3), mark=lidx(S(3), 'ownerReferences=None'), done=lidx(S(3), '--cascade=orphan:')), kv=KV([['orphan', '从属保留'], ['ownerReferences', '被摘掉,不会再被级联'], ['用途', '比如保留 Pod 而只重建 ReplicaSet']], ['orphan'])),
    step("所有者找不到:ownerReferences 指向不存在的 uid,从属 ghost 在 39 毫秒后被垃圾回收器删掉;所有者 owner4 在另一个命名空间 k13-other 里真实存在,从属 child4 在 k13,同样在约 40 毫秒后被删,事件 OwnerRefInvalidNamespace 写明 owner4 does not exist in namespace \"k13\"。", f=fl(F4, cur=[1], mark=[2], done=[0]), t=tl(S(4), mark=lidx(S(4), '毫秒后被垃圾回收器删掉', '毫秒后被删掉'), done=lidx(S(4), 'OwnerRefInvalidNamespace')), kv=KV([['uid 对不上', '按所有者不存在处理 → 删除从属'], ['跨命名空间', '不支持,同样被当成不存在'], ['写 ownerReferences', '要用真实的 uid,且在同一命名空间']], ['跨命名空间'])),
]
A = mkartk('k13', 13, 'Kubernetes,ownerReferences,垃圾回收,级联删除,foregroundDeletion,orphan,真实验证,动画演示',
    '在 kind 集群里用 ConfigMap 实测 ownerReferences 与垃圾回收:--cascade=background 所有者立刻消失、从属约 40 毫秒后被回收;foreground 时所有者留着 foregroundDeletion 的 finalizer,等 blockOwnerDeletion=true 的从属删完才消失,blockOwnerDeletion=false 的不阻塞;orphan 会摘掉从属的 ownerReferences;指向不存在的 uid 或跨命名空间的所有者会让从属被直接删除,并产生 OwnerRefInvalidNamespace 事件。',
    '删掉 Deployment,ReplicaSet 和 Pod 为什么也跟着没了?靠的是从属对象上的 ownerReferences 和垃圾回收器。这篇用 ConfigMap 搭出所有者和从属,把 background、foreground、orphan 三种级联模式各跑一遍,再看 ownerReferences 写错了会发生什么。',
    [('~40 ms', '--cascade=background 删除所有者后,从属被垃圾回收器删掉的时间'), ('foregroundDeletion', 'foreground 删除时所有者暂时带着的 finalizer'), ('OwnerRefInvalidNamespace', '所有者在别的命名空间时垃圾回收器产生的事件(从属同时被删)')],
    [('background:先删所有者', '<p>从属 <code>ownerReferences</code> 里写着所有者的名字和 <code>uid</code>。<code>--cascade=background</code>(默认)删除所有者,40 毫秒就返回,所有者立刻消失;垃圾回收器随后发现从属的所有者没了,在约 40 毫秒内把从属也删掉。</p>'),
     ('foreground:先删从属', '<p>所有者被标记删除,但仍然存在,<code>finalizers</code> 里多了 <code>foregroundDeletion</code>。无 finalizer 的从属 <code>fast</code> 很快被删,带 finalizer 的 <code>slow</code>(<code>blockOwnerDeletion: true</code>)卡住了所有者;只摘掉 <code>slow</code> 的 finalizer,所有者 38 毫秒后消失,而 <code>noblock</code>(<code>blockOwnerDeletion: false</code>,finalizer 还在)仍然存在——只有 <code>blockOwnerDeletion: true</code> 的从属才会阻塞所有者。</p>'),
     ('orphan:放走从属', '<p><code>--cascade=orphan</code> 删除所有者之后,从属还在,但 <code>ownerReferences</code> 已经被垃圾回收器摘掉(实测为 <code>None</code>),今后不会再被级联。把 Deployment 删掉而保留它的 Pod 就是这个模式。</p>'),
     ('所有者找不到', '<p>从属的 <code>ownerReferences</code> 指向一个不存在的 <code>uid</code>,约 40 毫秒就被垃圾回收器删掉。所有者真的存在、只是在别的命名空间,结果一样,同时产生事件 <code>OwnerRefInvalidNamespace</code>:跨命名空间的 ownerReferences 不被支持,所有者按“不存在”处理。所以手写 ownerReferences 一定要用真实的 <code>uid</code>,并且和从属在同一个命名空间(或者所有者是集群级资源)。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);所有者和从属都是 ConfigMap,ownerReferences 手写(apiVersion v1、kind ConfigMap、真实 uid);foreground 实验里用自己写的 finalizer example.com/slow 让从属停留;“消失时间”是脚本以 50 毫秒间隔轮询的结果,包含 kubectl 调用的开销;每种情形各一次',
     '没有验证:Pod / ReplicaSet / Deployment 这类真实工作负载的级联;集群级所有者与命名空间级从属;多个所有者(多个 ownerReferences)时的删除规则;垃圾回收器的重新同步与大规模对象下的耗时;kubectl delete 的 --cascade 默认值在不同资源上的差别'],
    '级联删除', PANELS)
