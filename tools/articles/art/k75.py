from lib import *
S = SS('k75')
F1 = [['Lease kx-main-worker2', 'kube-node-lease 命名空间'], ['holderIdentity', '节点名;leaseDurationSeconds=40'], ['renewTime', '每约 10 秒更新'], ['ownerReference', 'Node']]
F2 = [['Lease', '100 秒更新 10 次'], ['Node status', '100 秒变 1 次'], ['Ready.lastHeartbeatTime', '约 5 分钟才刷新一次']]
F3 = [['systemctl stop kubelet', ''], ['Lease renewTime', '停在 17:10:33'], ['47~48 秒', 'Ready=Unknown + unreachable 污点'], ['重新启动 kubelet', '5 秒后恢复']]
F4 = [['delete lease', ''], ['5.7 秒', 'kubelet 重建'], ['新 uid', 'holderIdentity 不变'], ['节点', 'Ready']]
PANELS = [('f', 'flow', '心跳'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("kube-node-lease 命名空间里每个节点一个 Lease(kx-main-control-plane、kx-main-worker、kx-main-worker2),名字就是节点名。worker2 的 Lease:holderIdentity=kx-main-worker2,leaseDurationSeconds=40,ownerReferences 指向 Node。观察 65 秒,renewTime 变了 6 次,相邻间隔 10.0、10.1、10.3、10.1、10.3、10.2 秒,约 10 秒一次。", f=fl(F1, cur=[2], done=[0, 1, 3]), t=tl(S(1), mark=lidx(S(1), 'holderIdentity', '观察 65 秒'), done=lidx(S(1), '所有节点的 Lease')), kv=KV([['Lease', '很小的对象,专门用于心跳'], ['约 10 秒', 'kubelet 的续约间隔'], ['leaseDurationSeconds=40', '对应控制器的容忍时间']], ['Lease'])),
    step("同样 100 秒:Lease 的 resourceVersion 变了 10 次(约每 10 秒);Node 对象本身只变了 1 次——Ready 条件的 lastHeartbeatTime 出现了 2 个不同值(从 17:04:43 开始;这一次已经是上一次更新后的第 258 秒,到 300 秒左右才更新)。没有状态变化时,Node status 每 5 分钟才刷新一次。", f=fl(F2, cur=[0, 1], done=[2]), t=tl(S(2), mark=lidx(S(2), '100 秒内', 'lastHeartbeatTime'), done=lidx(S(2), '100 秒内')), b=bars([['Lease 更新次数', 10, '10'], ['Node 对象更新次数', 1, '1']], 10, done=[0], mark=[1]), kv=KV([['拆开的原因', '频繁心跳不再写大体积的 Node 对象'], ['Node status', '有变化立刻报,没变化 5 分钟一次'], ['etcd 压力', '节点多时差别很大']], ['拆开的原因'])),
    step("停掉 worker2 的 kubelet:最后一次 renewTime 是 17:10:33,之后 Lease 再没更新。47 秒时出现污点 node.kubernetes.io/unreachable:NoSchedule,48 秒时 Ready 条件变成 NodeStatusUnknown,message 是 Kubelet stopped posting node status.(约 40 秒的节点监控宽限期加检查周期)。重新启动 kubelet,5 秒后 Ready=True,污点被清除。", f=fl(F3, cur=[1, 2], done=[3]), t=tl(S(3), mark=lidx(S(3), '停掉 kubelet', 'Lease 的 renewTime 仍停在'), done=lidx(S(3), '重新启动 kubelet')), kv=KV([['约 40 秒', 'node-monitor-grace-period 的量级'], ['Unknown', '控制器写的 Ready 状态'], ['污点', 'unreachable 让新 Pod 不再调度到这里']], ['约 40 秒'])),
    step("kubectl delete lease kx-main-worker2:5.7 秒后 kubelet 又把它建回来(新 uid,holderIdentity 仍是 kx-main-worker2),节点 Ready 没受影响。Lease 是 kubelet 持有的,不是用户该管的对象。", f=fl(F4, cur=[1], done=[2, 3]), t=tl(S(4), mark=lidx(S(4), 'kubectl delete lease'), done=lidx(S(4), '建回来')), kv=KV([['Lease 归 kubelet', '删了会被重建'], ['节点状态', '不受一次删除影响'], ['不要手动改', '和 controller 的假设冲突']], ['Lease 归 kubelet'])),
]
A = mkartk('k75', 75, 'Kubernetes,节点心跳,Lease,NodeStatus,kubelet,node controller,真实验证,动画演示',
    '在 kind 集群里实测节点心跳:kube-node-lease 里每个节点一个 Lease,leaseDurationSeconds=40、renewTime 约每 10 秒更新(间隔 10.0~10.3 秒);同样 100 秒 Lease 更新 10 次而 Node 对象只更新 1 次,没变化时 Node status 约 5 分钟才刷新;停掉 kubelet 后约 48 秒 Ready 变 NodeStatusUnknown 并出现 unreachable 污点;删除 Lease 5.7 秒后被 kubelet 重建。',
    '节点是怎么告诉控制面“我还活着”的?Lease 和 Node status 有什么分工?kubelet 停了多久才会被标成 NotReady?这篇在真集群里观察 Lease 的续约节奏、对比 Node 对象的更新频率,再停掉 kubelet 看超时判定。',
    [('10 次 vs 1 次', '100 秒内 Lease 与 Node 对象各自被更新的次数'), ('~10 秒', 'Lease 的 renewTime 续约间隔'), ('48 秒', '停掉 kubelet 后 Ready 变成 NodeStatusUnknown 的用时')],
    [('Lease:专用心跳', '<p><code>kube-node-lease</code> 命名空间里每个节点一个 Lease,名字就是节点名。worker2 的 Lease:<code>holderIdentity=kx-main-worker2</code>,<code>leaseDurationSeconds=40</code>,<code>ownerReferences</code> 指向 Node。观察 65 秒,<code>renewTime</code> 变了 6 次,间隔 10.0、10.1、10.3、10.1、10.3、10.2 秒——约 10 秒一次。</p>'),
     ('Node status 慢得多', '<p>同样 100 秒,Lease 的 <code>resourceVersion</code> 变了 10 次,而 Node 对象本身只变了 1 次:<code>Ready</code> 条件的 <code>lastHeartbeatTime</code> 出现了 2 个不同值(从 17:04:43 开始,到约 300 秒时才刷新)。没有状态变化时,Node status 每 5 分钟才更新一次。把“我还活着”的高频信号放进只有几十字节的 Lease,避免了频繁改写大体积的 Node 对象,节点多时对 etcd 压力差别很大。</p>'),
     ('心跳停了', '<p>停掉 worker2 的 kubelet:最后一次 <code>renewTime</code> 是 17:10:33,此后 Lease 不再更新。47 秒时出现污点 <code>node.kubernetes.io/unreachable:NoSchedule</code>,48 秒时 Ready 条件变成 <code>NodeStatusUnknown</code>,message 是 <code>Kubelet stopped posting node status.</code>——这是约 40 秒的节点监控宽限期加检查周期。重新启动 kubelet,5 秒后 <code>Ready=True</code>,污点被清除。(驱逐 Pod 的时间线见下一篇。)</p>'),
     ('Lease 归 kubelet 管', '<p><code>kubectl delete lease kx-main-worker2</code>:5.7 秒后 kubelet 又把它建回来,新 uid,<code>holderIdentity</code> 不变,节点 Ready 没受影响。Lease 是 kubelet 持有的对象,手动删除/修改会和控制器的假设冲突。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0),观察对象是 worker2;renewTime 与 resourceVersion 每 0.5~1 秒轮询一次;“48 秒”是 systemctl stop kubelet 起到 Ready 条件不再是 True 的用时,单次测量;每种情形各一次(第二节中的 5 分钟周期是由 lastHeartbeatTime 的两次取值推出的,不是等了完整 5 分钟)',
     '没有验证:node-monitor-grace-period、nodeStatusUpdateFrequency、nodeStatusReportFrequency 的参数调整;NoExecute 污点与 Pod 驱逐(下一篇);控制面节点的心跳;大规模集群的 etcd 写入量对比;Lease 为什么在 Node 上有 ownerReference 的 GC 行为'],
    '心跳', PANELS)
