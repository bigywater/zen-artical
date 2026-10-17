from lib import *
S = SS('f102')
R = J('f102')
steps = [
    step("默认:不存在的路径 404、abort(404, description=...) 的 404、方法不允许 405、未处理异常 500、非法 JSON 400,响应的 Content-Type 全是 text/html,正文是 Werkzeug 的 HTML 页面。API 客户端按 JSON 解析会直接失败。", t=tl(S(1)), mark=lidx(S(1), 'text/html'), kv=KV([['所有错误', '默认都是 HTML 页面'], ['API 客户端', '解析 JSON 会失败']], ['所有错误'])),
    step("统一成 JSON 需要三个处理器:errorhandler(HTTPException) 覆盖 404、405、400、415 等(code 由 e.name 转成 not_found 之类,message 用 e.description,并把 e.get_headers() 里的头(例如 405 的 Allow: OPTIONS, HEAD, GET)带上);errorhandler(ApiError) 处理自己的异常(409 conflict,还带了额外字段 current: 5);errorhandler(Exception) 兜底,未处理异常返回 500 internal_error 和一句通用的话。每个响应都带 request_id(调用方传了 X-Request-Id 就原样回显 abc-123)。500 的响应里没有泄漏异常信息(搜不到 hunter2)。注意 400、404 的 message 是 Werkzeug 的英文默认文字。", t=tl(S(2)), done=lidx(S(2), '不存在的路径', 'abort(404', '自定义 ApiError', '未处理异常', '405 响应保留', '500 的响应里'), kv=KV([['HTTPException 处理器', '覆盖 4xx,保留 Allow 等头'], ['ApiError', '自己的业务错误,可带字段'], ['Exception', '兜底 500,不泄漏细节']], ['Exception'])),
    step("同一个应用里 HTML 页面要保持 HTML:处理器里按 request.path.startswith('/api/') 区分——/api/nope 返回 JSON(404、application/json),/page 里 abort(403) 仍然是 text/html 的 403 页面(处理器直接 return e)。", t=tl(S(3)), done=lidx(S(3), '/api/nope', '/page'), kv=KV([['/api/ 开头', 'JSON'], ['其它', '保持 HTML']], ['/api/ 开头'])),
    step("蓝图里的 404 处理器只管蓝图视图里主动 abort(404):蓝图里的视图 abort(404) 得到 {src: blueprint};而 /api/unknown(路由根本没匹配上,Flask 还不知道属于哪个蓝图)走的是应用级的 404 处理器({src: app})。要统一处理未匹配路径的 404,处理器必须注册在应用上。", t=tl(S(4)), done=lidx(S(4), '蓝图里的视图'), mark=lidx(S(4), '路由没匹配'), kv=KV([['蓝图的 errorhandler(404)', '只管蓝图视图里抛出的'], ['路由没匹配', '只能由应用级处理器处理']], ['路由没匹配'])),
    step("兜底的 Exception 处理器在默认、TESTING=True、DEBUG=True 三种模式下都生效,都返回 500 {error: handled, type: RuntimeError};也就是说注册了它之后,debug 模式的交互式调试页面不会出现(异常在到达调试器之前就被处理掉了)——这一点我只验证了处理器仍然生效,没有实际打开调试页面。", t=tl(S(5)), done=lidx(S(5), '默认', 'TESTING', 'DEBUG'), kv=KV([['Exception 处理器', '各模式下都接管未处理异常']], ['Exception 处理器'])),
]
A = mkartf('f102', 102, 'Flask,API,错误处理,errorhandler,真实验证,动画演示',
    '实测 Flask API 错误响应的统一格式:默认所有错误都是 HTML;用 HTTPException、自定义 ApiError 与 Exception 三个处理器统一成 {error: {code, message, request_id}};405 的 Allow 头保留、500 不泄漏异常信息;按路径前缀区分 API 与页面;蓝图的 404 处理器抓不到未匹配的路由。',
    'API 出错时应该返回什么格式?怎么让 404、405、400、500 都变成 JSON?蓝图里的错误处理器有什么陷阱?这篇用 test_client 逐个验证每种错误在默认与统一之后的样子。',
    [('HTML → JSON', '默认错误页是 HTML,统一处理后 7 种错误都变成 JSON'), ('request_id', '每个错误响应都带的请求标识,调用方可以传入'), ('蓝图 404', '蓝图的 404 处理器接不到路由没匹配的请求')],
    [('默认的错误响应', '<p>上一篇:<a href="flask-json-api.html">Flask 实现 JSON API</a>;下一篇:<a href="flask-request-validation.html">请求参数校验</a>。</p>'), ('统一成 JSON', None), ('API 与页面共存', None), ('蓝图里的 404', None), ('debug 与测试模式', None)],
    steps, [ENV_F, '没有验证:真实 HTTP 下的行为(与 test_client 相同,没有差别的预期但未验证)、RFC 9457(Problem Details)格式、多语言 message、异步视图里的错误处理、日志与 Sentry 等错误上报的集成'], 'API 错误响应格式')
