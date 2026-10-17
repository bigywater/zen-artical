from lib import *
S = SS('c47')
steps = [
    step("--network host 的容器,网络命名空间就是 Docker Desktop 虚拟机自己的:读 /proc/self/ns/net,默认容器是 net:[4026534595],--network host 的容器是 net:[4026531833],虚拟机 PID 1 的也是 net:[4026531833]。网卡列表也一样:默认容器只有 eth0、lo 和一些内核隧道设备;host 模式容器看到 docker0、br-c76c209e2a7a、services1、bond0 和一串 veth…(与虚拟机本身一致)。hostname:默认容器是容器 ID(1184e6a1e4ac),host 模式容器是 docker-desktop,和虚拟机相同。注意这个“host”是 Docker Desktop 的虚拟机,不是你的 Mac。", t=tl(S(1)), done=lidx(S(1), '网络命名空间', '--network host 的容器的网卡'), mark=lidx(S(1), '默认容器的网卡', '虚拟机自己的网卡'), kv=KV([['net 命名空间', 'host 模式 = 虚拟机 PID 1 的 net:[4026531833]'], ['网卡', 'host 模式能看到 docker0、br-…、veth…'], ['hostname', 'docker-desktop(虚拟机的),不是容器 ID']], ['net 命名空间'])),
    step("host 模式下 -p 没有意义:docker run --network host -p 9711:80 退出码 0,但输出 WARNING: Published ports are discarded when using host network mode,端口映射被丢弃。", t=tl(S(2)), done=lidx(S(2), 'WARNING') if False else lidx(S(2), '--network host -p 9711:80'), kv=KV([['--network host -p', 'WARNING: Published ports are discarded'], ['退出码', '0,容器照常运行']], ['--network host -p'])),
    step("host 模式容器里起一个 HTTP 服务监听 9755:虚拟机里 ss 能看到 9755 在监听;但 Mac 上 curl 127.0.0.1:9755 → Connection refused(Errno 61);另一个默认 bridge 容器访问 172.17.0.1:9755(虚拟机上 docker0 的地址)→ 成功。在 macOS 的 Docker Desktop 上,host 模式的端口监听在虚拟机里,Mac 够不着。", t=tl(S(3)), done=lidx(S(3), '另一个默认 bridge 容器', '虚拟机里 ss'), mark=lidx(S(3), 'Mac 宿主机 curl'), kv=KV([['虚拟机里', '在监听'], ['Mac 访问 127.0.0.1', 'Connection refused'], ['bridge 容器访问 172.17.0.1', '成功']], ['Mac 访问 127.0.0.1'])),
    step("两个 host 模式的容器绑定同一个端口:第二个失败,退出码 1,OSError: [Errno 98] Address in use——它们共用一个网络命名空间。对比:两个默认 bridge 容器各自监听容器内的 8000,都成功(listening / listening)。", t=tl(S(4)), done=lidx(S(4), '对比'), mark=lidx(S(4), '第二个 host 容器'), kv=KV([['两个 host 容器同端口', '冲突:Address in use'], ['两个 bridge 容器同端口', '各有各的命名空间,不冲突']], ['两个 host 容器同端口'])),
]
A = mkartc('c47', 47, 'Docker,host网络,--network host,网络命名空间,macOS,真实验证,动画演示',
    '在 Docker Desktop(macOS)上实测 --network host:容器共用虚拟机的网络命名空间(net:[4026531833]、hostname docker-desktop),不是 Mac 的;-p 被丢弃并打印 WARNING;host 模式容器监听的端口 Mac 访问不了(Connection refused),但虚拟机里的 bridge 容器能通过 172.17.0.1 访问;两个 host 容器绑同一个端口会 Address in use。',
    '--network host 在 macOS 上到底是谁的网络?这篇读网络命名空间的编号、网卡列表和 hostname,验证 -p 为什么没用、从 Mac 能不能访问到,以及端口冲突。',
    [('net:[4026531833]', 'host 模式容器和虚拟机 PID 1 共用的网络命名空间编号'), ('Connection refused', 'Mac 上访问 host 模式容器监听的端口的结果'), ('Address in use', '两个 host 模式容器绑定同一端口的第二个得到的错误')],
    [('host 是谁', '<p>在 Docker Desktop 上,<code>--network host</code> 的“host”是运行 Docker 的 Linux 虚拟机。容器的网络命名空间编号和虚拟机的 PID 1 完全相同,网卡里有 docker0、br-…、veth…,hostname 是虚拟机的 <code>docker-desktop</code>。Linux 宿主机上的情形不同,我没有测。</p>'),
     ('-p 无效', '<p>host 模式下 <code>-p</code> 被丢弃,docker 只打印一个 WARNING,退出码仍是 0。</p>'),
     ('Mac 够不着', '<p>host 模式容器监听 9755,虚拟机里 <code>ss</code> 能看到,虚拟机里的其它容器通过 docker0 的地址 172.17.0.1 能访问,Mac 上 <code>curl 127.0.0.1:9755</code> 被拒绝。Docker Desktop 有单独的「主机网络」功能开关,我没有改任何设置,所以没有测它打开后的表现。</p>'),
     ('端口冲突', '<p>host 模式的容器之间没有网络隔离,绑定同一端口会冲突;bridge 模式的容器各有各的命名空间,可以都监听 8000。</p>')],
    steps,
    [ENV_C + '。网络命名空间编号读自 /proc/self/ns/net;网卡列表读自 /sys/class/net;虚拟机侧信息用特权容器加 nsenter 读取(方法见 c19);HTTP 服务用 python:3.12-alpine 的 socketserver;端口从 9730 以后挑一个空闲的(中间有一次因为端口 9721 在虚拟机里绑定失败而换了端口,原因我没有查);实验后已删除容器',
     '没有验证:Docker Desktop 的「启用主机网络」设置打开后从 Mac 访问、Linux 宿主机上的 --network host、host 模式下的 iptables 与防火墙、IPv6、host 模式容器与 bridge 容器之间的 DNS'],
    'host 网络')
