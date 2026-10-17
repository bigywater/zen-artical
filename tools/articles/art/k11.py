from lib import *
S = SS('k11')
F1 = [['last-applied', '{a:1, b:2}'], ['live', '{a:hand-edited, b:2, c:3}'], ['这次的 manifest', '{a:10}'], ['结果', '{a:10, c:3}']]
F2 = [['kubectl create', '没有 last-applied'], ['apply 去掉 k2', '无“上次”可比'], ['k2 保留', '并补写 last-applied']]
F3 = [['--server-side', '不写注解'], ['managedFields', '改用字段所有权']]
F4 = [['create 270000 字节', '成功'], ['apply 同样大小', '注解 > 262144 字节'], ['--server-side', '成功']]
PANELS = [('f', 'flow', '三方合并'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("第一次 apply {a: 1, b: 2},注解 last-applied 里记下 data={a: 1, b: 2}。有人手工 patch 了 {c: 3, a: hand-edited}(集群里变成 {a: hand-edited, b: 2, c: 3},注解不变)。再 apply {a: 10}(去掉了 b):结果是 {a: 10, c: 3},注解变成 {a: 10}——a 以这次的为准,b 在上次有这次没有 → 删除,c 不在任何一次 apply 里 → 保留。", f=fl(F1, cur=[2], done=[3], mark=[0]), t=tl(S(1), mark=lidx(S(1), '再 apply {a: 10}', '结果:集群里'), done=lidx(S(1), '解读')), kv=KV([['上次 apply 有、这次没有', '删除'], ['live 里有、从没 apply 过', '保留'], ['两边都有', '这次的赢']], ['上次 apply 有、这次没有'])),
    step("kubectl create 出来的 made 没有 last-applied 注解。去掉 k2 后再 apply:退出码 0,但提示 Warning: resource configmaps/made is missing the kubectl.kubernetes.io/last-applied-configuration annotation;结果 k2 没有被删(没有“上次”可比),并且这次 apply 把注解补写成 {x: 1}。", f=fl(F2, cur=[1], mark=[2], done=[0]), t=tl(S(2), mark=lidx(S(2), 'Warning', 'k2 没有被删'), done=lidx(S(2), 'last-applied=None')), kv=KV([['没有注解', '只能当成“上次什么都没有”'], ['第一次 apply', '补写注解,但不会删任何东西'], ['结论', 'create 之后改用 apply,删字段要等第二次']], ['没有注解'])),
    step("--server-side apply 创建的 ConfigMap ss:last-applied 注解为 None——server-side apply 不用这个注解,改用 managedFields 记录字段所有权。", f=fl(F3, cur=[1], done=[0]), t=tl(S(3), mark=lidx(S(3), 'last-applied 注解:None')), kv=KV([['client-side apply', '靠 last-applied 注解'], ['server-side apply', '靠 managedFields']], ['server-side apply'])),
    step("注解有大小上限:kubectl create 一个 data 约 270000 字节的 ConfigMap 成功;kubectl apply 同样大小 → 退出码 1,The ConfigMap \"big2\" is invalid: metadata.annotations: Too long: may not be more than 262144 bytes(last-applied 把整份配置又存了一遍);--server-side 同样大小成功。", f=fl(F4, cur=[1], mark=[1], done=[0, 2]), t=tl(S(4), mark=lidx(S(4), 'Too long'), done=lidx(S(4), 'serverside-applied', 'configmap/big created')), kv=KV([['last-applied', '把整份配置再存一遍到注解里'], ['262144 字节', '注解总大小上限'], ['大对象', '改用 --server-side']], ['262144 字节'])),
]
A = mkartk('k11', 11, 'Kubernetes,kubectl apply,last-applied-configuration,三方合并,client-side apply,真实验证,动画演示',
    '在 kind 集群里实测 kubectl apply(client-side)的三方合并:last-applied 注解、这次的 manifest、集群里现在的对象三者比较,上次有这次没有的字段被删除、从没 apply 过的字段(手工添加的 c)被保留;kubectl create 出来的对象没有注解,apply 会警告且不会删字段;server-side apply 不写注解;data 约 270000 字节的 ConfigMap 能 create 却因注解超过 262144 字节而 apply 失败。',
    '为什么 kubectl apply 能删掉你从 YAML 里去掉的字段,却不动别人手工加的字段?靠的是 metadata.annotations 里的 last-applied-configuration。这篇把三方合并的每一个输入都打印出来,再看它的几个坑:没有注解时的行为、server-side 的区别,以及大对象 apply 会撞上的注解上限。',
    [('{a: 10, c: 3}', '三方合并的结果:a 以这次为准、b 被删除、手工加的 c 保留'), ('Warning: … missing the … annotation', 'kubectl create 出来的对象第一次 apply 时的提示,这次 apply 不会删字段'), ('262144 字节', 'data 约 270000 字节的 ConfigMap 用 apply 时因注解过长被拒绝')],
    [('三个输入', '<p>client-side apply 比较三样东西:<b>上次 apply 的配置</b>(存在 <code>kubectl.kubernetes.io/last-applied-configuration</code> 注解里)、<b>这次的 manifest</b>、<b>集群里现在的对象</b>。实验里第一次 apply <code>{a: 1, b: 2}</code>,有人手工 patch 加了 <code>c: 3</code> 并改了 <code>a</code>,再 apply <code>{a: 10}</code>:<code>a</code> 以这次的为准变成 10;<code>b</code> 在上次 apply 里有、这次没有,被删除;<code>c</code> 从没出现在任何一次 apply 里,保留。</p>'),
     ('没有注解的对象', '<p><code>kubectl create</code> 出来的对象没有这个注解(除非加 <code>--save-config</code>)。第一次 apply 时 kubectl 提示 <code>missing the kubectl.kubernetes.io/last-applied-configuration annotation</code>,因为没有“上次”可比,去掉的字段 <code>k2</code> 没有被删,但这次 apply 会把注解补上。所以先 create 再 apply,想删的字段要等第二次 apply 才删得掉。</p>'),
     ('server-side 不用注解', '<p><code>--server-side</code> 创建的对象没有 last-applied 注解,字段归属改由 <code>managedFields</code> 记录(上一篇的内容),也不再有“上次配置”这个概念。</p>'),
     ('注解的大小上限', '<p>last-applied 把整份配置又存了一遍到注解里,而一个对象的所有注解加起来不能超过 262144 字节。data 约 270000 字节的 ConfigMap 用 <code>kubectl create</code> 没问题,用 <code>kubectl apply</code> 就报 <code>metadata.annotations: Too long: may not be more than 262144 bytes</code>;<code>--server-side</code> 没有这个问题。大 ConfigMap、嵌入大段配置的 CRD 是最常撞上的地方。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);对象是 k11 命名空间里的 ConfigMap,注解内容用 kubectl get -o json 读出再解析;“有人手工修改”用 kubectl patch --type=merge 模拟;大 ConfigMap 的 data 是 270000 个字符的字符串;每种情形各一次',
     '没有验证:嵌套 map 与列表(带 merge key 与不带)在三方合并里的删除规则;kubectl apply --prune;kubectl.kubernetes.io/last-applied-configuration 与 server-side apply 的 managedFields 之间的迁移(csa-to-ssa 升级);--save-config 的行为;apply 对 CRD 的三方合并(CRD 没有 strategic patch,走 JSON merge patch)'],
    '三方合并', PANELS)
