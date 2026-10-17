from lib import *
S = SS('c62')
steps = [
    step("不写 networks 时,compose 为项目建一个 <项目名>_default 网络(bwlab-c62_default,驱动 bridge);web 在这个网络里的别名是 [bwlab-c62-web-1, web](容器名和服务名),所以 web ping api(服务名)和 ping bwlab-c62-api-1(容器名)都通。docker compose down 之后这个网络被删除。", t=tl(S(1)), done=lidx(S(1), 'web ping api', '项目的网络'), mark=lidx(S(1), 'down 之后网络还在吗'), kv=KV([['默认网络', '<项目名>_default,bridge'], ['别名', '容器名 + 服务名'], ['down', '连网络一起删除']], ['默认网络'])),
    step("前后端分网:proxy 只在 front,app 在 front 和 back,db 只在 back。proxy ping app 通;proxy ping db 不通(bad address 'db'——解析不了名字);app ping db 通;db ping proxy 不通(bad address 'proxy')。项目的网络是 bwlab-c62_back 和 bwlab-c62_front。不在同一个网络里的服务,连名字都解析不了。", t=tl(S(2)), done=lidx(S(2), 'proxy ping app'), mark=lidx(S(2), '项目的网络名'), kv=KV([['proxy → app', '通(同在 front)'], ['proxy → db', '不通,名字解析失败'], ['app → db', '通(同在 back)']], ['proxy → db'])),
    step("internal: true 的网络不能出网:priv 的 Internal = true、pub 的 Internal = false。inside(在 priv)ping 1.1.1.1 不通(0.1 秒就失败),nslookup github.com 失败,路由表里只有 172.20.0.0/16,没有默认路由;outside(在 pub)ping 1.1.1.1 通(0.3 秒),nslookup github.com 成功,有 default via 172.19.0.1。", t=tl(S(3)), done=lidx(S(3), 'outside ping 1.1.1.1'), mark=lidx(S(3), 'inside ping 1.1.1.1', '路由'), kv=KV([['internal: true', '没有默认路由,ping 外网 0.1 秒就失败,DNS 解析外部名字失败'], ['普通网络', '有 default via 网关,可以出网']], ['internal: true'])),
    step("别名与固定 IP:a 在网络 n 里配了 aliases [alpha, first] 和 ipv4_address 10.62.0.10(网络 ipam 子网 10.62.0.0/24),docker compose up -d 退出码 0;a 的地址 10.62.0.10,别名列表是 [bwlab-c62-a-1, a, alpha, first];b 解析 alpha、first、a 都得到 10.62.0.10。", t=tl(S(4)), done=lidx(S(4), 'b 解析 alpha', 'a 的地址'), mark=lidx(S(4), '网络子网'), kv=KV([['aliases', '服务名之外再加别名'], ['ipv4_address', '固定 IP,需要自己定义子网'], ['解析', 'alpha / first / a 都指向同一个 IP']], ['ipv4_address'])),
]
A = mkartc('c62', 62, 'Docker,Docker Compose,networks,internal,别名,固定IP,真实验证,动画演示',
    '在 Docker Compose v5.5.1 里实测 compose 的网络:默认建「项目名_default」,服务名和容器名都能解析;前后端分网后 proxy 连 db 的名字都解析不了;internal: true 的网络没有默认路由、不能出网;aliases 与 ipv4_address 可以固定名字和地址。',
    'compose 默认是怎么给服务建网络的?怎么把数据库藏在后端网络里?internal 网络到底隔离到什么程度?这篇用 ping 和路由表逐项验证。',
    [('bad address', '不在同一个网络里的服务,名字解析就失败(proxy ping db)'), ('没有默认路由', 'internal: true 的网络里容器的路由表只有本网段'), ('10.62.0.10', '用 ipv4_address 给服务 a 固定的 IP,别名 alpha / first / a 都解析到它')],
    [('默认网络', '<p>不写 <code>networks</code>,所有服务共享一个 <code>&lt;项目名&gt;_default</code> bridge 网络,服务名和容器名都是别名。<code>docker compose down</code> 会把它删掉。</p>'),
     ('分网', '<p>服务只加入声明的网络。proxy 在 front、db 在 back,二者之间连名字都解析不了,只有同时在两个网络里的 app 能连两边。想隐藏数据库,就别让它进前端网络。</p>'),
     ('internal', '<p><code>internal: true</code> 的网络里没有默认路由,容器 ping 外网立刻失败,也解析不了外部域名;同一网络里的容器之间仍然互通(本文只验证了出网这一面)。</p>'),
     ('别名与固定 IP', '<p>在服务的 networks 下可以写 <code>aliases</code> 和 <code>ipv4_address</code>;固定 IP 要求网络自己声明 ipam 子网。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;连通性用 busybox ping(-c 1 -W 2/3)和 nslookup;出网测试的 1.1.1.1 是 ICMP,github.com 是 DNS 解析;每个场景一个 compose 项目 bwlab-c62,实验后已 down -v;固定网段 10.62.0.0/24 是我选的私有网段',
     '没有验证:internal 网络里容器之间的互通与 DNS(只验证了出网被阻断)、ipv6 网络、external: true 引用已有网络、driver_opts(如 MTU)、网络的 labels、跨项目通信'],
    'compose 网络')
