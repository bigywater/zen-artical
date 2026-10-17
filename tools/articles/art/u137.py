from lib import *
import re
S = SS('u137')
R = J('u137'); nd = re.search(r'默认 (\d+) µs,set_nodelay\(true\) (\d+) µs', R['nodelay']); n0, n1 = nd.group(1), nd.group(2)
steps = [
    step("服务端 TcpListener::bind(\"127.0.0.1:0\") 让系统分配端口(端口号 > 1024),local_addr() 取回实际地址;accept() 返回每个连接的 TcpStream 和对端地址(这里是 127.0.0.1,回环地址)。最小回显服务:客户端发 \"hello\" 收到 \"hello\",发 \"世界\"(6 字节)收到 \"世界\"。", t=tl(S(1)), done=lidx(S(1), '监听地址', '客户端:发'), kv=KV([['bind(\"…:0\")', '系统分配端口'], ['accept', '返回 (TcpStream, 对端地址)']], ['bind(\"…:0\")'])),
    step("错误是 io::Error:连接一个没人监听的端口 → ConnectionRefused(os error 61);同一个地址再 bind 一次 → AddrInUse(os error 48);set_read_timeout(100 ms) 之后对没有数据的连接 read,约 100 ms 后得到 WouldBlock(超时在 Unix 上表现为 WouldBlock,不是 TimedOut)。", t=tl(S(2)), done=lidx(S(2), '连接一个没人监听', '同一个地址', '读超时'), kv=KV([['没人监听', 'ConnectionRefused / 61'], ['地址被占用', 'AddrInUse / 48'], ['读超时', 'WouldBlock']], ['读超时'])),
    step("TCP 是字节流,没有消息边界:发送端分 3 次 write 各 4 字节,接收端一次 read 就读到 12 字节 \"AAAABBBBCCCC\";再 read 得到 0 字节,表示对端关闭(EOF)。所以应用层要自己分帧(长度前缀、分隔符、读到 EOF)。", t=tl(S(3)), done=lidx(S(3), '一次 read 读到', '再 read'), kv=KV([['3 次 write', '接收端一次读到 12 字节'], ['read 返回 0', '对端关闭(EOF)']], ['3 次 write'])),
    step("半关闭 shutdown(Write):客户端发完 \"request body\"(12 字节)后 shutdown(Write),服务端的 read_to_end 读到 EOF 返回,回复「收到 12 字节」,结果 (12, None)。如果客户端不关闭写端,read_to_end 一直等,设了 400 ms 读超时后返回错误 WouldBlock,已读到的 12 字节仍留在 Vec 里:(12, Some(WouldBlock))。", t=tl(S(4)), done=lidx(S(4), '客户端 shutdown(Write)', '服务端结果'), mark=lidx(S(4), '客户端不关闭写端'), kv=KV([['shutdown(Write)', '服务端读到 EOF'], ['不关闭写端', '服务端等到超时']], ['shutdown(Write)'])),
    step(f"TCP_NODELAY:同一个连接上把一个 4 字节的请求分成两次 2 字节的 write,再等回复,2000 轮。默认(Nagle 算法开启)每轮往返 {n0} µs,set_nodelay(true) 后 {n1} µs。回环地址上差距不大;在真实网络上 Nagle 与延迟确认配合可能产生几十毫秒的停顿,本文没有复现。", t=tl(S(5)), done=lidx(S(5), '每轮往返'), b=bars([['默认', int(n0), f'{n0} µs'], ['set_nodelay(true)', int(n1), f'{n1} µs']], int(n0), cur=[0], done=[1]), kv=KV([['默认', f'{n0} µs'], ['nodelay', f'{n1} µs']], ['nodelay'])),
]
A = mkart('u137', 137, 'Rust,TCP,TcpListener,TcpStream,网络,真实验证,动画演示',
    f'用回环地址上的真实 TCP 验证 TcpListener 与 TcpStream:bind 端口 0、accept 与回显;ConnectionRefused(61)、AddrInUse(48)、读超时为 WouldBlock;字节流无消息边界(3 次 write 一次读到 12 字节);shutdown(Write) 与 read_to_end;set_nodelay 往返 {n0} → {n1} µs。',
    'std::net 的 TCP API 很小,但每个细节都值得验证:端口怎么分配、各种错误长什么样、为什么「一次 write 一次 read」不成立、半关闭是什么、NODELAY 影响多大。这篇用本机的回环地址把它们都跑一遍。',
    [('12 字节', '发送端 3 次 write 各 4 字节,接收端一次 read 读到的字节数'), ('61 / 48', 'ConnectionRefused 与 AddrInUse 的 OS 错误码(macOS)'), (f'{n0} → {n1} µs', '默认与 TCP_NODELAY 的小请求往返时间')],
    [('listener 与 stream', '<p>非阻塞与多路复用见<a href="rust-nonblocking-io.html">非阻塞 IO</a>;异步版本见<a href="rust-tokio-tcp-echo.html">Tokio TCP Echo Server</a>。</p>'), ('各种错误', None), ('字节流', '<p>HTTP 如何在字节流上分帧见<a href="rust-http-request-raw.html">HTTP 请求的底层实现</a>。</p>'), ('半关闭', None), ('NODELAY', '<p>只在本机回环地址上测量,绝对数值和真实网络无关。</p>')],
    steps, [ENV_U + '。全部使用 127.0.0.1 与系统分配的临时端口', '没有验证:跨主机的网络行为、Nagle 与延迟确认的真实停顿、SO_REUSEADDR 与 TIME_WAIT(没有单独验证)、IPv6、连接队列 backlog、keepalive、被 RST 重置时的错误'], 'TCP')
