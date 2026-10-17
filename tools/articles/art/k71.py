from lib import *
S = SS('k71')
F1 = [['far 10.244.1.194(worker)', ''], ['Pod 内路由', 'via 10.244.1.1'], ['worker 路由表', '10.244.2.0/24 via 172.18.0.4'], ['worker2', '10.244.2.229 dev veth…']]
F2 = [['far → srv', 'client=10.244.1.194'], ['KIND-MASQ-AGENT', '目的 10.244.0.0/16 → RETURN'], ['其他目的', 'MASQUERADE'], ['结论', 'Pod 到 Pod 不做 NAT']]
F3 = [['near → srv(同节点)', '0.069 ms'], ['far → srv(跨节点)', '0.097 ms'], ['多一跳', '约 0.03 ms']]
F4 = [['ip route del 10.244.2.0/24', ''], ['wget', 'timed out'], ['kindnet', '周期性补路由'], ['7.4 秒后', '路由回来,恢复']]
PANELS = [('f', 'flow', '跨节点路径'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("srv(10.244.2.229)在 worker2,far(10.244.1.194)在 worker。worker 的路由表里有 10.244.0.0/24 via 172.18.0.3、10.244.2.0/24 via 172.18.0.4——每个别的节点的 Pod 网段,下一跳是那个节点的 IP;worker2 对称。除 veth 以外节点上只有 lo、eth0 和内核自带的 DOWN 状态兜底设备(tunl0、gre0 等),没有 vxlan / geneve / wireguard 之类的隧道。Pod far 里去往 srv 的路由是 via 10.244.1.1 dev eth0:先到本节点,由节点上的路由表再发往 172.18.0.4。", f=fl(F1, cur=[1, 2], done=[3]), t=tl(S(1), mark=lidx(S(1), '10.244.2.0/24 via 172.18.0.4', '没有 vxlan'), done=lidx(S(1), 'Pod far 里去往')), kv=KV([['没有隧道', '节点之间二层互通,直接按路由转发'], ['每节点一条', '去往其他节点 podCIDR 的路由'], ['数据包原样', '不封装,Pod IP 直接在节点网络上传']], ['没有隧道'])),
    step("far 访问 srv,srv 的 nginx 看到 client=10.244.1.194,正是 far 自己的 IP,没有被 SNAT;同节点的 near 访问看到 client=10.244.2.230。worker 上的 KIND-MASQ-AGENT 规则:目的地址在 10.244.0.0/16 的 RETURN(不处理),其他目的 MASQUERADE——只有去集群外的流量才做源地址转换。", f=fl(F2, cur=[0, 1], mark=[2], done=[3]), t=tl(S(2), mark=lidx(S(2), 'KIND-MASQ-AGENT -d 10.244.0.0/16 -j RETURN'), done=lidx(S(2), 'far 访问 srv', 'near 访问 srv')), kv=KV([['Kubernetes 网络模型', 'Pod 之间不经 NAT 直接通信'], ['masq-agent', '只对集群外的目的做 SNAT'], ['服务端看到的', '真实的 Pod IP']], ['不经 NAT'])),
    step("ping 30 个包:同节点 near → srv 平均 0.069 ms、最大 0.161 ms;跨节点 far → srv 平均 0.097 ms、最大 0.180 ms,多约 0.03 ms。kind 的“节点”都是同一台机器上的容器,所以差别本来就很小。", f=fl(F3, cur=[1], done=[0, 2]), t=tl(S(3), mark=lidx(S(3), '跨节点'), done=lidx(S(3), '同节点')), b=bars([['同节点', 0.069, '0.069 ms'], ['跨节点', 0.097, '0.097 ms']], 0.12, done=[0, 1]), kv=KV([['多一跳', '只多了经过一次节点路由转发'], ['本实验', '节点在同一台机器,延迟不代表真实网络'], ['真实环境', '取决于二层/三层网络,封装会再多一层']], ['多一跳'])),
    step("手动 ip route del 10.244.2.0/24(worker 上去往 worker2 网段的路由):立刻再访问,wget: download timed out;等待 kindnet 周期性对账,7.4 秒后路由回来,far → srv 恢复 client=10.244.1.194。多次运行恢复时间在 4.6~7.4 秒之间。", f=fl(F4, cur=[1, 2], done=[3]), t=tl(S(4), mark=lidx(S(4), 'download timed out'), done=lidx(S(4), '路由回来了')), kv=KV([['路由是命脉', '少一条就断跨节点通信'], ['kindnet', '一个 DaemonSet,周期性把路由补回来'], ['恢复约 5~8 秒', '单次测量,不固定']], ['路由是命脉'])),
]
A = mkartk('k71', 71, 'Kubernetes,跨节点通信,CNI,路由,kindnet,NAT,真实验证,动画演示',
    '在 kind 集群里实测跨节点 Pod 通信:没有隧道,每个节点路由表里有一条去往别的节点 podCIDR 的路由(下一跳是节点 IP);服务端看到的是客户端真实的 Pod IP,KIND-MASQ-AGENT 对目的在 10.244.0.0/16 的流量 RETURN,只有出集群才 MASQUERADE;跨节点 ping 比同节点平均多约 0.03 ms;手动删掉去往另一节点的路由后访问超时,kindnet 约 5~8 秒内补回。',
    '两个在不同节点上的 Pod 是怎么通信的?要不要封装?源 IP 会被改吗?如果路由表里少了一条会怎样?这篇在 kind 里把这条路径的每个环节(路由、NAT、延迟、故障恢复)都直接看出来。',
    [('0 个隧道设备', '节点上没有 vxlan / geneve 之类的设备,跨节点流量靠节点路由表直接转发'), ('client=10.244.1.194', '跨节点访问时服务端看到的客户端 IP 就是对方 Pod 的 IP,没有 NAT'), ('7.4 秒', '手动删除去往另一节点的路由后,kindnet 把它补回来所用的时间(多次在 4.6~7.4 秒)')],
    [('靠节点路由表,没有隧道', '<p>srv 在 worker2(10.244.2.229),far 在 worker(10.244.1.194)。worker 的路由表里有 <code>10.244.0.0/24 via 172.18.0.3</code> 和 <code>10.244.2.0/24 via 172.18.0.4</code>——每个别的节点的 Pod 网段,下一跳是那个节点的 IP;worker2 对称。除了 veth,节点上只有 <code>lo</code>、<code>eth0</code> 和内核自带但 DOWN 状态的 <code>tunl0</code>、<code>gre0</code> 等兜底设备,没有 vxlan、geneve、wireguard 之类的隧道。Pod far 里去往 srv 的路由是 <code>via 10.244.1.1 dev eth0</code>:先到本节点,再由节点的路由表发往 172.18.0.4。(这依赖节点之间二层互通,云上常需要 VXLAN / BGP / 云路由表来补这一条。)</p>'),
     ('不做 NAT', '<p>far 访问 srv,nginx 看到 <code>client=10.244.1.194</code>,就是 far 自己的 IP;同节点的 near 看到 <code>10.244.2.230</code>。worker 上 kind 的 masq-agent 规则是:目的在 <code>10.244.0.0/16</code> 的直接 <code>RETURN</code>,其他目的才 <code>MASQUERADE</code>——只有出集群的流量才做 SNAT。这正是 Kubernetes 网络模型要求的:Pod 之间不经 NAT 直接通信。</p>'),
     ('多一跳的代价', '<p>ping 30 个包:同节点平均 0.069 ms、最大 0.161 ms;跨节点平均 0.097 ms、最大 0.180 ms,多了约 0.03 ms。kind 的节点是同一台机器上的容器,所以差别很小,这个数字只说明“多一次路由转发”,不代表真实网络。</p>'),
     ('路由是命脉', '<p>在 worker 上手动 <code>ip route del 10.244.2.0/24</code>,立刻访问 srv 得到 <code>wget: download timed out</code>;kindnet(DaemonSet)周期性对账,7.4 秒后把路由补回来,访问恢复。多次运行里恢复时间在 4.6~7.4 秒之间。跨节点通信完全依赖这些路由,少一条就断。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0),CNI 是 kind 默认的 kindnet(节点间二层互通,按 podCIDR 装路由);服务端是 nginx:1.27-alpine,返回 $remote_addr,客户端是 busybox 的 wget / ping;Pod 用 nodeName 固定在不同节点;删除路由只在 worker 上做,实验后已自动恢复;每种情形各一次(延迟是 30 个包的平均)',
     '没有验证:VXLAN / IPIP / WireGuard 封装下的 MTU 与吞吐;BGP(Calico)与云路由表;overlay 与 underlay 的差异;控制面节点上的 Pod 与其他节点的通信;NodePort 访问跨节点时的 SNAT(见前面 externalTrafficPolicy 一篇);IPv6;Pod 数量增多后路由表和 conntrack 的开销'],
    '跨节点通信', PANELS)
