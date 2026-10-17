from lib import *
S = SS('f159')
steps = [
    step("真实运行的 9 个 Blueprint 测试(pytest -v -s,9 passed)。fixture 里只创建一个最小的 Flask 应用、注册这个蓝图(url_prefix='/shop')再加一个蓝图之外的 /other 路由。GET /shop/items → 200,视图读到:蓝图的 before_request 设置的 g.shop_hook = ran、request.endpoint 是 shop.items(蓝图名加视图名)、url_for('.items') 是 /shop/items(点开头表示当前蓝图)、应用配置里的 CURRENCY = CNY(蓝图用的是注册它的应用的配置)。", t=tl(S(1)), done=lidx(S(1), 'route', 'cfg'), kv=KV([['端点名', '蓝图名.视图名'], ['url_for(".items")', '点开头 = 当前蓝图'], ['配置', '用应用的配置']], ['端点名'])),
    step("url_for 要写完整的端点名:test_request_context 里 url_for('shop.items') 是 /shop/items,url_for('shop.one', i=3) 是 /shop/3。蓝图的钩子只作用于它自己的请求:GET /shop/items 的响应有 X-Shop: 1,GET /other 没有(None)。", t=tl(S(1)), done=lidx(S(1), 'url_for', 'hooks'), kv=KV([['bp.after_request', '只加到蓝图自己的响应']], ['bp.after_request'])),
    step("注册时可以换前缀:register_blueprint(bp, url_prefix='/v2/store') 之后 /v2/store/items 是 200、原来的 /shop/items 是 404(前缀以注册时的为准)。同一个蓝图注册两次,第二次抛 ValueError「The name 'shop' is already registered for this blueprint. Use 'name=' to provide a unique name」;给第二次传 name='shop2' 之后,/one/items 与 /two/items 都是 200。", t=tl(S(1)), done=lidx(S(1), 'other-prefix', 'twice'), kv=KV([['url_prefix', '注册时可覆盖'], ['注册两次', '必须给不同的 name']], ['注册两次'])),
    step("隔离测试:一个只注册这个蓝图的新应用,app.blueprints 只有 shop,路由表只有 /shop/<int:i> 与 /shop/items;没注册蓝图的应用访问 /shop/items 是 404。蓝图的测试不需要启动整个应用,也不会被别的蓝图的钩子影响。with client: 里请求之后还能读 g.shop_hook = ran,可以直接断言钩子的效果。", t=tl(S(1)), done=lidx(S(1), 'isolated', 'unregistered', 'RESULT g'), kv=KV([['最小应用 + 单个蓝图', '蓝图的单元测试'], ['未注册', '404']], ['最小应用 + 单个蓝图'])),
]
A = mkartf('f159', 159, 'Flask,测试,Blueprint,蓝图,pytest,真实验证,动画演示',
    '用真实的 pytest 运行 9 个 Flask Blueprint 测试:最小应用只注册一个蓝图、端点名带蓝图前缀与 url_for 的点写法、蓝图钩子只作用于自己的请求、注册时覆盖 url_prefix、同一蓝图注册两次要 name、隔离的应用里路由表只含该蓝图。',
    '蓝图怎么单独测?端点名与 url_for 有什么规则?蓝图的钩子会不会影响别的路由?同一个蓝图能注册两次吗?这篇用一组真实运行的 pytest 用例把这些行为逐项验证。',
    [('9 passed', '本篇真实运行的 Blueprint 测试数'), ('shop.items', 'request.endpoint 与 url_for 里蓝图视图的完整端点名'), ('name=', '同一个蓝图注册第二次必须提供的参数')],
    [('最小应用里的蓝图', '<p>上一篇:<a href="flask-test-error-handler.html">测试异常处理器</a>;下一篇:<a href="flask-request-timing.html">请求耗时统计</a>(第 160 篇起是性能部分)。</p>')],
    steps, [ENV_F + '。pytest 9.1.1', '没有验证:蓝图嵌套(蓝图里注册蓝图)、蓝图的 template_folder 与 static_folder 在测试里的行为、蓝图级的 errorhandler(第 102、158 篇看过)、蓝图的 CLI 命令测试(test_cli_runner)'], '测试 Blueprint', panels=[('t', 'term', '实验输出'), ('kv', 'kv', '要点')])
