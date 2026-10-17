from lib import *
S = SS('c55')
steps = [
    step("默认容器的 /etc/hosts:127.0.0.1 localhost、::1 localhost ip6-localhost ip6-loopback、fe00:: ip6-localnet、ff00:: ip6-mcastprefix、ff02::1 ip6-allnodes、ff02::2 ip6-allrouters,最后一行是容器自己的 IP 加主机名(容器 ID 前 12 位);hostname 命令输出也是这 12 位。", t=tl(S(1)), done=lidx(S(1), '127.0.0.1\tlocalhost', 'hostname 命令'), mark=lidx(S(1), '<容器ID前12位>'), kv=KV([['固定的 6 行', 'localhost、ip6-*'], ['最后一行', '容器 IP + 容器 ID 前 12 位(主机名)']], ['最后一行'])),
    step("--hostname web01 --domainname corp.test --add-host db.internal:10.9.9.9 --add-host cache:10.9.9.10:/etc/hosts 里 --add-host 的两行排在固定 6 行之后(10.9.9.9 db.internal、10.9.9.10 cache),最后一行变成容器 IP 对应“web01.corp.test web01”;hostname = web01,hostname -f = web01.corp.test;docker inspect 的 HostConfig.ExtraHosts = [db.internal:10.9.9.9, cache:10.9.9.10]。", t=tl(S(2)), done=lidx(S(2), 'hostname = web01', '10.9.9.9\tdb.internal'), mark=lidx(S(2), 'ExtraHosts'), kv=KV([['--add-host', '追加在固定行之后'], ['--hostname + --domainname', '最后一行:web01.corp.test web01'], ['inspect', 'HostConfig.ExtraHosts']], ['--add-host'])),
    step("/etc/hosts 优先于 DNS:ping db.internal(只在 /etc/hosts 里)解析到 10.9.9.9;--add-host github.com:10.9.9.11 之后 ping github.com 解析到 10.9.9.11,而同一个容器里 busybox 的 nslookup github.com 直接问 DNS,得到 20.205.243.166;没加 --add-host 的容器 ping github.com 解析到 20.205.243.166。", t=tl(S(3)), done=lidx(S(3), 'ping db.internal', '--add-host github.com:10.9.9.11 之后'), mark=lidx(S(3), 'nslookup github.com', '对比'), kv=KV([['ping(getaddrinfo)', '先看 /etc/hosts'], ['nslookup', '直接问 DNS,不看 /etc/hosts'], ['覆盖真实域名', '--add-host github.com:10.9.9.11 生效']], ['ping(getaddrinfo)'])),
    step("同名多条:--add-host multi:10.9.9.20 --add-host multi:10.9.9.21 → /etc/hosts 里两行 multi,ping multi 解析到第一条 10.9.9.20。在容器里追加 10.9.9.99 edited.local,docker exec cat 看得到;docker restart 之后 edited.local 不在了,--add-host 的 multi 还在——/etc/hosts 每次启动重新生成。", t=tl(S(4)), done=lidx(S(4), 'docker restart 之后', '--add-host multi'), mark=lidx(S(4), 'ping multi', '容器里追加'), kv=KV([['同名两条', 'ping 取第一条'], ['容器里手改', 'restart 后丢失'], ['--add-host', 'restart 后仍在']], ['容器里手改'])),
]
A = mkartc('c55', 55, 'Docker,/etc/hosts,--add-host,--hostname,host-gateway,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测容器的 /etc/hosts:默认 6 行固定内容加“容器 IP + 容器 ID 前 12 位”;--add-host 的条目排在固定行之后,--hostname 与 --domainname 决定最后一行;/etc/hosts 优先于 DNS(--add-host github.com:10.9.9.11 让 ping 解析到该地址,而 nslookup 不受影响);容器里手改的内容在 restart 后丢失,--add-host 保留。',
    '--add-host 到底写进了哪里?它和 DNS 谁优先?在容器里直接改 /etc/hosts 能保存吗?这篇逐项实测,包括同名多条记录和 ping 与 nslookup 的差别。',
    [('10.9.9.11', '--add-host github.com:10.9.9.11 之后 ping github.com 解析到的地址(真实地址是 20.205.243.166)'), ('第一条', '同名两条 --add-host 时 ping 取的是第一条'), ('restart 后丢失', '容器里手工追加到 /etc/hosts 的内容,docker restart 之后不在了')],
    [('默认内容', '<p>/etc/hosts 固定有 6 行本地和 IPv6 条目,最后一行是容器自己的 IP 和主机名(默认是容器 ID 前 12 位)。</p>'),
     ('--add-host 与主机名', '<p><code>--add-host 名字:IP</code> 追加在固定行之后;<code>--hostname</code> 与 <code>--domainname</code> 改的是最后一行,以及 <code>hostname -f</code> 的结果。</p>'),
     ('优先级', '<p>解析器(ping 用的 getaddrinfo)先查 /etc/hosts,所以可以用 --add-host 覆盖一个真实域名;但 busybox 的 nslookup 直接问 DNS,看不到 /etc/hosts 里的条目,排查解析问题时别被它误导。</p>'),
     ('重复与持久', '<p>同名多条,ping 取第一条。容器里手改的 /etc/hosts 在 docker restart 后丢失,而 --add-host 的条目会重新写入,所以要持久地加条目用 <code>--add-host</code>。</p>')],
    steps,
    [ENV_C + '。内容取自 docker exec cat /etc/hosts(容器 IP 和容器 ID 在输出中替换成了占位符);解析用 busybox 的 ping 与 nslookup;github.com 的真实地址取自一次 DNS 查询;每种情形运行一次;实验后已删除容器',
     '没有验证:host-gateway 的值(见 c51)、自定义网络里 --add-host 与内置 DNS 的优先级、IPv6 条目的 --add-host、Compose 的 extra_hosts、glibc 与 musl 解析器的差别'],
    '--add-host 与 /etc/hosts')
