from lib import *
S = SS('n8')
steps = [
    step("默认 HandleMethodNotAllowed=false:/x 只注册了 GET、POST,DELETE /x 得到的是 404(PATCH /y/5、HEAD /x、OPTIONS /x 也是)。设成 true 之后,DELETE /x → 405 加 Allow: GET, POST;PATCH /y/5 与 GET /y/5 → 405,Allow: PUT;HEAD /x 与 OPTIONS /x 也是 405(Gin 不会自动把 GET 路由当作 HEAD,也不自动处理 OPTIONS);完全没有的路径 /nothing 仍是 404。", t=tl(S(1)), mark=lidx(S(1), 'HandleMethodNotAllowed = true'), done=lidx(S(1), 'DELETE  /x             → 405', 'PATCH   /y/5           → 405', 'HEAD    /x             → 405', 'DELETE  /nothing       → 404'), kv=KV([['默认', '方法不对 = 404'], ['打开后', '405 + Allow'], ['HEAD / OPTIONS', '不会自动处理,同样是 405']], ['HEAD / OPTIONS'])),
    step("判定的源码:只有 HandleMethodNotAllowed 开着才走这里;对所有“别的方法”的树各用 getValue 查一遍当前路径(传 nil 作为 params,不取参数),只要有一棵树有 handlers 就把它的方法名收进 allowed;allowed 非空就设置 Allow 头,走 allNoMethod 链返回 405,否则落到 404。", t=tl(S(2)), mark=lidx(S(2), 'if engine.HandleMethodNotAllowed && len(t) > 0', 'tree.root.getValue(rPath, nil, c.skippedNodes, unescape)'), done=lidx(S(2), 'allowed = append(allowed, tree.method)', 'c.writermem.Header().Set("Allow"'), kv=KV([['判定', '其它每个方法的树都查一次当前路径'], ['Allow', '把查到的方法名按树的顺序拼起来'], ['开销', '只发生在要返回 404 / 405 的请求上']], ['判定'])),
    step("Allow 里方法的顺序就是各方法的树被创建的顺序:先注册 GET、POST、PUT → Allow: GET, POST, PUT;先注册 PUT、POST、GET → Allow: PUT, POST, GET;DELETE、PATCH、GET、POST → Allow: DELETE, PATCH, GET, POST。r.TreeMethods()(源码副本里加的只读函数)印证了这一点。", t=tl(S(3)), mark=lidx(S(3), 'Allow: PUT, POST, GET', 'Allow: DELETE, PATCH, GET, POST'), done=lidx(S(3), 'Allow: GET, POST, PUT', 'TreeMethods'), kv=KV([['顺序', '谁先注册谁在前,不排序'], ['注意', 'RFC 不要求 Allow 有序']], ['顺序'])),
    step("NoMethod 处理器可以自定义 405 页面,并读到 Allow:DELETE /x → 405,JSON 里 allow=GET。405 只在“路径精确匹配”时判定,不做尾斜杠修正:路由只有 POST /dir/ 时,DELETE /dir/ 是 405(Allow: POST),而 DELETE /dir、GET /dir 都是 404,GET /dir/ 是 405。", t=tl(S(4)), mark=lidx(S(4), 'DELETE  /dir           → 404', 'GET     /dir           → 404'), done=lidx(S(4), 'DELETE  /x             → 405', 'DELETE  /dir/          → 405', 'GET     /dir/          → 405'), kv=KV([['NoMethod', '自定义 405 的 body,Allow 已设好'], ['/dir 与 /dir/', '405 只做精确匹配'], ['GET /dir', '404:GET 树里没有它']], ['405 只做精确匹配'])),
]
A = mkartn('n8', 8, 'Gin,HandleMethodNotAllowed,405,Allow,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 405:HandleMethodNotAllowed 默认 false,方法不对只是 404;打开后返回 405 与 Allow 头(HEAD、OPTIONS 也不会自动处理);判定方式是到其它方法的树里查同一路径;Allow 的顺序是方法树的创建顺序;405 只做精确匹配,不做尾斜杠修正。',
    '给 /x 注册了 GET 和 POST,然后 DELETE 它,Gin 默认返回 404,而不是 405。这篇打开 HandleMethodNotAllowed,看它怎么判定、Allow 怎么拼、顺序由什么决定,以及自定义的 NoMethod 页面能拿到什么。',
    [('404 → 405', '打开 HandleMethodNotAllowed 之后 DELETE /x 的状态码'), ('GET, POST', 'DELETE /x 的 Allow 头'), ('PUT, POST, GET', '先注册 PUT 再 POST 再 GET 时的 Allow')],
    [('默认是 404', '<p>HTTP 语义上“路径存在但方法不允许”应该是 405,但 Gin 默认关着这个功能。想要 405 就得 <code>r.HandleMethodNotAllowed = true</code>。注意 <code>HEAD</code> 和 <code>OPTIONS</code> 也不会被自动处理:没有显式注册 HEAD 的路由,HEAD 请求得到的是 405(打开时)或 404(默认)。</p>'),
     ('怎么判定', '<p>先在当前方法的树里找,找不到(也没触发重定向)才进入 405 的判断:遍历其它所有方法的树,看哪棵能匹配当前路径,匹配到的方法名组成 <code>Allow</code>。没有任何一棵能匹配就仍然是 404。这个遍历只发生在会返回 404/405 的请求上。</p>'),
     ('Allow 的顺序', '<p>顺序就是 <code>engine.trees</code> 的顺序,也就是每个 HTTP 方法第一次被注册的顺序,不排序、不去重。RFC 没有要求 Allow 有序,所以这只是个实现细节,但写测试断言 Allow 的字符串时要知道它取决于注册顺序。</p>'),
     ('NoMethod 与边界', '<p><code>r.NoMethod(handler)</code> 可以自定义 405 的响应体,进入 handler 时 <code>Allow</code> 头已经设好。405 只做精确匹配:路由是 <code>POST /dir/</code> 时,<code>DELETE /dir</code> 因为路径少了斜杠,得到的是 404,而不是 405 或重定向。</p>')],
    steps,
    [ENV_N_GIN + '。请求用 httptest 直接调用 ServeHTTP;TreeMethods 是源码副本里加的只读函数(zz_dump.go);每种情形各一次',
     '没有验证:Allow 里是否应该出现 HEAD(Gin 的行为是不自动加,没有对照其它框架);大量方法树(自定义方法)时 405 判定的耗时;NoMethod 与全局中间件的交互;CORS 预检请求(OPTIONS)在 405 打开时的处理(后面讲自定义方法的文章会再提)'],
    '405 判定')
