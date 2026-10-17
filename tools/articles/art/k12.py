from lib import *
S = SS('k12')
F1 = [['kubectl delete', '39 ms 返回'], ['apiserver', '设 deletionTimestamp'], ['对象', '还在,等 finalizer'], ['控制器', '清理后摘 finalizer']]
F2 = [['改 data', '允许'], ['加 finalizer', 'Forbidden'], ['再删一次', '时间戳不变'], ['撤销删除', '(no change)']]
F3 = [['kubectl delete', '默认等待'], ['4 秒后摘 finalizer', '控制器完成清理'], ['对象消失', '共等 4.1 秒']]
F4 = [['PVC', 'pvc-protection'], ['delete pvc', 'Bound + deletionTimestamp'], ['Pod 删除', 'PVC 随即消失']]
PANELS = [('f', 'flow', '删除的两个阶段'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("ConfigMap a 的 metadata.finalizers 里写了 example.com/block。kubectl delete cm a --wait=false 39 毫秒就返回 deleted,但对象还在:deletionTimestamp 已经设置、deletionGracePeriodSeconds=0、finalizers 仍是 ['example.com/block'],data 原样保留。", f=fl(F1, cur=[1], mark=[2], done=[0]), t=tl(S(1), mark=lidx(S(1), 'deletionTimestamp=', 'data 还在')), kv=KV([['delete 带 finalizer 的对象', '只设置 deletionTimestamp'], ['对象', '继续存在,可读可写'], ['谁来摘 finalizer', '写下它的控制器']], ['delete 带 finalizer 的对象'])),
    step("“正在删除”的对象:改 data 允许;再加一个 finalizer → Forbidden: no new finalizers can be added if the object is being deleted;再删一次,deletionTimestamp 不变;用 JSON patch 删掉 deletionTimestamp → (no change),撤销不了;同名重建 → object is being deleted: configmaps \"a\" already exists。", f=fl(F2, cur=[1], mark=[3], done=[0, 2]), t=tl(S(2), mark=lidx(S(2), 'Forbidden', 'no change', 'already exists'), done=lidx(S(2), '改 data', '没有变化')), kv=KV([['只能减不能加', '新增 finalizer 被拒绝'], ['deletionTimestamp', '设置后不可撤销'], ['同名重建', '失败,直到旧对象真正消失']], ['只能减不能加'])),
    step("kubectl delete cm b(默认 --wait=true),4 秒后由“控制器”把 finalizers 置空:命令一直等了 4.1 秒才返回,之后 get 得到 NotFound。有两个 finalizer 的 c:摘掉一个,对象还在,剩下 ['example.com/second'];摘掉最后一个,对象才消失。", f=fl(F3, cur=[1], done=[2]), t=tl(S(3), mark=lidx(S(3), '总共等了 4.1 秒', '只摘掉一个'), done=lidx(S(3), 'NotFound', '再摘掉最后一个')), kv=KV([['kubectl delete', '默认等到对象真的没了'], ['多个 finalizer', '全部摘光才消失'], ['控制器要做的', '先清理,再摘自己的那一个']], ['多个 finalizer'])),
    step("内置的 finalizer:PVC data 带着 kubernetes.io/pvc-protection,Pod user 正在使用它。kubectl delete pvc data 之后 PVC 仍是 Bound,deletionTimestamp 已设置;删除用它的 Pod 之后 PVC 约 0.1 秒内消失。", f=fl(F4, cur=[1], done=[2]), t=tl(S(4), mark=lidx(S(4), 'kubectl delete pvc data 之后'), done=lidx(S(4), 'PVC 消失了')), kv=KV([['pvc-protection', '有 Pod 在用就不让删'], ['Pod 删完', '控制器摘掉 finalizer'], ['PVC 的状态', '仍是 Bound,只是被标记删除']], ['pvc-protection'])),
]
A = mkartk('k12', 12, 'Kubernetes,Finalizer,deletionTimestamp,对象删不掉,pvc-protection,真实验证,动画演示',
    '在 kind 集群里实测 finalizer:带 finalizer 的 ConfigMap 被 delete 后 39 毫秒返回但对象仍在,只多了 deletionTimestamp;正在删除的对象能改 data、不能新增 finalizer、不能撤销删除、不能同名重建;kubectl delete 默认等到最后一个 finalizer 被摘掉(这次等了 4.1 秒);内置的 kubernetes.io/pvc-protection 让被 Pod 使用的 PVC 保持 Bound 直到 Pod 删除。',
    '对象删不掉?十有八九是 metadata.finalizers 里还有人没点头。这篇在 ConfigMap 上模拟一个“控制器”,把带 finalizer 对象的删除过程拆成两步看清楚:先打标记、再摘 finalizer;并用 PVC 保护这个内置例子对照真实场景。',
    [('39 ms', '带 finalizer 的对象 kubectl delete --wait=false 的返回时间,而对象仍然存在'), ('Forbidden', '给正在删除的对象新增 finalizer 的结果'), ('4.1 秒', 'kubectl delete 默认等到“控制器”摘掉 finalizer 所花的时间')],
    [('删除其实是两步', '<p>对象带着 <code>finalizers</code> 时,<code>kubectl delete</code> 几十毫秒就返回 <code>deleted</code>,但对象还在:apiserver 只做了一件事,把 <code>metadata.deletionTimestamp</code> 设上。这时 <code>kubectl get</code> 照常能读到,<code>data</code> 原样保留。真正的删除要等 <code>finalizers</code> 变空,由写下这个 finalizer 的控制器负责:先做完清理工作,再把自己那一项摘掉。</p>'),
     ('正在删除的对象还能做什么', '<p>改 <code>data</code> 仍然允许;新增 finalizer 被拒绝(<code>no new finalizers can be added if the object is being deleted</code>);再删一次不会改变 <code>deletionTimestamp</code>;想用 patch 把 <code>deletionTimestamp</code> 删掉得到 <code>(no change)</code>,撤销不了;同名重建报 <code>object is being deleted: configmaps "a" already exists</code>。规则很简单:finalizer 只能减不能加。</p>'),
     ('摘掉 finalizer', '<p><code>kubectl delete</code> 默认等到对象真的消失才返回:“控制器”4 秒后把 finalizers 置空,命令就等了 4.1 秒。有多个 finalizer 时必须全部摘光,摘掉一个对象仍在。所谓“强制删除卡住的对象”,就是替那个不工作的控制器把 finalizer 摘掉——对象会立刻消失,但它本该做的清理没有发生。</p>'),
     ('内置例子:PVC 保护', '<p>PVC 创建时就带着 <code>kubernetes.io/pvc-protection</code>。Pod user 正在使用它时 <code>kubectl delete pvc data</code>,PVC 仍是 <code>Bound</code>,只是多了 <code>deletionTimestamp</code>;把用它的 Pod 删掉后,PVC 在约 0.1 秒内消失。这个 finalizer 防止的是“卷还在被挂载时底层存储被回收”。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);对象是 k12 命名空间里的 ConfigMap,finalizer 是自己起的名字 example.com/block(没有真正的控制器,由脚本在需要时 patch 摘掉);PVC 用 kind 默认的 local-path StorageClass,Pod 用 busybox:1.36 并等到 Running 后再删 PVC;实验末尾摘掉了故意留下的 finalizer,否则命名空间会卡在 Terminating;每种情形各一次',
     '没有验证:foregroundDeletion 与 orphan 这两个由垃圾回收器管理的 finalizer(下一篇);自定义资源上 finalizer 的差别;finalizer 名字的格式校验(这里只用了合法名字);PV 的 pv-protection;apiserver 重启时 deletionTimestamp 的持久化(它本来就存在 etcd 里);强制删除(--force --grace-period=0)对带 finalizer 对象的行为'],
    '两步删除', PANELS)
