from lib import *
R = J('u3')
S = SS('u3')
steps = [
    step("let x = 5; 之后再写 x = 6; 编译不过:error[E0384]: cannot assign twice to immutable variable `x`。编译器同时标出第一次赋值的位置(第 2 行)与第二次赋值的位置(第 4 行),并建议把 let x 改成 let mut x。这是语言的默认行为:变量绑定不可变,想改要显式写 mut。", t=tl(S(1)), mark=lidx(S(1), 'error[E0384]'), kv=KV([['错误码', 'E0384'], ['默认', '绑定不可变']], ['错误码'])),
    step("加上 mut 就能编译运行:x = 5、x = 6。把 mut 变量的值赋给不可变变量 y 也允许(y = 6)—— mut 是「这个变量绑定可以被重新赋值或可变借用」的属性,不改变值的类型。", t=tl(S(2)), done=[0], kv=KV([['let mut x', '可重新赋值'], ['let y = x', '允许,y 是另一个不可变绑定']], ['let mut x'])),
    step("不可变是「深」的,不只是变量本身:给没有 mut 的结构体 p 的字段赋值是 E0594(cannot assign to `p.a`),对没有 mut 的 Vec 调用需要 &mut self 的 push 是 E0596(cannot borrow `v` as mutable)。两个错误同时报出,每个都带「consider changing this to be mutable」的修复建议。", t=tl(S(3)), mark=lidx(S(3), 'error[E0594]', 'error[E0596]'), kv=KV([['字段赋值', 'E0594'], ['&mut self 方法', 'E0596']], ['字段赋值'])),
    step("延迟初始化:let x; 声明后,if/else 两个分支各赋一次 x 是合法的(每条路径恰好赋值一次);但 x = 1; x = 2; 报 E0384(cannot assign twice),并额外给出一个 unused_assignments 警告(第一次赋的值从未被读)。", t=tl(S(4)), mark=lidx(S(4), 'error[E0384]'), kv=KV([['分支各赋一次', '合法'], ['赋两次', 'E0384']], ['赋两次'])),
    step("mut 没有运行时开销:同一个计算分别用 let 与 let mut 写成两个函数,-O 编译后 imm 只有 4 条指令(mov、mov、madd、ret);mutv 在汇编里没有单独的函数体,只有一行 `_mutv = _imm` —— LLVM 发现两个函数完全相同,直接把它们合并成别名。可变性检查完全发生在编译期。", t=tl(S(5)), done=[0, 1], b=bars([['imm 的指令数', 4, '4'], ['mutv 的指令数(别名)', 4, '4(= imm)']], 5, done=[0, 1]), kv=KV([['机器码', 'imm 与 mutv 完全相同']], ['机器码'])),
]
A = dict(
    n=3, series='rust', tags='Rust,不可变,mut,编译错误,真实验证,动画演示',
    desc='用真实的 rustc 1.98 报错验证「变量默认不可变」:重复赋值 E0384、字段赋值 E0594、对不可变 Vec 调用 push E0596、延迟初始化的合法与非法形式;并用汇编证明 let 与 let mut 写出的函数机器码完全相同(LLVM 直接合并成别名)。',
    lead='「变量默认不可变」是 Rust 最先遇到的规则。这篇把规则逐条变成编译器的原话:哪些写法会报什么错、错误提示怎么指出两次赋值的位置、延迟初始化到底允许什么,最后用汇编确认 mut 这个修饰词在运行时一点代价都没有。',
    facts=[('E0384', '给不可变变量重复赋值的错误码'), ('深', '不可变连字段赋值(E0594)与 &mut self 方法(E0596)都挡住'), ('0 开销', 'let 与 let mut 的函数 -O 后机器码相同(合并成别名)')],
    body=[
        sec('默认不可变', '', term('', blk('u3', 1)), '<p>注意编译器给的修复建议(consider making this binding mutable)—— 但是否该这么改,要看你为什么要重新赋值。很多时候新建一个变量(见<a href="rust-shadowing-vs-mut.html">Shadowing 与 mut 的区别</a>)更合适。</p>'),
        sec('加上 mut', '', term('', blk('u3', 2))),
        sec('不可变是深的', '', term('', blk('u3', 3)), '<p>字段赋值与 push 为什么要求 mut,与借用规则有关:push 需要 <code>&amp;mut self</code>,而要拿到可变借用,绑定必须是 mut 的(见<a href="rust-shared-vs-mut-borrow.html">不可变借用与可变借用</a>)。</p>'),
        sec('延迟初始化', '', term('', blk('u3', 4))),
        sec('机器码里没有 mut', '', term('', blk('u3', 5)), '<p>这是「零成本抽象」的一个最小例子(见<a href="rust-zero-cost-abstraction.html">Zero-Cost Abstraction</a>)。</p>'),
        sec('分步演示', '', demo('不可变与 mut', [('t', 'term', '编译器输出'), ('b', 'bars', '指令数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。编译器报错是原样的 rustc 1.98.1 输出(路径已替换为 <实验目录>);汇编用 --emit=asm -O 生成,目标 aarch64-apple-darwin', '没有验证:其它目标平台(x86_64)上的汇编、debug 构建里 let 与 let mut 的 MIR 差别、模式匹配里 mut 绑定、闭包捕获时的可变性'],
)
