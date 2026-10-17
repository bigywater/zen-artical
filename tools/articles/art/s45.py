from lib import *
S = SS('s45')
steps = [
    step("同样 41 个 https 请求、并发 20,过 nginx(HTTPS + HTTP/2)访问日志统计:默认的 HTTP11DownloadHandler 用了 20 条连接(一条上最多 3 个请求),协议 HTTP/1.1,response.protocol = HTTP/1.1;换成 H2DownloadHandler(DOWNLOAD_HANDLERS = {'https': '…http2.H2DownloadHandler'},需要装 h2 库,本机装的 4.4.1)后只有 1 条连接,41 个请求(含 seed)全在上面多路复用,nginx 记录协议 HTTP/2.0,response.protocol = h2。两者都是 TLSv1.3,response.certificate 都能拿到。", t=tl(S(1)), mark=lidx(S(1), 'H2DownloadHandler'), done=lidx(S(1), '默认 HTTP11'), b=bars([['HTTP11 处理器 连接数', 20, '20 条连接'], ['H2 处理器 连接数', 1, '1 条连接']], 20, mark=[1], done=[0]), kv=KV([['HTTP11', '20 条连接,HTTP/1.1,protocol = HTTP/1.1'], ['H2DownloadHandler', '1 条连接,HTTP/2.0,protocol = h2'], ['依赖', 'h2 库(pip install h2)']], ['H2DownloadHandler'])),
    step("证书校验:DOWNLOAD_VERIFY_CERTIFICATES 默认是 False(不校验证书)——本机自签名证书的 nginx 默认就能连(callback status 200);设成 True 后同一个请求失败,errback 收到 DownloadFailedError,里面是 OpenSSL.SSL.Error “certificate verify failed”。", t=tl(S(2)), mark=lidx(S(2), 'DOWNLOAD_VERIFY_CERTIFICATES=True', '默认 = False'), done=lidx(S(2), '默认(不校验)'), kv=KV([['默认', 'DOWNLOAD_VERIFY_CERTIFICATES = False:不校验'], ['设成 True', '自签名证书 → DownloadFailedError(certificate verify failed)']], ['默认'])),
    step("HTTP/2 的最大并发流由服务器说了算:nginx http2_max_concurrent_streams = 128 时,Scrapy 想同时发 20 个,后端并发峰值 20、nginx 只有 1 条连接、40 个请求(每个 0.3 s)总耗时 0.66 s;把流上限改成 4,后端并发峰值降到 4、仍是 1 条连接,总耗时 3.12 s(≈ 40 × 0.3 ÷ 4);同样的流上限对 HTTP/1.1 处理器没有影响:20 条连接、后端峰值 20、0.67 s。H2 处理器尊重服务器的流数上限,多出来的请求在这条连接上排队。", t=tl(S(3)), mark=lidx(S(3), 'H2 + 流上限 4'), done=lidx(S(3), 'H2 + 流上限 128', 'HTTP11'), b=bars([['H2 + 流上限 128', 0.66, '0.66 s(峰值 20)'], ['H2 + 流上限 4', 3.12, '3.12 s(峰值 4)'], ['HTTP11 + 流上限 4', 0.67, '0.67 s(峰值 20)']], 3.12, mark=[1], done=[0, 2]), kv=KV([['流上限 128', '峰值 20,0.66 s'], ['流上限 4', '峰值 4,3.12 s'], ['HTTP/1.1 处理器', '不受流上限影响']], ['流上限 4'])),
    step("H2 处理器不支持代理:给 https 请求设 meta proxy,errback 立刻收到 NotImplementedError “_ScrapyH2Agent doesn't support proxies.”,根本没有尝试连接。需要代理时只能退回 HTTP/1.1 处理器。", t=tl(S(4)), mark=lidx(S(4), 'NotImplementedError'), kv=KV([['H2 + meta proxy', 'NotImplementedError:不支持代理'], ['替代', '代理场景用 HTTP/1.1 处理器']], ['H2 + meta proxy'])),
]
A = mkarts('s45', 45, 'Scrapy,HTTP/2,H2DownloadHandler,多路复用,TLS,真实验证,动画演示',
    '用 nginx(HTTPS + HTTP/2)实测 H2DownloadHandler:41 个请求只用 1 条连接(默认处理器 20 条),response.protocol = h2;DOWNLOAD_VERIFY_CERTIFICATES 默认 False,自签名证书能连、设 True 就失败;服务器的最大并发流 4 把总耗时从 0.66 s 拉到 3.12 s;不支持代理。',
    'Scrapy 能用 HTTP/2 吗?一条连接上多路复用是不是真的?并发流上限由谁决定?证书默认校验吗?这篇用 nginx 当 HTTPS + HTTP/2 服务器,看连接数、协议和耗时。',
    [('20 → 1', '同样 41 个 https 请求,HTTP/1.1 与 H2 处理器用的连接数'), ('3.12 s', 'nginx 最大并发流 4 时 40 个请求(各 0.3 s)的总耗时(流上限 128 时是 0.66 s)'), ('False', 'DOWNLOAD_VERIFY_CERTIFICATES 的默认值')],
    [('启用', '<p>把 <code>https</code> 映射到 <code>H2DownloadHandler</code> 并安装 <code>h2</code> 库;只支持 TLS 上的 HTTP/2。响应的 <code>protocol</code> 是 <code>h2</code>。</p>'),
     ('多路复用', '<p>同一主机的请求共用一条连接,以流的形式并发;并发流数受服务器上限(<code>http2_max_concurrent_streams</code>)约束,超出的排队。</p>'),
     ('证书', '<p><code>DOWNLOAD_VERIFY_CERTIFICATES</code> 默认关闭,不校验证书;打开后自签名证书会得到 <code>DownloadFailedError</code>。</p>'),
     ('限制', '<p>不支持代理(抛 <code>NotImplementedError</code>)。</p>')],
    steps,
    [ENV_Y + '(另装 h2 4.4.1;nginx 来自 Homebrew,监听 127.0.0.1,HTTPS + HTTP/2,反向代理到本机的 Python 后端;证书是 openssl 生成的 EC P-256 自签名证书)。连接数来自 nginx 访问日志里的连接序号',
     '没有验证:服务器推送(Scrapy 不支持);HTTP/2 下的流量控制窗口和大响应;连接断开后的重连;h2c(明文 HTTP/2);TLS 会话复用的收益(只比较了连接数,没有拆分握手耗时);真实网络上 H2 与 HTTP/1.1 的吞吐对比(本机后端太快,0.06 s 对 0.04 s 没有统计意义)'],
    'HTTP/2')
