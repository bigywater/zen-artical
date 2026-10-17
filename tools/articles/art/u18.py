from lib import *
S = SS('u18')
steps = [
    step("fn dangle() -> &String 里返回指向局部变量 s 的引用:先报 error[E0106]: missing lifetime specifier(返回类型里有借用,却没有任何参数可以借来,编译器建议直接返回 String)。给它写上生命周期 fn dangle<'a>() -> &'a String 之后,换成更直接的 error[E0515]: cannot return reference to local variable `s` —— s 在函数结束时就被释放。", t=tl(S(1)), mark=lidx(S(1), 'error[E0106]', 'error[E0515]'), kv=KV([['没写生命周期', 'E0106'], ['写了也不行', 'E0515']], ['写了也不行'])),
    step("引用比被引用的值活得久:内层块里 let x = 5; r = &x; 块结束后 x 被释放,外面还用 r,报 error[E0597]: `x` does not live long enough。", t=tl(S(2)), mark=lidx(S(2), 'error[E0597]'), kv=KV([['x 先死', 'E0597']], ['x 先死'])),
    step("最经典的悬垂:let first = &v[0]; v.push(4); println!(first) 报 error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable。为什么必须禁止:用裸指针观察 —— 容量 3 的 Vec 在 push 时重新分配(cap 变成 6),v[0] 的地址从 0x…5300 变成 0x…5170,旧地址上的内存已被释放;如果 first 还留着,就指向已释放的内存。", t=tl(S(3)), mark=lidx(S(3), 'error[E0502]', '地址变了'), kv=KV([['push 与持有引用', 'E0502'], ['push 之后', 'cap 3 → 6,元素搬家']], ['push 与持有引用'])),
    step("合法的写法:返回所有权(返回 String)、让被引用的值活得更久(x 在 r 之前声明)、先把值拷贝出来(let first = v[0],i32 是 Copy)再 push。输出:hello、r = 5、first = 1, v = [1, 2, 3, 4]。", t=tl(S(4)), done=lidx(S(4), 'hello', 'r = 5', 'first = 1'), kv=KV([['返回所有权', '不借用'], ['拷贝出值', '不再持有引用']], ['返回所有权'])),
]
A = mkart('u18', 18, 'Rust,借用检查,悬垂引用,生命周期,真实验证,动画演示',
    '用真实编译验证借用检查器如何阻止悬垂引用:返回局部变量的引用(E0106、E0515)、引用比值活得久(E0597)、持有 Vec 元素引用时 push(E0502);并用裸指针观察 push 重新分配后元素地址确实变了(cap 3→6)。',
    '悬垂引用(指向已释放内存的引用)是 C/C++ 里最常见的崩溃来源,Rust 在编译期就把它们拒之门外。这篇把三种典型的悬垂场景各编译一遍、读编译器的报错,再用 unsafe 偷看一眼 Vec 重新分配时元素真的搬家了 —— 这就是编译器拒绝它们的原因。',
    [('E0597', '`x` does not live long enough —— 引用比值活得久'), ('E0502', '持有元素引用时 push 的错误'), ('cap 3 → 6', 'push 触发重新分配,v[0] 的地址改变')],
    [('返回局部变量的引用', None), ('引用比值活得久', None), ('Vec 的悬垂', '<p>借用规则的细节见<a href="rust-shared-vs-mut-borrow.html">不可变借用与可变借用</a>、<a href="rust-exclusive-mut-borrow.html">可变借用为什么不能同时存在</a>;容量增长见<a href="rust-vec-growth.html">Vec 扩容机制</a>。</p>'), ('合法的写法', None)],
    steps, [ENV_U + '。地址对比用 unsafe 裸指针只做观察;扩容的容量值(3→6)是当前标准库的行为', '没有验证:Polonius 之类更精确的借用检查、self-referential 结构体、Box<dyn Trait + \'a> 的悬垂检查、编译器是怎么在 MIR 上计算 borrow 区域的(见 NLL 一篇)'], '悬垂引用')
