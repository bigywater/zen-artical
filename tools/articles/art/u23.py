from lib import *
S = SS('u23')
steps = [
    step("fn longest(x: &str, y: &str) -> &str 编译不过:error[E0106]: missing lifetime specifier —— 返回类型里有借用,但签名没说它借自 x 还是 y。写成 fn longest<'a>(x: &'a str, y: &'a str) -> &'a str 就编译运行,longest(\"abc\", \"de\") 输出 abc。", t=tl(S(1)), mark=lidx(S(1), 'error[E0106]'), done=lidx(S(1), 'abc'), kv=KV([['无标注', 'E0106'], ['<\'a>', '声明返回值与两个输入的关系']], ['<\'a>'])),
    step("标注不改变任何值活多久,它只声明「返回值的有效期不超过两个输入里较短的那个」:内层块里 b 先死,result 在外层使用 → error[E0597]: `b` does not live long enough;同样的调用,result 只在内层使用就没问题(输出「在内层使用 result:long string」)。", t=tl(S(2)), mark=lidx(S(2), 'error[E0597]'), done=lidx(S(2), '在内层使用'), kv=KV([['result 用在 b 之后', 'E0597'], ['result 用在 b 之内', '合法']], ['result 用在 b 之后'])),
    step("两个不同的生命周期参数:fn first<'a, 'b>(x: &'a str, y: &'b str) -> &'a str,函数体却返回 y,报 error: lifetime may not live long enough(建议加约束 'b: 'a)。改成只返回 x,调用时 b 比返回值先死也没关系 —— 返回值只和 a 相关,输出 long。", t=tl(S(3)), mark=lidx(S(3), 'lifetime may not live long enough'), done=lidx(S(3), 'long'), kv=KV([['返回借自 y', 'lifetime may not live long enough'], ['只返回 x', '合法']], ['返回借自 y'])),
    step("生命周期只存在于编译期:不带标注(靠省略规则)的 elided(x: &(u32, u32)) -> &u32 与显式写 <'a> 的 explicit 编译后是同样的机器码 —— 汇编里只剩一个函数体,另一个被 LLVM 合并成别名。运行时没有任何生命周期信息,它只是类型系统里的检查。", t=tl(S(4)), mark=lidx(S(4), '汇编', '别名'), kv=KV([['运行时', '没有生命周期'], ['有无标注', '机器码相同']], ['运行时'])),
]
A = mkart('u23', 23, 'Rust,生命周期,借用检查,真实验证,动画演示',
    '用真实编译验证生命周期标注描述的是什么:两个输入引用时不标注报 E0106;<\'a> 声明「返回值有效期不超过较短的输入」而不改变任何值的寿命(返回值在 b 之后使用报 E0597);不同的生命周期参数与 \'b: \'a 的提示;标注与否机器码相同。',
    '生命周期标注 \'a 是 Rust 里最容易被误解的语法:它不是「让某个值活更久」,而是「描述几个引用的有效期之间的关系」。这篇用一个 longest 函数,从四个角度验证这一点,最后用汇编确认它在运行时完全不存在。',
    [('E0106', '返回引用但没说借自哪个输入'), ('E0597', '返回值在较短的输入之后使用'), ('0', '生命周期在运行时占用的指令数(标注前后机器码相同)')],
    [('为什么需要标注', None), ('标注描述的是关系', None), ('多个生命周期参数', None), ('运行时不存在', '<p>省略规则见<a href="rust-lifetime-elision.html">生命周期省略规则</a>;函数返回引用的具体情形见<a href="rust-returning-references.html">函数返回引用的生命周期</a>。</p>')],
    steps, [ENV_U + '。汇编目标 aarch64-apple-darwin', '没有验证:高阶生命周期(for<\'a>)、生命周期子类型的更多形式、struct 里的生命周期(见后面的文章)、\'static 约束'], '生命周期标注')
