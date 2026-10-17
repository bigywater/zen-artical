from lib import *
S = SS('w56')
steps = [
    step("系统默认值:net.inet.tcp.keepidle = 7200000(毫秒,即 2 小时)、keepintvl = 75000(75 秒)、keepcnt = 8、always_keepalive = 0。也就是说,打开 SO_KEEPALIVE 之后,一条空闲连接要等 2 小时才发第一个探测,之后每 75 秒一个,连续 8 个都没有回应才判死。对端消失后最长要 7200 + 75 × 8 = 7800 秒(2.17 小时)才会报错——这是按默认值算出来的公式结果,不是实测;实测在第四节用缩短的参数做。", t=tl(S(1)), mark=lidx(S(1), '按默认值,一条空闲连接', '单位:keepidle'), done=lidx(S(1), 'keepidle: 7200000', 'keepintvl: 75000', 'keepcnt: 8'), kv=KV([['keepidle', '7200 秒(2 小时)'], ['keepintvl', '75 秒'], ['keepcnt', '8 次'], ['最长发现时间', '7800 秒(公式)']], ['最长发现时间'])),
    step("每个套接字自己的选项:新连接上 SO_KEEPALIVE 读回 0(关);Python 在这台机器上有 TCP_KEEPALIVE(值 16,单位秒的空闲时间)、TCP_KEEPINTVL(257)、TCP_KEEPCNT(258),没有 Linux 的名字 TCP_KEEPIDLE。没设置时读回的是系统默认:7200 / 75 / 8。设成 idle=2、intvl=1、cnt=3 之后,TCP_KEEPALIVE=2、TCP_KEEPINTVL=1、TCP_KEEPCNT=3;SO_KEEPALIVE 打开后读回 8(内部标志位,不是 1)。", t=tl(S(2)), mark=lidx(S(2), '设成 (idle=2', '新连接上 SO_KEEPALIVE'), done=lidx(S(2), '不设置时读回', 'socket 模块的常量'), kv=KV([['SO_KEEPALIVE', '默认 0,开启后读回 8'], ['TCP_KEEPALIVE', '空闲秒数(Linux 叫 TCP_KEEPIDLE)'], ['TCP_KEEPINTVL / KEEPCNT', '间隔、最多几次'], ['不设置', '读回系统默认 7200 / 75 / 8']], ['TCP_KEEPALIVE'])),
    step("探测包长什么样(对端活着,idle=2、intvl=1、cnt=3,空闲 9 秒):线上 8 个包,即 4 个探测加 4 个回应。探测包载荷是 0 字节,标志只有 ACK(0x10),序号是“对端期望的下一个序号减 1”(例如探测的 seq = 10576,对端回的 ack = 10577),这是一个故意过期的序号,逼对端回一个 ACK;回应也是纯 ACK。对端一直在回应时,探测间隔是 2.0 s、2.0 s、2.0 s,即每个 idle 周期一个,不会变成 intvl 的 1 秒——intvl 只用于“上一个探测没有回应”时的重发。", t=tl(S(3)), mark=lidx(S(3), '探测包个数 4'), done=lidx(S(3), '9 秒内线上共 8 个包'), kv=KV([['探测包', '0 字节载荷,仅 ACK'], ['探测序号', '= 对端 ack − 1(过期序号)'], ['对端活着', '每 idle(2 s)一个,回应纯 ACK'], ['intvl', '只用于无回应时的重发(此处未触发)']], ['探测序号'])),
    step("对端“消失”时的判死:真正的黑洞在 lo0 上造不出来(netlab 丢包上限 50%),这里用每个方向丢 50% 的链路代替,只用来看“连续 cnt 次探测都没有得到回应就断开”的规则。30 条连接都设 idle=2、intvl=1、cnt=3,空闲 25 秒:30 / 30 条被内核判死,recv 的错误都是 ETIMEDOUT(Operation timed out);判死时间最短 5.0 秒,中位 7.5 秒,最长 22.0 秒。最短值正好等于下限 idle + intvl × cnt = 2 + 1 × 3 = 5 秒;中位和最长更晚,是因为丢包下有的探测偶尔得到了回应,计数被清零重来。真实黑洞下的时间没有测。", t=tl(S(4)), mark=lidx(S(4), '判死的时间', '25 秒内被内核判死'), done=lidx(S(4), '规则下限'), b=bars([['最短', 5.0, '5.0 s'], ['中位', 7.5, '7.5 s'], ['最长', 22.0, '22.0 s']], 22, mark=[0], done=[1, 2]), kv=KV([['判死', '30 / 30 条,ETIMEDOUT'], ['下限', 'idle + intvl × cnt = 5 秒'], ['实测最短', '5.0 秒'], ['注意', '50% 丢包是替身,不是黑洞']], ['实测最短'])),
    step("真实网络上的探测:本机连 example.com:80,握手后什么都不发,idle=2、intvl=1、cnt=3。握手之后本机发出 3 个探测、服务器回 3 个包:探测在 +2.00 s、+4.23 s、+6.46 s,回应在 +2.23 s、+4.46 s、+6.69 s,延迟 227 / 226 / 230 ms(就是这条路径的往返时间)。相邻探测的间隔是 2.23 s 而不是 2.00 s:下一个 idle 周期是从收到上一个回应时才开始数的。服务器(公网)会回应 keepalive 探测。", t=tl(S(5)), mark=lidx(S(5), '握手之后(第 1 秒起)', '探测到回应的延迟'), done=lidx(S(5), '+  2.00 s', '+  2.23 s'), b=bars([['第 1 次回应', 227, '227 ms'], ['第 2 次回应', 226, '226 ms'], ['第 3 次回应', 230, '230 ms']], 230, mark=[], done=[0, 1, 2]), kv=KV([['探测', '+2.00 / +4.23 / +6.46 s'], ['回应延迟', '约 227 ms'], ['探测间隔', '2.23 s = idle + 一个 RTT']], ['探测间隔'])),
]
A = mkartw('w56', 56, '网络协议,TCP,keepalive,SO_KEEPALIVE,TCP_KEEPALIVE,死连接检测,真实验证,动画演示',
    '实测 TCP keepalive:macOS 默认 2 小时才探测(最长 7800 秒才判死,公式);探测包是 0 字节、序号减 1 的纯 ACK;idle=2、intvl=1、cnt=3 的连接在 50% 丢包下最短 5.0 秒判死(ETIMEDOUT);对 example.com 的探测 3 个 3 个回应。',
    'TCP 连接空闲时不会自己发现对端已经没了。keepalive 就是内核替你定期问一句“你还在吗”。这篇在 macOS 上看默认参数有多保守、探测包长什么样、连续几次没回应才判死、公网服务器会不会回应探测。其中“对端真的消失”这一步造不出真黑洞,我用 50% 丢包替代,并会写明。',
    [('7800 s', '按默认值(2 小时空闲 + 75 s × 8 次)对端消失后最长发现时间(公式)'), ('5.0 s', '30 条 idle=2、intvl=1、cnt=3 的连接在 50% 丢包下最短判死时间,等于 idle + intvl × cnt'), ('227 ms', '对 example.com 的 keepalive 探测到回应的延迟')],
    [('默认值', '<p>keepalive 默认关闭;打开后空闲 7200 秒才探测、间隔 75 秒、8 次判死。这三个参数可以用 TCP_KEEPALIVE、TCP_KEEPINTVL、TCP_KEEPCNT 针对单个套接字修改。</p>'),
     ('套接字选项', '<p>macOS 的名字是 TCP_KEEPALIVE(相当于 Linux 的 TCP_KEEPIDLE);SO_KEEPALIVE 读回的是内部标志位 8,不是 1。</p>'),
     ('探测包', '<p>0 字节载荷的纯 ACK,序号比对端期望的小 1,对端回一个纯 ACK。对端一直回应时,探测每个 idle 周期一个。</p>'),
     ('判死规则', '<p>连续 cnt 次没有回应才断开,recv 得到 ETIMEDOUT;最短时间等于 idle + intvl × cnt。注意本篇用 50% 丢包代替黑洞。</p>'),
     ('公网路径', '<p>example.com 会回应探测;下一个探测周期是从收到回应开始数的,所以间隔是 idle 加一个 RTT。</p>')],
    steps,
    [ENV_W + '。第二、三、四节在 lo0 上,第四节用 netlab 丢包 50% 代替真正的黑洞(netlab 丢包上限 50%);第五节对 example.com:80 的 en0;参数都缩短为 idle=2、intvl=1、cnt=3 以便观察',
     '没有验证:真正黑洞下(100% 丢包)的判死时间;默认参数下的实际等待(2 小时);always_keepalive 的作用;对端重启(收到 RST)时的行为;应用层心跳与 keepalive 的比较;NAT 超时对 keepalive 间隔的影响;最后一个探测之后内核发 RST 的细节(没有在正式输出里统计)'],
    'keepalive')
