from lib import *
S = SS('u78')
steps = [
    step("swap! 宏内部 let tmp = $a;,调用处恰好也有 let tmp = 100:swap!(x, y) 之后 x = 2、y = 1,调用处的 tmp 仍是 100,没有被宏里的 tmp 覆盖。参数本身就叫 tmp2 时也一样:tmp2 = 6、other = 5。", t=tl(S(1)), done=lidx(S(1), 'x = 2', 'tmp2 = 6'), kv=KV([['宏里的 tmp', '与调用处的 tmp 是两个变量']], ['宏里的 tmp'])),
    step("编译器的 hygiene 打印(-Z unpretty=expanded,hygiene):twice!(v + 1) 展开后,调用处的 v 是 v /* 2348#0 */,宏里的 v 是 v /* 2348#4 */,同一个名字带不同的语法上下文编号(#0 与 #4),于是 let v = v + 1 里右边的 v 指调用处的 #0,v + v 里的指宏里新声明的 #4。#4 对应的展开是 Macro(Bang, \"twice\"),标记类型 SemiOpaque。", t=tl(S(2)), mark=lidx(S(2), '2348#4'), done=lidx(S(2), '2348#0'), kv=KV([['调用处的 v', '#0'], ['宏里的 v', '#4(SemiOpaque)']], ['宏里的 v'])),
    step("反过来,宏里引用调用处的局部变量 y(没有作为参数传入)报 error[E0425]: cannot find value `y` in this scope,help 解释「an identifier with the same name exists, but is not accessible due to macro hygiene」。", t=tl(S(3)), mark=lidx(S(3), 'error[E0425]', 'macro hygiene'), kv=KV([['宏里用调用处的 y', 'E0425']], ['宏里用调用处的 y'])),
    step("通过参数传入的标识符可以:show!(y) 打印 y = 5;decl!(z = 9) 里的 let $name = $val 让 z 在调用处可见,z = 9。但宏内部自己写死名字的 let hidden = $val 在调用处不可见:使用 hidden 报 error[E0425]: cannot find value `hidden`,help 说「defined here, but is not accessible due to macro hygiene」。", t=tl(S(3)), done=lidx(S(3), 'y = 5', 'z = 9'), mark=lidx(S(3), 'hidden'), kv=KV([['$name:ident 传入', '调用处可见'], ['宏里写死的名字', '调用处不可见']], ['宏里写死的名字'])),
    step("卫生只管局部变量与标签,不管 item:def_helper!() 定义的 fn helper 在 main 里可以直接调用,输出「宏里定义的 helper」。", t=tl(S(4)), done=lidx(S(4), 'helper'), kv=KV([['局部变量 / 标签', '卫生'], ['fn / struct 等 item', '不卫生']], ['fn / struct 等 item'])),
    step("标签同样是卫生的:find_first! 宏里写了 'outer: for ... break 'outer,调用处也有一个 'outer 循环,两者不冲突:i = 0 与 i = 1 各找到 Some(8),并在 i == 1 时按调用处的 'outer 退出外层循环。", t=tl(S(5)), done=lidx(S(5), 'i = 0', 'i = 1'), kv=KV([['标签', '卫生,不冲突']], ['标签'])),
]
A = mkart('u78', 78, 'Rust,宏,卫生性,hygiene,真实验证,动画演示',
    '用真实运行与编译器的 hygiene 打印验证宏卫生性:宏里的 tmp 与调用处的 tmp 是两个变量(#4 对 #0 的语法上下文);宏里引用未传入的调用处变量报 E0425;宏里写死的名字在调用处不可见而传入的 ident 可见;fn 等 item 不卫生;标签也是卫生的。',
    '为什么宏里的 let tmp 不会弄坏调用处的 tmp?这个叫「卫生性」。这篇不靠概念,而是让编译器把每个标识符的语法上下文编号打印出来,再用四个编译与运行实验划清卫生的边界。',
    [('#0 对 #4', '同名变量 v 在调用处与宏内部的语法上下文编号'), ('E0425', '宏里引用未传入的调用处变量,或调用处引用宏里写死的变量'), ('2 类', '不卫生的:item(fn 等);卫生的:局部变量与标签')],
    [('局部变量不会冲突', '<p>macro_rules 基础见<a href="rust-macro-rules.html">声明宏 macro_rules!</a>。</p>'), ('编译器如何区分', '<p>hygiene 打印用 RUSTC_BOOTSTRAP=1 -Z unpretty=expanded,hygiene;编号是该次编译的内部值,会随编译器版本变化。</p>'), ('反方向的限制', None), ('item 与标签', None), ('标签的卫生性', None)],
    steps, [ENV_U + '。展开用 RUSTC_BOOTSTRAP=1 -Z unpretty=expanded,hygiene', '没有验证:过程宏的 Span 与卫生性(call_site / mixed_site)、$crate、泛型参数与生命周期名的卫生性、宏 2.0 的 item 卫生'], '宏卫生性')
