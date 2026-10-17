from lib import *
S = SS('k56')
F1 = [['kubectl apply 新值', ''], ['kubelet 周期同步', '约 60~86 秒'], ['挂载的文件', '变了'], ['环境变量', '不变']]
F2 = [['新建带时间戳目录', ''], ['..data 符号链接切换', '原子'], ['旧目录删除', ''], ['level → ..data/level', '路径不变']]
F3 = [['ConfigMap 已是 v5', ''], ['环境变量', '仍是 v1'], ['容器重启(uid 不变)', 'restartCount=1'], ['环境变量', 'v5']]
F4 = [['删除 ConfigMap', ''], ['Pod', '仍然 Running'], ['挂载的文件', '还是 v5'], ['事件', 'FailedMount']]
PANELS = [('f', 'flow', 'ConfigMap 更新'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("Pod 里同时有 env(configMapKeyRef)和挂载的 ConfigMap。连续改 3 次 ConfigMap(v2、v3、v4),挂载文件在 apply 后 60.0、66.7、76.0 秒才在容器里读到新内容;这期间和之后环境变量 LEVEL 始终是 v1,文件最终是 v4。", f=fl(F1, cur=[1], mark=[3], done=[2]), t=tl(S(1), mark=lidx(S(1), '延迟(秒)'), done=lidx(S(1), "文件 /etc/cfg/level='v4'")), b=bars([['第 1 次改', 60.0, '60.0 s'], ['第 2 次改', 66.7, '66.7 s'], ['第 3 次改', 76.0, '76.0 s']], 90, done=[0, 1, 2]), kv=KV([['文件', '由 kubelet 周期性同步,延迟上限约一分多钟'], ['环境变量', '容器启动时一次性注入,之后不变'], ['延迟不固定', '60~76 秒,另一次测到 86 秒']], ['文件'])),
    step("更新前 ..data -> ..2026_10_10_14_43_46.…,level -> ..data/level;更新后 ..data 指向新目录 ..2026_10_10_14_45_14.…,level 的路径不变,旧的时间戳目录已被删除(\"是否还在\" 为 False)。kubelet 先写好整个新目录,再把 ..data 符号链接一次性切过去,读文件的进程看到的总是完整的一份。", f=fl(F2, cur=[1], done=[0, 2, 3]), t=tl(S(2), mark=lidx(S(2), '..data ->'), done=lidx(S(2), '是否还在')), kv=KV([['..data', '指向当前版本目录的符号链接'], ['level', '永远是 ..data/level,路径不变'], ['切换', '换链接,不是改文件内容']], ['..data'])),
    step("这时 ConfigMap 里 level 是 v5,容器的环境变量 LEVEL 仍是 v1。用 crictl 停掉容器、让 kubelet 重启它(restartCount=1,Pod uid 没变)之后,LEVEL 是 v5——环境变量在容器每次启动时重新取值,不需要重建 Pod。", f=fl(F3, cur=[2], mark=[1], done=[3]), t=tl(S(3), mark=lidx(S(3), "LEVEL='v1'"), done=lidx(S(3), "LEVEL='v5'")), kv=KV([['容器重启', '会重新读 ConfigMap 注入环境变量'], ['Pod uid', '不变,没有重建 Pod'], ['想让改动生效', '重启容器或 rollout restart']], ['容器重启'])),
    step("删除 ConfigMap cfg 之后,Pod 仍然 Running,挂载的 /etc/cfg/level 5 秒后和 100 秒后都还是 v5;只是 Pod 上多了事件 FailedMount: MountVolume.SetUp failed for volume \"cfg\" : configmap \"cfg\" not found。", f=fl(F4, cur=[1], done=[2], mark=[3]), t=tl(S(4), mark=lidx(S(4), 'FailedMount'), done=lidx(S(4), '100 秒后')), kv=KV([['已挂载', '删除 ConfigMap 不影响运行中的 Pod'], ['新 Pod', '会因 FailedMount 卡在 ContainerCreating'], ['文件内容', '保持最后一次同步的版本']], ['已挂载'])),
]
A = mkartk('k56', 56, 'Kubernetes,ConfigMap,热更新,环境变量,kubelet,符号链接,真实验证,动画演示',
    '在 kind 集群里实测 ConfigMap 更新:挂载的文件要等 kubelet 同步,连续三次测到 60.0、66.7、76.0 秒(另一次 86 秒),环境变量始终不变;文件靠 ..data 符号链接整体切换,路径不变、旧目录被删;重启容器(不用重建 Pod)后环境变量才取到新值;删除 ConfigMap 后已运行的 Pod 不受影响,文件保留最后的版本,只多一条 FailedMount 事件。',
    '改了 ConfigMap,容器里多久能看到?环境变量会跟着变吗?更新是原子的吗?把 ConfigMap 删了会怎样?这篇在真集群里改三次、测三次延迟,读符号链接,重启容器,逐个回答。',
    [('60~86 秒', '改 ConfigMap 后挂载的文件在容器里更新所需的时间'), ('环境变量不变', '无论等多久,只有容器重启才会取新值'), ('..data', '更新靠切换这个符号链接,而不是改文件')],
    [('文件会变,环境变量不会', '<p>Pod 里同时用 <code>env.valueFrom.configMapKeyRef</code> 和挂载。连续改 3 次 ConfigMap,挂载的文件分别在 60.0、66.7、76.0 秒后才在容器里读到新值(另一次测到 86 秒)——kubelet 靠周期同步,不是 watch 到变化马上写。环境变量始终是 <code>v1</code>:它在容器启动时一次性注入,之后无论怎么改 ConfigMap 都不会变。</p>'),
     ('原子切换靠 ..data', '<p>挂载目录里每个键是 <code>level -> ..data/level</code> 的符号链接,<code>..data</code> 再指向一个带时间戳的目录。更新时 kubelet 先把完整的新目录写好,再把 <code>..data</code> 一次性改指向新目录,最后删掉旧目录:读文件的进程不会读到“一半新一半旧”。这也是 <code>subPath</code> 挂载不更新的根源(下一篇)。</p>'),
     ('环境变量要等容器重启', '<p>ConfigMap 已经是 <code>v5</code>,环境变量还是 <code>v1</code>。用 crictl 停掉容器,kubelet 重启它(<code>restartCount=1</code>,Pod uid 没变),新容器里 <code>LEVEL</code> 就是 <code>v5</code>。所以改 ConfigMap 想让环境变量生效,重启容器就够,不一定要重建 Pod;常见做法是 <code>kubectl rollout restart</code>。</p>'),
     ('删掉 ConfigMap', '<p>删除 ConfigMap 之后,运行中的 Pod 仍是 <code>Running</code>,<code>/etc/cfg/level</code> 5 秒后和 100 秒后都还是 <code>v5</code>:kubelet 同步失败只产生一条 <code>FailedMount: … configmap "cfg" not found</code> 事件,不会把已有文件清掉。但此时新建的 Pod 没法挂载它,会卡在 <code>ContainerCreating</code>。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);延迟是每 0.5 秒 kubectl exec 读一次文件得到的相对 apply 的时间;kubelet 默认同步周期约 1 分钟加缓存延迟,所以延迟在 60~90 秒间波动;容器用 crictl 在节点上停止来触发 kubelet 重启;每种情形各一次(第一节连测 3 次)',
     '没有验证:kubelet 配置 configMapAndSecretChangeDetectionStrategy 不同取值(Watch / Cache / Get)对延迟的影响;syncFrequency 参数调小之后的延迟;Secret 挂载是否同样 60~90 秒(同一机制,但本文没有单独测);immutable ConfigMap(见后面一篇);二进制数据 binaryData;应用用 inotify 监听 ..data 的行为'],
    'ConfigMap 更新', PANELS)
