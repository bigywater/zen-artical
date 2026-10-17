from lib import *
import re
S = SS('u140')
R = J('u140'); kp = re.search(r'复用连接 (\d+) µs,每次新建连接 (\d+) µs', R['keep']); k1, k2 = kp.group(1), kp.group(2)
steps = [
    step("HTTP/1.1 请求就是几行文本:\"GET /hello HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\nConnection: close\\r\\n\\r\\n\"(59 字节),用 TcpStream 写出去,发给本机一个独立实现的服务端(Python http.server)。响应共 188 字节:状态行 HTTP/1.1 200 OK,一组头部,一个空行(\\r\\n\\r\\n),然后正文。", t=tl(S(1)), done=lidx(S(1), '请求(', 'HTTP/1.1 200 OK', 'Content-Length: 13'), kv=KV([['请求', '请求行 + 头部 + 空行'], ['响应', '状态行 + 头部 + 空行 + 正文']], ['响应'])),
    step("解析响应:状态行 \"HTTP/1.1 200 OK\" 拆成版本、状态码 200、原因短语 \"OK\";头部共 6 个,键按小写比较(大小写不敏感);同名头可以重复(X-Demo 出现两次,值 a、b);Content-Length = 13 是字节数 —— \"hello 世界\\n\" 里每个汉字 3 字节,共 13 字节。", t=tl(S(2)), done=lidx(S(2), '状态行', '头部(键转小写)', 'Content-Length = 13', '同名头'), kv=KV([['头部名', '大小写不敏感'], ['同名头', '可以重复'], ['Content-Length', '字节数,不是字符数']], ['Content-Length'])),
    step("正文有三种结束方式。没有 Content-Length 且 Connection: close:/close 的响应头里没有 Content-Length,正文靠读到连接关闭(EOF)才知道结束。", t=tl(S(3)), done=lidx(S(3), '/close'), kv=KV([['有 Content-Length', '读指定字节数'], ['没有 + Connection: close', '读到 EOF']], ['没有 + Connection: close'])),
    step("分块传输 Transfer-Encoding: chunked:原始正文是 \"6\\r\\nfirst-\\r\\n7\\r\\nsecond-\\r\\n5\\r\\nthird\\r\\n0\\r\\n\\r\\n\" —— 每块是「十六进制长度、\\r\\n、数据、\\r\\n」,长度 0 结束。手写的十几行解码得到 \"first-second-third\"。", t=tl(S(3)), done=lidx(S(3), '/chunked 的原始正文', '手写分块解码'), kv=KV([['每块', '十六进制长度 + 数据'], ['结束', '长度 0']], ['结束'])),
    step(f"Keep-Alive:HTTP/1.1 默认持久连接,同一个 TCP 连接上连续发两个请求都得到 200 OK,本地端口没变。500 个请求,复用连接平均每个 {k1} µs,每次新建连接平均 {k2} µs(回环地址上三次握手很快,真实网络上差距更大)。", t=tl(S(4)), done=lidx(S(4), '同一连接上的第 1', '同一连接上的第 2', '500 个请求'), b=bars([['复用连接', int(k1), f'{k1} µs'], ['每次新连接', int(k2), f'{k2} µs']], int(k2), cur=[1], done=[0]), kv=KV([['复用连接', f'{k1} µs / 请求'], ['新建连接', f'{k2} µs / 请求']], ['复用连接'])),
    step("与 curl 对照:curl -i 访问 /redirect 得到 HTTP/1.1 302 Found、Location: /hello、Content-Length: 0,不会自动跟随;加 -L 才跟随,得到正文 \"hello 世界\"。curl 默认还会加 User-Agent: curl/8.7.1 和 Accept: */*;而我们手写的最小请求,服务端只看到 Host 和 Connection 两个头。HTTP 客户端的「魔法」就是自动加头、解析响应、处理重定向与分块。", t=tl(S(5)), done=lidx(S(5), 'curl -i /redirect', 'curl -L', '服务端看到的请求头', '最小请求'), kv=KV([['302', 'curl 默认不跟随,-L 才跟随'], ['curl 请求头', 'Host + User-Agent + Accept'], ['手写最小请求', 'Host + Connection']], ['302'])),
]
A = mkart('u140', 140, 'Rust,HTTP,TCP,协议,真实验证,动画演示',
    f'用 TcpStream 手写 HTTP/1.1 对独立实现的服务端(Python http.server)和 curl 验证:请求与响应的原始字节、状态行与头部解析(Content-Length 是字节数、同名头可重复)、无长度时读到 EOF、chunked 分块的原始格式与手写解码、Keep-Alive 复用连接 {k1} 对 {k2} µs/请求、302 与 curl -L。',
    'HTTP 客户端库替你做了哪些事?这篇不用任何 HTTP 库:自己拼请求文本、自己解析响应头、自己处理 Content-Length、EOF 与 chunked 三种正文结束方式,再和 curl 对照。',
    [('188 字节', '最小的 GET /hello 请求得到的原始响应字节数'), ('13', '"hello 世界\\n" 的 Content-Length(字节数,汉字各占 3 字节)'), (f'{k1} 对 {k2} µs', '复用连接与每次新建连接的平均请求耗时')],
    [('请求与响应是文本', '<p>TCP 的基础见<a href="rust-tcp-listener-stream.html">TCP Listener 与 TcpStream</a>。服务端用 Python 3 自带的 http.server(独立实现,方便对照),监听本机系统分配的端口。</p>'), ('解析响应', None), ('正文怎么结束(含分块解码)', None), ('持久连接', '<p>耗时是本机回环地址的结果。从 Socket 到完整 HTTP 服务端见<a href="rust-http-server-from-socket.html">HTTP Server 从 Socket 到 Response</a>。</p>'), ('curl 与重定向', None)],
    steps, [ENV_U + '。curl 8.7.1;服务端 Python http.server', '没有验证:HTTPS/TLS、HTTP/2 与 HTTP/3、请求体与 POST(Content-Length 与 chunked 的上传)、压缩 Content-Encoding、超大头部、响应拆分与安全问题、reqwest/hyper 等库的行为'], 'HTTP 请求')
