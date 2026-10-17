from lib import *
S = SS('w54')
steps = [
    step("先看延迟 ACK。本机 net.inet.tcp.delayed_ack = 3(自适应模式;sendmoreacks 这个参数在这台机器上不存在)。客户端发一个孤立的 100 字节小包、服务端不回数据,量服务端什么时候发纯 ACK:10 次全部在 0.0~0.1 ms 内,没有任何等待。再用 TCP_NODELAY 连续发两个小包,10 轮共抓到 20 个数据段、19 个纯 ACK——几乎每个包一个 ACK,没有看到“两个包合并成一个 ACK”。也就是说,这台机器在回环上并没有表现出传统意义上的“延迟 ACK”,经典的“等 40~200 ms 再回”没有出现。", t=tl(S(1)), mark=lidx(S(1), '一个孤立的小包之后', '对照:连续发 2 个小包'), done=lidx(S(1), 'delayed_ack: 3'), kv=KV([['delayed_ack', '3(自适应)'], ['孤立小包的 ACK', '约 0.1 ms,立刻回'], ['连发 2 个小包', '20 个数据段 / 19 个纯 ACK']], ['孤立小包的 ACK'])),
    step("Nagle 与延迟 ACK 的经典冲突:一个请求分两次 write(10 字节 + 10 字节),服务端凑齐 20 字节才应答。各 30 次,请求到应答的延迟:Nagle 开、一次 write 20 字节,中位 0.22 ms;Nagle 开、分两次 write,中位 0.22 ms;TCP_NODELAY、分两次 write,中位 0.20 ms。三者没有差别,没有复现经典的 40 ms 级停顿。原因就是上一节:回环上 ACK 立刻就回,Nagle 不需要等。这里测到的只是“在回环上没复现”,不是“Nagle 与延迟 ACK 的冲突不存在”。", t=tl(S(2)), mark=lidx(S(2), 'Nagle 开(默认),分两次 write'), done=lidx(S(2), '一次 write 20 字节', 'TCP_NODELAY,分两次 write'), b=bars([['Nagle 一次 write', 0.22, '0.22 ms'], ['Nagle 分两次', 0.22, '0.22 ms'], ['NODELAY 分两次', 0.20, '0.20 ms']], 0.3, mark=[1], done=[0, 2]), kv=KV([['三种写法', '中位都在 0.2 ms 左右'], ['40 ms 停顿', '没有复现'], ['原因', '回环上 ACK 立刻回(推测,见上一节)']], ['40 ms 停顿'])),
    step("抓一次“Nagle 开 + 分两次 write”的时间线:第一个 10 字节在 +0.00 ms 发出;服务端纯 ACK 在 +0.05 ms;第二个 10 字节在 +0.08 ms 才发出——它是在第一个包的 ACK 回来之后发的,这就是 Nagle 的行为(有未确认的小包时新数据先攒着),只是回环上 ACK 几十微秒就到,等待小到看不出来;服务端应答在 +0.11 ms,客户端 ACK 在 +0.13 ms;从第一个 write 到收到应答一共 0.17 ms。", t=tl(S(3)), mark=lidx(S(3), '第二个 write 的 10 字节'), done=lidx(S(3), '从第一个 write 到收到应答'), kv=KV([['第一个包', '+0.00 ms'], ['它的 ACK', '+0.05 ms'], ['第二个包', '+0.08 ms(ACK 之后)'], ['总共', '0.17 ms']], ['第二个包'])),
    step("换到真实网络:往 example.com:80 发 HTTP 请求,分成两次 write(请求行和 Host 一次,Connection 头和空行一次),服务器要收到完整请求才响应。握手耗时(约一个 RTT)中位 192 ms。Nagle 开(默认)时,第一次 write 到响应第一批字节,8 次有效,中位 403 ms(最小 377 / 最大 514);TCP_NODELAY 时 8 次有效,中位 201 ms(最小 189 / 最大 320)。差值中位 202 ms,约 1.0 个握手耗时:第二次 write 被 Nagle 扣着,等第一个包的 ACK 回来才发,请求整体推迟了一个 RTT。这里不涉及服务器的延迟 ACK,只是 Nagle 自己的代价。", t=tl(S(4)), mark=lidx(S(4), 'Nagle 开(默认):8 次', '两者之差'), done=lidx(S(4), '握手耗时', 'TCP_NODELAY:8 次'), b=bars([['Nagle 开(默认)', 403, '403 ms'], ['TCP_NODELAY', 201, '201 ms']], 403, mark=[0], done=[1]), kv=KV([['握手耗时(≈RTT)', '192 ms'], ['Nagle 开', '403 ms'], ['TCP_NODELAY', '201 ms'], ['差', '202 ms ≈ 1 个 RTT']], ['差'])),
    step("看本机在真实网卡 en0 上怎么回 ACK:抓一次对 example.com 的 HTTP 请求,服务器一共只发来 2 个数据包,其中 1 个找到了本机对应的纯 ACK:5 字节的数据包,0.1 ms 后就回了。样本只有这一个,另一个数据包没有配对到纯 ACK(原因没有查)。结论只能是“这一次没看到延迟”,不能据此说 en0 上本机从不延迟 ACK。", t=tl(S(5)), mark=lidx(S(5), '服务器发来 2 个数据包'), done=lidx(S(5), '服务器发来 2 个数据包'), kv=KV([['数据包', '2 个'], ['配对到纯 ACK', '1 个(5 字节 → 0.1 ms)'], ['样本', '太小,只作旁证']], ['样本'])),
    step("Nagle 对大量小写入:连续 write 20000 次 100 字节(共 2,000,000 字节)。Nagle 开:用时 0.04 秒,线上数据段 908 个,平均每段 2203 字节,纯 ACK 908 个;TCP_NODELAY:用时 0.11 秒,线上数据段 20000 个,每段 100 字节,纯 ACK 8813 个。Nagle 把小写入合并成大段,包数少了 95%;代价是交互式小消息可能被推迟。这一节的用时是回环上的 Python 循环,只看相对大小。", t=tl(S(6)), mark=lidx(S(6), 'Nagle 开(默认):20000', 'TCP_NODELAY:20000'), done=lidx(S(6), 'Nagle 把小写入'), b=bars([['Nagle 数据段', 908, '908 个'], ['NODELAY 数据段', 20000, '20000 个']], 20000, mark=[1], done=[0]), kv=KV([['Nagle 开', '908 段 · 平均 2203 字节'], ['TCP_NODELAY', '20000 段 · 100 字节'], ['用时', '0.04 秒 vs 0.11 秒']], ['Nagle 开'])),
]
A = mkartw('w54', 54, '网络协议,TCP,Nagle,延迟ACK,TCP_NODELAY,真实验证,动画演示',
    '实测 Nagle 与延迟 ACK:本机 delayed_ack=3,回环上孤立小包 0.1 ms 就回 ACK,经典 40 ms 冲突没复现;但对 example.com 把 HTTP 请求分两次 write,Nagle 开 403 ms 对 TCP_NODELAY 201 ms,差约一个 RTT;2 万次 100 字节小写入 Nagle 合并成 908 段,NODELAY 是 20000 段。',
    'Nagle 算法和延迟 ACK 单独看都合理,放在一起据说会产生几十毫秒的停顿。这篇在本机上实测:延迟 ACK 到底延不延迟、经典冲突能不能复现、真实网络上 Nagle 的代价是多少、它又省下了多少包。有一半的结论是“没复现”,我会如实写。',
    [('0.22 vs 0.20 ms', '回环上 Nagle 开分两次 write 与 TCP_NODELAY 的请求到应答延迟中位数(没有差别)'), ('403 → 201 ms', '对 example.com 分两次 write 发 HTTP 请求,Nagle 开与 TCP_NODELAY 的首字节时间,差约一个 RTT'), ('908 vs 20000', '2 万次 100 字节小写入后线上的数据段个数')],
    [('延迟 ACK', '<p>接收方不一定马上回 ACK,可以等一等好捎带数据或合并。macOS 的 <code>net.inet.tcp.delayed_ack</code> 是 3(自适应)。实测回环上孤立小包 0.1 ms 就被确认。</p>'),
     ('经典冲突没有复现', '<p>Nagle 要等 ACK,ACK 又被延迟,就会停顿。本机回环上三种写法都是 0.2 ms 左右,没有 40 ms 级的停顿——这是“没复现”,不是“不存在”。</p>'),
     ('Nagle 的时间线', '<p>第二个小写入是在第一个包的 ACK 回来之后才发出的,这就是 Nagle;回环上 ACK 几十微秒就到。</p>'),
     ('真实网络的代价', '<p>对 example.com 把请求分两次 write,Nagle 开时第二次 write 要等一个 RTT,首字节时间从 201 ms 变成 403 ms。</p>'),
     ('en0 上的 ACK', '<p>只抓到一个可配对的数据包,0.1 ms 回 ACK,样本太小,仅作旁证。</p>'),
     ('Nagle 的好处', '<p>2 万次 100 字节小写入,Nagle 合并成 908 个数据段,TCP_NODELAY 则是 20000 个,每段 100 字节。</p>')],
    steps,
    [ENV_W + '。第一至三节、第六节在 lo0 上用 Python 套接字加 tcpdump,第四、五节对 example.com:80 和 en0;第四节各 8 次,握手耗时当作 RTT 的近似;用时只看相对大小',
     '没有验证:延迟 ACK 在 delayed_ack 取 0、1、2 时的行为(没有改 sysctl);服务器端(Linux)延迟 ACK 与 Nagle 的 40 ms 冲突;TCP_NOPUSH 在本篇没有涉及;en0 上本机延迟 ACK 的完整分布;Nagle 在拥塞或丢包时的行为'],
    'Nagle 与延迟 ACK')
