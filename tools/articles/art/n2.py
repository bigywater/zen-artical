from lib import *
S = SS('n2')
steps = [
    step("incrementChildPrio 只有 20 行:每有一条路由经过第 pos 个子节点,它的 priority 加 1;然后在 for 里只要前一个兄弟的 priority 严格小于它(cs[newPos-1].priority < prio),就和前一个交换,最后把 indices 字符串里对应的那个字节挪到同样的位置。严格小于意味着平局不交换。", t=tl(S(1)), mark=lidx(S(1), 'cs[pos].priority++', 'cs[newPos-1].priority < prio'), done=lidx(S(1), 'n.indices = n.indices[:newPos]'), kv=KV([['priority++', '每多一条路由经过该子节点就加 1'], ['冒泡条件', '前一个兄弟的 priority 严格小于它'], ['indices', '跟着 children 一起重排']], ['冒泡条件'])),
    step("按 /a/1、/b/1、/c/1、/b/2、/c/2、/c/3、/c/4、/a/2、/a/3、/a/4、/a/5 的顺序一条条注册,看根节点的 indices:ab → abc;/b/2 之后 b 有 2 条超过 a 的 1 条,变成 bac;/c/2 之后 bca;/c/3 之后 c 有 3 条,变成 cba;/a/3 之后 a 有 3 条超过 b 的 2 条,变成 cab;/a/5 之后 a 有 5 条超过 c 的 4 条,最终 acb。", t=tl(S(2)), mark=lidx(S(2), 'indices="bac"', 'indices="cba"', 'indices="cab"'), done=lidx(S(2), 'indices="acb"'), b=bars([['a/ 子树的路由数', 5, '5'], ['c/ 子树的路由数', 4, '4'], ['b/ 子树的路由数', 2, '2']], 5, done=[0], mark=[1, 2]), kv=KV([['最终顺序', 'a(5) → c(4) → b(2)'], ['/b/2 之后', 'abc → bac'], ['/a/5 之后', 'cab → acb']], ['最终顺序'])),
    step("priority 数的是子树里注册了多少条路由,与访问无关:a 组 20 条、z 组 1 条(/z/hot),indices=\"az\"。对 /z/hot 连发 200000 次请求之后,把整棵树(23 个节点)再打印一遍,和请求前逐字节相同。Gin 在运行时从不重排这棵树。", t=tl(S(3)), mark=lidx(S(3), 'prio=21 indices="az"', '"z/hot" [static prio=1'), done=lidx(S(3), '逐字节相同'), kv=KV([['priority', '子树里的路由条数'], ['20 万次请求之后', '树逐字节不变'], ['重排发生在', '注册路由的时候']], ['20 万次请求之后'])),
    step("顺序到底值多少?两棵形状相同的树都查 /z/item0:树 A 里每个首字母 1 条路由,z 在 indices 的第 26 位:32.6 ns;树 B 里 z 组有 10 条,z 排第 1 位:27.7 ns。对照组 /a/item0:树 A 里 a 排第 1 位 24.3 ns。同一棵树里,第 26 位比第 1 位多约 8 ns(一次 ServeHTTP 的总耗时,两轮结果一致)。", t=tl(S(4)), mark=lidx(S(4), 'A: GET /z/item0'), done=lidx(S(4), 'B: GET /z/item0', 'A: GET /a/item0'), b=bars([['A:/z/item0(第 26 位)', 32.6, '32.6 ns'], ['B:/z/item0(第 1 位)', 27.7, '27.7 ns'], ['A:/a/item0(第 1 位)', 24.3, '24.3 ns'], ['B:/a/item0(第 2 位)', 24.4, '24.4 ns']], 32.6, mark=[0], done=[1, 2, 3]), kv=KV([['第 26 位 vs 第 1 位', '32.6 ns vs 24.3 ns,差约 8 ns'], ['每个兄弟', '约 0.3 ns(25 次字节比较)'], ['注意', 'B 里 z 子树更深,所以 B 的 z 不是 24 ns']], ['第 26 位 vs 第 1 位'])),
]
A = mkartn('n2', 2, 'Gin,路由树,节点优先级,priority,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测节点优先级:priority 是子树里的路由条数,注册时让条数多的子节点冒泡到 indices 前面(平局不交换);对一条路由发 20 万次请求后树逐字节不变;26 个兄弟节点里排在末位比排在首位多约 8 ns。',
    '常有人说 Gin 的路由“把常用的路由排在前面”。这篇用逐条注册看 indices 怎么重排,再对 20 万次请求前后的整棵树做对比,最后量出排在第 26 位和第 1 位到底差多少纳秒,看这个优化究竟优化了什么。',
    [('abc → bac → cba → cab → acb', '依次注册 11 条路由时根节点 indices 的变化'), ('0 处变化', '对 /z/hot 发 20 万次请求前后整棵树的差异'), ('≈ 8 ns', '第 26 位与第 1 位的查找耗时差(32.6 vs 24.3 ns)')],
    [('冒泡的规则', '<p>每注册一条经过某个子节点的路由,<code>incrementChildPrio</code> 先把它的 <code>priority</code> 加 1,再和前面的兄弟比:前一个兄弟的 priority <b>严格小于</b>它就换位置,并同步改写 <code>indices</code>。这一步只在注册时发生。</p>'),
     ('逐条注册看 indices 的变化', '<p>indices 记录的是兄弟节点按 priority 从大到小排列的首字节。注册 <code>/b/2</code> 让 b 的 2 条超过 a 的 1 条(abc → bac);注册 <code>/c/3</code> 让 c 的 3 条排到最前(cba);<code>/a/3</code> 让 a 的 3 条超过 b 的 2 条(cab);最后 <code>/a/5</code> 让 a 的 5 条超过 c 的 4 条(acb)。平局时(如 <code>/c/4</code>、<code>/a/2</code> 之后)顺序保持不变。</p>'),
     ('不是“访问次数”', '<p>文章标题里的“常用路由”容易误导:Gin 并不统计访问。priority 是子树里的路由条数,假设“路由多的分支更可能被访问”。实验里对 <code>/z/hot</code> 发了 20 万次请求,整棵树和请求前逐字节相同,<code>z</code> 仍然排在 <code>a</code>(20 条路由)后面。</p>'),
     ('排在前面能省多少', '<p>查找时用请求路径的下一个字节在 <code>indices</code> 里线性扫描。两棵形状相同的树,查同一条路由,它在 indices 里排第 26 位比排第 1 位多约 8 ns,折合每个兄弟 0.3 ns 左右。一次完整的 <code>ServeHTTP</code> 本身只有二三十纳秒,所以兄弟多的时候这个顺序才有一点意义;树 B 里 z 的数字(27.7 ns)比树 A 的 a(24.3 ns)高,是因为 z 子树里多了一层(item0…item9),不是顺序的问题。</p>')],
    steps,
    [ENV_N_GIN + '。DumpTree 是源码副本里加的只读打印函数;基准用 testing.Benchmark,每个数字是 9 轮的中位数,整个实验跑了两轮,两轮的中位数相差不超过 0.1 ns;被测的是 Engine.ServeHTTP 加一个丢弃输出的 ResponseWriter,不含网络',
     '没有验证:真实业务路由表(几百条、带参数)里顺序对延迟的影响;更多兄弟节点(几百个)时线性扫描的耗时;不同 CPU 架构上的数字;为什么 Gin 选“路由条数”而不是真实访问量做优先级(只能从源码看出它这样做,设计动机我没有查证)'],
    '节点优先级')
