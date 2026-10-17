from lib import *
S = SS('w39')
steps = [
    step("最普通的关闭:客户端 close(),服务端读到 EOF 后也 close()。SYN 和 SYN-ACK 之外线上共 8 个包(第一个是握手的第三个 ACK):客户端 ACK、服务端 ACK、客户端 ACK+PSH 带 2 字节、服务端 ACK,然后才是四次挥手——客户端 ACK+FIN → 服务端 ACK → 服务端 ACK+FIN → 客户端 ACK。服务端的 ACK 和它自己的 FIN 是分开发的(因为服务端是等应用读到 EOF 再 close 才发 FIN)。重复 10 次,每次都是 8 个包。每个 FIN 占一个序号,所以每次挥手都是“FIN → ACK”成对出现。", t=tl(S(1)), mark=lidx(S(1), '客户端:ACK → 服务端:ACK → 客户端:ACK+PSH(2字节)'), done=lidx(S(1), '共 8 个包', '重复 10 次'), b=bars([['每次关闭的包数(握手之外)', 8, '8(10 次全相同)']], 8, mark=[0], done=[]), kv=KV([['四次挥手', '客户端 FIN → 服务端 ACK → 服务端 FIN → 客户端 ACK'], ['服务端的 ACK 与 FIN', '分开发(FIN 等应用 close)'], ['重复 10 次', '都是 8 个包']], ['服务端的 ACK 与 FIN'])),
    step("半关闭:客户端发完请求后 shutdown(SHUT_WR) 只关发送方向(发 FIN),连接并没有结束。服务端读到 EOF 后才发应答:线上客户端 ACK+PSH 带 7 字节请求 → 客户端 ACK+FIN → 服务端 ACK → 服务端 ACK+PSH 带 26 字节的应答 → 服务端 ACK+FIN → 客户端 ACK。客户端在发出 FIN 之后仍然收到了服务端的 26 字节数据 b'RESPONSE-after-EOF:REQUEST'。这就是“半关闭”:TCP 的两个方向是独立关闭的,“我发完了”不等于“我不收了”。", t=tl(S(2)), mark=lidx(S(2), '客户端:ACK → 服务端:ACK → 客户端:ACK+PSH(7字节)'), done=lidx(S(2), '客户端在 FIN 之后'), kv=KV([['shutdown(SHUT_WR)', '发 FIN,只关发送方向'], ['之后', '服务端发来 26 字节,客户端照常收到'], ['意义', '两个方向独立关闭']], ['意义'])),
    step("close() 不一定发 FIN。服务端的接收缓冲区里还有客户端发来的 11 字节没读,就 close():线上服务端发出的是 ACK+RST,而不是 FIN,客户端随后 recv 得到 ConnectionResetError。对照:服务端先把数据读完再 close(),发的是 ACK+FIN,客户端再回 ACK+FIN,recv 得到 b''(正常 EOF)。设了 SO_LINGER(开,0 秒)后 close() 也直接发 ACK+RST。所以缓冲区里有没读的数据(或 SO_LINGER 0)时,对方看到的是“连接被重置”而不是正常的 EOF——对方还没读走的数据可能因此丢失。", t=tl(S(3)), mark=lidx(S(3), '服务端(accepted 套接字)未读完数据', 'SO_LINGER'), done=lidx(S(3), '客户端随后 recv', '对照:服务端先把数据读完', '所以 close 不一定发 FIN'), kv=KV([['未读数据 + close()', '发 RST,对方 recv 报 Connection reset'], ['读完再 close()', '发 FIN,对方 recv 得 b\'\'(EOF)'], ['SO_LINGER(开,0)', '直接 RST']], ['未读数据 + close()'])),
    step("shutdown(SHUT_RD) 的行为:服务端对已接受的连接调用 shutdown(SHUT_RD) 之后,线上没有发出任何包(没有 FIN)。客户端随后发来 17 字节,服务端回的是 RST;客户端第二次 send 报 Broken pipe。服务端对 SHUT_RD 之后到达的数据 recv 得到 b''。也就是说关掉读方向并不是静默丢弃,对方继续发数据时会被 RST 终止连接——它是一个本地的状态,对方要在下一次发数据时才知道。", t=tl(S(4)), mark=lidx(S(4), '客户端:ACK → 服务端:ACK → 客户端:ACK+PSH(17字节)'), done=lidx(S(4), '服务端对 SHUT_RD'), kv=KV([['SHUT_RD 本身', '线上不发包'], ['之后对方发来的数据', '被 RST'], ['对方第二次 send', 'Broken pipe']], ['之后对方发来的数据'])),
    step("同时关闭:两端同时 close() 时 FIN 在线上交叉。回环太快几乎抓不到,所以给 lo0 加了 50 ms 单向延迟,重复 10 次:两端都发出了 FIN 的 10 次、FIN 相隔不到 40 ms 即“交叉”的 10 次(同一个包会被 dummynet 在 lo0 上多次抓到,已按序号去重)。一次交叉的序列:服务端 ACK+FIN、客户端 ACK+FIN 几乎同时发出,之后双方各回一个 ACK。两端刚 close 之后 30 ms 时 netstat 看到的状态:FIN_WAIT_1 出现 14 次、CLOSING 出现 6 次(外加监听套接字 LISTEN 10 次)。同时关闭走 FIN_WAIT_1 → CLOSING → TIME_WAIT,与一方先关(FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT,另一方 CLOSE_WAIT → LAST_ACK)的路径不同。", t=tl(S(5)), mark=lidx(S(5), '一次交叉的序列', 'close 之后 30 ms'), done=lidx(S(5), '10 次里两端都发出了 FIN'), b=bars([['两端都发 FIN', 10, '10 / 10'], ['FIN 交叉', 10, '10 / 10'], ['30 ms 时 FIN_WAIT_1 的套接字', 14, '14'], ['30 ms 时 CLOSING 的套接字', 6, '6']], 14, mark=[1], done=[0, 2, 3]), kv=KV([['同时 close', '两个 FIN 在线上交叉'], ['路径', 'FIN_WAIT_1 → CLOSING → TIME_WAIT'], ['30 ms 时', '看到 FIN_WAIT_1 和 CLOSING']], ['路径'])),
]
A = mkartw('w39', 39, '网络协议,TCP,四次挥手,FIN,半关闭,shutdown,RST,SO_LINGER,真实验证,动画演示',
    '抓包四次挥手(FIN → ACK → FIN → ACK,10 次都是 8 个包);半关闭后仍能收到 26 字节;close 时有未读数据发 RST 而不是 FIN;SHUT_RD 后对方再发数据被 RST;50 ms 延迟下 10 / 10 次同时关闭 FIN 交叉。',
    'close() 和 shutdown() 在线上到底有什么区别?为什么有时对方读到的是“连接被重置”而不是正常的结束?半关闭是怎么回事?这篇用抓包逐个验证:普通挥手、半关闭、带未读数据的 close()、SHUT_RD、同时关闭。',
    [('8 个包', '一次普通的 close 在握手之外的包数(10 次都一样)'), ('RST 而不是 FIN', '接收缓冲区里有没读的数据时 close() 发出的包;对方 recv 得到 ConnectionResetError'), ('10 / 10', '加了 50 ms 延迟后同时关闭时 FIN 交叉的次数')],
    [('四次挥手', '<p>每个方向各一次 FIN + ACK。服务端的 ACK 与 FIN 常常分开发,因为 FIN 要等应用调用 close()。</p>'),
     ('半关闭', '<p>shutdown(SHUT_WR) 只发 FIN,连接的另一个方向继续可用:客户端发完请求后仍然收到了服务端的 26 字节应答。</p>'),
     ('close 与 RST', '<p>close() 时接收缓冲区里有没读的数据,发的是 RST;SO_LINGER(开,0)也是 RST。对方看到的是连接被重置,数据可能丢失。</p>'),
     ('SHUT_RD', '<p>SHUT_RD 本身不发包,但之后对方发来的数据会被 RST。</p>'),
     ('同时关闭', '<p>两端同时 close() 时 FIN 交叉,状态走 FIN_WAIT_1 → CLOSING → TIME_WAIT。</p>')],
    steps,
    [ENV_W + '。全部在 lo0 上做;第五节的延迟由 netlab 在 lo0 的 9400~9499 端口注入,dummynet 会让同一个包被 tcpdump 抓到多次,已按 (源端口, 序号, 标志) 去重;netstat 的状态是在 close 之后 30 ms 取的快照',
     '没有验证:真实网络(en0)上的挥手;TIME_WAIT 的持续时间与影响(见下一篇之后);FIN 丢失后的重传;半关闭对负载均衡 / 代理的影响;不同系统对 SHUT_RD 之后到达的数据的处理'],
    '四次挥手')
