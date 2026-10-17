from lib import *
S = SS('w55')
steps = [
    step("先看选项本身。新连接上 TCP_NODELAY 默认是 0(客户端、服务端 accept 出来的都是 0);客户端 setsockopt 成 1 之后读回的不是 1 而是 4(macOS 读回内部标志位的值,非 0 就是已开启);在监听套接字上先设,accept 出来的连接读回也是 4,即继承。Python 的 socket 模块在这台机器上没有 TCP_CORK(Linux 的名字)、没有 TCP_NOPUSH、没有 MSG_MORE;TCP_NOPUSH 的值是 4,默认读回 0,设成 1 后读回 4096——同样是内部标志位,不是 1。", t=tl(S(1)), mark=lidx(S(1), '读回 = 4', '设成 1 后读回 4096'), done=lidx(S(1), '(客户端)', '有 TCP_CORK'), kv=KV([['TCP_NODELAY 默认', '0'], ['开启后读回', '4(不是 1)'], ['监听套接字上设置', 'accept 出来的连接继承'], ['TCP_CORK / MSG_MORE', 'socket 模块里没有'], ['TCP_NOPUSH', '值 4,开启后读回 4096']], ['开启后读回'])),
    step("同样 200 条消息,每条是 5 字节头 + 100 字节体,间隔 1 ms。先 write 头再 write 体:Nagle 开线上数据段 400 个,TCP_NODELAY 也是 400 个;拼成一个缓冲区一次 send:两种模式都是 200 个;sendmsg([头, 体]) 一次发出(writev 的做法):两种模式也都是 200 个。分两次 write 的写法在回环上不论 Nagle 开不开都是一条消息两个包——第一个包的 ACK 几十微秒就回来,Nagle 没来得及把第二次 write 合并进去。要少包,办法是应用层一次交给内核。", t=tl(S(2)), mark=lidx(S(2), '先 write 头、再 write 体'), done=lidx(S(2), '拼成一个缓冲区一次 send', 'sendmsg'), b=bars([['两次 write', 400, '400 段'], ['拼接一次 send', 200, '200 段'], ['sendmsg 一次', 200, '200 段']], 400, mark=[0], done=[1, 2]), kv=KV([['两次 write', '400 段,Nagle 开关一样'], ['一次 send / sendmsg', '200 段'], ['要点', '合并要由应用在一次系统调用里完成']], ['要点'])),
    step("TCP_NOPUSH(BSD 版的“软木塞”)的行为,两种模式(Nagle 开、TCP_NODELAY)结果一样。开着 NOPUSH 写 3×100 字节:0.5 秒后线上 0 个数据段、接收方读到 0 字节——数据被攒着。清除 NOPUSH 后再等 0.5 秒:线上仍然 0 个数据段、接收方仍然 0 字节——在这台机器上,清除选项并没有把攒着的数据冲出去。再写 1 字节后:线上出现 1 个数据段、载荷 301 字节,即攒着的 300 字节连同新的 1 字节一起发出。随后 shutdown(SHUT_WR) 没有再多出数据段。所以在 macOS 上用 NOPUSH 做“软木塞”,拔塞之后要再发一次数据才会冲出去,这与 Linux TCP_CORK 清除时立即发送的描述不一样(Linux 这里没有验证,只是文档说法)。", t=tl(S(3)), mark=lidx(S(3), '清除 NOPUSH 后 0.5 秒', '再写 1 字节后 0.5 秒'), done=lidx(S(3), '写 3×100 字节', '各数据段载荷'), b=bars([['NOPUSH 开,写 300 字节后', 0, '0 段'], ['清除 NOPUSH 后', 0, '0 段'], ['再写 1 字节后', 1, '1 段 / 301 字节']], 1, mark=[1], done=[0, 2]), kv=KV([['开 NOPUSH 写 300 字节', '0.5 秒后仍无数据发出'], ['清除 NOPUSH', '数据仍未发出'], ['再写 1 字节', '301 字节一个段发出']], ['清除 NOPUSH'])),
    step("NOPUSH 开着一次写 40000 字节(lo0 的 MSS 是 16344,数据段载荷 16332):接收方 1.5 秒内读到 32664 字节,线上正好是两个 16332 字节的满段;剩下的 7336 字节零头没有发出。清除 NOPUSH 后再等 0.5 秒,接收方也没有读到这 7336 字节——和上一节一致,拔塞本身不发送。结论:NOPUSH 开着时,攒满一个 MSS 的数据会照常发出,只有不满一个 MSS 的尾巴被扣住;macOS 上要在拔塞之后再触发一次发送才能把尾巴冲出去(这里只验证了“再写一次数据”能冲出去,是上一节的结果)。", t=tl(S(4)), mark=lidx(S(4), '零头没有发出', '清除 NOPUSH 后 0.5 秒'), done=lidx(S(4), '接收方在 1.5 秒内读到'), b=bars([['发出的满段', 32664, '2 段 / 32664 字节'], ['被扣住的零头', 7336, '7336 字节']], 32664, mark=[1], done=[0]), kv=KV([['写入', '40000 字节'], ['发出', '2 个满段 = 32664 字节'], ['扣住', '7336 字节,拔塞后仍未发出']], ['扣住'])),
]
A = mkartw('w55', 55, '网络协议,TCP,TCP_NODELAY,TCP_NOPUSH,TCP_CORK,sendmsg,小包合并,真实验证,动画演示',
    '实测 macOS 上 TCP_NODELAY 与 TCP_NOPUSH:读回值是内部标志(4 与 4096)而非 1;分两次 write 的消息 400 个段,拼接或 sendmsg 一次发只要 200 个;NOPUSH 开着 300 字节一个段都不发,拔塞后也不发,要再写 1 字节才以 301 字节一个段冲出。',
    '想减少小包有三条路:TCP_NODELAY 让小包马上发、Nagle 帮你合并、或者像 Linux 的 TCP_CORK 那样先塞住再一起发。这篇在 macOS 上把这些手段逐个实测:选项读回是什么、分两次 write 到底能不能被合并、NOPUSH 这个软木塞到底在什么时候放气。',
    [('400 vs 200', '200 条消息分两次 write 与一次 sendmsg 在线上的数据段个数'), ('0 → 301 字节', 'NOPUSH 拔塞后仍无数据发出,再写 1 字节才以一个段发出'), ('4 与 4096', 'TCP_NODELAY、TCP_NOPUSH 开启后 getsockopt 读回的值,都不是 1')],
    [('选项与读回', '<p>TCP_NODELAY 默认关;macOS 读回的不是 1 而是标志位值 4,监听套接字上设置会被 accept 的连接继承。Python 的 socket 模块这里没有 TCP_CORK 和 MSG_MORE。</p>'),
     ('合并要靠应用', '<p>头和体分两次 write,不论 Nagle 开还是 TCP_NODELAY,回环上每条消息都是两个包。拼成一个缓冲区或用 sendmsg 一次交给内核,才是一条消息一个包。</p>'),
     ('NOPUSH 的拔塞', '<p>开着 NOPUSH,小数据一个包都不发;在这台 macOS 上清除选项并不会把攒着的数据冲出去,下一次写入才会连同新数据一起发出。</p>'),
     ('满段照发', '<p>NOPUSH 开着写 40000 字节,满 MSS 的两个段正常发出,只有 7336 字节的尾巴被扣住。</p>')],
    steps,
    [ENV_W + '。全部在 lo0 上,Python 套接字加 tcpdump;分两次 write 的对照只测了 Nagle 开 / TCP_NODELAY 两种,每条消息间隔 1 ms',
     '没有验证:Linux 的 TCP_CORK 与 MSG_MORE(本机没有);NOPUSH 在 en0 真实网络上的行为;NOPUSH 在没有后续写入时是否有超时自动发出(只等了 0.5 秒);writev 与 sendmsg 在内核里的差别;FreeBSD 与 macOS 在清除 NOPUSH 时是否冲出数据的差异原因'],
    'NODELAY 与 NOPUSH')
