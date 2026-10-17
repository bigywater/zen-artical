from lib import *
S = SS('f23')
R = J('f23')
steps = [
    step("不同写法得到的 methods:默认 @app.route('/default') 是 GET、HEAD、OPTIONS;methods=['POST'] 是 OPTIONS、POST;methods=['GET','POST','DELETE'] 是 DELETE、GET、HEAD、OPTIONS、POST;@app.get、@app.post、@app.delete 各自对应 GET(+HEAD、OPTIONS)、POST(+OPTIONS)、DELETE(+OPTIONS);MethodView 按定义了的 get 与 post 方法得到 GET、HEAD、OPTIONS、POST。HEAD 只会跟着 GET 出现。", t=tl(S(1)), done=lidx(S(1), '/default', '/post-only', '/multi'), mark=lidx(S(1), '/g ', '/mv'), kv=KV([['默认', 'GET、HEAD、OPTIONS'], ['methods=[POST]', 'OPTIONS、POST'], ['HEAD', '只跟着 GET']], ['HEAD'])),
    step("方法 × 路径的状态码矩阵(实测):/default 只有 GET、HEAD、OPTIONS 是 200,其余 405;/post-only 只有 POST、OPTIONS 是 200,GET 与 HEAD 是 405;/multi 的 GET、POST、DELETE、HEAD、OPTIONS 是 200,PUT 与 PATCH 是 405;/mv 的 GET、POST、HEAD、OPTIONS 是 200。405 的响应带 Allow 头(PUT /default → Allow: OPTIONS, HEAD, GET)与默认 HTML 页「405 Method Not Allowed」。", t=tl(S(2)), done=lidx(S(2), '/default    ', '/post-only  ', '/multi      ', '/mv         '), mark=lidx(S(2), 'PUT /default 的 405 响应', '正文'), kv=KV([['不在 methods 里', '405'], ['405 响应头', 'Allow: 允许的方法列表']], ['405 响应头'])),
    step("一个视图可以同时处理多个方法:/multi 里 GET、POST、DELETE 分别返回 multi GET、multi POST、multi DELETE(通过 request.method 区分)。请求方法写成小写 'get' 也能匹配到 GET(得到 200 multi GET)。", t=tl(S(3)), done=lidx(S(3), 'GET /multi'), mark=lidx(S(3), '小写'), kv=KV([['request.method', '区分 GET / POST / DELETE'], ['小写 \"get\"', '也匹配 GET']], ['request.method'])),
    step("methods 参数:写小写 ['get','post'] 会被规整成大写,规则的方法集合是 GET、HEAD、OPTIONS、POST;写成字符串 'POST' 抛 TypeError「Allowed methods must be a list of strings, for example: @app.route(..., methods=[\"POST\"])」;写自定义方法 ['FOO'] 不报错,用 FOO 方法请求得到 200。", t=tl(S(4)), mark=lidx(S(4), 'TypeError'), done=lidx(S(4), 'methods=["get","post"]', 'FOO'), kv=KV([['小写', '规整成大写'], ['字符串', 'TypeError'], ['自定义方法 FOO', '可用']], ['字符串'])),
    step("MethodView 的 methods 属性是 GET、POST(取决于类里定义了哪些方法);PUT /mv → 405,Allow: OPTIONS, HEAD, GET, POST。", t=tl(S(5)), done=lidx(S(5), 'MethodView 的 methods'), mark=lidx(S(5), 'PUT /mv'), kv=KV([['methods', 'GET、POST'], ['PUT', '405,Allow: OPTIONS, HEAD, GET, POST']], ['PUT'])),
    step("浏览器表单只能发 GET 与 POST。常见做法是自己写一个中间件(不是 Flask 内置功能):收到 POST 且带 X-HTTP-Method-Override: DELETE 头时改写 REQUEST_METHOD。这里的实测:POST /res + 该头 → 200,视图里 request.method 是 DELETE。", t=tl(S(6)), done=lidx(S(6), 'POST + X-HTTP-Method-Override'), kv=KV([['POST + X-HTTP-Method-Override: DELETE', '视图里 request.method = DELETE']], ['POST + X-HTTP-Method-Override: DELETE'])),
]
A = mkartf('f23', 23, 'Flask,HTTP 方法,405,MethodView,真实验证,动画演示',
    '实测 Flask 的 HTTP 方法限制:默认只允许 GET(自动加 HEAD 与 OPTIONS);各路由 × 7 种方法的状态码矩阵;405 带 Allow 头;methods 写小写会规整、写字符串报 TypeError;MethodView 的 methods;用中间件做方法覆盖。',
    '路由默认允许哪些方法?不允许的方法得到什么响应?Allow 头里是什么?这篇用 4 种路由和 7 种方法做一张完整的矩阵。',
    [('405', '方法不在 methods 里时的状态码'), ('7 × 4', '本篇矩阵里的方法数 × 路由数'), ('GET、HEAD、OPTIONS', '默认路由的 methods')],
    [('methods 的各种写法', '<p>上一篇:<a href="flask-static-route.html">静态文件路由的注册方式</a>;下一篇:<a href="flask-options-head-auto.html">OPTIONS 与 HEAD 自动处理</a>。</p>'), ('方法矩阵', None), ('同一个视图处理多个方法', None), ('methods 参数的取值', None), ('MethodView', None), ('方法覆盖', None)],
    steps, [ENV_F, '没有验证:RESTful 资源的 PATCH 与 PUT 语义、浏览器对 405 页面的呈现、方法覆盖头在反向代理与 CDN 下的行为、真实 HTTP 服务器对非标准方法的处理(这里全部用 test client)'], 'HTTP 方法')
