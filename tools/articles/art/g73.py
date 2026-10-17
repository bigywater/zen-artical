from lib import *
S = SS('g73')
steps = [
    step("key 用字符串会撞车:两个“包”都用字符串 \"id\" 作 key,包 A 取回的是包 B 写进去的值(被覆盖)。各自定义 struct{} 类型作 key:包 A 取回自己的值,包 B 也取回自己的。自定义类型 type S string 作 key:ctx.Value(\"id\") = <nil>,ctx.Value(S(\"id\")) 才能取到——类型不同就是不同的 key。", t=tl(S(1)), mark=lidx(S(1), '被包 B 覆盖'), done=lidx(S(1), 'struct{} 类型作 key', 'type S string'), kv=KV([['字符串 key', '不同包会互相覆盖'], ['各自的 struct{} 类型', '互不干扰'], ['type S string', '和普通 string 是不同的 key']], ['字符串 key'])),
    step("查找是沿着链表往上找:链长 1 / 10 / 100 / 1000 层时,查最早加入的 key(要走遍整条链)3 / 12 / 136 / 1331 ns/次;查最后加入的 key(就在最外层)3 / 3 / 3 / 9 ns/次。", t=tl(S(2)), mark=lidx(S(2), '链长 1000 层', '链长  100 层'), done=lidx(S(2), '链长    1 层', '链长   10 层'), b=bars([['1 层:最早的 key (ns)', 3, '3'], ['10 层', 12, '12'], ['100 层', 136, '136'], ['1000 层', 1331, '1331']], 1331, done=[0, 1], mark=[2, 3]), kv=KV([['最外层的 key', '3 ns,与层数无关'], ['最里层的 key', '随层数线性增加:1000 层 1331 ns']], ['最里层的 key'])),
    step("每次 WithValue 的分配:struct{} 类型的 key + 字符串值 1 次;指针 key 1 次;struct{} key + 整数值 1 次;自定义 int 类型 key 1 次;字符串 key 1 次。ctx.Value(key) 查找一层 0 次分配。也就是说每加一层就分配一个节点,不管 key 是什么类型(这组测量没有区分出 key 类型对分配的影响)。", t=tl(S(3)), mark=lidx(S(3), 'WithValue'), done=lidx(S(3), 'ctx.Value(key) 查找一层'), kv=KV([['WithValue', '每次 1 次分配'], ['Value', '0 次分配'], ['key 类型的影响', '本测法下没看出差别']], ['key 类型的影响'])),
    step("取回来的是 any,类型要自己断言:存进去的是 int 42,ctx.Value 取回 42(类型 int),断言成 string 会 panic:interface conversion: interface {} is int, not string。", t=tl(S(4)), mark=lidx(S(4), 'interface conversion'), done=lidx(S(4), '取回 42'), kv=KV([['存入', 'int 42'], ['取回', 'any,实际是 int'], ['错误断言', 'panic: interface conversion']], ['错误断言'])),
    step("文档与源码:go doc context.WithValue——Use context Values only for request-scoped data that transits processes and APIs, not for passing optional parameters to functions;key 必须可比较,不应该是 string 或其它内置类型,以免包之间碰撞;用户应该定义自己的 key 类型,常用 struct{} 以避免赋给接口时分配。context.go 的 value 函数:循环里遇到 *valueCtx 就比较 key == ctx.key,相等返回 ctx.val,否则 c = ctx.Context 继续往上。", t=tl(S(5)), done=lidx(S(5), 'request-scoped data', 'must be comparable'), mark=lidx(S(5), 'case *valueCtx', 'key == ctx.key', 'c = ctx.Context'), kv=KV([['该放什么', '跨进程/API 的请求范围数据,不是可选参数'], ['key 类型', '自定义类型,不用内置类型'], ['查找', '沿父链逐层比较 key']], ['该放什么'])),
]
A = mkartg('g73', 73, 'Go,context,WithValue,key,链表查找,真实验证,动画演示',
    '在 Go 1.27.1 里实测 context.Value:字符串 key 会被另一个包覆盖,自定义类型 key 互不干扰;查找沿父链线性往上找,1000 层时查最里层的 key 要 1331 ns、查最外层仍是 3–9 ns;每次 WithValue 一次分配;取回的是 any,断言错类型会 panic;并摘录文档和 value 函数源码。',
    'context.WithValue 看起来像一个随处可用的“全局变量”,但它有两个陷阱:key 类型冲突和线性查找。这篇用实验复现它们,量层数对查找耗时的影响,并核对文档的建议。',
    [('覆盖', '两个包都用字符串 "id" 作 key 时,先写入的值被后写入的覆盖'), ('3 vs 1331 ns', '1000 层的 ctx 链上,查最外层的 key 与查最里层的 key'), ('1 次', '每次 WithValue 的分配次数,查找 0 次')],
    [('key 要用自己的类型', '<p>两个包都用字符串 <code>"id"</code>,后写入的值把前面的盖住。各自定义一个 <code>struct{}</code> 类型当 key,就互不干扰;连 <code>type S string</code> 也和普通字符串是不同的 key。这就是文档要求不要用内置类型作 key 的原因。</p>'),
     ('线性查找', '<p><code>value</code> 函数沿着父链一层一层比较 key。查最外层的 key 只需 3 ns,查最里层的:10 层 12 ns、100 层 136 ns、1000 层 1331 ns。链一般不长,但如果每个中间件都往 ctx 里塞东西,又在深处取外层的值,就会感觉到。</p>'),
     ('每次 WithValue 一次分配', '<p>每个 <code>WithValue</code> 分配一个节点(1 次分配);查找不分配。这组测量里换 key 的类型(struct{}、指针、自定义 int、字符串)分配次数都是 1,没看出区别。</p>'),
     ('取回的是 any', '<p>断言错类型会 panic(<code>interface conversion: interface {} is int, not string</code>),所以包里最好封装 <code>FromContext</code> 函数用带 ok 的断言。</p>'),
     ('文档怎么说', '<p>文档的建议是只放跨进程、跨 API 的请求范围数据(请求 ID、认证信息),不要拿来给函数传可选参数,后者会让依赖变成隐式的,难以测试;key 要自定义类型,常用 <code>struct{}</code>。源码里 <code>value</code> 函数的循环就是前面看到的逐层比较。</p>')],
    steps,
    [ENV_G + '。第二节的链用 context.WithValue 反复嵌套,key 为 struct{} 类型加不同的 int 类型 key,查最里层/最外层各一次基准;分配用 testing.AllocsPerRun;文档与源码取自本机 go doc context.WithValue 与 src/context/context.go 的 value 函数',
     '没有验证:cancelCtx/timerCtx 混在链中的查找开销、链很深时对 GC 的影响、不同 key 类型对装箱分配的影响(本测法没有看出差别)、第三方 ctx 实现(走 default 分支调用 Value 方法)'],
    'context.Value')
