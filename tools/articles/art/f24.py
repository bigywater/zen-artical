from lib import *
S = SS('f24')
R = J('f24')
steps = [
    step("自动的 OPTIONS:对 methods 为 GET、POST 的 /res 发 OPTIONS,得到 200,正文长度 0,响应头有 Allow: OPTIONS, GET, POST, HEAD、Content-Type: text/html; charset=utf-8、Content-Length: 0;视图函数没有被调用(只触发了 before_request)。", t=tl(S(1)), done=lidx(S(1), 'OPTIONS /res', '这次请求触发的回调'), kv=KV([['状态', '200,正文为空'], ['Allow', 'OPTIONS, GET, POST, HEAD'], ['视图函数', '没有执行']], ['视图函数'])),
    step("自动的 HEAD:GET /res 的 Content-Length 是 11、正文 11 字节;HEAD /res 的 Content-Length 也是 11,正文 0 字节。但视图函数里记录到的方法是 ['GET', 'HEAD'] —— HEAD 请求也执行了视图,Werkzeug 只是去掉了正文。视图里有副作用(计数、写库)时,HEAD 也会触发。", t=tl(S(2)), done=lidx(S(2), 'GET →', 'HEAD →'), mark=lidx(S(2), '视图函数里记录到的方法'), kv=KV([['Content-Length', 'GET 与 HEAD 都是 11'], ['HEAD 的正文', '0 字节'], ['视图执行', "GET、HEAD 各一次"]], ['视图执行'])),
    step("自己处理 OPTIONS:methods 里写上 OPTIONS 后 Flask 不再自动生成,视图被调用:OPTIONS /custom → 204,Allow: GET, OPTIONS,X-Custom: 1(都是视图自己设的)。", t=tl(S(3)), done=lidx(S(3), 'OPTIONS /custom'), kv=KV([['状态', '204'], ['Allow / X-Custom', '视图自己设置']], ['Allow / X-Custom'])),
    step("provide_automatic_options=False:OPTIONS /noauto → 405,Allow: GET, HEAD;这条规则的 methods 只有 GET、HEAD(没有 OPTIONS)。", t=tl(S(4)), done=lidx(S(4), 'OPTIONS /noauto', 'noauto 规则的 methods'), kv=KV([['OPTIONS', '405'], ['methods', 'GET、HEAD']], ['OPTIONS'])),
    step("before_request 对 OPTIONS 也会执行:OPTIONS /res 触发的回调是 ['before:OPTIONS']。所以放在 before_request 里的鉴权如果不放行 OPTIONS,浏览器的跨域预检会失败。", t=tl(S(5)), done=lidx(S(5), 'OPTIONS /res 触发的回调'), kv=KV([['before_request', 'OPTIONS 也执行']], ['before_request'])),
    step("跨域预检(带 Origin 与 Access-Control-Request-Method 的 OPTIONS):没有 flask-cors 时只返回 200 与 Allow: OPTIONS, GET, POST, HEAD,没有任何 Access-Control-* 头 —— 浏览器会判定预检失败,跨域请求不会发出。", t=tl(S(6)), mark=lidx(S(6), '→ 200'), kv=KV([['预检响应', '只有 Allow'], ['Access-Control-* 头', '没有']], ['Access-Control-* 头'])),
]
A = mkartf('f24', 24, 'Flask,OPTIONS,HEAD,自动处理,真实验证,动画演示',
    '实测 Flask 自动的 OPTIONS 与 HEAD:OPTIONS 是 200 带 Allow 且不调用视图;HEAD 会执行视图只是去掉正文;自己处理 OPTIONS 与 provide_automatic_options=False;before_request 对 OPTIONS 也执行;没有 CORS 头时的预检响应。',
    '谁在默默处理 OPTIONS 与 HEAD 请求?视图函数会不会被执行?预检请求为什么会被鉴权拦掉?这篇用最小的例子把这些都实测出来。',
    [('0 字节', 'HEAD 响应的正文大小(但视图仍然执行了)'), ('Allow', '自动 OPTIONS 响应里携带的头'), ('0', '没有 flask-cors 时预检响应里的 Access-Control-* 头个数')],
    [('自动 OPTIONS', '<p>上一篇:<a href="flask-http-method-restriction.html">HTTP 方法限制</a>;下一篇:<a href="flask-route-conflict.html">路由冲突如何解决</a>;跨域预检的专题:<a href="flask-cors-preflight.html">CORS 预检请求</a>。</p>'), ('自动 HEAD', None), ('自己处理 OPTIONS', None), ('关闭自动 OPTIONS', None), ('before_request 与 OPTIONS', None), ('跨域预检', None)],
    steps, [ENV_F, '没有验证:flask-cors 对预检的处理(见第 79 篇)、HEAD 请求在生成器响应上的行为、真实浏览器发出的预检请求的完整头、HTTP 服务器(gunicorn)对 HEAD 的额外处理'], 'OPTIONS 与 HEAD')
