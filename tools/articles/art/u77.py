from lib import *
S = SS('u77')
steps = [
    step("最小的宏:macro_rules! square { ($x:expr) => { $x * $x }; },square!(7) = 49。重复模式 $($x:expr),+ 实现可变参数:my_vec![] = [],my_vec![1,2,3,] = [1,2,3](允许结尾逗号);递归宏 maxm!(3, 9, 4, 7) = 9,maxm!(5) = 5。", t=tl(S(1)), done=lidx(S(1), 'square!(7)', 'my_vec', 'maxm!'), kv=KV([['($x:expr)', '匹配一个表达式'], ['$(...),+', '一个或多个,逗号分隔']], ['$(...),+'])),
    step("编译器真实展开(-Z unpretty=expanded):square!(2 + 3) 变成 (2 + 3) * (2 + 3),my_vec![1, 2, 3] 变成 { let mut v = Vec::new(); v.push(1); v.push(2); v.push(3); v }。$(...)+ 被展开成三条 push。", t=tl(S(2)), done=lidx(S(2), '(2 + 3) * (2 + 3)', 'v.push(1)'), kv=KV([['square!(2 + 3)', '(2 + 3) * (2 + 3)'], ['my_vec![1,2,3]', '三条 push']], ['square!(2 + 3)'])),
    step("$x:expr 作为整体:square!(2 + 3) = 25,而不是 2 + 3 * 2 + 3 = 11。但宏是文本级的复制,表达式的副作用会重复:square!(next()) 把 next() 展开了两次,调用次数 2;同样的 square_fn(next()) 函数只求值一次,调用次数 1。", t=tl(S(3)), done=lidx(S(3), 'square!(2 + 3)'), mark=lidx(S(3), 'square!(next())', 'square_fn'), kv=KV([['宏', '实参写几次就求值几次'], ['函数', '实参只求值一次']], ['宏'])),
    step("规则没匹配上时的错误:pair!(1) 缺第二个参数,报 error: unexpected end of macro invocation,note 写「while trying to match `,`」,指出规则里卡在哪个 token。", t=tl(S(4)), mark=lidx(S(4), 'unexpected end of macro invocation', 'while trying to match'), kv=KV([['pair!(1)', '卡在期待的 ,']], ['pair!(1)'])),
    step("宏必须先定义后使用:macro_rules! 写在 main 之后,main 里调用 late!(2) 报 error: cannot find macro `late` in this scope,note 说同名宏出现在后面(macro_rules 的作用域按文本顺序)。", t=tl(S(4)), mark=lidx(S(4), 'cannot find macro', 'appears later'), kv=KV([['定义在使用之后', 'cannot find macro']], ['定义在使用之后'])),
    step("常用的片段类型:ident 生成函数名(make_fn!(seven, 7) → fn seven()),ty 生成结构体字段类型(make_struct! 生成带 derive 的 Point,Default 值 Point { x: 0, y: 0, tag: \"\" }),literal 匹配字面量并配合自定义关键字(op!(3 plus 4) = 7,op!(3 times 4) = 12),tt 逐个 token 递归计数(count!(a b c d e) = 5)。", t=tl(S(5)), done=lidx(S(5), 'seven()', 'Point', 'op!(3 plus 4)', 'count!'), kv=KV([['ident', '生成名字'], ['ty', '生成类型'], ['tt', '任意一个 token tree']], ['tt'])),
]
A = mkart('u77', 77, 'Rust,宏,macro_rules,元编程,真实验证,动画演示',
    '用真实运行验证 macro_rules!:模式匹配、$(...),+ 重复、递归宏;用 -Z unpretty=expanded 看展开结果;$x:expr 作为整体但副作用会求值两次;规则不匹配与定义顺序的编译错误;ident/ty/literal/tt 等片段类型。',
    'macro_rules! 是 Rust 最常用的宏机制,但它的规则、展开和陷阱都不直观。这篇从最小的例子开始,让编译器展开宏,验证表达式被重复求值的坑,以及编译错误长什么样。',
    [('2 次', 'square!(next()) 中 next() 被展开并求值的次数(函数只有 1 次)'), ('25', 'square!(2 + 3) 的结果(整体,不是 11)'), ('5', 'tt 递归计数 count!(a b c d e) 的结果')],
    [('第一个宏', None), ('编译器的展开', '<p>展开用 RUSTC_BOOTSTRAP=1 与 -Z unpretty=expanded;输出里的括号来自编译器对表达式片段的打印。宏的卫生性见<a href="rust-macro-hygiene.html">宏卫生性</a>。</p>'), ('表达式被重复求值', None), ('编译错误', None), ('常用的片段类型', None)],
    steps, [ENV_U + '。展开用 RUSTC_BOOTSTRAP=1 -Z unpretty=expanded', '没有验证:#[macro_export] 与跨 crate 的宏作用域、$crate、宏递归深度上限(recursion_limit)、宏 2.0(不稳定)、其它片段类型(pat、vis、lifetime、meta、item)'], 'macro_rules!')
