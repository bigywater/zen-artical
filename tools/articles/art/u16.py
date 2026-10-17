from lib import *
S = SS('u16')
steps = [
    step("let s2 = s1; 之后再用 s1:error[E0382]: borrow of moved value: `s1`。编译器标出三处:s1 的类型是 String、它没有实现 Copy(move occurs because `s1` has type `String`, which does not implement the `Copy` trait);值在哪里被移动(let s2 = s1);哪里在移动之后又用了(println!)。它还建议在 let s2 = s1.clone() 处克隆。", t=tl(S(1)), mark=lidx(S(1), 'error[E0382]', 'value moved here'), kv=KV([['错误码', 'E0382'], ['原因', 'String 没有实现 Copy']], ['原因'])),
    step("移动的到底是什么:移动之后 s2.as_ptr() 与移动前 s1 的 as_ptr() 相等 —— 堆上的字符串数据没动,动的是 String 本身那 24 字节(指针、长度、容量)。clone() 才会分配新的堆缓冲区(新旧地址不同)。所以移动很便宜,与字符串多长无关。", t=tl(S(2)), done=lidx(S(2), 'true'), kv=KV([['移动', '拷贝 24 字节的三个字,堆数据不动'], ['clone', '新的堆缓冲区']], ['移动'])),
    step("把值传给函数也是移动:takes(a) 之后再用 a 报同样的 E0382,并建议「consider changing this parameter type in function `takes` to borrow instead」。想继续使用就让函数把所有权还回来:let b = gives_back(b),输出「拿回来了:b」;函数里的 s 在函数结束时被 drop。", t=tl(S(3)), mark=lidx(S(3), 'error[E0382]'), done=lidx(S(3), '拿回来了'), kv=KV([['传参', '移动所有权'], ['还回所有权', '函数返回它']], ['传参'])),
    step("循环里移动:for _ in 0..2 { consume(s); } 报 error[E0382]: use of moved value: `s`,并指出「value moved here, in previous iteration of loop」—— 第一轮已经把 s 移走,第二轮没有值可用。", t=tl(S(4)), mark=lidx(S(4), 'in previous iteration', 'error[E0382]'), kv=KV([['循环里移动', 'E0382(上一轮已移走)']], ['循环里移动'])),
    step("部分移动:let moved = p.a; 只把字段 a 移走,p.b 仍然可用(打印 b)。被移走的值由新的所有者负责释放:moved 又被移进内层块的 _inner,内层块结束时打印「drop a」;main 结束时才 drop 剩下的 b。每个值恰好被 drop 一次,由当前的所有者在其作用域结束时执行。", t=tl(S(5)), mark=lidx(S(5), 'drop a', 'drop b'), kv=KV([['drop a', '新所有者的块结束时'], ['drop b', 'main 结束时']], ['drop a'])),
]
A = mkart('u16', 16, 'Rust,所有权,Move,E0382,真实验证,动画演示',
    '用真实编译与运行验证 Move 语义:赋值与传参都移动所有权,再用报 E0382(含「value moved here」等三处标注与 clone 建议);移动只拷贝 String 的 24 字节、堆数据地址不变而 clone 得到新缓冲区;循环里移动;部分移动与 drop 的归属。',
    '所有权是 Rust 最核心也最让人困惑的概念,而它的入口是「移动」。这篇用编译器的完整报错和运行时的地址、drop 顺序,把移动讲清楚:它拷贝了什么、没拷贝什么,编译器是怎么追踪「已被移走」的,以及值最终在哪里被释放。',
    [('E0382', '使用已移动的值'), ('24 字节', '移动一个 String 实际拷贝的大小(指针、长度、容量)'), ('每个值 drop 一次', '由当前所有者在作用域结束时执行')],
    [('赋值即移动', None), ('移动了什么', '<p>String 的内存布局见<a href="rust-box-rc-arc-layout.html">Box、Rc、Arc 的内存布局</a>。</p>'), ('传参与返回', None), ('循环里的移动', None), ('部分移动与 drop', '<p>Drop 的规则见<a href="rust-drop-trait.html">Drop Trait 与资源释放</a>;不想转移所有权时用借用,见<a href="rust-shared-vs-mut-borrow.html">不可变借用与可变借用</a>。</p>')],
    steps, [ENV_U + '。地址比较只用「是否相等」,不依赖具体数值', '没有验证:移动在优化后是否被消除(memcpy)、Pin 与不可移动类型、闭包捕获时的移动(move 关键字)、条件移动后的 drop flag 机制'], '移动语义')
