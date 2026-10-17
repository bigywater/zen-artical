from lib import *
S = SS('n51')
steps = [
    step("真实 curl 请求自定义方法:r.Handle(\"PURGE\", \"/cache/*key\", …) 让 curl -X PURGE /cache/a/b.png 命中(path=/cache/*key);PROPFIND 与 REPORT 两个方法共用 /dav/:name 路径、各自一个 handler;PROPFIND 带的请求体 <xml/> 在 handler 里读得到;用 PURGE 去请求只注册了 PROPFIND / REPORT 的 /dav/folder → 404。Handle 对方法名只要求全是大写英文字母(上一系列的方法树一篇验证过)。", t=tl(S(1)), mark=lidx(S(1), 'PURGE /dav/folder'), done=lidx(S(1), 'PURGE /cache/a/b.png', 'PROPFIND /dav/folder', 'REPORT /dav/folder'), kv=KV([['Handle(method, path)', '自定义方法照常匹配'], ['同一路径多个方法', '各自独立的 handler'], ['没注册的方法', '404(默认)']], ['Handle(method, path)'])),
    step("Any 注册了 9 个方法,包含 TRACE 与 CONNECT:TRACE /any、DELETE /any 都命中 any 的 handler(路由表里 /any 出现在 GET POST PUT PATCH HEAD OPTIONS DELETE CONNECT TRACE 九个方法下);Match([GET, POST], \"/m\") 只注册这两个:POST /m 命中,PATCH /m、PUT /m 都是 404。Any 会把 TRACE 也放进来,如果只想开放常用方法,用 Match 更稳妥。", t=tl(S(2)), mark=lidx(S(2), 'TRACE /any', 'PATCH /m', 'PUT /m'), done=lidx(S(2), 'DELETE /any', 'POST /m'), kv=KV([['Any', '9 个方法,含 TRACE / CONNECT'], ['Match', '只注册列出的方法'], ['没列出的方法', '404']], ['Any'])),
    step("HEAD、OPTIONS 与方法名大小写:只注册了 GET /hello:curl -I(HEAD)→ 404,OPTIONS → 404(CORS 预检要自己注册 OPTIONS,/cors 注册后返回 204 与 Allow),小写的 get → 404(方法名区分大小写)。单独注册了 HEAD /headonly:curl -I 命中 HEAD 的 handler(Content-Length: 30,但服务器不发正文),GET 命中另一个 handler。服务端启动时打印的路由表显示了每条路由实际登记的方法。", t=tl(S(3)), mark=lidx(S(3), '-I /hello', 'OPTIONS /hello', 'get /hello'), done=lidx(S(3), 'OPTIONS /cors', '-I /headonly', 'curl /headonly'), kv=KV([['HEAD', '不会自动用 GET 的 handler'], ['OPTIONS', '要自己注册(预检请求)'], ['方法名', '区分大小写,get ≠ GET']], ['OPTIONS'])),
    step("打开 HandleMethodNotAllowed 之后:DELETE /dav/folder → 405,Allow: PROPFIND, REPORT(自定义方法也出现在 Allow 里,顺序是各方法树第一次创建的顺序);GET /cache/x → Allow: PURGE;DELETE /m → Allow: GET, POST;PURGE /hello → Allow: GET;Any 注册的 /any 对所有 9 个方法都命中,所以 DELETE /any 仍是 200。", t=tl(S(4)), mark=lidx(S(4), '405 Method Not Allowed'), done=lidx(S(4), 'DELETE /any'), kv=KV([['Allow', '自定义方法照常列出'], ['Any 的路径', '9 个方法都命中,不会 405'], ['顺序', '方法树的创建顺序']], ['Allow'])),
]
A = mkartn('n51', 51, 'Gin,自定义HTTP方法,Handle,Any,Match,HEAD,OPTIONS,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里用真实 curl 实测自定义方法与 Any:Handle 注册 PURGE / PROPFIND / REPORT 等方法并正常匹配;Any 注册 9 个方法(包含 TRACE、CONNECT),Match 只注册指定的;HEAD 与 OPTIONS 不会自动处理,方法名区分大小写;打开 HandleMethodNotAllowed 后 Allow 头里包含自定义方法。',
    'WebDAV 的 PROPFIND、缓存清理的 PURGE、浏览器预检的 OPTIONS——这些在 Gin 里该怎么注册?Any 会不会把不该开放的方法也开放了?HEAD 请求为什么 404?这篇用真实的 curl 请求把 Handle、Any、Match 以及 HEAD / OPTIONS 的行为逐个验证。',
    [('9 个', 'r.Any 注册的方法数(含 HEAD、OPTIONS、CONNECT、TRACE)'), ('404', '只注册 GET 的路径,HEAD 与 OPTIONS 请求以及小写的 get 请求的状态码'), ('Allow: PROPFIND, REPORT', '打开 HandleMethodNotAllowed 后 DELETE /dav/folder 的响应头')],
    [('Handle:任意大写方法', '<p><code>Handle(method, path, ...)</code> 接受任何全大写的方法名,和内置的 <code>GET</code>/<code>POST</code> 走同样的路由树。同一个路径可以给不同方法注册不同 handler(WebDAV 的 PROPFIND 与 REPORT);请求体照常可读。没注册的方法默认 404。</p>'),
     ('Any 与 Match', '<p><code>Any</code> 一口气注册 9 个方法,其中包括 <code>TRACE</code> 和 <code>CONNECT</code>。如果这条路径其实只该接受几种方法,<code>Any</code> 会让多余的方法也进入你的 handler(并且在 405 判定里永远命中)。<code>Match([]string{...})</code> 只注册你列出的方法,更精确。</p>'),
     ('HEAD、OPTIONS 与大小写', '<p>Gin 不会把 GET 路由自动用于 HEAD,也不会自动响应 OPTIONS:<code>curl -I</code> 访问只注册了 GET 的路径得到 404,CORS 预检要自己注册 OPTIONS(或用中间件)。HEAD 请求即使进了 handler 写了正文,服务器也不会发出,只保留 Content-Length。方法名区分大小写,<code>get</code> 与 <code>GET</code> 是不同的方法。</p>'),
     ('405 与自定义方法', '<p>打开 <code>HandleMethodNotAllowed</code> 后,405 的 <code>Allow</code> 头把自定义方法也列出来,顺序是各方法树第一次创建的顺序(与前面方法树一篇一致)。注册了 <code>Any</code> 的路径不会返回 405,因为所有方法都命中。</p>')],
    steps,
    [ENV_N_GIN + '。服务端是编译好的真实二进制(127.0.0.1:9761 / 9762,r.Run);客户端是 curl 8.7.1,-i 输出响应头;表中只保留与本文有关的头;每种情形各一次',
     '没有验证:CONNECT 方法(请求目标是 authority 形式,curl 不容易构造,没有测);TRACE 请求的安全影响(只验证了能进入 handler);WebDAV 客户端的真实交互;CORS 中间件的完整实现;HTTP/2 下自定义方法的行为;自定义方法的路径匹配与重定向规则(与标准方法相同,没有逐项验证)'],
    '自定义方法与 Any')
