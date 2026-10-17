from lib import *
import re, textwrap
S = SS('u142')
R = J('u142')
code = re.search(r"SERVER = r'''\n(.*?)\n'''", open(HERE / 'exp' / 'u142.py').read(), re.S).group(1)
code = textwrap.dedent(code)
rt = R['routes']; bad = R['bad']
steps = [
    step("一个只用标准库的 HTTP/1.1 服务端:每个连接一个线程,循环 { 读请求行 → 读头部到空行 → 按 Content-Length 读正文 → 路由 → 写响应 }。用 curl 访问各路由:GET / 得 200 OK \"hello, request #1\";GET /nope 得 404 Not Found;HEAD / 只有头没有正文;POST /echo -d payload 得 200 并原样回显 \"payload\";DELETE / 得 405 Method Not Allowed。", t=tl(S(1)), done=lidx(S(1), 'curl GET /  ', 'GET /nope', 'HEAD', 'POST /echo', 'DELETE'), kv=KV([['GET /', '200 + 正文'], ['/nope', '404'], ['HEAD', '只有头'], ['POST /echo', '回显请求正文'], ['DELETE', '405']], ['POST /echo'])),
    step("服务端按 curl 发来的请求头保存(键转小写):accept=*/*、host=127.0.0.1:<端口>、user-agent=curl/8.7.1。HTTP 头部名大小写不敏感,所以统一小写后再查找。", t=tl(S(2)), done=lidx(S(2), 'accept', 'host', 'user-agent'), kv=KV([['头部名', '转小写后存入 HashMap']], ['头部名'])),
    step("keep-alive:一条 curl 命令访问同一个服务端两次,详细输出里第二次显示「Re-using existing connection」,连接 #0 始终保持;两次响应分别是 \"request #7\"、\"request #8\"(服务端的计数器是连续的)。服务端在 HTTP/1.1 下默认保持连接,请求头里 Connection: close 才关闭。", t=tl(S(3)), done=lidx(S(3), 'Connected to', 'Re-using existing connection', 'request #'), kv=KV([['HTTP/1.1', '默认 keep-alive'], ['Connection: close', '响应后关闭']], ['HTTP/1.1'])),
    step("不合法的请求要得到 4xx 而不是崩溃:请求行只有两段 → 400 bad request line;头部没有冒号 → 400 bad header;Content-Length 不是数字 → 400 bad content-length;一个 9000 字节的头部 → 431 headers too large(限制了头部总大小 8 KiB);声明 Content-Length: 100 却只发 5 字节 → 等 2 秒读超时后 400 short body 并关闭连接。", t=tl(S(4)), done=lidx(S(4), '请求行只有两段', '头部没有冒号', 'Content-Length 不是数字', '头部超过 8 KiB', '声明 100'), kv=KV([['畸形请求行/头', '400'], ['头部过大', '431'], ['正文不完整', '读超时 → 400']], ['头部过大'])),
    step(f"并发:20 个 curl 同时请求,每个连接一个线程,请求序号 9 到 28 没有重复、没有缺失({R['conc'][0]} 个不同的值),累计 {R['conc'][1]} 个请求。计数器用原子整数,所以并发下不丢更新。", t=tl(S(5)), done=lidx(S(5), '20 个并发请求'), kv=KV([['20 个并发 curl', f'序号不重复({R["conc"][0]} 个不同值)']], ['20 个并发 curl'])),
]
A = mkart('u142', 142, 'Rust,HTTP,服务端,TCP,真实验证,动画演示',
    '用标准库的 TcpListener 写一个约 60 行的 HTTP/1.1 服务端并用 curl 验证:GET/HEAD/POST/DELETE 与 404、405;头部转小写;keep-alive 复用连接;畸形请求得 400/431;读超时;20 个并发请求计数不丢更新。',
    '一个 Web 框架最底层在做什么?这篇不用任何框架,只用 TcpListener 写出能被 curl 访问的 HTTP 服务端:读请求、解析头部、读正文、路由、响应、持久连接、错误处理、并发,每一步都用 curl 与原始 socket 验证。',
    [('约 60 行', '这个标准库 HTTP 服务端的代码量'), ('400 / 431 / 405 / 404', '服务端对畸形、过大、不支持的方法与未知路径的状态码'), ('Re-using', 'curl 对 keep-alive 连接的确认')],
    [('路由与响应', '<p>下面是服务端的完整代码(release 编译)。客户端侧的原始字节见<a href="rust-http-request-raw.html">HTTP 请求的底层实现</a>。</p>' + src('server.rs', code)), ('请求头', '<p>TCP 的基础见<a href="rust-tcp-listener-stream.html">TCP Listener 与 TcpStream</a>。</p>'), ('keep-alive', None), ('畸形请求', '<p>这只是演示,没有处理分块请求体、Expect: 100-continue、HTTP/1.0 的 keep-alive 等,不要当作生产服务端。</p>'), ('并发', '<p>异步版本见<a href="rust-tokio-tcp-echo.html">Tokio TCP Echo Server</a>。</p>')],
    steps, [ENV_U + '。curl 8.7.1;全部使用 127.0.0.1 与系统分配的端口', '没有验证:chunked 请求体、压缩、HTTPS、路径遍历等安全问题、慢速攻击(slowloris)、大文件的流式响应、线程数上限下的行为、与 hyper 等框架的性能对比'], 'HTTP 服务端')
