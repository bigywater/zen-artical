from lib import *
S = SS('u27')
steps = [
    step("规则 1:每个被省略的输入引用各自得到一个独立的生命周期。lens(a: &str, b: &str) 与完整写法 lens_explicit<'a, 'b>(a: &'a str, b: &'b str) 完全等价:a 活得久、b 先死,两种调用都成功,输出相同的 (15, 15)。", t=tl(S(1)), done=lidx(S(1), '(15, 15)'), kv=KV([['输入各自独立', "'a、'b 互不相关"]], ['输入各自独立'])),
    step("规则 2:只有一个输入生命周期时,它被赋给所有省略的输出生命周期。first_char(s: &str) -> &str 等价于 <'a>(s: &'a str) -> &'a str(输出 a 与 x);甚至输出里有两个引用也都借自唯一的输入:pair(p: &(String, String)) -> (&String, &String) 返回 a 与 b。", t=tl(S(2)), done=lidx(S(2), 'a x', 'a b'), kv=KV([['一个输入生命周期', '赋给所有输出']], ['一个输入生命周期'])),
    step("规则 3:有 &self 或 &mut self 时,所有省略的输出生命周期等于 self 的生命周期,即使还有别的引用参数。get(&self, other: &str) -> &str 返回 &self.name 没问题;wrong 想返回 other 就被拒绝:error: lifetime may not live long enough —— 省略规则已经把返回值绑在 self 上了。", t=tl(S(3)), mark=lidx(S(3), 'lifetime may not live long enough'), kv=KV([['&self', '输出的生命周期 = self 的'], ['返回 other', 'lifetime may not live long enough']], ['返回 other'])),
    step("省略规则覆盖不到的情形:没有任何输入引用却返回引用(fn make() -> &str)报 error[E0106],编译器建议返回拥有的 String(或用 'static);两个输入引用、没有 self 的普通函数(fn pick(a: &str, b: &str) -> &str)也报 E0106:「signature does not say whether it is borrowed from `a` or `b`」。这两种就必须显式写生命周期。", t=tl(S(4)), mark=lidx(S(4), 'error[E0106]'), kv=KV([['无输入引用', 'E0106'], ['两个输入、无 self', 'E0106']], ['两个输入、无 self'])),
    step("匿名生命周期 '_:不需要名字时可以写 impl Excerpt<'_> 或 &Excerpt<'_>,表示「这里有一个生命周期但我不关心」。如果写成 show(e: &Excerpt) 把它藏在类型路径里,打开 -W elided-lifetimes-in-paths 会给出警告 hidden lifetime parameters in types are deprecated,并提示写成 Excerpt<'_>。", t=tl(S(5)), mark=lidx(S(5), 'warning: hidden lifetime'), kv=KV([["'_", '显式标出被省略的生命周期'], ['-W elided-lifetimes-in-paths', '提示隐藏的生命周期']], ["'_"])),
]
A = mkart('u27', 27, 'Rust,生命周期,省略规则,真实验证,动画演示',
    '用真实编译验证生命周期省略的三条规则:每个省略的输入各得一个独立生命周期;只有一个输入时赋给所有输出;有 &self 时输出绑定 self(返回其它参数被拒绝);规则覆盖不到时(无输入引用、两个输入无 self)报 E0106;匿名生命周期 \'_ 与 elided-lifetimes-in-paths 提示。',
    '你很少需要写 \'a,是因为编译器有三条省略规则帮你补全。这篇把这三条规则逐条用真实代码验证,再看规则不够用时的报错,以及 \'_ 这个「我知道这里有个生命周期但不想起名」的写法。',
    [('3 条', '生命周期省略规则:输入各自独立 / 单一输入赋给输出 / &self 赋给输出'), ('E0106', '规则覆盖不到时的错误'), ("'_", '匿名生命周期的写法')],
    [('规则 1', None), ('规则 2', None), ('规则 3', '<p>方法里返回值借自 self 的更多场景见<a href="rust-returning-references.html">函数返回引用的生命周期</a>。</p>'), ('规则不够用', None), ("匿名生命周期 '_", None)],
    steps, [ENV_U + '。尝试过 -Z unpretty=hir 查看展开后的签名,只显示 \'_ 而没有展开成具体名字,所以这里没有使用', '没有验证:trait 方法与 dyn Trait 的默认对象生命周期界限、impl Trait 的捕获规则(2024 edition 变化)、高阶 trait bound(for<\'a>)里的省略'], '省略规则')
