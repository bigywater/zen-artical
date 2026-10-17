from lib import *
S = SS('c48')
steps = [
    step("默认 bridge 上的容器,/etc/resolv.conf 只有一行 nameserver 192.168.65.7(Docker Desktop 提供的 DNS 地址);自定义网络上的容器是 nameserver 127.0.0.11 加 options ndots:0——127.0.0.11 是 Docker 内置的 DNS 服务。", t=tl(S(1)), done=lidx(S(1), '自定义网络上的容器'), mark=lidx(S(1), '默认 bridge 上的容器'), kv=KV([['默认 bridge', 'nameserver 192.168.65.7'], ['自定义网络', 'nameserver 127.0.0.11,options ndots:0']], ['自定义网络'])),
    step("自定义网络 172.19.0.0/16 里,容器 b 用 nslookup 解析:容器名 bwlab-c48a → 172.19.0.2,--network-alias 设的别名 web 和 frontend → 也是 172.19.0.2,另一个容器名 bwlab-c48b → 172.19.0.3;不存在的名字退出码 1。服务器地址显示 127.0.0.11:53。默认 bridge 上的容器解析不了自定义网络里的 bwlab-c48a。", t=tl(S(2)), done=lidx(S(2), 'nslookup web', 'nslookup frontend', 'nslookup bwlab-c48a'), mark=lidx(S(2), 'nonexistent-name', '默认 bridge 上'), kv=KV([['容器名', '解析到容器 IP'], ['--network-alias', 'web、frontend 都解析到同一个容器'], ['不存在的名字', '退出码 1'], ['别的网络', '解析不了']], ['--network-alias'])),
    step("127.0.0.11 在哪里监听:容器自己的网络命名空间里,UDP 127.0.0.11:56362 和 TCP 127.0.0.11:46227(端口号每个容器随机);给外部名字 github.com 解析,服务器仍显示 127.0.0.11:53,拿到 20.205.243.166,用时 real 0.00 秒——内置 DNS 对外部名字转发给上游。", t=tl(S(3)), done=lidx(S(3), '外部名字'), mark=lidx(S(3), '容器里监听'), kv=KV([['127.0.0.11:53', '客户端看到的地址'], ['实际监听', '127.0.0.11 的随机 UDP / TCP 端口'], ['外部名字', '转发给上游并返回']], ['实际监听'])),
    step("--dns 与 --dns-search:自定义网络 + --dns 1.1.1.1 --dns-search example.internal --dns-opt ndots:2,resolv.conf 里仍是 nameserver 127.0.0.11,多了 search example.internal 和 options ndots:2(--dns 的 1.1.1.1 作为上游,不出现在 resolv.conf 里)。这个容器 ping bwlab-c48a 成功(172.19.0.2),但 busybox 的 nslookup bwlab-c48a 失败,写成 bwlab-c48a.(末尾带点)才成功——busybox nslookup 遇到 search 域时的行为和 ping 的 getaddrinfo 不同,原因我没有查。默认 bridge + --dns 1.1.1.1:resolv.conf 直接就是 nameserver 1.1.1.1。", t=tl(S(4)), done=lidx(S(4), 'ping bwlab-c48a', 'nslookup bwlab-c48a.'), mark=lidx(S(4), '自定义网络 + --dns', '默认 bridge + --dns', '同一个容器 nslookup bwlab-c48a:'), kv=KV([['自定义网络 + --dns', 'resolv.conf 仍是 127.0.0.11,加 search / ndots'], ['默认 bridge + --dns', 'resolv.conf 直接写 1.1.1.1'], ['容器名解析', 'ping 成功,nslookup(无末尾点)失败']], ['自定义网络 + --dns'])),
]
A = mkartc('c48', 48, 'Docker,内置DNS,127.0.0.11,resolv.conf,网络别名,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测内置 DNS:自定义网络上的容器 resolv.conf 是 nameserver 127.0.0.11(默认 bridge 是 192.168.65.7);容器名和 --network-alias 都能解析到容器 IP,不存在的名字退出码 1,别的网络里的名字解析不了;--dns 在自定义网络里只改上游,resolv.conf 仍是 127.0.0.11。',
    '容器之间为什么能按名字互相访问?127.0.0.11 是什么?--dns 和 --dns-search 又改了什么?这篇读 resolv.conf、用 nslookup 和 ping 逐项验证,并看 127.0.0.11 在容器里具体监听在哪里。',
    [('127.0.0.11', '自定义网络里容器的 nameserver,Docker 内置 DNS 的地址'), ('3 个名字 → 1 个 IP', '容器名和两个 --network-alias 都解析到 172.19.0.2'), ('ndots:0', '自定义网络里容器 resolv.conf 的默认选项')],
    [('resolv.conf', '<p>自定义网络里的容器 resolv.conf 指向 <code>127.0.0.11</code>,选项 <code>ndots:0</code>;默认 bridge 上的容器拿到的是 Docker Desktop 的 DNS 地址 192.168.65.7,所以解析不了容器名。</p>'),
     ('解析容器名与别名', '<p>容器名、<code>--network-alias</code> 都能解析,不存在的名字失败,别的网络里的容器名解析不了。一个名字对应多个容器时的表现(轮询),见后面的 DNS 轮询一篇。</p>'),
     ('127.0.0.11 的实现', '<p>127.0.0.11:53 只是客户端看到的地址;容器自己的网络命名空间里,127.0.0.11 的一个随机 UDP 端口和一个随机 TCP 端口在监听(这里是 56362 和 46227)。把 53 端口的请求如何转到这些端口,我没有看 iptables 规则。外部名字被转发给上游,github.com 解析正常。</p>'),
     ('--dns 与 search', '<p>自定义网络里 <code>--dns 1.1.1.1</code> 并不出现在 resolv.conf,内置 DNS 继续服务容器名,外部名字才转给指定的上游(我没有验证上游确实换成了 1.1.1.1);<code>--dns-search</code>、<code>--dns-opt</code> 则直接写进 resolv.conf。默认 bridge 上 <code>--dns</code> 直接写进 resolv.conf。注意 busybox 的 nslookup 在有 search 域时对短名字表现不同于 ping。</p>')],
    steps,
    [ENV_C + '。解析用 busybox 的 nslookup 和 ping;内置 DNS 的监听用容器里的 netstat 读取;github.com 的解析结果与耗时取自一次查询(依赖网络,不具可比性);实验后已删除容器和网络',
     '没有验证:127.0.0.11 的 iptables DNAT 规则、--dns 上游确实被使用、多个容器共用一个别名的轮询、IPv6(AAAA)、DNS 缓存与 TTL、docker compose 的服务名与容器名、搜索域对短名字的完整行为'],
    '内置 DNS')
