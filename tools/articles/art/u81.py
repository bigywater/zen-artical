from lib import *
S = SS('u81')
steps = [
    step("属性宏收到两个 token 流:属性自己的参数(attr)和被修饰的条目(item),返回值整个替换原条目。#[timed] 用 syn 把 item 解析成 ItemFn,再用 quote! 输出同名同签名的新函数:原函数体被包进闭包 (|| { … })(),前后加计时与打印,返回值 __r 原样返回。", t=tl(S(1)), done=lidx(S(1), '展开后的 add', 'let __r'), kv=KV([['attr', '属性括号里的 token'], ['item', '被修饰的条目'], ['返回值', '整个替换原条目']], ['返回值'])),
    step("运行结果:add(2, 3) 先打印「[timed] add 返回了(耗时数量级 微秒以内)」再得到 5;sleep 5 毫秒的 slow() 打印「毫秒」后返回 \"done\"。函数签名、返回值都没变。", t=tl(S(1)), done=lidx(S(1), '[timed] add', '[timed] slow', 'add = 5', 'slow = done'), kv=KV([['add(2, 3)', '5(微秒以内)'], ['slow()', '\"done\"(毫秒)']], ['slow()'])),
    step("带参数的属性宏 #[route(\"GET\", \"/users\")]:用自定义 Parse 解析两个字符串字面量;宏输出里保留了原函数(#f)并额外生成常量 ROUTE_LIST_USERS。运行得到 (\"GET\", \"/users\", \"list_users\")、(\"POST\", \"/users\", \"create_user\"),原函数仍可调用。", t=tl(S(2)), done=lidx(S(2), 'GET', 'POST', '原函数仍可调用'), kv=KV([['保留原函数', '输出里带上 #f'], ['额外生成', 'pub const ROUTE_…']], ['额外生成'])),
    step("参数写错时,syn 的错误带着位置:#[route(\"GET\")] 报 error: expected `,`(指向整个属性),#[route(GET, \"/x\")] 报 error: expected string literal,精确指向 GET。note 提示错误来自 attribute macro `route`。", t=tl(S(3)), mark=lidx(S(3), 'expected `,`', 'expected string literal'), kv=KV([['缺第二个参数', 'expected `,`'], ['参数不是字符串', 'expected string literal']], ['参数不是字符串'])),
    step("返回值替换整个条目:一个返回空 TokenStream 的 #[vanish] 让被修饰的函数消失,main 里调用 gone() 报 error[E0425]: cannot find function `gone` in this scope。想保留原条目,必须自己在输出里重新输出它。", t=tl(S(4)), mark=lidx(S(4), 'error[E0425]'), kv=KV([['返回空', '条目消失'], ['想保留', '输出里带上原 item']], ['返回空'])),
    step("放错位置:#[timed](按 ItemFn 解析)用在 struct 上,报 error: expected `fn`,指向 struct 关键字。属性宏自己负责检查它能用在哪些条目上。", t=tl(S(5)), mark=lidx(S(5), 'error: expected `fn`'), kv=KV([['#[timed] struct', 'expected `fn`']], ['#[timed] struct'])),
]
A = mkart('u81', 81, 'Rust,属性宏,过程宏,syn,quote,真实验证,动画演示',
    '真实写三个属性宏:#[timed] 用 ItemFn 包装函数体(展开后原体进闭包,返回值不变)、#[route("GET", "/users")] 解析参数并保留原函数加生成常量、#[vanish] 返回空令函数消失(E0425);参数写错时 syn 错误精确指位置;放在 struct 上报 expected `fn`。',
    '属性宏比 derive 更强大也更危险:它能改写甚至删除被修饰的条目。这篇写三个最小的属性宏,让编译器展开出来,再验证参数解析、保留原条目、解析错误和用错位置的各种报错。',
    [('2 个输入', '属性宏收到的 token 流:attr 与 item'), ('E0425', '属性宏返回空时,被修饰函数消失后的错误'), ('1', '展开后的 add 里,原函数体被包进的闭包个数')],
    [('包装函数体', '<p>过程宏的阶段见<a href="rust-proc-macro-phases.html">过程宏的执行阶段</a>。</p>'), ('带参数并保留原函数', None), ('参数错误', None), ('返回值替换原条目', None), ('用错位置', '<p>derive 宏的写法见<a href="rust-derive-macro-codegen.html">Derive 宏如何生成代码</a>。</p>')],
    steps, [ENV_U + '。crates:syn 2、quote 1、proc-macro2 1', '没有验证:对 impl 块与 trait 的属性宏、async fn 的包装(闭包写法不适用于 async)、#[timed] 对带 self 方法的处理、属性宏之间的叠加顺序、tracing / tokio::main 等真实 crate 的做法'], '属性宏')
