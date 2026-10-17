from lib import *
S = SS('k62')
F1 = [['普通 Service cip', 'A → 10.96.204.228(1 个)'], ['headless hl', 'A → 3 个 Pod IP'], ['多次查询', '顺序被打乱']]
F2 = [['web-1.hl…', '10.244.1.84'], ['删除 web-1', ''], ['重建', 'IP → 10.244.1.85'], ['同一个名字', '解析到新 IP']]
F3 = [['web-2 就绪失败', ''], ['hl 返回', '2 个(不含 web-2)'], ['publishNotReadyAddresses', 'true'], ['hl 返回', '3 个(含 web-2)']]
F4 = [['SRV _http._tcp.hl', '3 条:各 Pod 的名字'], ['SRV _http._tcp.cip', '1 条:指向 Service 自己']]
PANELS = [('f', 'flow', 'DNS 返回什么'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("3 个 Pod(10.244.1.83、10.244.1.84、10.244.2.120)。普通 Service cip 的 A 记录只有一个,就是 ClusterIP 10.96.204.228;headless Service hl(clusterIP: None,kubectl get svc 的 CLUSTER-IP 列是 None)返回三个 Pod IP,正好是全部三个;连续查 4 次,顺序是 [83,120,84]、[83,84,120]、[83,120,84]、[120,84,83],每次不同。", f=fl(F1, cur=[1], done=[0, 2]), t=tl(S(1), mark=lidx(S(1), 'nslookup hl →', '连续查 4 次'), done=lidx(S(1), 'nslookup cip')), kv=KV([['普通 Service', 'DNS 给一个虚拟 IP,负载均衡在 kube-proxy'], ['headless', 'DNS 直接给所有 Pod IP,客户端自己选'], ['顺序', '每次不同,别依赖第一个']], ['headless'])),
    step("StatefulSet web 的 Pod 有稳定的 DNS 名 web-N.hl.k62.svc.cluster.local:web-0、web-1、web-2 分别解析到各自的 Pod IP。删掉 web-1 重建,IP 从 10.244.1.84 变成 10.244.1.85,web-1.hl… 现在解析到新 IP——名字不变,IP 跟着变。普通 Service 没有这种名字,web-1.cip.… 查不到。", f=fl(F2, cur=[2], done=[0, 1, 3]), t=tl(S(2), mark=lidx(S(2), '删掉 web-1'), done=lidx(S(2), 'web-0.hl', 'web-1.hl 现在')), kv=KV([['稳定名字', 'StatefulSet 的 serviceName 指向 headless Service'], ['IP 会变', '名字不会,所以用名字'], ['普通 Service', '没有每 Pod 的名字']], ['稳定名字'])),
    step("让 web-2 的就绪探针失败(把 index.html 移走):hl 的 A 记录只剩 2 个(末段 83、85,不含 web-2 的 120),web-2.hl.… 单独查也没有记录。给 hl 加 publishNotReadyAddresses: true:hl 返回 3 个地址,web-2.hl.… 解析到 10.244.2.120——没就绪的 Pod 也出现了。", f=fl(F3, cur=[1], mark=[0], done=[2, 3]), t=tl(S(3), mark=lidx(S(3), '返回 2 个地址'), done=lidx(S(3), '返回 3 个地址')), kv=KV([['默认', '只发布 Ready 的 Pod'], ['publishNotReadyAddresses', '没就绪的也发布(用于集群成员发现)'], ['单个 Pod 名', '同样跟着就绪状态']], ['publishNotReadyAddresses'])),
    step("SRV 记录:_http._tcp.hl.k62.svc.cluster.local 返回 3 条,每条指向一个 Pod 的名字(0 33 80 web-0.hl.…);普通 Service 的 SRV 只有 1 条,指向 Service 自己 0 100 80 cip.k62.svc.cluster.local。端口名(http)和协议(tcp)构成 SRV 的前缀。", f=fl(F4, cur=[0], done=[1]), t=tl(S(4), mark=lidx(S(4), '3 条'), done=lidx(S(4), '指向 Service 自身')), kv=KV([['SRV', '_<端口名>._<协议>.<服务名>'], ['headless', '每个 Pod 一条,带端口'], ['需要端口名', 'Service 里的端口必须有 name']], ['SRV'])),
]
A = mkartk('k62', 62, 'Kubernetes,Headless Service,DNS,StatefulSet,SRV,CoreDNS,真实验证,动画演示',
    '在 kind 集群里实测 headless Service(clusterIP: None)的 DNS:普通 Service 只返回一个 ClusterIP,headless 返回全部 3 个 Pod IP 且每次顺序不同;StatefulSet 的 Pod 有稳定的 web-N.hl 域名,Pod 重建后 IP 变而名字不变;没就绪的 Pod 默认不在 DNS 里,publishNotReadyAddresses 才会发布;SRV 记录每个 Pod 一条。',
    'headless Service 的 DNS 到底返回什么?StatefulSet 的 Pod 为什么有固定的域名?没就绪的 Pod 会出现在 DNS 里吗?这篇用 nslookup 在真集群里把这些问题的答案都查出来。',
    [('3 个 Pod IP', 'headless Service 的 A 记录,而不是一个 ClusterIP'), ('10.244.1.84 → 10.244.1.85', 'web-1 重建后 IP 变了,web-1.hl 域名不变'), ('2 → 3', '没就绪的 Pod 在 DNS 里的数量变化(加 publishNotReadyAddresses 之后)')],
    [('A 记录:ClusterIP 还是 Pod IP', '<p>普通 Service <code>cip</code> 的 A 记录只有一个,就是 ClusterIP;headless Service <code>hl</code>(<code>clusterIP: None</code>,<code>kubectl get svc</code> 里 CLUSTER-IP 显示 <code>None</code>)返回的是全部三个 Pod IP。连续查 4 次,顺序每次不同(CoreDNS 默认打乱),所以客户端不要依赖第一个。没有虚拟 IP,也就没有 kube-proxy 做的负载均衡——选哪个由客户端决定。</p>'),
     ('稳定的 Pod 域名', '<p>StatefulSet 的 <code>serviceName</code> 指向这个 headless Service,Pod 的 hostname 是 <code>web-N</code>、subdomain 是 <code>hl</code>,于是每个 Pod 有自己的 A 记录 <code>web-N.hl.k62.svc.cluster.local</code>。删掉 <code>web-1</code> 重建,IP 从 10.244.1.84 变成 10.244.1.85,同一个域名现在解析到新 IP。普通 Service 没有这种名字,查 <code>web-1.cip.…</code> 得不到记录。(注意 busybox 的 <code>nslookup</code> 对带点的短名字不展开 search 域,实验里用了完整域名。)</p>'),
     ('没就绪的 Pod', '<p>让 <code>web-2</code> 的就绪探针失败后,<code>hl</code> 的 A 记录从 3 个变成 2 个,<code>web-2</code> 自己的域名也查不到。给 Service 加 <code>publishNotReadyAddresses: true</code>,3 个地址回来了,<code>web-2.hl.…</code> 也能解析——数据库集群成员互相发现时要用它,因为成员还没就绪时就得先互相找到。</p>'),
     ('SRV 记录', '<p><code>nslookup -type=SRV _http._tcp.hl.k62.svc.cluster.local</code> 返回 3 条,每条指向一个 Pod 的名字和端口(<code>0 33 80 web-0.hl.…</code>);普通 Service 只有 1 条,指向 Service 自己(<code>0 100 80 cip.k62.svc.cluster.local</code>)。前缀里的 <code>_http</code> 是 Service 端口的名字,<code>_tcp</code> 是协议。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0,CoreDNS 默认配置);3 副本的 StatefulSet(nginx:1.27-alpine,Parallel)+ headless Service hl + 普通 Service cip;查询用 busybox 的 nslookup,对带点的名字用完整域名;“让 web-2 不就绪”靠移走 nginx 的 index.html;每种情形各一次',
     '没有验证:CoreDNS 的 pods insecure / verified 选项;跨命名空间查 headless Service;ExternalName 与 headless 的区别(见上一篇);headless 无 selector 时靠手写 EndpointSlice 的行为;DNS 缓存 TTL;客户端库对多条 A 记录的选择策略;一个没有任何 endpoint 的普通 Service 的 DNS 行为(实验中曾观察到 NXDOMAIN,没有深入)'],
    'headless', PANELS)
