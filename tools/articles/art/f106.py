from lib import *
S = SS('f106')
R = J('f106')
steps = [
    step("方法与状态码:POST /users/ 创建,201 加 Location: /users/2;PUT /users/2 整体替换,200;PATCH 只改给出的字段(加上 email,name 保留),200;再 PUT 一次 {name} 时 email 没了——PUT 是整体替换;DELETE 返回 204 与空正文;再 DELETE 一次仍是 204(这个实现把「删不存在的」也当成功,所以是幂等的),之后 GET 是 404。", t=tl(S(1)), done=lidx(S(1), 'POST /users/', 'PUT /users/2 {name}', 'PATCH', 'DELETE'), mark=lidx(S(1), '再 PUT', '再 DELETE'), kv=KV([['POST', '201 + Location'], ['PUT', '整体替换'], ['PATCH', '部分更新'], ['DELETE', '204']], ['POST'])),
    step("405 与 OPTIONS:对只定义了 GET 与 POST 的 /users/ 发 DELETE 得 405,Allow 头列出 OPTIONS, HEAD, POST, GET;OPTIONS /users/1 返回 200,Allow 是 PATCH, DELETE, OPTIONS, PUT, HEAD, GET;GET 路由自动支持 HEAD(正文长度 0,但 Content-Length 头是 22,和对应 GET 响应一致)。", t=tl(S(2)), done=lidx(S(2), 'OPTIONS', 'HEAD'), mark=lidx(S(2), 'DELETE /users/ →'), kv=KV([['405', 'Allow 头列出支持的方法'], ['OPTIONS / HEAD', 'Flask 自动处理']], ['405'])),
    step("尾部斜杠:路由定义成 /users/(带斜杠)时,请求 /users 得到 308 重定向到 http://localhost/users/(GET 和 POST 都是,308 保持原方法与请求体);请求 /users/ 是 200。路由定义成 /ping(不带斜杠)时,请求 /ping/ 是 404。所以带不带斜杠要在设计时统一。", t=tl(S(3)), done=lidx(S(3), 'GET   /users/', 'GET   /ping '), mark=lidx(S(3), '308', '/ping/'), kv=KV([['规则带斜杠', '无斜杠请求 → 308'], ['规则不带斜杠', '带斜杠请求 → 404']], ['规则带斜杠'])),
    step("路由优先级:/users/me(静态)优先于 /users/<name>,/users/ann 走 <name>,/users/1 走 <int:uid>(转换器更具体的规则排在字符串转换器前面),三者互不抢。", t=tl(S(4)), done=lidx(S(4), '/users/me', '/users/ann', '/users/1'), kv=KV([['静态路径', '优先'], ['int 转换器', '优先于 <name>']], ['静态路径'])),
    step("转换器:<uuid:i> 把合法 UUID 转成 UUID 对象,not-a-uuid 是 404;<path:p> 能匹配带斜杠的 a/b/c.txt;/users/1/posts/2 匹配,/users/x/posts/2 因为 x 不是整数是 404。", t=tl(S(5)), done=lidx(S(5), '12345678', 'c.txt', '/users/1/posts/2'), mark=lidx(S(5), 'not-a-uuid', '/users/x/'), kv=KV([['uuid / int', '格式不对 → 404'], ['path', '可含斜杠']], ['uuid / int'])),
    step("嵌套资源:路由只管格式,/v/users/2/posts/5 能匹配,但帖子 5 属于用户 1,视图里自己校验归属才返回 404;/v/users/1/posts/5 是 200。不校验归属就是越权访问。", t=tl(S(6)), done=lidx(S(6), '/v/users/1/posts/5'), mark=lidx(S(6), '/v/users/2/posts/5'), kv=KV([['路由', '只校验格式'], ['归属', '视图里自己校验']], ['归属'])),
    step("POST 不幂等:同一个创建请求发两次,用户数从 1 变成 3(多了 2 条);PUT /users/50 发两次,第一次之后 4 个、第二次之后仍是 4 个。网络重试时 POST 会产生重复数据,这就是下一篇 Idempotency-Key 要解决的问题。", t=tl(S(7)), mark=lidx(S(7), 'POST 两次'), done=lidx(S(7), 'PUT /users/50'), kv=KV([['POST', '重复发送 = 重复创建'], ['PUT', '重复发送结果相同']], ['POST'])),
]
A = mkartf('f106', 106, 'Flask,RESTful,URL设计,HTTP方法,真实验证,动画演示',
    '实测 Flask 里 RESTful URL 设计的细节:POST 201 加 Location、PUT 整体替换与 PATCH 部分更新、DELETE 204、405 的 Allow 头与自动的 OPTIONS 和 HEAD、尾部斜杠的 308 与 404、静态路径优先于动态路径、转换器的匹配、嵌套资源要自己校验归属、POST 不幂等而 PUT 幂等。',
    'RESTful 的 URL 与方法在 Flask 里是怎么落地的?尾部斜杠到底会怎样?静态路径和动态路径冲突谁赢?嵌套资源要注意什么?这篇用 test_client 把每个细节逐个验证。',
    [('308', '访问 /users(规则是 /users/)时的重定向状态码,保持 POST 方法'), ('404', '规则没有斜杠而请求带斜杠时的状态码'), ('2 条', 'POST 同一请求发两次多出的用户数')],
    [('方法与状态码', '<p>上一篇:<a href="flask-api-versioning.html">API 版本控制</a>;下一篇:<a href="flask-idempotency-key.html">Idempotency-Key</a>。</p>'), ('405 与 OPTIONS', None), ('尾部斜杠', None), ('路由优先级', None), ('转换器', None), ('嵌套资源', None), ('幂等性', None)],
    steps, [ENV_F, '没有验证:strict_slashes=False 的行为、真实 HTTP 客户端对 308 的处理差异、HATEOAS 与超媒体链接、批量操作与子资源动作(如 /orders/1/cancel)的命名约定、Flask-RESTful 与 MethodView 的写法'], 'RESTful URL 设计')
