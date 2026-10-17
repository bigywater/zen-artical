from lib import *
R = J('u7')
S = SS('u7')
steps = [
    step("Tuple:(500, 6.4, 'z') 可以混合类型,用 .0 .1 .2 取字段,也可以 let (a, b, c) = t 解构;(i32, f64, char) 占 16 字节(4 + 8 + 4,没有浪费);单元类型 () 占 0 字节;单元素元组要写成 (1,),不带逗号的 (1) 只是加了括号的表达式。", t=tl(S(1)), done=lidx(S(1), '='), kv=KV([['(i32, f64, char)', '16 字节'], ['()', '0 字节']], ['()'])),
    step("Struct:命名字段结构体 User、元组结构体 Point(f64, f64)、单元结构体 Marker(0 字节)。结构体更新语法 User { name: \"bob\".into(), ..u1.clone() } 复用其余字段。布局上有个关键事实:Loose { u8, u32, u8 } 默认布局只有 8 字节,而 #[repr(C)] 的同一个结构体是 12 字节 —— Rust 编译器可以重排字段来减少 padding(字段字节数之和是 6)。", t=tl(S(2)), mark=lidx(S(2), 'Loose{'), kv=KV([['Loose 默认布局', '8 字节'], ['#[repr(C)]', '12 字节']], ['Loose 默认布局'])),
    step("Enum:每个变体带不同的数据:Shape::Circle(f64)、Shape::Rect { w, h }、Shape::Empty。size_of::<Shape>() = 24 字节(最大变体 Rect 是 16 字节,加上标签并对齐到 8)。无数据的 Color 只占 1 字节,Red = 0、Green = 10(手动指定)、Blue = 11(接着前一个加 1)。Option<u8> 2 字节、Option<u32> 8 字节、Option<f64> 16 字节:标签的代价随对齐而变。", t=tl(S(3)), mark=lidx(S(3), 'size_of'), kv=KV([['Shape', '24 字节'], ['Option<u8> / <u32> / <f64>', '2 / 8 / 16 字节']], ['Shape'])),
    step("枚举变体里的数据不能像结构体字段那样直接访问:s.0 报 error[E0609]: no field `0` on type `Shape`。因为变量 s 可能是任何一个变体,必须先 match 或 if let 确认是哪个变体才能取数据(见下一篇)。", t=tl(S(4)), mark=lidx(S(4), 'E0609'), kv=KV([['s.0', 'E0609']], ['s.0'])),
]
A = dict(
    n=7, series='rust', tags='Rust,Tuple,Struct,Enum,内存布局,真实验证,动画演示',
    desc='用真实运行验证 Tuple、Struct、Enum:元组解构与 () 占 0 字节;结构体更新语法;默认布局会重排字段(u8,u32,u8 只占 8 字节而 repr(C) 占 12);枚举大小 = 最大变体 + 标签(Shape 24 字节),Option<u8>/<u32>/<f64> 是 2/8/16 字节;变体字段不能直接访问(E0609)。',
    lead='元组、结构体和枚举是 Rust 组织数据的三种基本形状。这篇不重复语法,而是用真实输出回答:它们各占多少内存、编译器会不会偷偷重排字段、枚举的「标签」要付出多少空间,以及为什么不能像访问字段一样访问枚举里的数据。',
    facts=[('8 vs 12', '{u8,u32,u8} 默认布局与 repr(C) 的字节数(字段之和 6)'), ('24 字节', 'enum Shape(最大变体 16 字节 + 标签)'), ('0 字节', '单元类型 () 与单元结构体')],
    body=[
        sec('Tuple', '', term('', blk('u7', 1))),
        sec('Struct', '', term('', blk('u7', 2)), '<p>字段重排的规则与 <code>#[repr(C)]</code> 的区别见<a href="rust-struct-alignment-padding.html">Struct 对齐与 Padding</a>。</p>'),
        sec('Enum', '', term('', blk('u7', 3)), '<p>枚举的内存布局(标签放在哪、niche 优化)见<a href="rust-enum-layout.html">Enum 的内存布局</a>与<a href="rust-option-ref-niche.html">Option&lt;&amp;T&gt; 的空指针优化</a>。</p>'),
        sec('枚举字段的访问', '', term('', blk('u7', 4)), '<p>取出枚举里的数据靠<a href="rust-match-exhaustive.html">match 的穷尽匹配</a>。</p>'),
        sec('分步演示', '', demo('Tuple、Struct、Enum', [('t', 'term', '编译与运行输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。大小为 64 位目标、rustc 1.98.1 的默认布局结果;默认布局不是语言规范保证的,可能随编译器版本变化', '没有验证:#[repr(u8)] 枚举、带泛型参数的枚举大小、联合体 union、结构体字段重排在不同编译器版本间是否一致'],
)
