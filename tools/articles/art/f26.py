from lib import *
S = SS('f26')
R = J('f26')
steps = [
    step("蓝图只是「记录」:定义 @bp.route('/ping') 之后,蓝图对象上 deferred_functions 里记着 1 个待执行的函数;register_blueprint 之前 app.url_map 里没有这条规则、app.blueprints 是空的;注册之后规则变成 ('/ping', 'api.ping'),app.blueprints = {'api': Blueprint}。", t=tl(S(1)), done=lidx(S(1), 'deferred_functions', '注册前'), mark=lidx(S(1), '注册后'), kv=KV([['注册前', 'url_map 里没有规则'], ['deferred_functions', '1 个'], ['注册后', "('/ping', 'api.ping')"]], ['注册后'])),
    step("蓝图被注册之后再给它加路由,抛 AssertionError「The setup method 'route' can no longer be called on the blueprint 'api'. It has already been registered at least once, any changes will not be applied consistently.」—— 路由必须在注册之前定义完。", t=tl(S(2)), mark=lidx(S(2), 'AssertionError'), kv=KV([['注册后再 @bp.route', 'AssertionError']], ['注册后再 @bp.route'])),
    step("请求 /shop/info 时记录到:request.blueprint = 'shop'、request.blueprints = ['shop']、request.endpoint = 'shop.info';相对写法 url_for('.info') 与绝对写法 url_for('shop.info') 都得到 /shop/info。", t=tl(S(3)), done=lidx(S(3), "'blueprint': 'shop'"), kv=KV([['request.blueprint', 'shop'], ['request.endpoint', 'shop.info'], ['url_for', "'.info' 与 'shop.info' 相同"]], ['request.endpoint'])),
    step("嵌套蓝图:子蓝图 child(/c)注册到父蓝图 parent(/p)里,规则是 ('/p/c/x', 'parent.child.x'),GET /p/c/x → child x;请求里 request.blueprints = ['parent.child', 'parent']、request.blueprint = 'parent.child'。前缀逐层叠加,endpoint 是「父.子.函数」。", t=tl(S(4)), done=lidx(S(4), '规则:', '请求里 request.blueprints'), kv=KV([['URL', '/p/c/x'], ['endpoint', 'parent.child.x'], ['request.blueprints', "['parent.child', 'parent']"]], ['endpoint'])),
    step("蓝图自己的钩子与上下文处理器只对本蓝图的请求生效:/b3/t 触发了 b3.before_request,模板里 who = b3;/plain(应用的路由)没有触发蓝图钩子,模板里 who 为(无)。蓝图的 @errorhandler(404) 对 GET /b3/nope 不起作用,得到的是应用默认的 404 页 —— 路由没匹配时请求不属于任何蓝图。", t=tl(S(5)), done=lidx(S(5), '/b3/t', '/plain'), mark=lidx(S(5), '蓝图的 errorhandler(404)'), kv=KV([['蓝图 before_request', '只对蓝图自己的路由'], ['蓝图 context_processor', '只对蓝图自己的模板'], ['蓝图 errorhandler(404)', '对未匹配的 URL 不生效']], ['蓝图 errorhandler(404)'])),
    step("拆分应用:shop 包里 Blueprint('shop', __name__, url_prefix='/shop'),views.py 里定义路由,main.py 里 app.register_blueprint(shop_bp)。实际运行:规则是 ('/shop/', 'shop.home')、('/shop/<int:i>', 'shop.item'),GET /shop/ → shop home,GET /shop/3 → item 3;蓝图的 root_path 是 shop 包所在目录。", t=tl(S(6)), done=lidx(S(6), "('/shop/', 'shop.home')", 'shop home', 'root_path'), kv=KV([['规则', "/shop/ → shop.home;/shop/<int:i> → shop.item"], ['root_path', '蓝图所在包的目录']], ['规则'])),
]
A = mkartf('f26', 26, 'Flask,Blueprint,蓝图,路由注册,真实验证,动画演示',
    '验证 Blueprint 路由注册:蓝图只记录(deferred_functions),register_blueprint 时才写进 url_map;注册后不能再加路由;endpoint 带蓝图名前缀;嵌套蓝图的 endpoint 与 request.blueprints;蓝图钩子与上下文处理器的作用范围;按包拆分应用的实际运行。',
    '蓝图到底是什么?定义路由的时候路由在哪里?注册的时候发生了什么?钩子和错误处理器的范围有多大?这篇从 deferred_functions 开始逐项打印。',
    [('1', '定义一个路由后蓝图上记录的延迟函数个数'), ('parent.child.x', '嵌套蓝图里路由的 endpoint'), ('AssertionError', '蓝图注册后再加路由时的报错')],
    [('蓝图只是记录', '<p>上一篇:<a href="flask-route-conflict.html">路由冲突如何解决</a>;下一篇:<a href="flask-blueprint-url-prefix.html">Blueprint 的 URL 前缀</a>。</p>'), ('注册之后不能再加路由', None), ('endpoint 与 request.blueprint', None), ('嵌套蓝图', None), ('钩子与处理器的作用范围', None), ('拆分应用', None)],
    steps, [ENV_F, '没有验证:蓝图的 cli_group 与 flask 命令、url_defaults 与 url_value_preprocessor、蓝图 register 时的 options(如 subdomain)、更深层(三层以上)嵌套的钩子顺序'], 'Blueprint')
