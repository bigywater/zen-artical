from lib import *
S = SS('w59')
steps = [
    step("同一个 127.0.0.1:P 能不能被两个套接字 bind(第一个已经 listen)。两边都不设选项:第二个 bind 得 EADDRINUSE。两边都设 REUSEADDR:仍然是 EADDRINUSE——REUSEADDR 并不让两个监听者共用同一个地址端口。两边都设 REUSEPORT:成功;两边都设 REUSEADDR + REUSEPORT:成功。只有一边设的所有组合(第一个设 REUSEPORT 第二个不设、反过来、REUSEADDR 同样两种)全部是 EADDRINUSE。所以 REUSEPORT 要求每个套接字在 bind 之前都设置,否则不算数。", t=tl(S(1)), mark=lidx(S(1), '两边都设 REUSEPORT', '两边都设 REUSEADDR '), done=lidx(S(1), '两边都设 都不设', '只有一边设', '第一个设 REUSEPORT', '第一个设 REUSEADDR'), kv=KV([['都不设 / 只 REUSEADDR', 'EADDRINUSE'], ['两边都设 REUSEPORT', '成功'], ['只有一边设', 'EADDRINUSE']], ['两边都设 REUSEPORT'])),
    step("REUSEADDR 的经典用途:服务端重启绕过 TIME_WAIT。让服务端一侧先 close,netstat 里这个端口留下 TIME_WAIT,再 bind + listen 同一个端口:不设选项 → EADDRINUSE;设 REUSEADDR → 成功;设 REUSEPORT → 也成功(这一项我没有料到:REUSEPORT 在 macOS 上同样允许在 TIME_WAIT 上重新绑定)。", t=tl(S(2)), mark=lidx(S(2), '新套接字 bind + listen → EADDRINUSE', '设 REUSEADDR '), done=lidx(S(2), '设 REUSEPORT'), kv=KV([['不设', 'TIME_WAIT 时 bind → EADDRINUSE'], ['REUSEADDR', '成功'], ['REUSEPORT', '也成功']], ['REUSEADDR'])),
    step("通配地址与具体地址:先绑 0.0.0.0:P 再绑 127.0.0.1:P,都不设 → EADDRINUSE;都设 REUSEADDR → 成功;反过来先具体后通配,都设 REUSEADDR → 成功;都设 REUSEPORT → 成功。这时两个套接字都在监听,连 127.0.0.1:P 100 次,100 次都被绑具体地址的那个接走,通配的那个 0 次——更具体的地址优先。这就是“一个服务绑 0.0.0.0、另一个绑特定 IP 同一个端口”能共存的原理。", t=tl(S(3)), mark=lidx(S(3), '具体地址优先于通配'), done=lidx(S(3), '都不设 ', '先 127.0.0.1 后 0.0.0.0', '都设 REUSEPORT'), b=bars([['具体 127.0.0.1', 100, '100'], ['通配 0.0.0.0', 0, '0']], 100, mark=[0], done=[1]), kv=KV([['都不设', 'EADDRINUSE'], ['都设 REUSEADDR', '成功,先后顺序都行'], ['连接到哪个', '具体地址优先(100 / 0)']], ['连接到哪个'])),
    step("REUSEPORT 的负载均衡:4 个监听套接字同绑 127.0.0.1:P,依次发起 400 个连接(源端口各不相同),每个监听者 accept 到的个数是 [0, 0, 0, 400]——全部给了最后绑定的那一个。在这台 macOS 上 REUSEPORT 允许多个监听者共存,但没有像 Linux 文档里那样把连接分摊给它们。", t=tl(S(4)), mark=lidx(S(4), '4 个监听者各 accept 到'), done=lidx(S(4), '4 个监听者各 accept 到'), b=bars([['监听者 1', 0, '0'], ['监听者 2', 0, '0'], ['监听者 3', 0, '0'], ['监听者 4(最后绑定)', 400, '400']], 400, mark=[3], done=[0, 1, 2]), kv=KV([['4 个监听者', '分别 accept 0 / 0 / 0 / 400'], ['结论', '没有负载均衡,全给最后绑定的'], ['Linux 的行为', '没有验证']], ['结论'])),
    step("UDP 单播 + REUSEPORT:3 个 UDP 套接字同绑 127.0.0.1:P。一个发送方发 300 个数据报:各收到 [0, 0, 300],全部给了最后绑定的;换成 30 个不同源端口的发送方、各发 10 个(共 300):各收到 [0, 0, 300],还是全部给最后一个。UDP 同样没有按四元组分流。", t=tl(S(5)), mark=lidx(S(5), '3 个 UDP 套接字各收到', '换成 30 个不同源端口'), done=lidx(S(5), '3 个 UDP 套接字各收到'), b=bars([['套接字 1', 0, '0'], ['套接字 2', 0, '0'], ['套接字 3(最后绑定)', 300, '300']], 300, mark=[2], done=[0, 1]), kv=KV([['1 个发送方 300 包', '0 / 0 / 300'], ['30 个源端口 300 包', '0 / 0 / 300'], ['结论', '单播全给最后绑定的']], ['结论'])),
    step("UDP 多播:3 个套接字同绑一个 UDP 端口并加入组 239.1.2.3,本机发 10 个多播包。只设 REUSEADDR、绑 0.0.0.0:3 次 bind 得到 [成功, EADDRINUSE, EADDRINUSE],只有 1 个套接字能绑,它收到 10 个。REUSEADDR + REUSEPORT、绑 0.0.0.0:3 次都成功,各收到 10 个。只设 REUSEADDR、但绑的是多播组地址本身:3 次都成功,各收到 10 个。也就是说,多播要让多个套接字都收到,要么两个选项都设,要么把套接字绑到组地址上;单设 REUSEADDR 绑 0.0.0.0 在 macOS 上不行。", t=tl(S(6)), mark=lidx(S(6), '只 REUSEADDR,绑 0.0.0.0', 'REUSEADDR+REUSEPORT', '绑多播组地址'), done=lidx(S(6), '只 REUSEADDR,绑 0.0.0.0'), kv=KV([['REUSEADDR 绑 0.0.0.0', '只有 1 个能 bind'], ['REUSEADDR+REUSEPORT', '3 个都 bind,各收 10 个'], ['REUSEADDR 绑组地址', '3 个都 bind,各收 10 个']], ['REUSEADDR+REUSEPORT'])),
]
A = mkartw('w59', 59, '网络协议,TCP,UDP,SO_REUSEADDR,SO_REUSEPORT,EADDRINUSE,TIME_WAIT,真实验证,动画演示',
    '实测 macOS 上 SO_REUSEADDR 与 SO_REUSEPORT:REUSEADDR 绕过 TIME_WAIT 但不能让两个监听者共存;共存要两边都设 REUSEPORT;但 4 个监听者 400 个连接全部给了最后绑定的一个,UDP 也一样;多播要 REUSEADDR+REUSEPORT 或绑组地址才能多个套接字都收到。',
    '“Address already in use”几乎人人遇到过,标准解法是 SO_REUSEADDR;后来又有了 SO_REUSEPORT。这两个选项到底分别允许什么、不允许什么?这篇在 macOS 上把 bind 冲突的组合一个个跑出来,还看了 REUSEPORT 到底会不会分摊连接。',
    [('0 / 0 / 0 / 400', 'REUSEPORT 下 4 个监听者各 accept 到的连接数:全部给最后绑定的'), ('EADDRINUSE', '两边都只设 REUSEADDR 时第二个监听者 bind 同一个地址端口的结果'), ('100 / 0', '通配 0.0.0.0 与具体 127.0.0.1 同端口时,连 127.0.0.1 的 100 次被谁接走')],
    [('谁和谁能共存', '<p>两个监听者共用同一个地址端口,要两边都设 REUSEPORT;只设 REUSEADDR 或只有一边设都是 EADDRINUSE。</p>'),
     ('TIME_WAIT', '<p>端口上留有 TIME_WAIT 时,重新 bind 需要 REUSEADDR(这台 macOS 上 REUSEPORT 也行)。</p>'),
     ('通配与具体', '<p>绑 0.0.0.0 和绑具体 IP 的两个套接字,设了 REUSEADDR 就能共存,连接给更具体的那个。</p>'),
     ('没有负载均衡', '<p>这台 macOS 上 REUSEPORT 的 4 个监听者,400 个连接全部给了最后绑定的一个。</p>'),
     ('UDP 单播', '<p>3 个 UDP 套接字同绑一个端口,无论 1 个还是 30 个发送方,300 个数据报都全部给最后绑定的那个。</p>'),
     ('多播', '<p>多播要多个套接字都收到,需要两个选项都设,或把套接字绑到多播组地址。</p>')],
    steps,
    [ENV_W + '。全部在本机 lo0 上,单个进程里的多个套接字;负载均衡只看了 400 个连接 / 300 个数据报,没有多进程的情形',
     '没有验证:Linux 上 REUSEPORT 的哈希分流;多个进程(而不是同一进程)用 REUSEPORT 的分流;不同用户之间 REUSEPORT 的安全限制;IPv6 的 IPV6_V6ONLY 对 bind 冲突的影响;SO_REUSEPORT_LB(FreeBSD 的分流选项);REUSEPORT 下关闭其中一个监听者时已排队连接的去向'],
    'REUSEADDR 与 REUSEPORT')
