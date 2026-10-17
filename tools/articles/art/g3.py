from lib import *
S = SS('g3')
def tail(lines, sub):
    i = [k for k, l in enumerate(lines) if sub in l][0]
    return lines[i:]
L1 = tail(S(1), 'buggy(false):')
steps = [
    step("经典陷阱:buggy 内部用 var e *MyErr 保存错误,没出错时 e 是 nil 指针,return e 把它装进 error 接口。结果 buggy(false) 与 nil 比较是 false,%T 是 *main.MyErr,%v 却打印 <nil>;fixed 直接 return nil,比较是 true,%T 是 <nil>。用 unsafe 读两个字:buggy 的 tab 不是 nil、data 是 nil;fixed 两个字都是 nil。go vet 对这份代码 rc=0、没有任何警告。", t=tl(L1), done=lidx(L1, 'fixed(false)', 'fixed 的两个字'), mark=lidx(L1, 'buggy(false)', 'go vet'), kv=KV([['buggy(false) == nil', 'false'], ['buggy 的两个字', 'tab ≠ nil,data = nil'], ['fixed(false) == nil', 'true'], ['go vet', 'rc=0,无任何警告']], ['buggy(false) == nil'])),
    step("五种“nil”和 nil 比较:var p *MyErr:p == nil 为 true;var e error:e == nil 为 true;var any1 any:any1 == nil 为 true;把 nil 的 *MyErr 装进 any:any2 == nil 是 false,any2 == (*MyErr)(nil) 是 true,any2 == any(nil) 是 false;装进 error:e3 == nil 是 false,e3 == error((*MyErr)(nil)) 是 true。接口值只有在类型字与数据字都为空时才等于 nil。", t=tl(S(2)), done=lidx(S(2), 'var p *MyErr', 'var e error', 'var any1 any'), mark=lidx(S(2), 'var any2 any = p', 'var e3 error = p'), kv=KV([['nil 指针 p == nil', 'true'], ['未赋值的 error / any == nil', 'true / true'], ['装着 nil *MyErr 的 any == nil', 'false'], ['同一个 any == (*MyErr)(nil)', 'true']], ['装着 nil *MyErr 的 any == nil'])),
    step("对 buggy(false) 的结果调用 Error():方法解引用 e.Code,直接 panic:runtime error: invalid memory address or nil pointer dereference;换成方法里先判断 n == nil 的版本(NilSafe),通过接口调用返回 <nil NilSafe>,没有 panic;类型断言 e1.(*MyErr) 的 ok = true、取到的指针 v == nil 为 true。所以“接口非 nil”并不保证方法能安全调用,也不保证不能。", t=tl(S(3)), done=lidx(S(3), '返回: <nil NilSafe>', '断言 ok = true'), mark=lidx(S(3), 'e1.Error()'), kv=KV([['e1.Error()(解引用 e.Code)', 'panic:nil pointer dereference'], ['NilSafe.Error()(先判 n == nil)', '返回 <nil NilSafe>'], ['e1.(*MyErr)', 'ok = true,v == nil']], ['e1.Error()(解引用 e.Code)'])),
    step("在一个函数里判断“接口里装的是不是 nil”:先 v == nil,再用 reflect 按 Kind 判断 IsNil。isNil(buggy(false)) 为 true、isNil(fixed(false)) 为 true、isNil(&MyErr{}) 为 false、isNil(0) 为 false;对 int 直接调用 reflect.ValueOf(0).IsNil() 会 panic;nil 的 map、slice、func 装进 any 以后 == nil 都是 false,isNil 都是 true——这个陷阱不只发生在指针上。", t=tl(S(4)), done=lidx(S(4), 'isNil(buggy(false))'), mark=lidx(S(4), 'nil map / nil slice / nil func', 'reflect.ValueOf(0)'), kv=KV([['isNil(buggy(false))', 'true'], ['isNil(&MyErr{})', 'false'], ['nil map / slice / func 装进 any', '== nil 都是 false'], ['同样三者的 isNil', '都是 true']], ['nil map / slice / func 装进 any'])),
]
A = mkartg('g3', 3, 'Go,接口,nil,error,reflect,真实验证,动画演示',
    '用 Go 1.27.1 复现“返回 nil 指针的 error 不等于 nil”:有错误类型的 nil 指针装进 error 后,接口的类型字非空、数据字为空,与 nil 比较是 false;go vet 没有警告;调用方法会不会 panic 取决于方法是否解引用接收者;nil 的 map、slice、func 装进 any 同样不等于 nil,用 reflect 判断 IsNil。',
    '接口值等于 nil 的条件是“类型字与数据字都为空”。当一个类型化的 nil 指针被装进接口时,类型字不再为空,于是 err != nil 为真,而打印出来又是 <nil>。这篇把这个现象拆开:读出两个字、对照五种 nil、看方法调用的结果,再给出判断的写法。',
    [('false', 'buggy(false) 没出错时,返回的 error 与 nil 比较的结果'), ('tab ≠ nil', '装着 nil *MyErr 的 error:类型字非空、数据字为空'), ('0 个警告', 'go vet 对这段有问题的代码没有任何输出')],
    [('经典陷阱', '<p>问题出在 <code>return e</code>:<code>e</code> 的静态类型是 <code>*MyErr</code>,装进 <code>error</code> 时编译器按 <code>(*MyErr)(nil)</code> 做了一次转换,接口的类型字(这里是 itab 指针)被填上了。用上一篇的方法读两个字,看得清清楚楚:<code>buggy</code> 的 tab 不为空、data 为空。解决办法很朴素:没有错误时直接 <code>return nil</code>,不要先装进具体类型的变量再返回。</p>'),
     ('五种“nil”和接口', '<p>规则可以压缩成一句:<b>接口值只有在两个字都是空时才等于 <code>nil</code></b>。比较 <code>any2 == (*MyErr)(nil)</code> 为真,是因为把右边也转成了同样的接口值再比较(类型字相同、数据字都是 nil)。</p>'),
     ('调用方法会怎样', '<p>非 nil 接口里装着 nil 指针,方法调用是合法的,会照常分派到 <code>(*MyErr).Error</code>。要不要出事,看方法体:解引用了接收者就 panic,先判断了 <code>n == nil</code> 就没事。这也是为什么这个陷阱常常在“不出错的路径”上才触发 panic。</p>'),
     ('怎么判断', '<p>最好的办法是不要制造这种值。不得已要判断时,<code>reflect</code> 的 <code>IsNil</code> 适用于 <code>Pointer</code>、<code>Map</code>、<code>Slice</code>、<code>Func</code>、<code>Chan</code>、<code>Interface</code> 这几种 Kind,其它 Kind 调用会 panic(上面实测 <code>reflect.ValueOf(0).IsNil()</code> 就是),所以先按 Kind 筛选。反射有成本,不要放在热路径上。</p>')],
    steps,
    [ENV_G + '。用 unsafe 把 error 按 {tab, data} 两个字读出来,只比较是否为 nil;go vet 用的是 Go 1.27.1 自带的默认检查集;其它静态检查工具(staticcheck、golangci-lint 等)本机没有安装,没有试',
     '没有验证:标准库里哪些类型的方法支持 nil 接收者、第三方静态检查工具能否发现这种返回、泛型代码里同样的陷阱、cgo 或 syscall.Errno 等非指针错误类型的行为'],
    'nil 接口陷阱')
