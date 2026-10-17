from lib import *
S = SS('f17')
R = J('f17')
steps = [
    step("静态路径优先于动态路径,与注册顺序无关:/users/<name> 与 /users/me 两条规则,无论谁先注册,GET /users/me 都进入静态规则 fixed,GET /users/ann 进入动态规则(name = 'ann')。", t=tl(S(1)), mark=lidx(S(1), '/users/me → fixed'), done=lidx(S(1), '两种顺序结果相同'), kv=KV([['/users/me', '静态规则'], ['/users/ann', '动态规则 name=ann'], ['注册顺序', '不影响']], ['注册顺序'])),
    step("转换器的优先级:/<x> 与 /<int:x> 同时存在,GET /123 进入 int 规则(x = 123),/abc 与 /-5 进入 string 规则(因为 int 默认不匹配负号);/files/<name> 与 /files/<path:p> 同时存在,/files/a 进入 name,/files/a/b 进入 path。两种注册顺序结果都相同。", t=tl(S(2)), mark=lidx(S(2), '/123 → int', '/files/a/b → path'), done=lidx(S(2), '两种顺序结果相同'), kv=KV([['/123', 'int 规则'], ['/abc、/-5', 'string 规则'], ['/files/a/b', 'path 规则']], ['/123'])),
    step("多个动态段:/<a>/<b>、/<a>/x、/api/<b> 三条规则下,/1/x 进入 /<a>/x;/1/y 进入 /<a>/<b>;/api/x 与 /api/zz 都进入 /api/<b>(静态前缀 api 优先)。两种注册顺序结果相同:匹配时先比较静态部分,再比较动态部分。", t=tl(S(3)), mark=lidx(S(3), '/1/x → ax', '/api/x → api_b'), done=lidx(S(3), '两种顺序结果相同'), kv=KV([['/1/x', '/<a>/x'], ['/1/y', '/<a>/<b>'], ['/api/x', '/api/<b>']], ['/api/x'])),
    step("完全相同的规则注册两次时,先注册的生效:先 first 后 second,GET /dup 得到 first;先 second 后 first,得到 second。没有报错,后注册的那条永远不会被匹配到 —— 这是 url_map 层面的行为,只有端点名相同才会触发 endpoint 冲突报错。", t=tl(S(4)), mark=lidx(S(4), '先注册 first', '先注册 second'), kv=KV([['先 first 后 second', 'first'], ['先 second 后 first', 'second']], ['先 first 后 second'])),
    step("同一路径不同方法挂在不同端点:GET /x → 200「GET 端点」,POST /x → 200「POST 端点」,PUT 与 DELETE → 405。方法不在任何一个端点的 methods 里时得到 405 而不是 404。", t=tl(S(5)), done=lidx(S(5), 'GET    /x', 'POST   /x'), mark=lidx(S(5), 'PUT', 'DELETE'), kv=KV([['GET /x', '200 GET 端点'], ['POST /x', '200 POST 端点'], ['PUT、DELETE', '405']], ['PUT、DELETE'])),
    step("iter_rules 按注册顺序列出(['/users/<name>', '/users/me', '/<x>', '/<int:x>']),并不按匹配优先级排序。每条规则被拆成片段并带权重(私有属性 Rule._parts):静态片段 users 的权重是 (0, -5)、me 是 (0, -2),动态片段 string 是 100,int 是 50 —— 数值越小越优先,所以 int 先于 string;path 转换器的权重是 200。", t=tl(S(6)), done=lidx(S(6), 'iter_rules 顺序'), mark=lidx(S(6), '[动态 [50]]', '[动态 [100]]'), kv=KV([['int', '权重 50'], ['string / uuid / any', '权重 100'], ['path', '权重 200']], ['int'])),
    step("匹配器是 StateMachineMatcher(状态机),merge_slashes 默认为 True:GET /users//me(两个斜杠)得到 308,Location 是 http://localhost/users/me,不是 404。", t=tl(S(7)), done=lidx(S(7), 'StateMachineMatcher'), mark=lidx(S(7), '308'), kv=KV([['匹配器', 'StateMachineMatcher'], ['merge_slashes', 'True'], ['/users//me', '308 → /users/me']], ['merge_slashes'])),
]
A = mkartf('f17', 17, 'Flask,路由匹配,Werkzeug,URL Rule,真实验证,动画演示',
    '实测 Flask 路由的匹配顺序:静态路径优先于动态路径、int 优先于 string、path 最宽松、静态前缀优先,都与注册顺序无关;完全相同的规则先注册的生效;同路径不同方法按方法分发;匹配器是状态机,权重 int=50、string=100、path=200。',
    '同一个 URL 同时能匹配好几条规则时,Flask 选哪一条?和写代码的先后顺序有关吗?这篇每种情形都用两种注册顺序各跑一遍。',
    [('50 / 100 / 200', 'int / string / path 转换器的权重(越小越优先)'), ('2 种', '每个实验用的注册顺序(正序与倒序),结果都相同'), ('StateMachineMatcher', '本机 Werkzeug 3.1.9 的路由匹配器类型')],
    [('静态优先于动态', '<p>上一篇:<a href="flask-route-registration.html">@app.route() 如何注册路由</a>;下一篇:<a href="flask-url-converters.html">path、int、float、uuid 转换器</a>。</p>'), ('转换器的优先级', None), ('多个动态段', None), ('重复的规则', None), ('同路径不同方法', None), ('权重', None), ('匹配器与斜杠合并', None)],
    steps, [ENV_F + '。权重取自私有属性 Rule._parts,版本不同可能变化', '没有验证:Werkzeug 2.2 之前的旧匹配器(按排序后的规则列表匹配)的行为、host_matching 与 subdomain 对顺序的影响、defaults 与 redirect_to 规则的匹配、大量规则(几千条)时的匹配耗时'], '匹配顺序')
