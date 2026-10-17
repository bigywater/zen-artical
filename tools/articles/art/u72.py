from lib import *
S = SS('u72')
steps = [
    step("用 RUSTC_BOOTSTRAP=1 -Z unpretty=hir 看 `let n: i32 = s.parse()?;` 的真实展开:match branch(s.parse()) { Break(residual) => return from_residual(residual), Continue(val) => val }。? 就是对 branch 返回值的 match:Continue(val) 取出 val 继续,Break(residual) 提前 return。", t=tl(S(1)), done=lidx(S(1), 'match branch', 'Continue'), mark=lidx(S(1), 'Break', 'from_residual'), kv=KV([['Continue(val)', '值就是 val'], ['Break(residual)', 'return from_residual(residual)']], ['Break(residual)'])),
    step("Option 上的 ? 展开成完全相同的形状:match branch(v.first()) { Break(residual) => return from_residual(residual), Continue(val) => val }。差别只在 branch 与 from_residual 的具体实现随类型(Result / Option)而不同。", t=tl(S(2)), done=lidx(S(2), 'match branch'), kv=KV([['Option', '同一个 branch / from_residual 形状']], ['Option'])),
    step("展开里看不到 From::from,它藏在 from_residual 里:手写版本 Err(e) => return Err(From::from(e)) 与 ? 版本的结果完全相同,失败时都恰好调用一次「From 转换」,成功(\"41\")时一次都不调用。", t=tl(S(3)), done=lidx(S(3), '? 版本 \"41\"', '手写版本 \"41\"'), mark=lidx(S(3), 'From 转换'), kv=KV([['From::from', '只在 Err 路径调用一次']], ['From::from'])),
    step("闭包里的 ? 只让闭包返回:parse(\"x\") 失败得到 Err(ParseIntError { kind: InvalidDigit }),outer 继续往下执行并返回 7。外层函数不会被 ? 提前结束。", t=tl(S(4)), done=lidx(S(4), 'outer 继续', 'outer 返回 7'), kv=KV([['闭包里的 ?', '只返回闭包本身']], ['闭包里的 ?'])),
    step("Box<dyn Error> 能接住任何实现 Error 的类型:\"x\" 的 ParseIntError 与 Err(\"负数不允许\")? 抛出的 &str 都能经 From 转成 Box<dyn Error>,最后分别打印「invalid digit found in string」和「负数不允许」。", t=tl(S(5)), done=lidx(S(5), '"x"', '"-1"'), kv=KV([['Box<dyn Error>', '接住不同的错误类型']], ['Box<dyn Error>'])),
]
A = mkart('u72', 72, 'Rust,问号运算符,HIR,错误处理,真实验证,动画演示',
    '用 -Z unpretty=hir 看 ? 的真实展开:match branch(expr) { Break(residual) => return from_residual(residual), Continue(val) => val },Result 与 Option 形状相同;From::from 藏在 from_residual 里,手写版本结果一致,成功路径不调用;闭包里的 ? 只返回闭包;Box<dyn Error> 接住不同错误。',
    '? 只有一个字符,背后是什么?这篇不靠背诵,而是让编译器打印出 HIR,再手写等价的 match 对比,最后验证闭包里的 ? 与 Box<dyn Error> 的行为。',
    [('2 个分支', '? 展开成的 match 分支:Continue 取值、Break 提前 return'), ('1 次', '失败路径上 From::from 的调用次数'), ('0 次', '成功路径上 From::from 的调用次数')],
    [('Result 上的展开', '<p>? 的使用规则见<a href="rust-result-propagation.html">Result 错误传播</a>。展开使用 RUSTC_BOOTSTRAP=1,输出格式随编译器版本变化。</p>'), ('Option 上的展开', None), ('手写展开', None), ('闭包里的 ?', None), ('Box<dyn Error>', '<p>自定义错误类型见<a href="rust-custom-error-type.html">自定义错误类型</a>。</p>')],
    steps, [ENV_U + '。HIR 用 RUSTC_BOOTSTRAP=1 -Z unpretty=hir', '没有验证:branch / from_residual 在标准库里的具体实现(只从行为上确认 From 被调用,没读源码)、Try trait 自定义实现(不稳定)、MIR 层的形态、? 在 async 块里的展开'], '? 的展开')
