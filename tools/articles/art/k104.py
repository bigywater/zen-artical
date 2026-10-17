from lib import *
S = SS('k104')
F1 = [['节点 capacity', '485473984512 字节 = df 的总大小'], ['allocatable', '同上,无预留'], ['requests 100Ti', 'Pending'], ['调度失败原因', 'Insufficient ephemeral-storage']]
F2 = [['写 120MiB 到容器根', 'limit 50Mi'], ['23 秒后', 'Failed / Evicted'], ['message', 'exceeds the total limit of containers 50Mi']]
F3 = [['写 120MiB 到磁盘 emptyDir', 'limit 50Mi'], ['33 秒后', 'Failed / Evicted'], ['同样的 message', '可写层和 emptyDir 合并计算']]
F4 = [['写 120MiB 到 Memory emptyDir', 'tmpfs'], ['100 秒后', 'Running'], ['算内存,不算 ephemeral-storage', '']]
PANELS = [('f', 'flow', '临时存储'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("节点 worker 的 capacity.ephemeral-storage=485473984512 字节,allocatable 与它相同(没有预留),正好是节点上 /var 所在文件系统 df 显示的总大小 474095688 KiB。requests.ephemeral-storage: 100Ti 的 Pod 一直 Pending,PodScheduled=False,0/3 nodes are available: … 2 Insufficient ephemeral-storage。", f=fl(F1, cur=[2], done=[0, 1, 3]), t=tl(S(1), mark=lidx(S(1), '节点 worker', '对照 df'), done=lidx(S(1), '100Ti')), kv=KV([['像 CPU/内存一样调度', 'requests 参与调度,limits 参与驱逐'], ['来源', 'kubelet 统计的 nodefs / imagefs 容量'], ['控制面节点', '带污点,所以是 2 个节点 Insufficient']], ['requests 参与调度'])),
    step("limits.ephemeral-storage: 50Mi 的容器往自己的根文件系统写 120 MiB:23 秒后 Pod 被驱逐,phase=Failed、reason=Evicted、message=Pod ephemeral local storage usage exceeds the total limit of containers 50Mi.,事件也是 Evicted 同样的内容。被驱逐的 Pod 对象还在(Failed),容器已被杀。", f=fl(F2, cur=[1], done=[0, 2]), t=tl(S(2), done=lidx(S(2), '写 120 MiB 到容器根文件系统', '事件')), kv=KV([['可写层算 ephemeral-storage', '容器里写的文件'], ['kubelet 周期性检查', '不是实时的(这里约 23 秒)'], ['驱逐不是 OOM', '没有 OOMKilled,是 kubelet 主动 Evicted']], ['可写层'])),
    step("同样 limit 50Mi,往磁盘型 emptyDir 写 120 MiB:33 秒后同样 Failed / Evicted,message 同样是 Pod ephemeral local storage usage exceeds the total limit of containers 50Mi.——kubelet 把容器可写层和磁盘型 emptyDir 合在一起,和 Pod 所有容器 limits 之和比较。", f=fl(F3, cur=[1], done=[0, 2]), t=tl(S(3), done=lidx(S(3), '写 120 MiB 到 emptyDir')), kv=KV([["合并计算", "可写层 + emptyDir"], ['比较对象', 'Pod 总用量对容器 limits 之和'], ['emptyDir.sizeLimit', '另一条独立的线,见 k54']], ['合并计算'])),
    step("medium: Memory 的 emptyDir 是 tmpfs:写 120 MiB 也不会触发 ephemeral-storage 驱逐,100 秒后 Pod 仍是 Running(这部分算内存,计入容器内存,不计入 ephemeral-storage)。", f=fl(F4, cur=[1], done=[0, 2]), t=tl(S(4), done=lidx(S(4), '写 120 MiB 到 medium: Memory')), kv=KV([['tmpfs 算内存', '不算 ephemeral-storage'], ['用 Memory 要设内存 limit', '见 k54:会触发 OOM'], ['选哪个', '磁盘型受 ephemeral-storage 管,内存型受内存管']], ['tmpfs 算内存'])),
]
A = mkartk('k104', 104, 'Kubernetes,ephemeral-storage,临时存储,驱逐,emptyDir,真实验证,动画演示',
    '在 kind 集群里实测 ephemeral-storage:节点 capacity 就是 df 的总大小(485473984512 字节)且 allocatable 无预留;requests 100Ti 的 Pod 因 Insufficient ephemeral-storage 一直 Pending;limit 50Mi 的 Pod 往容器可写层或磁盘型 emptyDir 写 120 MiB,分别在 23 秒和 33 秒后被 kubelet 以 Evicted 驱逐;内存型 emptyDir 不计入,100 秒后仍 Running。',
    '容器往根文件系统写了很多东西会怎样?ephemeral-storage 的 limit 超了是 OOM 吗?emptyDir 和可写层是分开算还是合起来算?tmpfs 算不算?这篇各写 120 MiB 到三个地方,看哪个会被驱逐、多久被驱逐。',
    [('23 / 33 秒', '可写层 / 磁盘型 emptyDir 超过 50Mi limit 后被驱逐所用的时间'), ('Evicted', '超限的结果是 kubelet 驱逐 Pod,不是 OOMKilled'), ('Memory 不算', 'medium: Memory 的 emptyDir 写 120 MiB,100 秒后仍 Running')],
    [('容量与调度', '<p>节点 worker 的 <code>capacity.ephemeral-storage</code> 是 485473984512 字节,<code>allocatable</code> 与它相同(没有预留),正好是节点上 <code>/var</code> 所在文件系统 <code>df</code> 显示的总大小(474095688 KiB)。<code>requests.ephemeral-storage: 100Ti</code> 的 Pod 一直 Pending,<code>PodScheduled=False</code>,<code>0/3 nodes are available: … 2 Insufficient ephemeral-storage</code>(控制面节点因污点被排除)。</p>'),
     ('可写层超限', '<p><code>limits.ephemeral-storage: 50Mi</code> 的容器往自己的根文件系统写 120 MiB:23 秒后 Pod 被驱逐,<code>phase=Failed</code>、<code>reason=Evicted</code>、<code>message=Pod ephemeral local storage usage exceeds the total limit of containers 50Mi.</code>,事件同样是 <code>Evicted</code>。被驱逐的 Pod 对象还在(<code>Failed</code>),容器已被杀。它不是 OOM,没有 <code>OOMKilled</code>,是 kubelet 周期性检查后主动驱逐的,所以有十几秒到几十秒的延迟。</p>'),
     ('emptyDir 一起算', '<p>同样 limit 50Mi,往磁盘型 emptyDir 写 120 MiB:33 秒后同样 <code>Failed / Evicted</code>,message 也是 <code>Pod ephemeral local storage usage exceeds the total limit of containers 50Mi.</code>——kubelet 把容器可写层和磁盘型 emptyDir 合在一起,与 Pod 所有容器 limits 之和比较。</p>'),
     ('内存型不算', '<p><code>medium: Memory</code> 的 emptyDir 是 tmpfs:写 120 MiB 也不触发 ephemeral-storage 驱逐,100 秒后 Pod 仍是 <code>Running</code>——这部分算内存(计入容器内存),不算 ephemeral-storage(内存型 emptyDir 写超内存 limit 的后果见 k54)。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0),节点是 Docker 容器,文件系统共享宿主机的虚拟磁盘,所以容量数字是宿主磁盘的大小;驱逐时间是 2 秒间隔轮询 Pod 状态得到,单次测量(kubelet 的检查周期决定了它在十几到几十秒之间波动);写入用 dd;每种情形各一次',
     '没有验证:容器日志大小计入 ephemeral-storage(日志轮转 containerLogMaxSize / containerLogMaxFiles);LocalStorageCapacityIsolation 特性关闭时的行为;节点级 nodefs / imagefs 压力驱逐(见 k31);limit 不设时的 Pod 优先级;ephemeral-storage 在 LimitRange / ResourceQuota 里的用法(本文只验证了 Pod 级)'],
    '临时存储', PANELS)
