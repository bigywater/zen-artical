from lib import *
S = SS('s28')
steps = [
    step("meta['proxy'] 指定代理:http 请求经代理时请求行变成绝对 URI——代理收到 GET http://127.0.0.1:端口/a HTTP/1.1,Host 头仍是源站;源站没有直接收到任何请求(回调拿到的正文是代理返回的 via-proxy)。代理 URL 里带用户名密码 http://user:p%40ss:w@… 时,请求头多一个 Proxy-Authorization: Basic dXNlcjpwQHNzOnc=,解码是 user:p@ss:w(百分号编码被还原,密码里的冒号也保留)。", t=tl(S(1)), mark=lidx(S(1), 'Proxy-Authorization=Basic', '源站直接收到'), done=lidx(S(1), 'GET http://127.0.0.1:9961/a'), kv=KV([['请求行', '绝对 URI:GET http://源站/路径'], ['代理 URL 里的凭据', '变成 Proxy-Authorization: Basic …'], ['%40 等编码', '还原后再 base64'], ['源站', '不会被直连']], ['代理 URL 里的凭据'])),
    step("环境变量:Scrapy 启动时用 urllib 的 getproxies() 读取 http_proxy / https_proxy / no_proxy,按请求协议挑代理。设了 http_proxy:/env 请求走代理,meta['proxy'] 指定的 /meta-override 走 meta 里的代理,meta['proxy'] = None 的 /meta-none 绕过环境变量直连源站;只设 https_proxy:http 请求不走代理(源站直连收到 /env 和 /meta-none);http_proxy 加 no_proxy=127.0.0.1:命中 no_proxy 的主机直连,meta 指定的仍走代理;大写的 HTTP_PROXY 同样有效;HTTPPROXY_ENABLED = 0 关掉环境变量代理,但 meta['proxy'] 仍然生效(代理仍收到 meta-override)。", t=tl(S(2)), mark=lidx(S(2), '只设 https_proxy', 'no_proxy', 'HTTPPROXY_ENABLED=0'), done=lidx(S(2), 'http_proxy=http', '只设大写'), kv=KV([['http_proxy', '只用于 http 请求'], ['no_proxy', '命中的主机直连'], ['meta["proxy"]', '优先于环境变量'], ['meta["proxy"] = None', '这个请求不用代理'], ['HTTPPROXY_ENABLED = 0', '只关环境变量,meta 仍有效']], ['meta["proxy"] = None'])),
    step("https 请求经代理:先发 CONNECT secure.example.test:443 HTTP/1.1,Host 头是 secure.example.test:443,Proxy-Authorization 解码是 alice:s3cret;代理回 200 之后 Scrapy 才在隧道里做 TLS 握手——这个假代理回 200 就关闭了连接,所以请求失败,errback 收到 scrapy.exceptions.DownloadFailedError(底层是 ConnectionLost)。", t=tl(S(3)), mark=lidx(S(3), 'CONNECT', '回调/errback'), kv=KV([['https 经代理', 'CONNECT host:443 + Proxy-Authorization'], ['代理回 200', '再在隧道里做 TLS'], ['隧道里断开', 'DownloadFailedError']], ['https 经代理'])),
    step("代理返回 407 Proxy Authentication Required(http 请求):回调不会被调用,errback 收到 HttpError,status = 407;代理收到 1 次请求,源站没有收到——407 没有被任何内置中间件处理,和其它 4xx 一样交给 HttpError,默认也不重试。", t=tl(S(4)), mark=lidx(S(4), '事件'), kv=KV([['407', 'HttpError(status 407)→ errback'], ['重试', '不在 RETRY_HTTP_CODES 里,不重试'], ['源站', '没收到']], ['407'])),
]
A = mkarts('s28', 28, 'Scrapy,HttpProxyMiddleware,代理,Proxy-Authorization,CONNECT,真实验证,动画演示',
    '用假代理实测 HttpProxyMiddleware:meta["proxy"] 让请求行变成绝对 URI,URL 里的凭据变成 Proxy-Authorization: Basic;启动时读取 http_proxy/https_proxy/no_proxy(大小写都行),meta["proxy"] = None 可逐个请求关掉;HTTPPROXY_ENABLED = 0 只关环境变量;https 先发 CONNECT;407 是 HttpError。',
    'Scrapy 怎么用代理?环境变量和 meta 谁优先?代理 URL 里的用户名密码怎么发?https 怎么走?这篇用一个能记录原始请求的假代理,看代理实际收到的每一个字节。',
    [('绝对 URI', '经代理的 http 请求的请求行写法(GET http://源站/路径 HTTP/1.1)'), ('CONNECT :443', 'https 请求经代理时先发的请求,带 Proxy-Authorization'), ('407', '代理要求认证时的结果:HttpError,不重试')],
    [('meta["proxy"]', '<p>请求的 <code>meta["proxy"]</code> 指向代理 URL;代理 URL 里的用户名密码被转成 <code>Proxy-Authorization: Basic</code>,先做百分号解码。</p>'),
     ('环境变量', '<p>中间件初始化时读取 <code>http_proxy</code>、<code>https_proxy</code>、<code>no_proxy</code>(大小写均可),按请求协议选代理;<code>meta["proxy"]</code> 优先,设为 <code>None</code> 则这个请求直连。</p>'),
     ('关闭中间件', '<p><code>HTTPPROXY_ENABLED = 0</code> 只让环境变量代理失效,请求 meta 里的 <code>proxy</code> 依然会被下载处理器使用。</p>'),
     ('https 与 407', '<p>https 先发 <code>CONNECT</code> 建立隧道;代理要求认证返回 407 时按普通的 4xx 处理。</p>')],
    steps,
    [ENV_Y + '。假代理是原始套接字服务器,记录请求行与头;普通请求回一个固定页面,CONNECT 回 200 后关闭连接,另有一个一律回 407 的模式;环境变量实验里用子进程环境显式增删 http_proxy 等变量(并清掉 pl 默认设置的 NO_PROXY)',
     '没有验证:SOCKS 代理(Scrapy 默认不支持);真实 HTTPS 站点经过真实 CONNECT 隧道的成功路径(本机没有可验证的证书链);代理失败后的重试与轮换;macOS 系统代理设置(getproxies 在没有环境变量时会读系统配置,这里的实验都先清掉了环境变量);重定向跨协议时代理凭据的处理(源码里有 _scheme_proxy / _auth_proxy 逻辑,没有测)'],
    '代理')
