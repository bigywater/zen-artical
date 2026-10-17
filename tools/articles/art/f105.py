from lib import *
S = SS('f105')
R = J('f105')
steps = [
    step("URL 前缀版本:两个蓝图(url_prefix 分别是 /v1 与 /v2)调用同一个 get_user,返回不同结构:/v1/users/1 是 {id, name: 'Ann Lee'},/v2/users/1 是 {id, first_name, last_name, email};/v3/users/1 没有注册,是 404(HTML 页面)。url_for('v1.u1') 与 url_for('v2.u2') 分别生成 /v1/users/1 与 /v2/users/1;路由表里每个版本一条独立的规则。", t=tl(S(1)), done=lidx(S(1), '/v1/users/1', '/v2/users/1', 'url_for', 'v1.u1'), mark=lidx(S(1), '/v3'), kv=KV([['蓝图 + url_prefix', '每个版本一套路由'], ['未注册的版本', '404']], ['蓝图 + url_prefix'])),
    step("废弃提示:给 v1 蓝图加 after_request,只有 v1 的响应带 Deprecation: true、Sunset: Wed, 31 Dec 2026 23:59:59 GMT 与 Link: </v2/users>; rel=\"successor-version\";/v2 与 /health 没有。v1 视图里 abort(404) 的响应也带这些头(蓝图的 after_request 对蓝图视图里抛出的错误同样生效)。", t=tl(S(2)), done=lidx(S(2), '/v1/users/1'), mark=lidx(S(2), 'v1 的 404'), kv=KV([['bp.after_request', '只作用于这个蓝图的请求'], ['Deprecation / Sunset', '告诉调用方何时下线']], ['bp.after_request'])),
    step("请求头版本:同一条路由 /users/<id>,按 Accept: application/vnd.app.v1+json 或 v2+json 选版本(request.accept_mimetypes.best_match);带 q 值时选权重高的 v2;Accept: */* 时得到列表里第一个(v1);Accept: text/html 得到 406;自定义头 X-API-Version: 2 得到 v2,X-API-Version: 9 得到 400。响应的 Content-Type 是 application/vnd.app.v2+json。响应里没有 Vary 头——Flask 不会替你加,按请求头选版本的接口要自己加 Vary: Accept,这一点的缓存后果我没有验证。", t=tl(S(3)), done=lidx(S(3), 'v1+json', 'v2+json', 'q 值', 'X-API-Version: 2'), mark=lidx(S(3), 'text/html', 'X-API-Version: 9', 'Vary'), kv=KV([['Accept 协商', 'best_match 选版本'], ['没有匹配', '406 / 400'], ['Vary', 'Flask 不自动加']], ['Vary'])),
    step("两种方式的路由代价:URL 版本每个版本都有自己的一套规则(这里 2 个版本是 2 条规则,接口一多就成倍增长),请求头版本只有 1 条规则,但视图里要写分支。URL 版本对浏览器、日志、缓存、文档都更直观;请求头版本地址干净,但不容易手工调试。", t=tl(S(4)), done=lidx(S(4), 'URL 版本'), kv=KV([['URL 版本', '2 条规则,直观'], ['请求头版本', '1 条规则,视图分支']], ['URL 版本'])),
]
A = mkartf('f105', 105, 'Flask,API,版本控制,蓝图,Accept,真实验证,动画演示',
    '实测 Flask API 版本控制的两种做法:URL 前缀的蓝图(/v1 与 /v2 共用业务代码、未注册版本 404、蓝图 after_request 只给 v1 加 Deprecation 与 Sunset 头)和请求头版本(Accept 协商、q 值、*/* 取第一个、406 与 400、Flask 不自动加 Vary)。',
    'API 要升级又不能破坏老客户端,版本怎么管?用 URL 前缀还是请求头?怎么提示调用方老版本要下线?这篇把两种做法都写出来,逐个验证每种请求会得到什么。',
    [('2 种', '实测的版本控制方式:URL 前缀与请求头'), ('Deprecation / Sunset', '只给 v1 响应加的废弃提示头'), ('406', 'Accept 里没有任何受支持的版本时的状态码')],
    [('URL 前缀版本', '<p>上一篇:<a href="flask-api-pagination.html">API 分页</a>;下一篇:<a href="flask-restful-url-design.html">RESTful URL 设计</a>。</p>'), ('废弃提示头', None), ('请求头版本', None), ('路由代价', None)],
    steps, [ENV_F, '没有验证:Vary 头缺失在真实 CDN 或代理缓存下的后果、查询参数版本(?version=2)、两个版本共用数据库迁移时的兼容策略、OpenAPI 文档按版本拆分(见第 114 篇)'], 'API 版本控制')
