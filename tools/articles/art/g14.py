from lib import *
S = SS('g14')
steps = [
    step("Counter 有三个方法:值接收者的 Value、IncLost 与指针接收者的 Inc。用 reflect 看方法集:Counter 的方法集是 IncLost、Value;*Counter 的方法集是 Inc、IncLost、IncNilSafe、Value(指针的方法集包含值的方法集)。c.Inc() 两次、c.IncLost() 一次之后 c.n = 2:值接收者的修改作用在副本上,丢了。", t=tl(S(1)), done=lidx(S(1), 'Counter 的方法集'), mark=lidx(S(1), 'c.n = 2'), kv=KV([['Counter(值)的方法集', 'IncLost、Value'], ['*Counter 的方法集', 'Inc、IncLost、IncNilSafe、Value'], ['c.IncLost()', '改的是副本,c.n 不变']], ['*Counter 的方法集'])),
    step("编译器的报错:var i2 I = Counter{}(I 要求 Inc,是指针接收者的方法):cannot use Counter{} (value of struct type Counter) as I value in variable declaration: Counter does not implement I (method Inc has pointer receiver);m[\"a\"].Inc()(map 元素不可寻址)与 get().Inc()(函数返回值不可寻址):cannot call pointer method Inc on Counter。var v2 V = &Counter{}、var i1 I = &Counter{}、var v1 V = Counter{} 都没有报错。", t=tl(S(2)), mark=lidx(S(2), 'main.go:16:13', 'main.go:18:9', 'main.go:19:8'), kv=KV([['Counter{} 赋给要求指针方法的接口', 'does not implement I (method Inc has pointer receiver)'], ['m[\"a\"].Inc()', 'cannot call pointer method Inc on Counter'], ['get().Inc()', 'cannot call pointer method Inc on Counter'], ['&Counter{} 赋给 V 或 I', '都可以']], ['Counter{} 赋给要求指针方法的接口'])),
    step("方法值在绑定时拷贝接收者:fv := c2.Value(值接收者,绑定了 c2 的拷贝)之后 c2.n = 50,fv() = 1;fp := c2.Inc(指针接收者,绑定 &c2),fp() 之后 c2.n = 51。方法表达式:Counter.Value 的类型是 func(main.Counter) int,(*Counter).Inc 的类型是 func(*main.Counter);pe(&cc) 之后 me(cc) = 8。", t=tl(S(3)), done=lidx(S(3), 'fv := c2.Value'), mark=lidx(S(3), '方法表达式'), kv=KV([['c2.Value 方法值', '绑定时拷贝 c2:之后改 c2.n,fv() 仍是 1'], ['c2.Inc 方法值', '绑定 &c2:fp() 之后 c2.n = 51'], ['Counter.Value', 'func(main.Counter) int'], ['(*Counter).Inc', 'func(*main.Counter)']], ['c2.Value 方法值'])),
    step("nil 接收者:通过 nil 的 *Counter 调用值接收者的方法 np.Value() panic:runtime error: invalid memory address or nil pointer dereference(要先把 *np 拷贝出来);指针接收者的 IncNilSafe 能收到 nil,在方法里判断后正常返回。", t=tl(S(4)), done=lidx(S(4), '正常返回'), mark=lidx(S(4), 'np.Value()'), kv=KV([['np.Value()(值接收者)', 'panic:nil pointer dereference'], ['np.IncNilSafe()(指针接收者)', '收到 nil,可以自己处理']], ['np.Value()(值接收者)'])),
]
A = mkartg('g14', 14, 'Go,方法集,接收者,接口,真实验证,动画演示',
    '用 Go 1.27.1 实测方法集:*T 的方法集包含 T 的方法集,T 的方法集不含指针接收者的方法,所以 T{} 不能赋给要求指针方法的接口;map 元素与函数返回值不可寻址,不能调用指针方法;值接收者的修改作用在副本上;方法值在绑定时拷贝接收者;nil 的 *T 调值接收者方法会 panic。',
    '“值接收者还是指针接收者”不只是风格问题,它决定了哪个类型能实现哪个接口,以及调用时修改会不会生效。这篇用 reflect 列出方法集,用编译器的原样报错确认规则,再看方法值、方法表达式与 nil 接收者的行为。',
    [('方法集', 'T 的方法集只有值接收者的方法;*T 的包含全部'), ('不可寻址', 'map 元素与函数返回值不能调用指针接收者的方法'), ('绑定时拷贝', '值接收者的方法值在绑定时拷贝接收者')],
    [('方法集与接口', '<p>规范里的规则:类型 <code>T</code> 的方法集由接收者是 <code>T</code> 的方法组成,<code>*T</code> 的方法集包含接收者是 <code>T</code> 或 <code>*T</code> 的方法。实验里 <code>reflect</code> 列出的两个集合正是这样。所以 <code>Counter{}</code> 不能赋给要求 <code>Inc</code> 的接口,必须用 <code>&Counter{}</code>。</p>'),
     ('编译器怎么说', '<p>报错信息直接指出了原因:<code>method Inc has pointer receiver</code>。直接对变量调用 <code>c.Inc()</code> 之所以可以,是因为编译器自动取了 <code>(&c).Inc()</code>——这要求 <code>c</code> 可寻址;map 元素和函数返回值不可寻址,所以不行。</p>'),
     ('方法值与方法表达式', '<p><code>c2.Value</code> 作为方法值时,值接收者会在绑定的那一刻被拷贝,之后 <code>c2</code> 再变化不影响它;指针接收者绑定的是地址,所以能看到后来的修改。方法表达式 <code>T.Method</code> 把接收者变成第一个参数,类型分别是 <code>func(main.Counter) int</code> 与 <code>func(*main.Counter)</code>。</p>'),
     ('nil 接收者', '<p>值接收者的方法要先解引用指针来拷贝接收者,所以对 nil 指针调用会 panic;指针接收者的方法可以收到 nil,是否安全看方法体自己的判断(上一节“nil 接口陷阱”里的 <code>NilSafe</code> 就是这样)。一个类型里混用两种接收者是允许的,不会有编译错误,这是否合适是风格问题,本文没有验证 go vet 或其它工具是否提示。</p>')],
    steps,
    [ENV_G + '。方法集用 reflect.Type.NumMethod / Method 列出;编译错误是 go build 的原样输出',
     '没有验证:嵌入结构体时方法集的提升规则(见下一篇)、泛型类型的方法集、接口里存放值时方法调用的拷贝开销、go vet 或 staticcheck 对混用接收者的提示'],
    '方法集')
