from lib import *
S = SS('n4')
steps = [
    step("18 组注册里 10 组 panic、8 组成功。成功的包括:/users/new 与 /users/:id 两个顺序都行、:id 后面接 /a 和 /b、根上的 /about 与 /:lang、/a/:id 与 /a/b/c。panic 的包括:同位置参数改名(:id → :uid)、根上 /:a 与 /:b/x、:id 与 *p、*p 与静态 /a/b、同一路由注册两次(哪怕带不同参数名)、空参数名 /u/:、一段里两个通配符 :a:b、*p 之后还有路径、没有斜杠的 /s*p。", t=tl(S(1)), mark=lidx(S(1), '✗'), done=lidx(S(1), '✓'), b=bars([['注册成功', 8, '8 组'], ['注册时 panic', 10, '10 组']], 18, done=[0], mark=[1]), kv=KV([['10 / 18', '在注册时 panic'], ['静态 + 参数', '两个顺序都能共存'], ['同一路由两次', 'handlers are already registered']], ['10 / 18'])),
    step("panic 发生在 r.GET 那一行:先打印“第一条路由注册完成,下一行会 panic”,recover 到的栈顶四帧依次是 (*node).addRoute、(*Engine).addRoute、(*RouterGroup).handle、(*RouterGroup).GET——程序启动注册路由时就崩了,而不是等到某个请求到来。“不会打印到这里”那一行没有出现。", t=tl(S(2)), mark=lidx(S(2), 'recover:', '(*node).addRoute'), done=lidx(S(2), '(*RouterGroup).GET', '第一条路由注册完成'), kv=KV([['栈顶', 'node.addRoute → Engine.addRoute → RouterGroup.handle → GET'], ['时机', '注册路由时,不是请求时']], ['时机'])),
    step("静态与参数共存时的选择:/files/a/b、/files/:id/c、/files/new、/files/:id 四条路由并存。/files/a/b → 静态;/files/a/c 先走进静态的 a 分支,没有 c,退回去匹配 /files/:id/c,id=a;/files/new → 静态;/files/newer → :id;/files/new/c 同样先走进 new 分支再退回,id=new;/files/a/d 没有任何路由匹配,404。", t=tl(S(3)), mark=lidx(S(3), '/files/a/c', '/files/new/c'), done=lidx(S(3), '/files/a/b   ', '/files/new  ', '/files/a/d'), kv=KV([['/files/a/c', '先走静态分支 a,走不通,回溯到 :id'], ['/files/new/c', 'id=new(回溯)'], ['/files/a/d', '404']], ['/files/new/c'])),
    step("panic 的信息都是 tree.go 里拼出来的:第 232 行和 355 行拼“conflicts with existing wildcard / path segment”,243 行是 handlers are already registered,298、304、345、363 行分别是一段里多个通配符、通配符没有名字、catch-all 不在末尾、catch-all 前没有 /;另外 gin.go 365–367 行断言路径以 / 开头、方法不为空、至少有一个 handler。", t=tl(S(4)), mark=lidx(S(4), 'conflicts with existing'), done=lidx(S(4), 'handlers are already registered', 'only one wildcard', 'catch-all routes', 'gin.go: 365'), kv=KV([['tree.go', '7 处 panic 文案'], ['gin.go 365–367', '路径、方法、handler 的断言']], ['tree.go'])),
]
A = mkartn('n4', 4, 'Gin,路由冲突,panic,回溯,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里把 18 组路由注册组合逐个试一遍,列出 panic 的原文:10 组 panic,静态与参数两个顺序都能共存;panic 发生在注册路由的那一行;静态与参数共存时请求先走静态分支,走不通再回溯到参数分支。',
    '/users/new 和 /users/:id 能放在同一个 Gin 里吗?哪些组合会 panic、panic 的原文长什么样、静态和参数共存后请求怎么选?这篇把 18 种组合逐个注册,再用请求验证回溯。',
    [('10 / 18', '18 组注册里在注册时 panic 的组数'), ('4 帧', 'panic 栈顶:addRoute → addRoute → handle → GET'), ('id=new', '/files/new/c 回溯到 :id 之后的参数值')],
    [('18 种组合', '<p>可以共存的:静态与 <code>:id</code>(两个顺序)、<code>:id</code> 后接不同静态段、根上的 <code>/about</code> 与 <code>/:lang</code>、<code>/a/:id</code> 与更长的 <code>/a/b/c</code>。会 panic 的:同一位置换一个通配符(名字不同也算)、通配符种类不同、与 catch-all 同位置的静态路径、同一路由注册两次、不合法的通配符写法。</p><p>另外 <code>RouterGroup.GET("users")</code> 虽然没有开头的斜杠,路由表里登记的是 <code>/users</code>——group 会把路径和 basePath 拼起来。</p>'),
     ('panic 在注册时,不在请求时', '<p>冲突检查在 <code>addRoute</code> 里,所以问题在启动阶段就暴露:栈顶是 <code>(*node).addRoute</code>,往上是 <code>Engine.addRoute</code>、<code>RouterGroup.handle</code>、<code>RouterGroup.GET</code>。这是个好事——路由冲突不会拖到线上流量到来才发现。</p>'),
     ('共存之后请求怎么选', '<p>静态节点优先:先在 <code>indices</code> 里找下一个字节,找到就进去;如果后面走不通,Gin 会回到之前记下的分叉点(源码里叫 <code>skippedNodes</code>),改走通配符子节点。所以 <code>/files/a/c</code> 虽然先进入了 <code>/files/a/b</code> 的静态分支,最终命中的是 <code>/files/:id/c</code>,<code>id=a</code>。没有任何路由匹配的 <code>/files/a/d</code> 才是 404。</p>'),
     ('panic 文案在哪里', '<p>冲突与格式错误的文案集中在 <code>tree.go</code> 的 <code>addRoute</code> 与 <code>insertChild</code>;路径要以 / 开头、方法不能为空、至少一个 handler 是 <code>gin.go</code> 里的断言。</p>')],
    steps,
    [ENV_N_GIN + '。DumpTree 之外没有改动 Gin;所有注册组合都在一个新的 gin.New() 上进行,panic 用 recover 捕获;请求用 httptest 直接调用 ServeHTTP;每种情形各一次',
     '没有验证:更早版本的 Gin(比如 1.6 以前)里静态与参数是否冲突(只测了 v1.12.0);回溯在很深的嵌套路由里的最坏耗时;Group 里注册冲突路由时的 panic 文案是否带 group 前缀'],
    '路由冲突')
