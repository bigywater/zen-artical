from lib import *
S = SS('u22')
steps = [
    step("NLL(非词法生命周期)让借用只持续到最后一次使用:let first = &v[0]; 打印 first 之后,v.push(4) 就合法了(输出 [1, 2, 3, 4]);同样 let r = &mut v; r.push(5); 之后 v.push(6) 也合法。在旧的「借用持续到块结束」规则下这两处都会被拒绝。", t=tl(S(1)), done=lidx(S(1), 'first = 1', '[1, 2, 3, 4'), kv=KV([['借用结束于', '最后一次使用'], ['不是', '块结束']], ['借用结束于'])),
    step("借用按控制流分析:let r = &s; 之后 if 分支里用 r,else 分支里 s.push('b')。r 只在 if 路径上存活,else 路径上它已经「死」了,所以 else 里可以修改 s,最终输出 ab(命令行参数少于 5 个,走 else)。编译器检查的是每一条路径。", t=tl(S(2)), done=lidx(S(2), 'ab'), kv=KV([['借用的存活', '按控制流路径计算']], ['借用的存活'])),
    step("两阶段借用:v.push(v.len()) 合法(输出 [1, 2, 3, 3]):调用 push 时先取 &mut v,但这个可变借用在参数求值完之前还没「激活」,所以可以先读 v.len()。如果提前把 &mut 保存下来 let r = &mut v; r.push(v.len());,就是真的冲突:error[E0502]: cannot borrow `v` as immutable because it is also borrowed as mutable。", t=tl(S(3)), mark=lidx(S(3), 'error[E0502]'), done=lidx(S(3), '[1, 2, 3, 3]'), kv=KV([['v.push(v.len())', '合法(两阶段借用)'], ['r.push(v.len())', 'E0502']], ['v.push(v.len())'])),
    step("NLL 不会缩短有 Drop 的持有者的借用:struct Guard<'a>(&'a mut Vec<i32>) 实现了 Drop(drop 里还会读 self.0),let g = Guard(&mut v); 之后 v.push(2) 报 error[E0499]: cannot borrow `v` as mutable more than once at a time —— g 虽然之后没有再被用,但在作用域结束时 drop 会用到它的借用。把 Guard 放进更小的块 { let _g = ...; } 让它先 drop,就合法了:输出「Guard 释放,vec 长度 1」与 [1, 2]。", t=tl(S(4)), mark=lidx(S(4), 'error[E0499]'), done=lidx(S(4), 'Guard 释放', '[1, 2]'), kv=KV([['有 Drop 的持有者', '借用延续到 drop'], ['缩小作用域', '先 drop,再借']], ['有 Drop 的持有者'])),
    step("rustc 的借用检查器内部确实是在 MIR 控制流图上算的:用 -Z dump-mir=main(RUSTC_BOOTSTRAP=1)得到 nll 的转储,里面「Inferred Region Values」是每个区域 '?N 覆盖的 MIR 位置集合,如 '?3 = {bb4[1..=16], bb5[0..=12], bb6[0..=4]} —— 区域是 MIR 点的集合,不是源码里的 {} 块。", t=tl(S(5)), mark=lidx(S(5), "'?3", "'?2"), kv=KV([['借用区域', 'MIR 位置的集合'], ['不是', '源码块']], ['借用区域'])),
]
A = mkart('u22', 22, 'Rust,NLL,借用检查,MIR,真实验证,动画演示',
    '用真实编译验证 NLL:借用只持续到最后一次使用(旧规则会拒绝的代码被接受);借用按控制流路径存活;两阶段借用使 v.push(v.len()) 合法而保存 &mut 后读 v 则 E0502;有 Drop 的持有者让借用延续到 drop(E0499),缩小作用域修复;用 -Z dump-mir 看 NLL 的区域是 MIR 位置的集合。',
    'NLL 是 Rust 2018 之后借用检查的基础:借用不再「到块结束」,而是「到最后一次使用」。这篇用几个对比实验验证它做了什么、没做什么:控制流里的借用、两阶段借用、Drop 为什么会让借用变长,最后直接看 rustc 内部保存的区域信息。',
    [('最后一次使用', 'NLL 下借用的结束位置'), ('两阶段借用', 'v.push(v.len()) 合法的原因'), ('MIR 点集', 'NLL 区域在 rustc 内部的表示(-Z dump-mir)')],
    [('借用到最后一次使用', None), ('控制流', None), ('两阶段借用', None), ('Drop 与借用', '<p>Drop 的规则见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>。</p>'), ('NLL 的区域', '<p>MIR 是什么见<a href="rust-mir.html">MIR 是什么</a>。-Z 选项靠 <code>RUSTC_BOOTSTRAP=1</code> 在稳定版上打开,仅用于观察。</p>')],
    steps, [ENV_U + '。MIR 转储来自 rustc 1.98.1 的 -Z dump-mir=main,格式随版本变化', '没有验证:Polonius(更精确的下一代借用检查,未稳定)、"问题案例 #3"(条件返回借用)在当前版本是否被接受、闭包与 NLL 的交互、对 async 状态机里借用的处理'], 'NLL')
