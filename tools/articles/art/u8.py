from lib import *
R = J('u8')
S = SS('u8')
steps = [
    step("match 必须覆盖所有可能:只写 North 与 East,漏掉 South、West,编译不过 —— error[E0004]: non-exhaustive patterns: `Dir::South` and `Dir::West` not covered。编译器不但列出漏掉的变体,还给出可以直接粘贴的修复(Dir::South | Dir::West => todo!())。", t=tl(S(1)), mark=lidx(S(1), 'error[E0004]'), kv=KV([['漏变体', 'E0004'], ['提示', '列出缺的模式 + 修复建议']], ['漏变体'])),
    step("模式的写法很丰富:字面量 0、多选 1 | 2 | 3、范围 4..=9、通配 _;对枚举解构 Msg::Move { x, y: 0 }、守卫 if *y < 0、@ 绑定 n @ 18..=64、元组 (x, y) if x + y == 0。输出里 Move { x: 3, y: -1 } 走了带守卫的分支「向下 -1,横向 3」,25 岁走了 @ 绑定「成年人,年龄 25」。", t=tl(S(2)), done=lidx(S(2), '→', '成年人', '元组'), kv=KV([['守卫', 'if 条件'], ['@ 绑定', '同时匹配范围并命名']], ['守卫'])),
    step("`_` 通配会隐藏「新增变体」:Level 只有 Low、High 时,显式列全的 match 与带 _ 的 match 都能编译。给 Level 新增变体 Critical 之后,显式列全的 match 立刻报 E0004(`Level::Critical` not covered)—— 编译器逼你检查所有用到这个枚举的地方;而带 _ 的 match 悄悄编译通过,Critical 被归入 _ 的分支(输出 2)。想在演进中被编译器保护,枚举上的 match 尽量不写 _。", t=tl(S(3)), mark=lidx(S(3), 'error[E0004]'), done=lidx(S(3), '运行(退出码 0)'), kv=KV([['显式列全', '新增变体 → 编译错误'], ['写 _', '新增变体 → 静默通过']], ['写 _'])),
    step("match 是表达式,所有分支的类型必须一致:一个分支返回 &str、另一个返回整数,报 error[E0308]: `match` arms have incompatible types。整数的穷尽性同样被检查:对 u8 写 0..=254,漏了 255,报 non-exhaustive patterns: `u8::MAX` not covered。", t=tl(S(4)), mark=lidx(S(4), 'error[E0308]', 'error[E0004]'), kv=KV([['分支类型不一致', 'E0308'], ['u8 漏 255', 'E0004(u8::MAX)']], ['u8 漏 255'])),
]
A = dict(
    n=8, series='rust', tags='Rust,match,模式匹配,枚举,真实验证,动画演示',
    desc='用真实的 rustc 报错验证 match 的穷尽性:漏变体报 E0004 并给出修复;字面量、范围、守卫、@ 绑定等模式;新增枚举变体时显式 match 报错而 _ 通配悄悄通过;分支类型不一致 E0308;u8 漏掉 255 也被发现。',
    lead='match 的「穷尽」是 Rust 最实用的安全网之一:编译器替你检查所有情况都处理了。这篇逐条验证它到底查什么、报错信息长什么样、模式有哪些写法,以及一个常被忽视的取舍 —— 用 _ 通配符会让这张安全网在你新增枚举变体时失效。',
    facts=[('E0004', '漏掉变体/数值时的错误码,并附修复建议'), ('_ 的代价', '新增枚举变体时,带 _ 的 match 不报错、显式 match 报错'), ('u8::MAX', '对 u8 写 0..=254 时编译器指出漏掉的值')],
    body=[
        sec('穷尽性检查', '', term('', blk('u8', 1))),
        sec('模式的写法', '', term('', blk('u8', 2)), '<p>更紧凑的单模式写法见<a href="rust-if-let-let-else.html">if let 与 let else</a>。</p>'),
        sec('_ 与枚举演进', '', term('', blk('u8', 3)), '<p>对「别人的、会增长的」枚举(标了 <code>#[non_exhaustive]</code> 的)你反而必须写 _;这个属性我没有在这里验证。</p>'),
        sec('分支类型与整数穷尽', '', term('', blk('u8', 4))),
        sec('分步演示', '', demo('match 的穷尽匹配', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。错误信息是原样的 rustc 1.98.1 输出', '没有验证:#[non_exhaustive]、match 在 release 下的代码生成(跳转表还是比较链)、or-pattern 在嵌套位置的限制、对引用与 Box 的 match 的自动解引用(match ergonomics)、字符串的 match'],
)
