from lib import *
S = SS('u21')
steps = [
    step("迭代时修改集合:for x in &v { v.push(99) } 报 error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable —— for 循环里的迭代器持有对 v 的只读借用,push 需要 &mut。这正是 C++ 里「迭代器失效」会引发未定义行为的场景,Rust 在编译期就拒绝。", t=tl(S(1)), mark=lidx(S(1), 'error[E0502]'), kv=KV([['迭代时 push', 'E0502']], ['迭代时 push'])),
    step("两个 &mut 指向同一个 Vec:swap_halves(&mut v, &mut v) 报 error[E0499]: cannot borrow `v` as mutable more than once at a time。合法的做法是把切片拆成不相交的两半:v.split_at_mut(2) 得到 left、right 两个互不重叠的 &mut,交换后 v = [3, 4, 1, 2]。独占的要求是针对「重叠」的,不是针对「同一个变量」。", t=tl(S(2)), mark=lidx(S(2), 'error[E0499]'), done=lidx(S(2), '[3, 4, 1, 2]'), kv=KV([['两个 &mut 重叠', 'E0499'], ['split_at_mut', '不相交,合法']], ['split_at_mut'])),
    step("独占性是优化的前提:with_mut(a: &mut i32, b: &mut i32) 写 *a = 1、*b = 2 后返回 *a —— 编译器知道 a、b 不会指向同一处,汇编里直接 mov w0, #1(返回常量);同样逻辑用裸指针写的 with_ptr,a、b 可能是同一个地址,汇编必须在写完 *b 之后 ldr w0, [x0] 重新读 *a。Rust 把 &mut 标成 noalias 告诉 LLVM 这一点。", t=tl(S(3)), mark=lidx(S(3), 'with_mut', 'with_ptr'), kv=KV([['&mut 版本', 'mov w0, #1(常量)'], ['裸指针版本', 'ldr w0, [x0](重新读)']], ['&mut 版本'])),
    step("&mut 不是 Copy:let b = a; 把 &mut 移动给 b,之后再用 a 报 error[E0382]: use of moved value: `a`。独占的引用只能有一个持有者。", t=tl(S(4)), mark=lidx(S(4), 'error[E0382]'), kv=KV([['&mut', '不能复制,只能移动']], ['&mut'])),
]
A = mkart('u21', 21, 'Rust,借用,&mut,noalias,真实验证,动画演示',
    '用真实编译与汇编验证可变借用为什么必须独占:迭代时 push 报 E0502(C++ 的迭代器失效在 Rust 里是编译错误);两个重叠的 &mut 报 E0499、split_at_mut 提供不相交的两个 &mut;&mut 版本函数直接返回常量 1 而裸指针版本要重新读内存;&mut 不是 Copy。',
    '为什么同一时刻只能有一个 &mut?除了防止数据竞争,独占性还给编译器带来了好处。这篇从四个角度验证:最常见的违规场景(迭代时修改)、合法的拆分(split_at_mut)、独占性换来的优化(汇编里少一次内存读取),以及 &mut 不能复制。',
    [('E0499', '两个 &mut 重叠时的错误'), ('mov w0, #1', '&mut 版本直接返回常量;裸指针版本要 ldr 重新读'), ('split_at_mut', '拆成不相交的两个 &mut 是合法的')],
    [('迭代时修改', None), ('别名与 split_at_mut', None), ('独占带来的优化', '<p>汇编用 <code>--emit=asm -O</code> 生成;只是一个很小的例子,不能据此估计实际程序里的收益。</p>'), ('不是 Copy', None)],
    steps, [ENV_U + '。汇编目标 aarch64-apple-darwin', '没有验证:noalias 对真实程序性能的影响、LLVM 在不同版本对 noalias 的使用、&mut 与 UnsafeCell 的关系、Stacked Borrows / Tree Borrows 模型(需要 Miri)'], '可变借用的独占')
