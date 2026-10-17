from lib import *
S = SS('w42')
steps = [
    step("RST 的第一种来源:连接没人监听的端口。应用得到 ConnectionRefusedError [Errno 61] Connection refused。线上 SYN 的序号是 2483746472,回来的是一个 ACK+RST,序号 0、确认号 2483746473 = SYN 序号 + 1(SYN 占一个序号)。规则:对一个没有连接的 SYN,RST 的序号取 0、确认号取 SYN 序号 + 1,发送方凭这个确认号相信这个 RST 是在回应它的 SYN。", t=tl(S(1)), mark=lidx(S(1), 'SYN:seq='), done=lidx(S(1), 'connect 一个没人监听的端口'), kv=KV([['SYN', '序号 = X'], ['RST', 'ACK+RST,序号 0,确认号 = X + 1'], ['应用', 'ConnectionRefusedError(errno 61)']], ['RST'])),
    step("连接已经不存在时再发数据:对端正常 close 了(发了 FIN,我方回了 ACK),我方不知道又发了 100 字节,对端的 TCP 回了 RST。应用依次看到:send #1 成功、send #2 BrokenPipeError [Errno 32]、send #3 BrokenPipeError、recv ConnectionResetError [Errno 54]。线上最后两个包:客户端 ACK+PSH 载荷 100 → 服务端 RST;RST 的序号 3977457150 正好等于触发它的数据包的确认号 3977457150。规则:对一个带 ACK 的段,RST 的序号取该段的确认号,这样落在发送方期望的序号上,发送方才会接受它。第一次 send 成功只是因为数据交给了内核,RST 要等往返之后才回来。", t=tl(S(2)), mark=lidx(S(2), '应用依次看到', 'RST 的序号'), done=lidx(S(2), '线上:'), b=bars([['send #1', 1, '成功'], ['send #2', 0, 'EPIPE'], ['send #3', 0, 'EPIPE'], ['recv', 0, 'ECONNRESET']], 1, mark=[1, 2, 3], done=[0]), kv=KV([['对端 FIN 后我方再发数据', '对端 TCP 回 RST'], ['RST 的序号', '= 数据包的确认号'], ['应用', 'send #1 成功 · 之后 EPIPE · recv ECONNRESET']], ['RST 的序号'])),
    step("RST 会丢数据吗?服务端先发 5 字节 hello,再用 SO_LINGER 0 中止连接(发 RST)。线上:服务端 ACK+PSH 载荷 5 → 客户端 ACK(确认号 6)→ 服务端 ACK+RST。客户端等 RST 到达之后再 recv:第一次拿到 b'hello',第二次才是 ConnectionResetError——在这台机器上,RST 之前已经到达接收缓冲区的数据没有被丢掉。对照:服务端发 hello 再正常 close(FIN),客户端依次得到 b'hello' 和 b''(EOF)。其它系统在收到 RST 时是否清空接收缓冲区,这里没有测。", t=tl(S(3)), mark=lidx(S(3), '服务端发了 hello 再中止', '对照:服务端发了 hello'), done=lidx(S(3), '线上:'), kv=KV([['hello + RST', 'recv #1 得到 b\'hello\',recv #2 ECONNRESET'], ['hello + FIN', 'recv #1 得到 b\'hello\',recv #2 得到 b\'\'(EOF)'], ['结论', '本机上 RST 前已到达的数据仍可读']], ['结论'])),
    step("应用侧的错误码一次列清:连接没人监听的端口 → connect ConnectionRefusedError [Errno 61];对端 RST 中止之后 → recv ConnectionResetError [Errno 54],send BrokenPipeError [Errno 32];对端 close 之后我方第二次 send → BrokenPipeError [Errno 32];SYN 无回应(我设了 2 秒超时)→ connect TimeoutError。含义:ECONNREFUSED 是对 SYN 回了 RST;ECONNRESET 是连接建立后收到 RST;EPIPE 是向已经收到 RST 或 FIN 的连接再写(默认还会给进程发 SIGPIPE,Python 屏蔽了它);超时是对方没有任何回应。", t=tl(S(4)), mark=lidx(S(4), '连接没人监听的端口', '对端 RST 中止后', '对端 close 后', 'SYN 无回应'), done=lidx(S(4), 'ECONNREFUSED ='), kv=KV([['ECONNREFUSED', 'connect 时对 SYN 回了 RST'], ['ECONNRESET', '连接建立后收到 RST'], ['EPIPE', '向已被 FIN / RST 的连接再写'], ['超时', '对方毫无回应']], ['EPIPE'])),
]
A = mkartw('w42', 42, '网络协议,TCP,RST,连接重置,ECONNRESET,EPIPE,真实验证,动画演示',
    'RST 的序号规则:对 SYN 回 ACK+RST(序号 0,确认号 = SYN 序号 + 1);对带 ACK 的数据段,RST 序号 = 该段的确认号;对端 FIN 后再发数据先成功一次、之后 EPIPE、recv 得 ECONNRESET;本机上 RST 之前到达的数据仍可读。',
    'RST 到底在什么时候出现?它的序号是怎么填的,应用侧看到的是 Connection refused、reset by peer 还是 Broken pipe?这篇抓真实的 RST 包验证填法,并把四种常见错误码对应到具体的场景。',
    [('seq = 对方的 ack', '对带 ACK 的段,RST 的序号取该段的确认号(实测相等);对 SYN 则序号 0、确认号 = SYN + 1'), ('send 成功 1 次', '对端 close 之后我方的第一次 send 仍会成功,第二次起 EPIPE:RST 要往返之后才回来'), ('b\'hello\' 然后 ECONNRESET', '服务端发 5 字节再 RST 中止时,客户端的两次 recv 的结果:数据没丢')],
    [('对 SYN 的 RST', '<p>连接没人监听的端口:ACK+RST,序号 0,确认号 = SYN 序号 + 1,应用得到 ECONNREFUSED。</p>'),
     ('对数据的 RST', '<p>连接已不存在时再发数据,对端回 RST,序号取该段的确认号;应用先成功一次 send,之后 EPIPE,recv 得 ECONNRESET。</p>'),
     ('RST 与数据', '<p>RST 之前已经到达的数据在这台机器上仍可读,RST 之后才是错误;而 FIN 之后是正常的 EOF。</p>'),
     ('错误码对照', '<p>ECONNREFUSED、ECONNRESET、EPIPE 分别对应对 SYN 的 RST、连接中的 RST、向已关闭的连接写;超时则是对方毫无回应。</p>')],
    steps,
    [ENV_W + '。全部在 lo0 上做,地址为 127.0.0.1;只有最后的“SYN 无回应”一项用了一个会丢弃 SYN 的公网地址(example.com 的 81 端口,2 秒超时);RST 的序号用抓包解析得到',
     '没有验证:RST 的窗口验证(收到序号落在窗口外的 RST 的行为需要注入包,没有权限);防火墙/NAT 主动发 RST 的情形;其它系统在收到 RST 时是否丢弃未读数据;SIGPIPE 的实际默认行为(Python 屏蔽了它)'],
    'TCP RST')
