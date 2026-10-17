from lib import *
S = SS('n10')
steps = [
    step("Engine 里存路由的是 methodTrees,一个 []methodTree,每项只有 method 和 root 两个字段。按方法找树的 get 就是一个 for 循环:逐项比较 tree.method == method,相等返回 root,走完返回 nil——是线性扫描,不是 map。", t=tl(S(1)), mark=lidx(S(1), 'type methodTree struct', 'for _, tree := range trees', 'if tree.method == method'), done=lidx(S(1), 'return tree.root', 'return nil'), kv=KV([['methodTree', 'method + root,两个字段'], ['查找', 'for 循环逐个比较方法名'], ['找不到', '返回 nil']], ['查找'])),
    step("注册 GET /users/:id、POST /users、GET /users、POST /users/:id/avatar、DELETE /users/:id 之后,有 3 棵树,顺序是 [GET POST DELETE](谁先被注册谁在前)。GET 树和 POST 树都有 \"/users\" 与 \":id\",但 POST 树的 :id 下多挂了 \"/avatar\",GET 树没有;DELETE 树只有一个 \"/users/\" 带 \":id\"——同一个路径在不同方法的树里互不相干。", t=tl(S(2)), mark=lidx(S(2), 'trees 的顺序', '"/avatar"'), done=lidx(S(2), '[GET]', '[POST]', '[DELETE]'), kv=KV([['3 棵树', 'GET、POST、DELETE'], ['顺序', '第一次注册该方法的顺序'], ['独立', 'POST 的 /avatar 不会出现在 GET 树里']], ['独立'])),
    step("r.Any 就是对 anyMethods 里每个方法调一次 handle,所以会创建 9 棵树:GET POST PUT PATCH HEAD OPTIONS DELETE CONNECT TRACE。Handle 对方法名用正则 ^[A-Z]+$ 检查:get(小写)、M-SEARCH(连字符)、空串、\"G E T\" 都 panic(http method … is not valid),PURGE、LINK 这种自定义大写方法可以注册。", t=tl(S(3)), mark=lidx(S(3), '共 9 棵', 'is not valid'), done=lidx(S(3), 'PURGE', 'LINK', 'for _, method := range anyMethods'), b=bars([['GET', 1, '1 棵'], ['Any', 9, '9 棵']], 9, mark=[1], done=[0]), kv=KV([['Any', '一次创建 9 棵树'], ['方法名', '必须全是大写英文字母'], ['自定义方法', 'PURGE、LINK 可以']], ['Any'])),
    step("因为是线性扫描,树越多、方法越靠后越慢。26 个自定义方法(XA…XZ)各一棵树:查第 1 棵的方法 21.7 ns,第 13 棵 50.8 ns,第 26 棵 84.2 ns(第二轮 21.8 / 51.0 / 84.3),折合每多一棵树约 2.5 ns。标准的 9 个方法里,GET 排得越靠前越好,Gin 的 trees 容量一开始就预留了 9 个。", t=tl(S(4)), mark=lidx(S(4), '第 26 棵树的方法', '第 13 棵树的方法'), done=lidx(S(4), '第 1 棵树的方法'), b=bars([['第 1 棵(XA)', 21.7, '21.7 ns'], ['第 13 棵(XM)', 50.8, '50.8 ns'], ['第 26 棵(XZ)', 84.2, '84.2 ns']], 84.2, done=[0], mark=[1, 2]), kv=KV([['每多一棵', '约 2.5 ns'], ['26 棵末位', '84.2 ns,是首位的 3.9 倍'], ['常见情形', '通常只有 GET / POST 等几棵,影响可以忽略']], ['每多一棵'])),
]
A = mkartn('n10', 10, 'Gin,路由树,HTTP方法,methodTrees,Any,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测每个 HTTP 方法一棵树:methodTrees 是线性扫描的切片;树的顺序是方法第一次被注册的顺序;r.Any 一次创建 9 棵树;Handle 要求方法名全是大写英文字母;26 棵方法树里,找第 26 棵比找第 1 棵慢约 62 ns。',
    '同一个路径用 GET 和 POST 注册,在 Gin 里是两棵完全独立的树。这篇看它们怎么存放、怎么找、顺序由什么决定,以及“方法很多”时线性扫描的代价到底有多大。',
    [('3 棵', 'GET、POST、DELETE 三种方法各注册后的树个数,彼此独立'), ('9 棵', 'r.Any 一次创建的方法树个数'), ('21.7 → 84.2 ns', '26 棵方法树里查第 1 棵与第 26 棵的耗时')],
    [('methodTrees:一个切片', '<p><code>Engine.trees</code> 是个切片,每项记录一个方法和它的根节点。找方法的树就是遍历切片比较字符串,找不到返回 nil——于是 <code>handleHTTPRequest</code> 里“这个方法没有树”和“这个方法的树里没有这条路由”是两种不同的失败路径。</p>'),
     ('每个方法各一棵', '<p>同一个路径在 GET、POST、DELETE 里互不影响:POST 注册了 <code>/users/:id/avatar</code>,GET 的树里就没有它。树的创建发生在该方法的第一次注册,所以 <code>trees</code> 的顺序是各方法第一次出现的顺序(405 的 Allow 头也是按这个顺序拼的)。</p>'),
     ('Any 与自定义方法', '<p><code>Any</code> 为 9 个标准方法各创建一棵树,如果只是想让 GET 和 POST 都能访问,分别注册这两个方法就够了,不必为 CONNECT、TRACE 也建树。自定义方法(比如缓存清理用的 PURGE)通过 <code>Handle</code> 注册,方法名必须全是大写英文字母,<code>M-SEARCH</code> 这种带连字符的会被拒绝。</p>'),
     ('线性扫描的代价', '<p>每多一棵树大约多 2.5 ns,26 棵树里最后一棵比第一棵慢约 62 ns。正常服务只有几个方法,GET 又通常最先注册,这个代价可以忽略;只有大量自定义方法、并且把热点方法放在最后注册时才需要关心。</p>')],
    steps,
    [ENV_N_GIN + '。DumpTree / TreeMethods 是源码副本里加的只读函数;基准是 testing.Benchmark 测 Engine.ServeHTTP(丢弃输出的 ResponseWriter),每个数字是 9 轮的中位数,整个实验跑了两轮;26 个自定义方法名是 XA…XZ,每个只注册 /x',
     '没有验证:每个方法树的内存开销;对比用 map 存方法树时的耗时(只测了现有的线性扫描);HTTP/2 / h2c 下方法的大小写处理'],
    '方法树')
