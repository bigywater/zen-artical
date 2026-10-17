from lib import *
S = SS('c52')
steps = [
    step("Docker Desktop 的默认 MTU 很大:虚拟机的 eth0 和 docker0 都是 65535;默认 bridge 的网络选项 com.docker.network.driver.mtu = 65535;默认容器里 eth0 的 MTU = 65535(常见的以太网 MTU 是 1500)。", t=tl(S(1)), done=lidx(S(1), '默认容器里 eth0'), mark=lidx(S(1), '虚拟机 eth0 / docker0'), b=bars([['默认容器 eth0 MTU', 65535, '65535'], ['常见以太网 MTU', 1500, '1500']], 65535, done=[0], mark=[1]), kv=KV([['虚拟机 eth0 / docker0', '65535 / 65535'], ['默认 bridge 选项', 'com.docker.network.driver.mtu = 65535'], ['默认容器 eth0', '65535']], ['默认容器 eth0'])),
    step("自定义网络可以改 MTU:docker network create -o com.docker.network.driver.mtu=1400 → 容器里 eth0 的 MTU = 1400,虚拟机里这个网络的网桥 br-… 的 MTU 也是 1400;设成 1280 同理,容器 eth0 和网桥都是 1280。", t=tl(S(2)), done=lidx(S(2), 'mtu=1400', 'mtu=1280'), kv=KV([['mtu=1400', '容器 eth0 = 1400,网桥 = 1400'], ['mtu=1280', '容器 eth0 = 1280,网桥 = 1280']], ['mtu=1400'])),
    step("MTU 决定 TCP 的 MSS:两个容器之间建立 TCP 连接,用 getsockopt(TCP_MAXSEG) 读:默认 bridge(MTU 65535)MSS = 32741;MTU 1400 的网络 MSS = 1348(1400 − 52);MTU 1280 的网络 MSS = 1228(1280 − 52)。", t=tl(S(3)), done=lidx(S(3), 'MTU 1400', 'MTU 1280'), mark=lidx(S(3), '默认 bridge(MTU 65535)'), b=bars([['MTU 65535 → MSS', 32741, '32741'], ['MTU 1400 → MSS', 1348, '1348'], ['MTU 1280 → MSS', 1228, '1228']], 32741, done=[1, 2], mark=[0]), kv=KV([['MTU 1400', 'MSS 1348'], ['MTU 1280', 'MSS 1228'], ['MTU 65535', 'MSS 32741(没有到 65483)']], ['MTU 1400'])),
]
A = mkartc('c52', 52, 'Docker,网络,MTU,MSS,Docker Desktop,真实验证,动画演示',
    '在 Docker Desktop 上实测网络 MTU:虚拟机、docker0 和默认容器的 eth0 都是 65535;docker network create -o com.docker.network.driver.mtu=1400 让容器 eth0 和虚拟机里的网桥都变成 1400;容器之间 TCP 连接的 MSS 分别是 32741(默认)、1348(MTU 1400)、1228(MTU 1280)。',
    'MTU 不匹配会让连接莫名其妙地卡住或变慢。这篇看 Docker Desktop 的默认 MTU 是多少,怎么给自定义网络设置 MTU,以及它怎样变成 TCP 的 MSS。',
    [('65535', 'Docker Desktop 里默认容器 eth0 的 MTU(常见物理网络是 1500)'), ('1348', 'MTU 1400 的自定义网络里两个容器之间 TCP 连接的 MSS'), ('32741', '默认 bridge(MTU 65535)上两个容器之间的 MSS')],
    [('默认值', '<p>Docker Desktop 虚拟机内部的网络 MTU 是 65535,默认 bridge 和容器都继承了这个值。Linux 宿主机上的默认是 1500,这是我知道的惯例,没有在这里验证。</p>'),
     ('设置 MTU', '<p>创建网络时用 <code>-o com.docker.network.driver.mtu=1400</code>,容器里的 eth0 和虚拟机里的网桥都变成 1400。当容器要经过 VPN、隧道之类有更小 MTU 的链路时,通常要这样降 MTU;我没有复现一个真实的 MTU 黑洞问题。</p>'),
     ('MSS', '<p>读 TCP_MAXSEG 看到:MTU 1400 → 1348,MTU 1280 → 1228,都是 MTU 减 52;默认 65535 的网络上是 32741,不是 65483,具体原因我没有查。我试过让容器连外网地址(github.com:443)读 MSS,连接超时了,所以没有外网路径上的数据。</p>')],
    steps,
    [ENV_C + '。MTU 取自 /sys/class/net/*/mtu;MSS 用 Python 的 getsockopt(IPPROTO_TCP, TCP_MAXSEG) 在建立连接后读取;每种配置运行一次;实验后已删除容器和网络',
     '没有验证:外网路径上的 MSS 与路径 MTU 发现、VPN 下的 MTU 黑洞、IPv6 的最小 MTU 1280 限制、ping -M do 分片测试、overlay / macvlan 网络、Linux 宿主机上的默认 MTU'],
    '网络 MTU')
