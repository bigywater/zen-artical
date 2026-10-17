from lib import *
S = SS('u25')
steps = [
    step("结构体里存引用必须声明生命周期参数:struct Excerpt { part: &str } 报 error[E0106]: missing lifetime specifier(建议引入命名的生命周期参数)。写成 struct Excerpt<'a> { part: &'a str } 就行,从一段文字里切出第一句存进去,输出「摘录:Call me Ishmael」。", t=tl(S(1)), mark=lidx(S(1), 'error[E0106]'), done=lidx(S(1), '摘录'), kv=KV([['字段是引用', '结构体要带 <\'a>']], ["字段是引用"])),
    step("结构体不能比它借用的数据活得久:e 在外层、novel 在内层块里先死,报 error[E0597]: `novel` does not live long enough。结构体活着(后面还用 e.part)期间也不能修改被借用的 novel:novel.push_str(...) 报 error[E0502]: cannot borrow `novel` as mutable because it is also borrowed as immutable。", t=tl(S(2)), mark=lidx(S(2), 'error[E0597]', 'error[E0502]'), kv=KV([['数据先死', 'E0597'], ['借用期间修改', 'E0502']], ['数据先死'])),
    step("带引用的结构体就是零拷贝:对 1 万个词的文本分词,借用版 Tokens { words: Vec<&str> } 只做了 13 次堆分配(都是 Vec 自己的扩容),拥有版 OwnedTokens { words: Vec<String> } 做了 10013 次(1 万个 String + 13 次扩容)。第 5000 个词两者内容相同(word5000)。代价就是借用版不能比 text 活得久。", t=tl(S(3)), mark=lidx(S(3), '借用版', '拥有版'), b=bars([['借用版 Vec<&str>', 13, '13 次'], ['拥有版 Vec<String>', 10013, '10,013 次']], 10013, mark=[1], done=[0]), kv=KV([['借用版', '13 次堆分配'], ['拥有版', '10013 次堆分配']], ['拥有版'])),
    step("一个结构体可以有多个互相独立的生命周期参数:Pair<'a, 'b> { left: &'a str, right: &'b str }。内层块里 b 先死,但只把 'a 那部分(tmp.left)取出来在外层用是合法的:输出「内层:长寿的 短命的」「外层:长寿的」。", t=tl(S(4)), done=lidx(S(4), '内层', '外层'), kv=KV([["<'a, 'b>", '各自独立'], ['取出 left', "只受 'a 约束"]], ["<'a, 'b>"])),
]
A = mkart('u25', 25, 'Rust,生命周期,Struct,零拷贝,分配,真实验证,动画演示',
    '用真实编译与计数分配器验证结构体里保存引用:字段是引用必须声明生命周期参数(E0106);结构体不能比数据活得久(E0597)、借用期间不能修改数据(E0502);借用版分词器堆分配 13 次而拥有 String 的版本 10013 次;多个互相独立的生命周期参数。',
    '把引用存进结构体是 Rust 里「零拷贝」的主要手段,也是生命周期标注最常出现的地方。这篇验证它的语法要求、它对数据寿命和修改的限制,并用一个自定义的计数分配器量出它省下了多少堆分配。',
    [('E0106', '结构体字段是引用却没声明生命周期'), ('13 vs 10013', '借用版与拥有版分词器的堆分配次数(1 万个词)'), ("<'a, 'b>", '一个结构体可以有多个独立的生命周期参数')],
    [('语法要求', None), ('寿命与修改限制', None), ('零拷贝的收益', '<p>分配次数通过自定义 <code>#[global_allocator]</code> 计数得到(只数 alloc 次数,不含字节数);release 构建。自定义分配器相关的更多内容这里没有展开。</p>'), ('多个生命周期参数', None)],
    steps, [ENV_U + '。分配次数为 release 构建下单次运行的结果', '没有验证:分配的字节数与耗时对比、带泛型与 trait bound 的 Struct<\'a, T>、自引用结构体(Pin 相关)、cow 版本(见 Cow 一篇)'], '结构体中的引用')
