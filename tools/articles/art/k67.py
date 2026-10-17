from lib import *
S = SS('k67')
F1 = [['plain(None)', '11 / 10 / 9'], ['sticky(ClientIP)', '30 全在同一个'], ['cli2 访问 sticky', '30,也固定,但可能是另一个后端']]
F2 = [['SVC 链前三条', 'recent --rcheck --seconds 10800'], ['命中', '直接跳到该 SEP'], ['没命中', '走 statistic 抽签'], ['SEP 链', 'recent --set 后 DNAT']]
F3 = [['timeoutSeconds=3', '--seconds 3'], ['间隔 1 秒', '同一后端 12/12'], ['间隔 4 秒', '换后端 8/12'], ['每 2 秒访问', '一直粘住']]
F4 = [['后端 44wps 被删', ''], ['重新访问 5 次', '都到 qzvtf'], ['之后', '固定在 qzvtf']]
PANELS = [('f', 'flow', '会话保持'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("同一个客户端发 30 个新连接:plain Service(sessionAffinity: None)分布 11/10/9;sticky Service(sessionAffinity: ClientIP,默认 sessionAffinityConfig.clientIP.timeoutSeconds=10800)30 个全落在同一个后端。另一个客户端 cli2 访问 sticky 同样全落在一个后端,但与 cli1 不是同一个(cli1→wgtmr,cli2→44wps)——按客户端 IP 各自固定。", f=fl(F1, cur=[1], done=[0, 2]), t=tl(S(1), mark=lidx(S(1), 'sticky(ClientIP)', 'cli2'), done=lidx(S(1), 'plain(None)')), b=bars([['plain:最多的后端', 11, '11'], ['sticky:最多的后端', 30, '30']], 30, done=[0], mark=[1]), kv=KV([['ClientIP', '按来源 IP 固定后端'], ['每个客户端独立', '不同客户端可能固定到不同后端'], ['默认 3 小时', '10800 秒']], ['ClientIP'])),
    step("iptables 里靠 recent 模块实现:sticky 的 SVC 链先有三条 -m recent --rcheck --seconds 10800 --reap --name KUBE-SEP-… -j KUBE-SEP-…(每个后端一条,查这个客户端 IP 是否在该后端的 recent 表里,在就直接跳过去),都没命中才走后面的 statistic random 抽签;SEP 链里的 DNAT 规则带 -m recent --set(记下客户端 IP)。内核 /proc/net/xt_recent/ 下每个后端一张表,表里有 src=10.244.1.174 这样的客户端和它最近的访问时间戳。", f=fl(F2, cur=[0, 1], mark=[2], done=[3]), t=tl(S(2), mark=lidx(S(2), 'recent --rcheck', 'recent --set'), done=lidx(S(2), 'src=10.244.1.174')), kv=KV([['rcheck', '先查有没有记录'], ['set', 'DNAT 时记下客户端'], ['xt_recent', '内核表,按后端一张']], ['rcheck'])),
    step("把 timeoutSeconds 改成 3:规则里的 --seconds 变成 3。12 轮试验:间隔 1 秒(小于 3 秒)的两次访问落在同一个后端 12/12;间隔 4 秒(大于 3 秒)的两次访问落在不同后端 8/12(超时后重新抽签,3 个后端时换一个的概率约 2/3)。每 2 秒访问一次共 7 次,全都在同一个后端——每次访问都会刷新计时器,不是从第一次访问开始算。", f=fl(F3, cur=[1, 2], done=[0, 3]), t=tl(S(3), mark=lidx(S(3), '12 轮试验'), done=lidx(S(3), '每 2 秒访问一次', '--seconds')), kv=KV([['超时', '距离上一次访问,不是距离第一次'], ['超时后', '重新抽签,可能仍是原来的'], ['最大值', '86400 秒(本文未验证)']], ['超时'])),
    step("固定后端 44wps 被删除后,客户端立即重新访问 5 次,全部到 qzvtf——被重新分配到存活的后端,并且之后又固定在它上面。", f=fl(F4, cur=[1], done=[0, 2]), t=tl(S(4), mark=lidx(S(4), '被删除后立即'), done=lidx(S(4), 'qzvtf')), kv=KV([['后端消失', '该 SEP 链及其 recent 表被清掉'], ['客户端', '被重新分配并重新固定'], ['滚动更新时', '会话保持的客户端会被打散']], ['后端消失'])),
]
A = mkartk('k67', 67, 'Kubernetes,Service,sessionAffinity,ClientIP,iptables,recent,真实验证,动画演示',
    '在 kind 集群里实测 Service 会话保持:sessionAffinity: ClientIP 让同一个客户端 IP 的 30 个连接全落在一个后端,不同客户端各自固定;iptables 里是 -m recent --rcheck/--set 加每个后端一张内核 recent 表;timeoutSeconds=3 时 1 秒间隔的访问 12/12 粘住、4 秒间隔 8/12 换了后端,每次访问刷新计时器;固定的后端被删后客户端被重新分配并重新固定。',
    'sessionAffinity: ClientIP 到底是怎么做的?超时是从第一次访问算还是最近一次?不同客户端会固定到同一个后端吗?后端被删了怎么办?这篇看 iptables 的 recent 规则并做定时实验。',
    [('30 / 30', 'ClientIP 会话保持下,同一客户端 30 个连接落在同一个后端的数量'), ('12/12 与 8/12', '超时 3 秒时,间隔 1 秒的访问仍粘住,间隔 4 秒的访问有 8 次换了后端'), ('recent', 'iptables 实现会话保持用的内核模块,每个后端一张表')],
    [('有无会话保持', '<p>同一个客户端 <code>cli1</code> 发 30 个新连接:<code>plain</code> Service(<code>sessionAffinity: None</code>)分布是 11/10/9;<code>sticky</code> Service(<code>sessionAffinity: ClientIP</code>,默认 <code>timeoutSeconds: 10800</code>)30 个全在一个后端。另一个客户端 <code>cli2</code> 访问 <code>sticky</code> 也全落在一个后端,但和 <code>cli1</code> 不是同一个——按来源 IP 各自固定。</p>'),
     ('iptables 里的 recent 模块', '<p>sticky 的 SVC 链前三条是 <code>-m recent --rcheck --seconds 10800 --reap --name KUBE-SEP-… -j KUBE-SEP-…</code>:每个后端一条,检查来源 IP 是否在该后端的 recent 表里,在就直接跳过去;都没命中才走后面的 <code>statistic random</code> 抽签。SEP 链里的 DNAT 规则带 <code>-m recent --set</code>,把客户端 IP 记进这个后端的表。内核的 <code>/proc/net/xt_recent/</code> 下每个后端一张表,能看到 <code>src=10.244.1.174</code> 和它的访问时间戳。</p>'),
     ('超时与刷新', '<p>把 <code>timeoutSeconds</code> 改成 3,规则里的 <code>--seconds</code> 随之变成 3。12 轮试验:间隔 1 秒(小于超时)的两次访问落在同一个后端 12/12;间隔 4 秒(大于超时)的两次访问有 8 次落在不同后端(超时后重新抽签,3 个后端时换一个的概率约 2/3)。每 2 秒访问一次共 7 次始终是同一个后端:每次访问都会刷新计时器,超时是从上一次访问算起,而不是第一次。</p>'),
     ('后端消失', '<p>固定的后端 <code>44wps</code> 被删除后,客户端立即重新访问 5 次,全部落到 <code>qzvtf</code>:被重新分配到存活的后端,并固定在它上面。所以滚动更新期间,会话保持的客户端会被打散到新的 Pod。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0),kube-proxy iptables 模式;后端是 3 副本 busybox httpd,返回各自主机名;客户端是两个 busybox Pod(cli1、cli2)里循环 wget(每次新连接);超时试验的间隔是 sleep 控制,精度约 ±0.3 秒;每种情形各一次(第三节 12 轮)',
     '没有验证:IPVS / nftables 模式下会话保持的实现(IPVS 用 persistent,nftables 用 set);通过 NodePort / LoadBalancer 进来时的源 IP(受 externalTrafficPolicy 和 SNAT 影响,见下一篇);timeoutSeconds 的取值范围 1~86400;客户端经过 NAT 后共享出口 IP 时会被当成同一个客户端;sessionAffinity 与 Headless Service 的关系'],
    '会话保持', PANELS)
