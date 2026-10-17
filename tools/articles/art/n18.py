from lib import *
S = SS('n18')
steps = [
    step("Abort 只有一行:c.index = abortIndex,而 abortIndex 是 math.MaxInt8 >> 1,也就是 63。Next 的循环条件是 c.index < len(c.handlers),所以 index 被设成 63 之后循环不再进行,后面的 handler 都不会执行;IsAborted 就是判断 c.index >= abortIndex。", t=tl(S(1)), mark=lidx(S(1), 'c.index = abortIndex', 'const abortIndex int8 = math.MaxInt8 >> 1'), done=lidx(S(1), 'for c.index < safeInt8(len(c.handlers))', 'c.index >= abortIndex'), kv=KV([['Abort', 'c.index = abortIndex(63)'], ['Next', '循环条件 index < len(handlers)'], ['IsAborted', 'index >= abortIndex']], ['Abort'])),
    step("Abort() 不是 return:中间件 M2 里调用 c.Abort() 之后,后面的 \"Abort() 之后这一行仍然执行\" 照样打印;之后再 c.Next() 什么也没发生;M2 的“后”半段和 M1 的“后”半段都照常执行,M1 里 IsAborted 为 true;handler 没有执行,响应是默认的 200 加空正文。", t=tl(S(2)), mark=lidx(S(2), 'Abort() 之后这一行仍然执行', 'IsAborted = true', '状态 200 正文 ""'), done=lidx(S(2), '[handler] 执行', 'IsAborted = false'), kv=KV([['Abort 之后', '本函数后面的代码照常执行'], ['外层中间件', '“后”半段照常执行'], ['默认响应', '没写任何东西就是 200 + 空']], ['Abort 之后'])),
    step("几种 Abort 写了什么:Abort() 只终止链,响应是 200 空;AbortWithStatus(401) 立刻写出 401(WriteHeaderNow);AbortWithStatusJSON(403, …) 写 403 和 JSON;AbortWithError(400, err) 写 400 空正文并把错误放进 c.Errors;Abort() 之后再 c.JSON(418, …) 状态是 418(还没写出,状态可改);AbortWithStatus(401) 之后再 c.JSON(200, …):状态仍是 401(已发出),但 JSON 正文照样写了出去。", t=tl(S(3)), mark=lidx(S(3), 'AbortWithStatus(401) 后 c.JSON(200', 'Abort() 后 c.JSON(418'), done=lidx(S(3), 'Abort()    ', 'AbortWithStatus(401)  ', 'AbortWithStatusJSON(403', 'AbortWithError(400'), kv=KV([['AbortWithStatus', '立刻写出状态行'], ['AbortWithStatus 之后再写 JSON', '状态不变,正文照样写出'], ['Abort 之后再写', '状态可改(还没写出)']], ['AbortWithStatus 之后再写 JSON'])),
    step("handler 数量上限:abortIndex=63 要求一条路由的 handler 总数小于 63(源码里 assert1(finalSize < int(abortIndex)))。实测:61、62 个能注册;63、64 个都 panic:too many handlers。含全局和 Group 的中间件,一条路由最多 62 个 handler。", t=tl(S(4)), mark=lidx(S(4), '63 个 handler', '64 个 handler'), done=lidx(S(4), '61 个 handler', '62 个 handler'), b=bars([['61 个', 61, '成功'], ['62 个', 62, '成功'], ['63 个', 63, 'panic'], ['64 个', 64, 'panic']], 64, done=[0, 1], mark=[2, 3]), kv=KV([['上限', '62 个(含全局与 Group 的中间件)'], ['超过', 'panic: too many handlers'], ['原因', 'index 是 int8,63 被留作 abortIndex']], ['上限'])),
]
A = mkartn('n18', 18, 'Gin,Abort,中间件,handler链,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 Abort 的语义:只是把 index 设成 63;调用之后当前函数继续往下执行,外层中间件的后半段照常执行;AbortWithStatus 立刻写出状态行,之后再写 JSON 状态也改不了;一条路由最多 62 个 handler,63 个就 panic。',
    'c.Abort() 之后,代码会立刻返回吗?后面的 handler、外层中间件的后半段会不会执行?AbortWithStatus、AbortWithStatusJSON、AbortWithError 各写了什么?这篇从 Next 的循环入手,用打印顺序和响应把这些行为一条条核对。',
    [('63', 'abortIndex 的值,即 math.MaxInt8 >> 1'), ('62 个', '一条路由最多能挂的 handler 个数(63 个会 panic)'), ('401 + 正文', 'AbortWithStatus(401) 之后再 c.JSON(200, …):状态仍是 401,JSON 照样写出')],
    [('Abort 只是改一个数', '<p><code>Next</code> 就是一个循环,条件是当前下标小于 handler 个数;<code>Abort</code> 把下标改成 63,循环自然结束。它没有 panic、没有 return,没有任何控制流跳转。</p>'),
     ('Abort 之后代码继续', '<p>调用 <code>c.Abort()</code> 之后,当前函数后面的代码照常执行,所以通常写成 <code>c.Abort(); return</code>。外层中间件的 <code>c.Next()</code> 之后的代码也照常执行,<code>c.IsAborted()</code> 在那里是 true,日志中间件可以用它来记录“被拦截”。</p>'),
     ('四种变体', '<p><code>AbortWithStatus</code> 会立刻 <code>WriteHeaderNow</code>,所以之后 <code>c.JSON(200, …)</code> 改不了状态,但仍会往已发出的响应里写正文,客户端会收到“状态 401、正文是 JSON”的怪响应。只想改状态再写正文的话,用 <code>c.Abort()</code> 加 <code>c.JSON(…)</code>,或者直接 <code>AbortWithStatusJSON</code>。</p>'),
     ('handler 上限', '<p>下标是 <code>int8</code>,63 被留给 abortIndex,所以一条路由连全局、Group、自己的 handler 在内最多 62 个,注册第 63 个时 panic。常见项目里远远用不到,但自动生成或循环拼接 handler 时要注意。</p>')],
    steps,
    [ENV_N_GIN + '。请求用 httptest 直接调用 ServeHTTP;每种情形各一次',
     '没有验证:Abort 与 gin.Recovery 的交互;在 Abort 之后继续 c.Next() 的所有边界情形(只验证了循环不再继续);超过 62 个 handler 是否有人会遇到(只验证了 panic 的文案)'],
    'Abort 语义')
