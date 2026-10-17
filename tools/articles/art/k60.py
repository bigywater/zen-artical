from lib import *
S = SS('k60')
F1 = [['immutable: true', ''], ['改 data / 增键', 'Forbidden'], ['immutable 改回 false', 'Forbidden'], ['改 labels', '允许'], ['可变 → 加锁', '允许,单向']]
F2 = [['删除 fixed 并重建', '值 debug'], ['mutable 被 patch', '87 秒后更新'], ['Pod 里 /f/level', '100 秒后仍是 info'], ['要新值', '重建 Pod']]
F3 = [['20 个可变 ConfigMap', 'watch +20'], ['20 个 immutable', 'watch +2'], ['kubelet', '不再 watch immutable 对象']]
PANELS = [('f', 'flow', 'immutable'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("immutable: true 的 ConfigMap:改 data 返回 Forbidden: field is immutable when `immutable` is set,新增一个键同样被拒,把 immutable 改回 false 也被拒;改 labels/annotations 可以;可变的 ConfigMap 可以补上 immutable: true(单向锁定),锁定之后再改 data 退出码 1。", f=fl(F1, cur=[1, 2], done=[0, 3, 4]), t=tl(S(1), mark=lidx(S(1), '退出码 1'), done=lidx(S(1), '元数据仍可改', '可以单向锁定')), kv=KV([['data', '创建后不能改'], ['immutable', '只能从 false 变 true,不能反过来'], ['元数据', 'labels、annotations 仍可改']], ['data'])),
    step("一个 Pod 同时挂 immutable 的 fixed 和可变的 mutable。把 fixed 删掉重建成值 debug,同时 patch mutable 为 debug:mutable 在 87 秒后 /m/level 变成 debug;等了 100 秒,/f/level 依然是 info——immutable 的对象被 kubelet 当成不会变,不再同步,新建同名对象也不行。", f=fl(F2, cur=[1], mark=[2], done=[0, 3]), t=tl(S(2), mark=lidx(S(2), '87 秒后', '依然是旧值'), done=lidx(S(2), '等了 100 秒')), kv=KV([['可变的', 'kubelet 周期同步,87 秒后更新'], ['immutable', '删除重建也不更新运行中的 Pod'], ['想用新值', '重建 Pod(通常改名字+滚动更新)']], ['immutable'])),
    step("20 个 Pod 各挂自己的 1 个 ConfigMap:可变版本的按名字 watch ConfigMap 的长连接数从 16 增加到 36(+20);immutable 版本从 14 增加到 16(+2)。kubelet 对 immutable 对象不再 watch,apiserver 少了与对象数成正比的长连接。", f=fl(F3, cur=[0, 1], done=[2]), t=tl(S(3), mark=lidx(S(3), '增加 20'), done=lidx(S(3), '增加 2)', '差别')), b=bars([['可变 ConfigMap', 20, '+20'], ['immutable ConfigMap', 2, '+2']], 20, done=[1], mark=[0]), kv=KV([['可变', '每个被挂载的对象一个 watch'], ['immutable', '只剩 +2(未逐个确认是哪两个)'], ['规模大时', '减少 apiserver 压力']], ['immutable'])),
]
A = mkartk('k60', 60, 'Kubernetes,ConfigMap,Secret,immutable,watch,kubelet,真实验证,动画演示',
    '在 kind 集群里实测不可变 ConfigMap:immutable: true 之后 data 不能改、不能撤销标志,元数据仍能改,可变对象可单向加锁;删除重建同名 immutable 对象,运行中的 Pod 100 秒后挂载的仍是旧值;20 个 Pod 各挂一个 ConfigMap 时,可变版本让按名字 watch 的连接数 +20,immutable 版本只 +2。',
    'immutable: true 为什么能减轻 apiserver 压力?它到底锁了什么?删了重建会怎样?这篇改了又改、删了又建,再用 apiserver 的 /metrics 数 watch 连接,看到差别。',
    [('+20 vs +2', '20 个 Pod 各挂一个 ConfigMap 时,按名字 watch ConfigMap 的连接数增量(可变 / immutable)'), ('只能 false → true', 'immutable 标志的方向是单向的'), ('100 秒', '删除重建同名 immutable 对象后,运行中的 Pod 等 100 秒仍是旧值')],
    [('锁住的是 data', '<p>给 ConfigMap 加 <code>immutable: true</code> 后,改 <code>data</code> 返回 <code>Forbidden: field is immutable when `immutable` is set</code>,新增键同样被拒,把 <code>immutable</code> 改回 <code>false</code> 也被拒;但 <code>labels</code>、<code>annotations</code> 这些元数据仍可修改。可变的 ConfigMap 可以随时补上 <code>immutable: true</code>,方向只能是 false → true。</p>'),
     ('改内容只能新建', '<p>Pod 挂着可变的 <code>mutable</code> 和 immutable 的 <code>fixed</code>。把 <code>fixed</code> 删掉重建成新值 <code>debug</code>,同时 patch <code>mutable</code>:<code>mutable</code> 在 87 秒后 <code>/m/level</code> 变 <code>debug</code>;等了 100 秒,<code>/f/level</code> 仍是 <code>info</code>——kubelet 把 immutable 对象视为不会变,不再同步,新建的同名对象也不会替换运行中的 Pod 已挂载的内容。要用新值只能换名字并滚动更新 Pod。</p>'),
     ('少了多少 watch', '<p>kubelet 对可变的 ConfigMap 为每个被挂载的对象保持一个按名字的 watch。20 个 Pod 各挂一个自己的 ConfigMap:可变版本让 <code>apiserver_longrunning_requests{verb="WATCH",resource="configmaps",scope="resource"}</code> 从 16 增加到 36(+20);immutable 版本从 14 增加到 16(+2)。那 +2 应该是新命名空间里本来就有的可变对象(比如 <code>kube-root-ca.crt</code>),我没有逐个确认。在节点和 Pod 很多的集群里,这是 apiserver 的压力来源之一。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);watch 数取自 apiserver /metrics 里 apiserver_longrunning_requests 中 verb=WATCH、resource=configmaps、scope=resource 的总和(按名字 watch 单个对象的连接);每次创建 20 对 ConfigMap + Pod 并等全部 Running 后再等 10 秒读指标;可变与 immutable 各一次,在不同命名空间里先后进行;每种情形各一次',
     '没有验证:Secret 上的 immutable 是否同样的 watch 效果(机制相同,本文只数了 ConfigMap);kubelet 的 configMapAndSecretChangeDetectionStrategy 取其他值时的差别;immutable 对 apiserver CPU/内存/etcd 的实际下降量;那 +2 具体是哪两个;大规模(数千个)对象下的差别'],
    '不可变', PANELS)
