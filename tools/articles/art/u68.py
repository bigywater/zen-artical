from lib import *
S = SS('u68')
steps = [
    step("最普通的 for x in v { s += x; }:用 RUSTC_BOOTSTRAP=1 加 -Z unpretty=hir 看编译器的真实展开 —— 先是 match into_iter(v) { mut iter => loop { … } },把迭代器绑定到 mut iter;", t=tl(S(1)), done=lidx(S(1), 'match into_iter', 'mut iter'), kv=KV([['第一步', 'into_iter(v) 绑定到 mut iter']], ['第一步'])),
    step("循环体是 loop { match next(&mut iter) { None => break, Some(x) => { s += x; } } }:每轮调用一次 next,None 就 break,Some(x) 就运行循环体。外面还包了一层块,把 loop 的结果赋给临时变量 _t 再返回。", t=tl(S(1)), done=lidx(S(1), 'loop', 'next(&mut iter)', 'None', 'Some'), kv=KV([['每轮', 'next(&mut iter)'], ['None', 'break'], ['Some(x)', '运行循环体']], ['每轮'])),
    step("手写这个展开(match IntoIterator::into_iter(&v) { mut iter => loop { match Iterator::next(&mut iter) {…} } }),带 continue 与 break 的循环体,得到的结果与 for 完全相同:[1, 3](偶数 continue 跳过,遇到 5 > 4 就 break)。", t=tl(S(2)), done=lidx(S(2), '相同: true'), kv=KV([['for', '[1, 3]'], ['手写展开', '[1, 3]']], ['手写展开'])),
    step("用自己写的 IntoIterator + Iterator 打印调用顺序:into_iter() 只调用 1 次,然后是 next → 循环体 → next → 循环体 …,第 4 次 next 返回 None 直接结束循环(没有循环体输出)。", t=tl(S(3)), done=lidx(S(3), 'into_iter()', 'next() 被调用', '循环结束'), mark=lidx(S(3), 'n = 3'), kv=KV([['into_iter', '1 次'], ['next', '4 次(3 次 Some + 1 次 None)']], ['next'])),
    step("因为 iter 在整个循环期间一直借着容器,遍历时往同一个 Vec 里 push:for x in &v { v.push(4); } 报 error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable。", t=tl(S(4)), mark=lidx(S(4), 'error[E0502]'), kv=KV([['遍历 &v 时 push', 'E0502']], ['遍历 &v 时 push'])),
    step("想边遍历边改:用下标 for i in 0..v.len() 改成 [1,20,3,40],或 iter_mut() 得 [2,21,4,41]。range 的上界只在进入循环时求值一次:for _ in 0..m 里把 m 改成 100,仍然只循环 3 次。", t=tl(S(4)), done=lidx(S(4), '下标写法', 'iter_mut', '仍然只循环 3 次'), kv=KV([['下标写法', '可以改元素'], ['iter_mut', '可以改元素'], ['0..m 的 m', '只求值一次']], ['0..m 的 m'])),
]
A = mkart('u68', 68, 'Rust,for循环,Iterator,HIR,真实验证,动画演示',
    '用 -Z unpretty=hir 看 for 循环的真实展开:match into_iter(v) { mut iter => loop { match next(&mut iter) { None => break, Some(x) => … } } };手写展开与 for 行为相同(含 break/continue);into_iter 调用 1 次、next 调用 4 次;遍历时 push 报 E0502;range 上界只求值一次。',
    'Rust 没有传统的 for(;;),for 只是语法糖。这篇用编译器的 HIR 输出直接看它被展开成什么,再手写同样的 match + loop 验证行为一致,用带打印的自定义迭代器数调用次数。',
    [('1 次', 'for 循环中 into_iter 的调用次数'), ('4 次', '3 个元素的迭代器上 next 的调用次数(最后一次是 None)'), ('E0502', '遍历 &v 时往 v 里 push')],
    [('编译器的展开', '<p>HIR 展开使用了 RUSTC_BOOTSTRAP=1 与 -Z unpretty=hir(稳定版编译器上打开 nightly 选项),输出格式随编译器版本变化。三种遍历写法见<a href="rust-into-iterator-three-ways.html">IntoIterator 的三种遍历方式</a>。</p>'), ('手写展开', None), ('调用顺序', '<p>自定义迭代器见<a href="rust-custom-iterator.html">自定义 Iterator</a>。</p>'), ('遍历时的限制', None)],
    steps, [ENV_U + '。HIR 用 RUSTC_BOOTSTRAP=1 -Z unpretty=hir', '没有验证:for 在 async 里的展开、for 对 break 带标签的展开、MIR 层的形态(只看到了 HIR)、HIR 里 into_iter/next 的完整路径(输出里被省略成短名)'], 'for 循环展开')
