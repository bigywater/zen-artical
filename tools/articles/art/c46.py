from lib import *
S = SS('c46')
steps = [
    step("docker network ls 里的内置网络:bridge、host、none(外加一个别人建的 kind)。默认 bridge 的 Subnet 172.17.0.0/16、Gateway 172.17.0.1。两个默认 bridge 上的容器:a=172.17.0.2、b=172.17.0.3;a ping b 的 IP 通(退出码 0);a ping b 的名字不通(退出码 1,bad address)——默认 bridge 上不能用容器名互相解析。容器里的默认路由是 default via 172.17.0.1 dev eth0。", t=tl(S(1)), done=lidx(S(1), 'a ping b 的 IP'), mark=lidx(S(1), 'a ping b 的名字', 'Subnet / Gateway'), kv=KV([['默认 bridge', '172.17.0.0/16,网关 172.17.0.1'], ['按 IP', '通'], ['按名字', '不通(bad address)']], ['按名字'])),
    step("docker network create 创建自定义 bridge 网络,拿到的 Subnet 是 172.19.0.0/16、网关 172.19.0.1(172.18 已被别的网络占用)。两个容器 c、d 接到这个网络后,c ping d 的名字成功(退出码 0),解析到 172.19.0.3。自定义 bridge 网络自带按名字解析。", t=tl(S(2)), done=lidx(S(2), '自定义网络里 c ping d'), mark=lidx(S(2), 'docker network create'), kv=KV([['新网络', '172.19.0.0/16,网关 172.19.0.1'], ['按名字 ping', '成功,解析到 172.19.0.3']], ['按名字 ping'])),
    step("不同网络之间默认互相隔离:自定义网络里的 c ping 默认 bridge 上的 a(172.17.0.2)→ 退出码 1;a ping c(172.19.0.2)→ 退出码 1。docker network connect 把 a 也接进自定义网络后,a 有两个 IP:172.17.0.2 和 172.19.0.4,这时 a ping c 的名字成功。", t=tl(S(3)), done=lidx(S(3), 'network connect', 'a ping c 的名字'), mark=lidx(S(3), 'c ping 默认 bridge', '默认 bridge 上的 a ping c'), kv=KV([['跨网络', '不通(退出码 1)'], ['docker network connect', '容器多一个网络、多一个 IP'], ['接入后', '按名字能通']], ['docker network connect'])),
    step("在虚拟机里看:网桥设备有 docker0、br-c76c209e2a7a、br-ae1a41b9fb47(每个自定义网络一个 br-…);docker0 的地址是 172.17.0.1/16。veth 设备个数起容器前 10 个,起 4 个容器(其中 a 连了两个网络)之后 15 个,增加 5 个——每个容器每连一个网络就多一个 veth。", t=tl(S(4)), done=lidx(S(4), '虚拟机里 veth 设备个数'), mark=lidx(S(4), '网桥设备', 'docker0 的地址'), b=bars([['起容器前 veth', 10, '10'], ['起 4 个容器后 veth', 15, '15']], 15, done=[0], mark=[1]), kv=KV([['网桥', 'docker0 + 每个自定义网络一个 br-…'], ['veth', '4 个容器 5 个接口 → +5']], ['veth'])),
]
A = mkartc('c46', 46, 'Docker,bridge网络,docker0,自定义网络,veth,容器网络,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 bridge 网络:默认 bridge 是 172.17.0.0/16,容器能按 IP 互通、不能按名字解析;自定义 bridge 网络(172.19.0.0/16)自带名字解析;不同网络之间互相隔离,docker network connect 后一个容器有两个 IP;虚拟机里每个自定义网络一个 br-… 网桥,每个容器每个网络一个 veth(4 个容器 +5)。',
    '默认 bridge 和自己创建的 bridge 网络有什么区别?为什么有的容器能按名字互访、有的不能?跨网络为什么不通?这篇用 ping 逐项验证,并进入虚拟机看网桥和 veth 设备。',
    [('按 IP 通、按名字不通', '默认 bridge 上两个容器的互访表现'), ('172.19.0.0/16', '新建自定义 bridge 网络分到的子网(172.18 已被占用)'), ('+5 个 veth', '起 4 个容器(其中一个连两个网络)后虚拟机里增加的 veth 设备数')],
    [('默认 bridge', '<p>默认 bridge 的子网是 172.17.0.0/16,网关 172.17.0.1(虚拟机里 docker0 的地址)。同一个网络里的容器按 IP 互通,但容器名解析不了(<code>bad address</code>)。</p>'),
     ('自定义 bridge', '<p><code>docker network create</code> 出来的网络按顺序分配新的 /16 子网(这里是 172.19,因为 172.18 已被另一个网络占用);容器按名字互访可以。名字解析的细节见后面的内置 DNS 一篇。</p>'),
     ('隔离与连接', '<p>不同 bridge 网络之间不通;<code>docker network connect</code> 把容器接入第二个网络,它就有了两个 IP,可以访问新网络里的容器。我没有查隔离是靠哪条 iptables 规则实现的。</p>'),
     ('虚拟机里的样子', '<p>每个自定义网络对应虚拟机里一个 <code>br-&lt;网络ID前缀&gt;</code> 网桥,默认 bridge 是 docker0;每个容器的每个网卡对应虚拟机里一个 veth 设备(另一端在容器的网络命名空间里,见后面的 veth 一篇)。</p>')],
    steps,
    [ENV_C + '。连通性用 busybox ping(-c 1 -W 2)判断退出码;网络信息取自 docker network inspect 和 docker inspect;虚拟机里的网桥与 veth 用特权容器加 nsenter 读取 ip link(方法见 c19);虚拟机里同时还有其它网络(如 kind)和容器,所以 veth 只看变化量;实验后已删除容器和网络',
     '没有验证:iptables 隔离规则、ICMP 以外的协议(TCP / UDP)、IPv6、macvlan / overlay 网络、--network host 与 none(见后面的 host 网络一篇)、容器访问外网的 NAT、Linux 宿主机上 docker0 的位置'],
    'bridge 网络')
