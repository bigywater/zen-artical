from lib import *
S = SS('c51')
steps = [
    step("容器里 nslookup:host.docker.internal → 192.168.65.254(外加一个 fdc4:f303:9324::254 的 IPv6 地址),gateway.docker.internal → 192.168.65.1,kubernetes.docker.internal → 192.168.65.3;不存在的 no.such.name.internal 退出码 1。这些名字由 Docker Desktop 的 DNS(默认 bridge 容器的 nameserver 192.168.65.7)解析,容器的 /etc/hosts 里没有它们(0 行)。", t=tl(S(1)), done=lidx(S(1), 'nslookup host.docker.internal', 'nslookup gateway.docker.internal'), mark=lidx(S(1), '/etc/hosts 有', 'no.such.name'), kv=KV([['host.docker.internal', '192.168.65.254(+ IPv6)'], ['gateway.docker.internal', '192.168.65.1'], ['/etc/hosts', '里面没有,靠 DNS 解析']], ['host.docker.internal'])),
    step("容器访问 Mac 上的服务:Mac 上只监听 127.0.0.1 的服务,容器访问 host.docker.internal 的端口 → hello from the Mac;监听 0.0.0.0 的服务同样成功;自定义网络里的容器也成功。容器访问 127.0.0.1(它自己的回环)→ Connection refused。对着 Mac 的 127.0.0.1 监听也能连上,我推断请求是由 Docker Desktop 转发到 Mac 本机的(没有抓包验证)。", t=tl(S(2)), done=lidx(S(2), '监听 127.0.0.1', '监听 0.0.0.0', '自定义网络里的容器'), mark=lidx(S(2), '容器自己的回环'), kv=KV([['Mac 上只监听 127.0.0.1', '容器经 host.docker.internal 能访问'], ['Mac 上监听 0.0.0.0', '也能访问'], ['容器的 127.0.0.1', '是容器自己,Connection refused']], ['Mac 上只监听 127.0.0.1'])),
    step("--add-host host.docker.internal:host-gateway:/etc/hosts 里多了两行,192.168.65.254 和 fdc4:f303:9324::254 都指向 host.docker.internal;加了之后访问 Mac 的服务仍然成功。在 Docker Desktop 上不加这个参数也能解析;这个写法主要是给没有预置这个名字的环境(如 Linux)用的,我没有在 Linux 上验证。", t=tl(S(3)), done=lidx(S(3), '这时访问'), mark=lidx(S(3), '加 --add-host'), kv=KV([['--add-host ...:host-gateway', '/etc/hosts 多两行(IPv4 与 IPv6)'], ['不加', 'Docker Desktop 上也能解析']], ['--add-host ...:host-gateway'])),
    step("--network host 的容器(共用虚拟机的网络命名空间,见 c47)访问 host.docker.internal 的端口,同样得到 hello from the Mac。", t=tl(S(4)), done=lidx(S(4), '--network host'), kv=KV([['--network host', '也能用 host.docker.internal 访问 Mac']], ['--network host'])),
]
A = mkartc('c51', 51, 'Docker,host.docker.internal,Docker Desktop,访问宿主机,gateway.docker.internal,真实验证,动画演示',
    '在 Docker Desktop(macOS)上实测 host.docker.internal:解析到 192.168.65.254(外加 IPv6),gateway.docker.internal 是 192.168.65.1;容器能访问 Mac 上只监听 127.0.0.1 的服务;容器自己的 127.0.0.1 是容器自己;--add-host host.docker.internal:host-gateway 让 /etc/hosts 里多两行;--network host 的容器也能用。',
    '容器里怎么访问 Mac 上跑的服务?host.docker.internal 是什么、解析到哪里、对只监听 127.0.0.1 的服务有用吗?这篇逐项实测,包括 --add-host host-gateway 的写法。',
    [('192.168.65.254', 'host.docker.internal 在容器里解析到的 IPv4 地址'), ('127.0.0.1 也能连', 'Mac 上只监听 127.0.0.1 的服务,容器经 host.docker.internal 访问成功'), ('Connection refused', '容器访问它自己的 127.0.0.1:Mac 上的服务端口,被拒绝')],
    [('名字从哪来', '<p>host.docker.internal 由 Docker Desktop 的 DNS 解析(192.168.65.254 和一个 IPv6 地址),容器的 /etc/hosts 里并没有。gateway.docker.internal、kubernetes.docker.internal 同理(后者我没有深究)。</p>'),
     ('访问 Mac 上的服务', '<p>Mac 上只监听 127.0.0.1 的 HTTP 服务,容器访问 host.docker.internal 的端口成功——按我的推断是被 Docker Desktop 转发到 Mac 本机的。容器里的 127.0.0.1 指的是容器自己,所以会被拒绝。</p>'),
     ('--add-host', '<p><code>--add-host host.docker.internal:host-gateway</code> 把 192.168.65.254 等地址写进 /etc/hosts。在 Docker Desktop 上不加也能解析,它主要用于没有预置这个名字的 Linux 宿主机,我没有在 Linux 上验证。</p>'),
     ('host 模式', '<p>--network host 的容器同样能访问。</p>')],
    steps,
    [ENV_C + '。Mac 侧用 Python 的 http.server 在 127.0.0.1 和 0.0.0.0 各起一个服务;容器里用 busybox wget / nslookup;输出中的 192.168.x.x 地址会被站点的脱敏规则替换为占位符,文中的 192.168.65.x 是 Docker Desktop 虚拟机内部网段(不是你的局域网);实验后已关闭服务并删除容器和网络',
     '没有验证:Linux 宿主机上的 host-gateway、防火墙对 Mac 本机服务的影响、host.docker.internal 在不同 Docker Desktop 版本里的地址、VPN 下的表现、Mac 上的服务绑定到特定网卡地址时的情形'],
    'host.docker.internal')
