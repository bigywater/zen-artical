from lib import *
S = SS('k69')
F1 = [['server 10.244.2.220:80', ''], ['同命名空间 frontend', 'ok'], ['同命名空间 other', 'ok'], ['k69b 的 frontend', 'ok']]
F2 = [['deny-all(Ingress)', 'podSelector: {}'], ['三个客户端', '全部超时'], ['连接表现', '包被 DROP,无 RST'], ['front 往外查 DNS', '仍然成功']]
F3 = [['from: podSelector', '只放本命名空间 frontend'], ['ns+pod 在同一条目', '且:只放 k69b 的 frontend'], ['ns / pod 两个条目', '或:两边都放']]
F4 = [['多条策略', '并集'], ['deny egress', 'IP 和 Service 名都超时'], ['DNS 也被拦', 'nslookup 超时'], ['放行 53 和 80', '恢复']]
PANELS = [('f', 'flow', '策略如何生效'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("kind 自带的 kindnet 实现了 NetworkPolicy。server 在命名空间 k69(label team=blue),k69b 命名空间是 team=red。没有任何策略时,三个客户端(同命名空间 role=frontend、同命名空间 role=other、k69b 命名空间 role=frontend)都能连上 server。", f=fl(F1, cur=[0], done=[1, 2, 3]), t=tl(S(1), done=lidx(S(1), '连通性')), kv=KV([['默认', '所有 Pod 之间互通'], ['实现', 'NetworkPolicy 由 CNI 执行,没有支持的 CNI 就没有效果'], ['kind', 'kindnet 内置实现']], ['默认'])),
    step("应用 podSelector: {}、policyTypes: [Ingress] 且没有 ingress 规则的 default-deny:第一次探测到 frontend 连不上用了 1.1 秒;三个客户端全部超时。被拒的连接表现为超时(wget -T 3 用时 3.1 秒),没有 RST,说明包被直接 DROP。这条策略只管进来的方向:front 自己往外查 DNS(nslookup kubernetes.default…)仍然成功。", f=fl(F2, cur=[0, 1], mark=[2], done=[3]), t=tl(S(2), mark=lidx(S(2), '超时', '3.1 秒'), done=lidx(S(2), 'front 自己往外查 DNS')), kv=KV([['default-deny', '选中 Pod 后,没写允许就全拒'], ['DROP', '客户端看到超时而不是拒绝'], ['约 1 秒生效', 'CNI 把策略翻译成节点上的规则']], ['default-deny'])),
    step("放行规则的写法:只写 podSelector(role=frontend)——只匹配策略所在命名空间的 Pod,同命名空间 frontend ok,k69b 的 frontend 超时;同一个 from 条目里写 namespaceSelector(team=red)和 podSelector(role=frontend)是“且”,只有 k69b 的 frontend 能连;拆成两个 from 条目(两个短横线)是“或”,同命名空间 frontend 和 k69b 的 frontend 都能连,role=other 始终不行。", f=fl(F3, cur=[0, 1, 2]), t=tl(S(3), mark=lidx(S(3), '只写 podSelector', '且', '或'), done=lidx(S(3), '或')), kv=KV([['podSelector 单独', '仅限策略所在命名空间'], ['同一条目', '与(AND)'], ['多个条目', '或(OR)——少一个短横线差很多']], ['同一条目'])),
    step("再加一条放行 role=other 的策略:三个客户端全都 ok,多条策略取并集,没有“拒绝”类规则。egress 的 default-deny(对 role=frontend,policyTypes: [Egress])让用 IP 和用 Service 名访问 server 都超时,nslookup server 报 connection timed out——DNS 查询也走 egress。放行到 kube-system 的 53/UDP+TCP 和到 server 的 80 之后,IP 和 Service 名都恢复 ok。", f=fl(F4, cur=[1, 2], done=[0, 3]), t=tl(S(4), mark=lidx(S(4), 'default-deny egress', 'connection timed out'), done=lidx(S(4), '放行到 kube-system', '并集')), kv=KV([['并集', '只能加放行,不能写拒绝'], ['egress deny', 'DNS 也要放行'], ['放行 DNS', 'kube-system 的 53,UDP 和 TCP']], ['egress deny'])),
]
A = mkartk('k69', 69, 'Kubernetes,NetworkPolicy,default-deny,namespaceSelector,podSelector,真实验证,动画演示',
    '在 kind 集群(kindnet)里实测 NetworkPolicy:没有策略时全通;default-deny ingress 约 1.1 秒生效且被拒的连接是超时而不是拒绝;podSelector 单独只匹配本命名空间,同一个 from 条目里 namespaceSelector 加 podSelector 是“且”,拆成两个条目是“或”;多条策略取并集;egress default-deny 会把 DNS 一起拦掉,必须单独放行 kube-system 的 53 端口。',
    'NetworkPolicy 的 default-deny 到底拒绝了什么?from 里 podSelector 和 namespaceSelector 写在一起和分开写有什么区别?为什么加了 egress 限制之后域名解析就坏了?这篇用 3 个客户端、2 个命名空间的连通性矩阵一项项验证。',
    [('超时而不是拒绝', '被 NetworkPolicy 拒绝的连接,客户端看到的是 wget 超时(包被 DROP)'), ('且 vs 或', '同一个 from 条目里写两种选择器是“且”,分成两个条目是“或”'), ('DNS 一起被拦', 'egress default-deny 后,用 IP 访问和用 Service 名访问都超时')],
    [('没有策略:全通', '<p>kind 默认的 CNI kindnet 自带 NetworkPolicy 实现。<code>server</code>(命名空间 <code>k69</code>,label <code>team=blue</code>)没有任何策略时,同命名空间的 <code>role=frontend</code>、<code>role=other</code> 和另一个命名空间 <code>k69b</code>(<code>team=red</code>)的 <code>role=frontend</code> 都能连上。NetworkPolicy 是由 CNI 插件执行的,没有支持它的 CNI 就是一个没有效果的对象。</p>'),
     ('default-deny', '<p>应用 <code>podSelector: {}</code> + <code>policyTypes: [Ingress]</code> 且不写任何 ingress 规则:第一次探测到 frontend 连不上用了 1.1 秒;三个客户端全部超时。被拒的连接不是 <code>Connection refused</code> 而是 <code>wget</code> 等了 3.1 秒超时——包被直接 DROP,没有 RST。这条策略只管进来的方向:<code>front</code> 自己往外查 DNS 仍然成功。</p>'),
     ('且与或', '<p>放行规则的写法决定结果。只写 <code>podSelector: {role: frontend}</code>:只匹配策略所在命名空间的 Pod,同命名空间 frontend 通,<code>k69b</code> 的 frontend 超时。同一个 <code>from</code> 条目里同时写 <code>namespaceSelector: {team: red}</code> 和 <code>podSelector: {role: frontend}</code> 是“且”,只有 <code>k69b</code> 的 frontend 能连。拆成两个条目(两个短横线)就是“或”:同命名空间 frontend 和 <code>k69b</code> 的 frontend 都能连,<code>role=other</code> 始终不行。少写一个短横线,放行范围就完全不同。</p>'),
     ('并集与 egress', '<p>再加一条放行 <code>role=other</code> 的策略,三个客户端全部变成 ok:多条策略取并集,只能“放行”,不存在“拒绝”规则。对 <code>role=frontend</code> 设 egress 的 default-deny 后,用 IP 访问 server 超时,用 Service 名访问也超时,<code>nslookup server</code> 报 <code>connection timed out</code>——DNS 查询同样走 egress。放行到 <code>kube-system</code> 的 53(UDP 和 TCP)以及到 server 的 80 之后,两种访问方式都恢复。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0),CNI 是 kind 默认的 kindnet(自带 NetworkPolicy);server 是 nginx:1.27-alpine,客户端是 busybox 的 wget(-T 2 或 -T 3);“超时”指耗时接近 -T 的失败;每种情形各一次',
     '没有验证:其他 CNI(Calico、Cilium)的行为差异;ipBlock 与 SCTP / 端口范围(endPort);策略对已建立连接的影响;hostNetwork Pod 与节点自身流量是否受策略约束;NodePort / Service 流量在策略检查前后是否已 DNAT;AdminNetworkPolicy;日志与审计'],
    'NetworkPolicy', PANELS)
