from lib import *
S = SS('k9')
F1 = [['team-a', 'a, shared=val-x'], ['team-b', 'b, shared=val-y'], ['.data.shared', '两人都要'], ['结果', '409 冲突']]
F2 = [['--force-conflicts', 'team-b 抢走'], ['team-a 原样再来', '冲突'], ['team-a 改成 val-y', '共同拥有']]
F3 = [['team-a 去掉 shared', '字段还在'], ['team-a 去掉 a', 'a 被删除'], ['team-b 清空', '字段都被删']]
F4 = [['deployer apply', 'replicas: 1'], ['kubectl scale 3', '夺走 replicas'], ['deployer 再 apply 1', '冲突'], ['改成 3', '共同拥有']]
PANELS = [('f', 'flow', '字段所有权'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("team-a 申请 {a: 1, shared: val-x},managedFields 里 a、shared 都归 team-a(Apply)。team-b 申请 {b: 2, shared: val-y}:退出码 1,error: Apply failed with 1 conflict: conflict with \"team-a\": .data.shared,后面跟着 11 行解决办法提示;对象一个字节都没变,data 仍是 {a: 1, shared: val-x}。", f=fl(F1, cur=[2], mark=[3], done=[0]), t=tl(S(1), mark=lidx(S(1), 'Apply failed with 1 conflict'), done=lidx(S(1), 'team-a 申请')), kv=KV([['managedFields', '记录每个字段归哪个管理者'], ['冲突', '同一字段、不同值、不同管理者'], ['失败时', '整个申请被拒绝,对象不变']], ['冲突'])),
    step("team-b 加 --force-conflicts:成功,shared 的所有者变成 team-b,data={a: 1, b: 2, shared: val-y};team-a 再按原样申请 shared: val-x → 冲突,conflict with \"team-b\";team-a 把 shared 改成和现值相同的 val-y 再申请:成功,shared 的所有者变成 team-a(Apply)+team-b(Apply)。", f=fl(F2, cur=[0], mark=[1], done=[2]), t=tl(S(2), mark=lidx(S(2), 'team-a 再按原样申请'), done=lidx(S(2), 'team-a(Apply)+team-b(Apply)')), kv=KV([['--force-conflicts', '抢走所有权,值被覆盖'], ['被抢的一方', '下次申请原值会冲突'], ['值相同', '不冲突,变成共同所有者']], ['值相同'])),
    step("共同拥有 shared 时,team-a 的申请里去掉 shared:shared 还在(team-b 仍拥有);再去掉 a:a 被删除,data={b: 2, shared: val-y};team-b 把申请清空:所有字段都被删除,data 为空。只有“最后一个所有者”不再申请某个字段,它才会被删掉。", f=fl(F3, cur=[1], mark=[2], done=[0]), t=tl(S(3), mark=lidx(S(3), '去掉 shared', '连 a 也去掉'), done=lidx(S(3), '清空')), kv=KV([['去掉共有的字段', '字段保留'], ['去掉独占的字段', '字段被删除'], ['申请就是“期望状态”', '没写的东西由你负责删掉']], ['去掉独占的字段'])),
    step("Update 也会成为字段所有者:deployer 申请 replicas: 1 后用 kubectl scale 改成 3,managedFields 里 replicas 变成 kubectl(Update,subresource=scale)所有,deployer(Apply)只剩 selector、template;deployer 再按 replicas: 1 申请 → conflict with \"kubectl\" with subresource \"scale\":.spec.replicas;改成 replicas: 3(与现值相同)申请成功。", f=fl(F4, cur=[1], mark=[2], done=[0, 3]), t=tl(S(4), mark=lidx(S(4), 'subresource=scale', '再按 replicas: 1 申请'), done=lidx(S(4), '与现值相同')), kv=KV([['kubectl scale / patch', '操作类型是 Update,也会占有字段'], ['apply 遇到它们', '同样要解决冲突'], ['HPA 管 replicas 时', 'manifest 里不要再写 replicas']], ['kubectl scale / patch'])),
]
A = mkartk('k9', 9, 'Kubernetes,Server-Side Apply,managedFields,字段所有权,冲突,真实验证,动画演示',
    '在 kind 集群里实测 Server-Side Apply 的字段所有权:team-a 与 team-b 申请同一字段得到 Apply failed with 1 conflict,对象不变;--force-conflicts 抢走所有权,被抢的一方原样再申请又冲突;把值改成与现值相同则共同拥有;共有字段被一方去掉仍保留,独占字段去掉就被删除;kubectl scale 这样的 Update 也会占有 replicas,再用 apply 申请不同的值会冲突。',
    'kubectl apply --server-side 和老的 client-side apply 最大的不同是:服务端记录“每个字段是谁写的”。这篇用两个管理者争同一个字段,把冲突、抢占、共同拥有和删除的规则都跑了一遍,再看 kubectl scale 这种 Update 是怎么悄悄抢走 replicas 的。',
    [('1 conflict', 'team-b 申请 team-a 已拥有的 shared 字段时的结果,对象一个字节都没变'), ('team-a(Apply)+team-b(Apply)', '值相同之后 shared 字段的所有者'), ('kubectl(Update, scale)', 'kubectl scale 之后 spec.replicas 的所有者,deployer 不再拥有它')],
    [('冲突', '<p><code>kubectl apply --server-side --field-manager=team-a</code> 之后,<code>managedFields</code> 里 <code>a</code> 和 <code>shared</code> 都归 team-a。team-b 申请 <code>{b: 2, shared: val-y}</code> 得到 <code>Apply failed with 1 conflict: conflict with "team-a": .data.shared</code>,整个申请被拒绝,<code>b</code> 也没写进去。冲突的条件是:同一个字段、值不同、管理者不同。</p>'),
     ('抢占与共同拥有', '<p><code>--force-conflicts</code> 让 team-b 抢走 <code>shared</code>(值变成 <code>val-y</code>),被抢的 team-a 按原样再申请就会反过来冲突。解决冲突还有第三种办法:把自己申请里的值改成和现值一样(<code>val-y</code>),不但不冲突,<code>shared</code> 的所有者还变成 <code>team-a(Apply)+team-b(Apply)</code>。</p>'),
     ('删除字段', '<p>申请就是“我期望自己负责的字段是这样”。共同拥有 <code>shared</code> 时 team-a 不再写它,字段还在(team-b 仍拥有);team-a 不再写 <code>a</code>,<code>a</code> 就被删除了;team-b 把申请清空,剩下的字段也跟着删掉。client-side apply 靠 last-applied 注解做到这件事,server-side apply 靠的是字段所有权。</p>'),
     ('Update 与 Apply', '<p>字段所有权不只属于 Apply:<code>kubectl scale</code> 是 <code>Update</code>,它改完之后 <code>spec.replicas</code> 归 <code>kubectl</code>(<code>subresource=scale</code>)所有,deployer 手里只剩 <code>selector</code> 和 <code>template</code>。deployer 再按 <code>replicas: 1</code> 申请就会冲突。典型场景:HPA 或有人手动 scale 了 Deployment,而 manifest 里还写着 <code>replicas</code>——要么去掉这个字段,要么用 <code>--force-conflicts</code> 明确夺回。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);所有管理者用 kubectl apply --server-side --field-manager=<名字> 模拟,所有者信息来自 kubectl get --show-managed-fields -o json;对象是 k9 命名空间里的 ConfigMap cfg 和 Deployment web(busybox:1.36);测试值用 val-x / val-y(YAML 里未加引号的 y 会被 kubectl 当成布尔值 true,实验时踩到过);每种情形各一次',
     '没有验证:Apply 对列表(map 型与 atomic 型)的所有权规则;转移所有权(把 Update 管理者改成 Apply 管理者)的迁移流程;冲突时 kubectl 的 --force-conflicts 对 HPA 等控制器的后果;managedFields 的大小对 etcd 的开销;CRD 里 x-kubernetes-list-type 对合并的影响'],
    '字段所有权', PANELS)
