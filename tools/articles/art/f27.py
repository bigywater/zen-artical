from lib import *
S = SS('f27')
R = J('f27')
steps = [
    step("url_prefix 的两个位置:写在 Blueprint(url_prefix='/a') 里,规则是 /a/x;写在 register_blueprint(url_prefix='/b') 里,规则是 /b/x;两处都写,注册时的覆盖定义时的(规则是 /b/x);都不写是 /x。", t=tl(S(1)), done=lidx(S(1), 'Blueprint(url_prefix="/a")', 'register_blueprint(url_prefix="/b")'), mark=lidx(S(1), '两处都写'), kv=KV([['只在 Blueprint 里写 /a', '/a/x'], ['只在注册时写 /b', '/b/x'], ['两处都写', '/b/x(注册时的赢)']], ['两处都写'])),
    step("拼接时的斜杠:前缀 /api + 路由 / → /api/;前缀 /api + 路由 \"\"(空串)→ /api;前缀 /api/ + 路由 /x → /api/x(尾斜杠被处理掉);前缀 /api + 路由 x(无前导斜杠)→ /api/x;但前缀写成 api(没有前导斜杠)+ 路由 /x 抛 ValueError「URL rule 'api/x' must start with a slash.」。", t=tl(S(2)), done=lidx(S(2), '前缀 /api + 路由 /  ', '前缀 /api/ + 路由 /x'), mark=lidx(S(2), 'ValueError', '空串'), kv=KV([['/api + /', '/api/'], ['/api + \"\"', '/api'], ['/api/ + /x', '/api/x'], ['api + /x', 'ValueError']], ['api + /x'])),
    step("两种写法的访问行为不同:路由是 \"/\"(规则 /api/)时,GET /api → 308,GET /api/ → 200;路由是 \"\"(规则 /api)时,GET /api → 200,GET /api/ → 404。是否带尾斜杠的规则见第 20 篇。", t=tl(S(3)), done=lidx(S(3), '路由 "/"', '路由 ""'), kv=KV([['路由 \"/\"', '/api → 308;/api/ → 200'], ['路由 \"\"', '/api → 200;/api/ → 404']], ['路由 \"\"'])),
    step("嵌套蓝图的前缀逐层叠加:父 /v1 + 子 /users → /v1/users/<int:i>;注册时覆盖:父蓝图注册时改成 /v2、子蓝图注册到父蓝图时改成 /people,得到 /v2/people/<int:i>。", t=tl(S(4)), done=lidx(S(4), 'v1 + users', '父蓝图注册时改成'), kv=KV([['定义时的前缀', '/v1 + /users'], ['注册时覆盖', '/v2 + /people']], ['注册时覆盖'])),
    step("同一个蓝图用不同前缀注册两次(第二次用 name='multi2' 区分):url_for('multi.ping') → /v1/ping,url_for('multi2.ping') → /v2/ping。endpoint 的前缀是注册时的 name,不是蓝图自己的名字。", t=tl(S(5)), done=lidx(S(5), "url_for('multi.ping')"), kv=KV([['multi.ping', '/v1/ping'], ['multi2.ping', '/v2/ping']], ['multi2.ping'])),
    step("前缀有包含关系的两个蓝图(/a 与 /a/b)声明了同一个最终 URL /a/b/c:规则列表里出现两条 /a/b/c,GET /a/b/c 得到先注册的 one。前缀不会自动「划地盘」,冲突规则同第 25 篇:先注册的赢。", t=tl(S(6)), done=lidx(S(6), "规则:"), kv=KV([['两个蓝图的最终 URL', '都是 /a/b/c'], ['GET /a/b/c', 'one(先注册的)']], ['GET /a/b/c'])),
]
A = mkartf('f27', 27, 'Flask,Blueprint,url_prefix,路由,真实验证,动画演示',
    '实测 Blueprint 的 URL 前缀:定义时与注册时的 url_prefix(注册时覆盖);与 /、空串、尾斜杠的拼接结果与访问行为;嵌套蓝图逐层叠加或覆盖;同一蓝图多前缀注册的 endpoint;前缀包含关系下的重复规则。',
    'url_prefix 写在哪里?和路由的斜杠怎么拼?嵌套时怎么叠加?这篇把各种组合的最终 URL 与访问结果都打印出来。',
    [('/b/x', 'Blueprint 定义 /a、注册时给 /b,最终规则'), ('308 / 200', '路由 "/" 时 /api 与 /api/ 的状态码'), ('200 / 404', '路由 "" 时 /api 与 /api/ 的状态码')],
    [('定义时与注册时的前缀', '<p>上一篇:<a href="flask-blueprint-routes.html">Blueprint 路由注册</a>;下一篇:<a href="flask-blueprint-static-templates.html">Blueprint 的静态文件和模板目录</a>。</p>'), ('斜杠的拼接', None), ('访问行为', None), ('嵌套蓝图', None), ('多前缀注册', None), ('前缀重叠', None)],
    steps, [ENV_F, '没有验证:subdomain 参数与前缀的组合、url_prefix 为空串与 None 的区别、第三方扩展注册蓝图时的前缀约定'], 'url_prefix')
