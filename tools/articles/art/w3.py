from lib import *
S = SS('w3')
steps = [
    step("MTU(链路层一次能发的最大 IP 包)因接口而异:ifconfig 里 lo0 的 mtu 是 16384,真实网卡 en0 是 1500。MTU 是链路层的限制,上层(IP、TCP)要根据它决定每个包最多装多少数据。", t=tl(S(1)), mark=lidx(S(1), 'lo0: flags', 'en0: flags'), done=lidx(S(1), 'lo0: flags'), b=bars([['lo0 MTU', 16384, '16384'], ['en0 MTU', 1500, '1500']], 16384, mark=[1], done=[0]), kv=KV([['lo0', 'MTU 16384'], ['en0', 'MTU 1500'], ['含义', '一个 IP 包(含 IP 头)的上限']], ['含义'])),
    step("TCP 在 SYN 里用 MSS 选项告诉对方“我一个段最多能收多少数据”,值 = MTU − 20(IP 头)− 20(TCP 头)。连本机服务(lo0):SYN 和 SYN-ACK 里 MSS 都是 16344(16384 − 40);访问 example.com:80(en0):本机的 SYN 里是 1460(1500 − 40),但对方的 SYN-ACK 里是 1400——比 1460 还小,说明对方一侧或路径上有设备把 MSS 钳小了。最终双方取较小值。", t=tl(S(2)), mark=lidx(S(2), 'en0:'), done=lidx(S(2), 'lo0:'), b=bars([['lo0 两端', 16344, 'MSS 16344'], ['en0 本机 SYN', 1460, 'MSS 1460'], ['en0 对方 SYN-ACK', 1400, 'MSS 1400']], 16344, mark=[2], done=[0, 1]), kv=KV([['MSS', 'MTU − 20 − 20'], ['lo0', '16344'], ['en0 → example.com', '本机 1460 / 对方 1400(被钳制)']], ['en0 → example.com'])),
    step("MSS 是上限,实际每个包装的数据还要减去 TCP 选项占的字节:上传 1 MiB 到本机,lo0 上被切成 66 个数据段,最大 16332 字节 = 16344 − 12(时间戳选项),其中 64 个正好是 16332;en0 上向 example.com POST 256 KiB 时,发出 30 个数据段,每个都是 1388 字节 = 通告的 1400 − 12。也就是说“MTU 1500”真正能装的应用数据是每包 1388 字节,而不是 1500。", t=tl(S(3)), mark=lidx(S(3), 'lo0:  1 MiB', 'en0:  发出的数据段'), done=lidx(S(3), '所以'), b=bars([['lo0 段长', 16332, '16332 B'], ['en0 段长', 1388, '1388 B']], 16332, mark=[1], done=[0]), kv=KV([['段长', 'MSS − TCP 选项(12 字节时间戳)'], ['lo0', '16332'], ['en0 → example.com', '1388']], ['段长'])),
    step("想把 MSS 调小:TCP_MAXSEG。在 macOS 上客户端在 connect 之前把它设成 512,环回连接里 getsockopt 读回的仍是 16332,抓到的 SYN 里 MSS 仍是 16344;访问 example.com:80 时 SYN 的 MSS 还是 1460,发出的 15 个数据段最大还是 1388——和不设置时一样,TCP_MAXSEG=512 没有生效。所以这个系统上调 MSS 的实验用不了这个选项。", t=tl(S(4)), mark=lidx(S(4), '环回:设置', 'en0 → example.com'), done=lidx(S(4), '结论'), kv=KV([['TCP_MAXSEG=512(connect 前)', 'setsockopt 不报错'], ['SYN 里的 MSS', '不变(16344 / 1460)'], ['段长', '不变(16332 / 1388)']], ['SYN 里的 MSS'])),
    step("段越小,包越多、开销越大。用“每次只 write 500 字节 + TCP_NODELAY”来模拟 MSS≈500(每次 write 立即成为一个包),与默认的 1 MiB 大块 write 对比,往本机发 64 MiB(3 轮中位数):大块写 10 ms(6104 MiB/s),发出 4326 个数据包,平均每包 15513 字节;500 字节小块写 535 ms(120 MiB/s),发出 134217 个数据包,平均每包 500 字节。包数多了 31 倍,耗时多了 50 多倍——每个包都要走一遍协议栈,开销按包计,不按字节计。", t=tl(S(5)), mark=lidx(S(5), '500 字节小块写'), done=lidx(S(5), '1 MiB 大块写'), b=bars([['大块写 耗时', 10, '10 ms'], ['500 B 小块写 耗时', 535, '535 ms']], 535, mark=[1], done=[0]), kv=KV([['大块写', '4326 个包,10 ms'], ['500 B 小块写', '134217 个包,535 ms'], ['原因', '开销按包计']], ['原因'])),
]
A = mkartw('w3', 3, '网络协议,MTU,MSS,TCP选项,分段,tcpdump,真实验证,动画演示',
    '实测 MTU 与 MSS:lo0 的 MTU 16384、en0 的 1500;SYN 里的 MSS = MTU − 40(16344 / 1460),example.com 一侧通告 1400;实际段长还要减 12 字节时间戳选项(16332 / 1388);macOS 上 TCP_MAXSEG 在 connect 前设置不生效;500 字节小块写比 1 MiB 大块写多 31 倍的包、慢 50 多倍。',
    '“MTU 1500”到底意味着一个包能装多少数据?MSS 是怎么在握手里协商出来的?为什么实际的段长又比 MSS 小一点?小包为什么那么贵?这篇用 tcpdump 和 TCP_CONNECTION_INFO 逐项量。',
    [('16344 / 1460', 'lo0 与 en0 上本机 SYN 里的 MSS(MTU − 40)'), ('1388', '访问 example.com 时每个数据段实际装的应用数据(对方通告 1400 − 12 字节时间戳)'), ('134217 vs 4326', '500 字节小块写与 1 MiB 大块写发送同样 64 MiB 所用的数据包数')],
    [('MTU', '<p>MTU 是链路层一次能发的最大 IP 包:lo0 是 16384,真实网卡 en0 是 1500。</p>'),
     ('MSS', '<p>TCP 在 SYN 里用 MSS 选项通告“我能收的最大段”,通常是 MTU − 20 − 20,双方取较小者。</p>'),
     ('实际段长', '<p>每个段还要给 TCP 选项让位:启用时间戳选项后,段长 = MSS − 12。lo0 上是 16332,en0 上访问 example.com 是 1388(对方通告了 1400,小于本机的 1460,说明路径上有设备把 MSS 钳小了)。</p>'),
     ('调不动的 MSS', '<p>macOS 上 connect 之前设置 TCP_MAXSEG=512 不生效,SYN 与段长都不变。</p>'),
     ('小包的代价', '<p>开销按包计:同样 64 MiB,500 字节一包要发 134217 个包、慢 50 多倍。这也是 Nagle 算法和 TSO / GSO 存在的原因(见后面的篇目)。</p>')],
    steps,
    [ENV_W + '。MSS 的值读自 SYN / SYN-ACK 的 TCP 选项(dpkt 解析 tcpdump -w 的 pcap);第三节的 en0 数据来自向 example.com:80 POST 256 KiB(服务端很快回复并关闭,所以只发出了 30 个段);TCP_MAXSEG 的尝试只在 macOS 上做过;第五节用大小写入模拟小 MSS,txpackets 来自发送方连接的 TCP_CONNECTION_INFO',
     '没有验证:Linux 上 TCP_MAXSEG 的行为;路径 MTU 发现与 ICMP(见 PMTUD 一篇);IPv6 的 MSS(MTU − 60);网卡 TSO 把大块拆包的位置;巨型帧(MTU 9000);example.com 一侧 MSS 钳制发生在哪一跳'],
    'MTU 与 MSS')
