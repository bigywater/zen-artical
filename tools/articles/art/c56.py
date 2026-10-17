from lib import *
S = SS('c56')
steps = [
    step("默认容器没有 IPv6:默认 bridge 网络的 EnableIPv6 = false;容器里 eth0 没有 IPv6 地址(只有 lo 上的 ::1/128);/proc/sys/net/ipv6/conf 的 disable_ipv6:all 是 0、eth0 是 1;没有默认 IPv6 路由。", t=tl(S(1)), done=lidx(S(1), 'EnableIPv6', 'eth0 的 IPv6'), mark=lidx(S(1), 'disable_ipv6', '默认路由(IPv6)'), kv=KV([['EnableIPv6', 'false'], ['eth0 的 IPv6 地址', '无'], ['disable_ipv6 (all / eth0)', '0 / 1']], ['eth0 的 IPv6 地址'])),
    step("docker network create --ipv6(不指定子网)退出码 0,网络的 IPAM 有两个子网:172.19.0.0/16(网关 172.19.0.1)和 fd5c:c1ec:db63::/64(网关 fd5c:c1ec:db63::1)——自动选了一个 fd 开头的私有 IPv6 子网。容器 b 的 eth0 有 IPv4 172.19.0.2/16、IPv6 fd5c:c1ec:db63::2/64,外加一个 fe80:: 的链路本地地址;容器 c 的 IPv6 是 fd5c:c1ec:db63::3。b 用 IPv6 地址 ping6 c 通(退出码 0);b 查询 bwlab-c56c 的 AAAA 记录,得到 fd5c:c1ec:db63::3;ping6 按名字也通。", t=tl(S(2)), done=lidx(S(2), 'b ping6 c 的 IPv6 地址', 'AAAA'), mark=lidx(S(2), 'IPAM', '容器 b 的地址'), kv=KV([['子网', '172.19.0.0/16 + fd5c:c1ec:db63::/64'], ['容器 b / c', 'fd5c:c1ec:db63::2 / ::3'], ['名字解析', 'AAAA 记录返回 IPv6 地址']], ['子网'])),
    step("IPv6 访问外网:容器 b ping6 Cloudflare 的 2606:4700:4700::1111,退出码 0,往返 202.382 ms;默认 IPv6 路由 default via fd5c:c1ec:db63::1 dev eth0。容器用的是私有地址 fd5c:c1ec:db63::2,说明出网时做了地址转换(我没有查具体是哪条规则)。守护进程配置里默认网络选项的 com.docker.network.enable_ipv6 是 \"false\",所以需要 --ipv6 明确打开。", t=tl(S(3)), done=lidx(S(3), 'ping6 2606:4700:4700::1111', '默认 IPv6 路由'), mark=lidx(S(3), '守护进程配置'), kv=KV([['ping6 外网', '成功,约 202 ms'], ['默认 IPv6 路由', '经 fd5c:c1ec:db63::1'], ['默认网络选项', 'enable_ipv6: false']], ['默认网络选项'])),
]
A = mkartc('c56', 56, 'Docker,IPv6,--ipv6,AAAA,ULA,容器网络,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测容器的 IPv6:默认 bridge 没有(EnableIPv6=false,eth0 无 IPv6 地址、没有默认 IPv6 路由);docker network create --ipv6 自动选出 fd5c:c1ec:db63::/64,容器之间能按 IPv6 地址和名字(AAAA 记录)互通,还能 ping6 通外网的 2606:4700:4700::1111(往返约 202 ms)。',
    '容器能用 IPv6 吗?默认是关的,怎么打开,打开之后容器之间、容器访问外网各是什么样?这篇用 docker network create --ipv6 实测地址分配、名字解析和外网连通性。',
    [('EnableIPv6=false', '默认 bridge 网络的 IPv6 开关'), ('fd5c:c1ec:db63::/64', '不指定子网时 docker network create --ipv6 自动选出的私有 IPv6 子网'), ('202 ms', '容器 ping6 Cloudflare IPv6 DNS 的往返时间(单次测量)')],
    [('默认没有', '<p>默认 bridge 网络的 EnableIPv6 是 false,容器 eth0 上的 disable_ipv6 是 1,没有 IPv6 地址和默认路由;守护进程配置里默认网络选项也是 enable_ipv6=false。</p>'),
     ('--ipv6 网络', '<p>创建网络时加 <code>--ipv6</code>,docker 自动分配一个 fd 开头的 /64 子网,容器拿到 IPv4 和 IPv6 两个地址;内置 DNS 对 AAAA 记录返回容器的 IPv6 地址,容器名可以直接用于 ping6。</p>'),
     ('出网', '<p>这个容器用私有的 fd 地址,仍然 ping6 通了外网的 IPv6 地址,说明出网经过了转换。这个结果依赖我这台 Mac 的网络是否有 IPv6 出口,在没有 IPv6 的网络上可能不通,我只测了一次。</p>')],
    steps,
    [ENV_C + '。IPv6 信息读自 ip -6 addr / route 和 /proc/sys/net/ipv6;连通性用 busybox 的 ping6 / nslookup -type=AAAA;外网 ping6 只发了 1 个包;子网是 docker 自动选的;实验后已删除容器和网络',
     '没有验证:指定 --subnet 的 IPv6 网络、全局单播地址与路由通告、IPv6 的端口映射、ip6tables 规则、IPv6 在 Linux 宿主机上的行为、没有 IPv6 出口的网络上的表现'],
    '容器 IPv6')
