from lib import *
S = SS('n11')
steps = [
    step("FullPath() 只有两行:return c.fullPath。这个字段在两个地方改变:Context.reset(每个请求开头)把它清成空串(context.go 109 行),handleHTTPRequest 查到路由后把路由节点上存的 fullPath 赋给它(gin.go 721 行)。所以它是“注册时的模板”,不是从请求 URL 现拼的。", t=tl(S(1)), mark=lidx(S(1), 'return c.fullPath'), done=lidx(S(1), 'context.go: 109', 'gin.go: 721'), kv=KV([['reset', '每个请求开头清成空串'], ['查到路由', '赋值为节点上的 fullPath'], ['来源', '注册时的模板']], ['来源'])),
    step("在全局中间件里,c.Next() 之前就能读到 FullPath:/users/42 → \"/users/:id\";/files/a/b.txt → \"/files/*path\";Group 里的 /api/v1/orders/7/items/9 → \"/api/v1/orders/:oid/items/:iid\"。404 的 /nope 与 /users/ 都是空串。重定向的 /dir(301 到 /dir/)根本没经过全局中间件:6 个请求,中间件只执行了 5 次。", t=tl(S(2)), mark=lidx(S(2), '/nope', '/users/ ', '没有经过中间件', '中间件执行了 5 次'), done=lidx(S(2), '/users/42', '/files/a/b.txt', '/api/v1/orders/7/items/9'), kv=KV([['/users/42', '"/users/:id"'], ['/nope', '空串'], ['/dir 的 301', '不经过中间件']], ['/dir 的 301'])),
    step("监控标签的基数:10000 个不同用户 ID 的请求(外加订单子路径和扫描器请求)共 16000 个不同的 URL.Path,按 URL.Path 打标签会产生 16000 个不同的值;按 FullPath 只有 3 个:/users/:id 10000 次、/users/:id/orders/:oid 5000 次,以及未匹配(把空串换成的“(未匹配)”)1000 次。", t=tl(S(3)), mark=lidx(S(3), '按 URL.Path 打标签'), done=lidx(S(3), '按 FullPath 打标签'), b=bars([['按 URL.Path', 16000, '16000 个标签'], ['按 FullPath', 3, '3 个标签']], 16000, mark=[0], done=[1]), kv=KV([['URL.Path', '16000 个不同的值'], ['FullPath', '3 个'], ['空串', '换成固定标签,别直接当标签值']], ['FullPath'])),
    step("r.Routes() 给出路由表:每项有 Method、Path、Handler(函数名)和 HandlerFunc。Handler 取的是这条路由链上最后一个函数:getUser 显示 main.getUser,方法值显示 main.S.List-fm,匿名函数显示 main.main.func1;/api/x 注册在 g.Use(Logger) 之后,链上最后一个是 Recovery 返回的闭包,于是显示成 gin.CustomRecoveryWithWriter.func1,而不是 Logger。", t=tl(S(4)), mark=lidx(S(4), 'main.S.List-fm', 'CustomRecoveryWithWriter'), done=lidx(S(4), 'main.getUser', 'main.main.func1'), kv=KV([['Handler', '链上最后一个函数的名字'], ['匿名函数', 'main.main.func1'], ['方法值', 'main.S.List-fm']], ['Handler'])),
]
A = mkartn('n11', 11, 'Gin,FullPath,路由模板,监控,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 c.FullPath():返回注册时的路由模板,在中间件里 Next 之前就能取到;404 与被重定向的请求为空;用它做监控标签,16000 个不同 URL 只产生 3 个标签值;r.Routes() 里 Handler 取的是链上最后一个函数的名字。',
    '给接口打监控的时候,用 c.Request.URL.Path 当标签,每个用户 ID 都会变成一个新时间序列。c.FullPath() 返回的是路由模板 /users/:id,正好能避免这个问题。这篇验证它在哪些情况下有值、哪些情况下是空串。',
    [('16000 → 3', '按 URL.Path 与按 FullPath 打监控标签得到的不同值个数'), ('""', '404 请求里 c.FullPath() 的值'), ('5 / 6', '含一个重定向请求时,全局中间件被执行的次数 / 请求数')],
    [('FullPath 从哪来', '<p><code>FullPath()</code> 本身只是返回字段。它的值在请求开头被清空,查到路由后由路由节点上存着的 <code>fullPath</code>(注册时的完整模板,包含 Group 前缀)赋值,因此在所有中间件和 handler 里都可以取到——前提是路由已经匹配。</p>'),
     ('什么时候有值', '<p>匹配到路由时,不管是参数路由、通配路由还是 Group 里的路由,返回的都是带 <code>:oid</code>、<code>*path</code> 的模板。404 时是空串。被重定向的请求(尾斜杠 301)在进入全局中间件之前就返回了,所以中间件根本拿不到它,监控里看不到这类请求。</p>'),
     ('监控标签', '<p>标签的基数决定监控系统的开销:按 URL.Path 打标签,一万个用户就是一万个时间序列;按 FullPath 只有几条。404 时 FullPath 是空串,标签要换成一个固定值(比如“(未匹配)”);如果退回去用原始 URL.Path 兜底,扫描器乱扫的路径又会把基数撑爆。</p>'),
     ('Routes() 的 Handler', '<p><code>r.Routes()</code> 返回每条路由的方法、路径和 handler 名。名字来自链上<b>最后一个</b>函数,所以中间件不会出现在里面;如果一条路由的最后一个 handler 本身是中间件(比如上面的 <code>gin.Recovery()</code>),显示的就是中间件的闭包名。方法值带 <code>-fm</code> 后缀。</p>')],
    steps,
    [ENV_N_GIN + '。请求用 httptest 直接调用 ServeHTTP;监控标签实验用 10000 个用户 ID 的请求(每个偶数 ID 再发一个订单路径请求,每 10 个再发一个扫描器路径),标签用 map 计数;每种情形各一次',
     '没有验证:真实的 Prometheus 中间件(如 ginprometheus)怎么处理 FullPath;HandlerName 在内联或泛型函数上的显示;与 UseRawPath 同时使用时 FullPath 是否改变;参数名带特殊字符时的显示'],
    'FullPath')
