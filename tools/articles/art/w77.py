from lib import *
S = SS('w77')
steps = [
    step("example.com 对各种方法的态度(同一个路径 /)。GET → 200,消息体 589 字节,Allow: GET, HEAD;HEAD → 200,消息体 0 字节,同样的 Allow: GET, HEAD;POST、PUT、DELETE、OPTIONS、PATCH → 全部 405 Method Not Allowed,各带 570 字节的错误页,而且响应里没有 Allow 头(规范要求 405 必须带 Allow,这个服务器没有带);TRACE → 405 Not Allowed,155 字节。这个站点只开放了两个方法,说明方法本身只是个标签,服务器要不要接受由它决定。", t=tl(S(1)), mark=lidx(S(1), 'POST ', 'PUT ', 'DELETE'), done=lidx(S(1), 'GET ', 'HEAD '), kv=KV([['GET / HEAD', '200,Allow: GET, HEAD'], ['POST / PUT / DELETE / OPTIONS / PATCH', '405,无 Allow 头'], ['TRACE', '405 Not Allowed']], ['POST / PUT / DELETE / OPTIONS / PATCH'])),
    step("HEAD 与 GET:HEAD 应该返回和 GET 相同的头部,但没有消息体。GET:200,12 个头部,消息体 589 字节;HEAD:200,11 个头部,消息体 0 字节。其余头部(accept-ranges、allow、alt-svc、cf-cache-status、connection、content-type、server)值完全相同(没比较 Date、Age、CF-RAY、Last-Modified,它们每次本来就不同)。唯一缺的是 transfer-encoding: chunked——因为没有消息体,就不需要划界;HEAD 响应也没有 Content-Length。HEAD 常被用来在不下载内容的情况下检查资源是否存在、有多大、有没有更新。", t=tl(S(2)), mark=lidx(S(2), 'GET:HTTP/1.1 200 OK', '值相同的头部'), done=lidx(S(2), 'GET 有 Transfer-Encoding'), b=bars([['GET 消息体', 589, '589 字节'], ['HEAD 消息体', 0, '0 字节']], 589, mark=[1], done=[0]), kv=KV([['GET', '12 个头部 + 589 字节'], ['HEAD', '11 个头部 + 0 字节'], ['差别', '只少了 Transfer-Encoding']], ['差别'])),
    step("幂等性决定了出错后能不能自动重试。本机服务器模拟“服务器处理了请求,但响应丢了”:收到请求先在账上记一笔,然后在前 2 次连接上直接复位(不返回响应),第 3 次才正常返回;客户端用 urllib3。urllib3 默认只对 DELETE、GET、HEAD、OPTIONS、PUT、TRACE 重试。GET:自动重试,最终成功,服务器共收到 3 次请求;PUT:同样自动重试成功,收到 3 次(幂等:执行 3 次和 1 次结果相同,所以安全);POST:不重试,直接失败(ProtocolError),服务器只收到 1 次。如果强制允许 POST 重试(allowed_methods=None),最终成功,但服务器账上的 POST 被执行了 3 次——前 2 次的响应丢了,业务已经执行了,重试把它重复执行了(比如重复扣款)。所以“请求超时或连接被复位”时,客户端并不知道服务器有没有已经执行了;只有幂等的方法才能放心重试,POST 要靠幂等键之类的应用层机制。", t=tl(S(3)), mark=lidx(S(3), 'POST :', 'POST,强制允许'), done=lidx(S(3), 'urllib3 的默认重试方法', 'GET  :', 'PUT  :'), b=bars([['GET 服务器收到', 3, '3 次'], ['PUT 服务器收到', 3, '3 次'], ['POST 服务器收到(默认)', 1, '1 次'], ['POST 强制重试时被执行', 3, '3 次']], 3, mark=[3], done=[0, 1, 2]), kv=KV([['GET / PUT', '自动重试,成功,重复执行无害'], ['POST(默认)', '不重试,失败,只执行 1 次'], ['POST(强制重试)', '成功,但被执行 3 次']], ['POST(强制重试)'])),
    step("几个边缘情况。方法名区分大小写:小写 get → 400 Bad Request。OPTIONS * → 400 Bad Request(HTTP/1.1 里 * 作为请求目标只用于 OPTIONS,这个服务器没有接受)。GET 带一个 5 字节的请求体(Content-Length: 5)→ 200 OK,服务器忽略了请求体并返回了页面(规范不禁止,但没有定义含义)。DELETE / → 405,同上一节。", t=tl(S(4)), mark=lidx(S(4), '小写 get', 'OPTIONS *'), done=lidx(S(4), 'GET 带请求体', 'DELETE /'), kv=KV([['小写 get', '400'], ['OPTIONS *', '400'], ['GET 带请求体', '200,请求体被忽略']], ['小写 get'])),
]
A = mkartw('w77', 77, '网络协议,HTTP,HTTP 方法,幂等性,安全方法,重试,POST,真实验证,动画演示',
    '实测 HTTP 方法语义:example.com 只开放 GET 与 HEAD(其它全部 405 且不带 Allow 头);HEAD 与 GET 的头部只差 Transfer-Encoding;响应丢失时 urllib3 自动重试 GET / PUT(服务器收到 3 次)而不重试 POST;强制重试 POST 会使服务器账上被重复执行 3 次。',
    'GET、POST、PUT、DELETE……HTTP 方法不只是动词,它们携带着“安全吗?幂等吗?能重试吗?”的约定。这篇先看一个真实服务器对每个方法的态度,再用一个“响应丢了”的模拟场景证明:为什么 GET 和 PUT 可以放心重试,而 POST 重试一次就可能把事情做两遍。',
    [('3 次 vs 1 次', '响应丢失时,强制重试的 POST 与默认不重试的 POST 在服务器账上被执行的次数'), ('405', 'example.com 对 POST / PUT / DELETE / OPTIONS / PATCH 的统一回答,且不带 Allow 头'), ('0 字节', 'HEAD 响应的消息体(GET 为 589 字节)')],
    [('方法只是标签', '<p>example.com 只接受 GET 与 HEAD,其它方法一律 405。</p>'),
     ('HEAD', '<p>HEAD 给出与 GET 相同的头部、没有消息体,不需要 Transfer-Encoding。</p>'),
     ('幂等与重试', '<p>GET 和 PUT 重试 3 次结果同 1 次;POST 重试会重复执行,默认客户端库不重试它。</p>'),
     ('边缘情况', '<p>方法名区分大小写;OPTIONS * 被拒;GET 带请求体被忽略。</p>')],
    steps,
    [ENV_W + '。第一、二、四节是对 example.com:80 的明文请求(PUT / POST / DELETE 带的是极小的无意义请求体);第三节用本机脚本服务器 + urllib3 2.8.0,“响应丢了”是用 SO_LINGER=0 的复位模拟的',
     '没有验证:PATCH、DELETE 在设计良好的 REST 服务上的真实语义;Idempotency-Key 之类的应用层幂等机制;浏览器对 POST 重新提交的提示;安全方法(GET)被错误地用来改状态时的后果(预取、爬虫);请求体里的 Expect: 100-continue'],
    'HTTP 方法')
