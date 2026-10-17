from lib import *
S = SS('k76')
F1 = [['停掉 kubelet', '+0'], ['+52 秒', 'Ready=Unknown + unreachable NoSchedule/NoExecute'], ['+82 秒', 'p-30s、dep 的 Pod 被标记删除(+30)'], ['+83 秒', 'dep 的替换 Pod 在 worker 上 Running'], ['+110 秒', 'p-default / p-forever 仍在']]
F2 = [['重启 kubelet', ''], ['Terminating 的 Pod', '被清理'], ['污点', '清除'], ['32 秒后', 'dep 只剩 1 个,p-default / p-forever 仍在']]
PANELS = [('f', 'flow', '失联后的时间线'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("worker2 上的四类 Pod:p-default(没写容忍,准入自动加了 not-ready / unreachable 各 300 秒的容忍)、p-30s(tolerationSeconds=30,优雅期 30 秒)、p-forever(无限容忍)、Deployment dep 的 Pod(容忍 30 秒)。停掉 kubelet 后 +52 秒节点 Ready=Unknown,同时出现 unreachable 的 NoSchedule 和 NoExecute 污点;+82 秒(正好多 30 秒)p-30s 和 dep 的 Pod 被标记删除,+83 秒 dep 的替换 Pod 在 worker 上 Running。+110 秒时 p-30s 与旧 dep Pod 显示 Terminating(节点上没有 kubelet 来真正终止它们),p-default 和 p-forever 仍是 Running。", f=fl(F1, cur=[1, 2], done=[3, 4]), t=tl(S(1), mark=lidx(S(1), 'Ready=Unknown', '被标记删除'), done=lidx(S(1), '替换 Pod', 'kubectl get pods')), kv=KV([['污点先到', 'NoExecute 污点一出现就开始计时'], ['tolerationSeconds', '从污点出现起算,到点才驱逐'], ['Terminating', 'kubelet 不在,Pod 停在 Terminating 直到它回来']], ['tolerationSeconds'])),
    step("重新启动 kubelet 32 秒后:节点污点已清除,Terminating 的 p-30s 被清理,dep 只剩 1 个 Running 的 Pod,p-default 和 p-forever 仍在运行——它们没到驱逐时间(默认 300 秒、无限),kubelet 回来后重新报告状态。", f=fl(F2, cur=[1], done=[0, 2, 3]), t=tl(S(2), mark=lidx(S(2), '重新启动 kubelet'), done=lidx(S(2), 'p-default 还在吗')), kv=KV([['默认 300 秒', '短暂失联不会触发驱逐'], ['想要更快', '给 Pod 写更短的 tolerationSeconds'], ['有状态应用', '驱逐前要确认旧节点真的不会再写数据']], ['默认 300 秒'])),
]
A = mkartk('k76', 76, 'Kubernetes,节点失联,NotReady,污点,驱逐,tolerationSeconds,真实验证,动画演示',
    '在 kind 集群里停掉一个 worker 的 kubelet,按秒记录时间线:+52 秒 Ready=Unknown 并同时打上 unreachable 的 NoSchedule 和 NoExecute 污点;容忍 30 秒的 Pod 在 +82 秒被标记删除,Deployment 在 +83 秒就有了新的替换 Pod,旧 Pod 停在 Terminating;默认容忍 300 秒和无限容忍的 Pod 都还在;kubelet 回来后 Terminating 的被清理。',
    '节点失联之后,Pod 什么时候被驱逐?默认容忍 300 秒是从哪里开始算的?Deployment 的替换 Pod 什么时候出现?旧 Pod 去哪了?这篇在真集群里停掉一个节点的 kubelet,把整个时间线按秒记下来。',
    [('+52 秒', '停掉 kubelet 后节点变成 Unknown 并打上污点(多次实测 44~52 秒)'), ('+30 秒', '从污点出现到容忍 30 秒的 Pod 被标记删除'), ('Terminating', '旧 Pod 在节点上没有 kubelet 时一直停在这个状态')],
    [('时间线', '<p>worker2 上放了四类 Pod:<code>p-default</code>(没写容忍,准入自动加了 <code>not-ready</code> 和 <code>unreachable</code> 各 300 秒)、<code>p-30s</code>(<code>tolerationSeconds=30</code>)、<code>p-forever</code>(无限容忍)和 Deployment <code>dep</code> 的 Pod(容忍 30 秒)。停掉 kubelet:+52 秒节点 <code>Ready=Unknown</code>,同时出现 <code>unreachable</code> 的 NoSchedule 和 NoExecute 污点;+82 秒(正好 30 秒后)<code>p-30s</code> 和 <code>dep</code> 的 Pod 被标记删除;+83 秒 Deployment 的替换 Pod 已经在 worker 上 <code>Running</code>。+110 秒时被驱逐的两个 Pod 显示 <code>Terminating</code>——节点上没有 kubelet 去真正终止它们;<code>p-default</code> 和 <code>p-forever</code> 仍是 <code>Running</code>。</p>'),
     ('kubelet 回来之后', '<p>重新启动 kubelet,32 秒后:污点已清除,<code>p-30s</code> 被清理,<code>dep</code> 只剩 1 个 Running 的 Pod,<code>p-default</code> 和 <code>p-forever</code> 一直没被动过——它们没到驱逐时间(默认 300 秒、无限容忍)。所以默认配置下节点短暂失联(五分钟内)不会驱逐 Pod;要更快迁移,就给 Pod 写更短的 <code>tolerationSeconds</code>。有状态应用要小心:Pod 被标记删除但旧节点上的容器可能还在跑。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0),在 worker2 上 systemctl stop kubelet 模拟失联(节点上的容器仍在运行,只是没有 kubelet);时间线每秒轮询节点与 Pod 状态,单次测量,失联到 Unknown 的时间在多次运行里是 44~52 秒;每种情形各一次',
     '没有验证:真正的节点宕机(网络分区时旧节点上的容器仍在写数据,这里的容器还在运行);Pod 优雅期较长时的终止顺序;StatefulSet 的行为(不会自动替换,需要强制删除);--pod-eviction-timeout 等控制器参数;Taint-based eviction 的速率限制(zone 不健康时降速);NodeOutOfServiceVolumeDetach 之类的非优雅关机处理'],
    '失联与驱逐', PANELS)
