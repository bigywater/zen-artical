from lib import *
S = SS('u121')
steps = [
    step("创建裸指针是安全的,只有解引用需要 unsafe:&x 和 &mut x 都能转成 *const i32 / *mut i32,两者地址相同(true);null() 的 is_null 为 true;通过 *mut 加 5 后 *p = 15。悬空指针(指向已离开作用域的 y)创建时编译器也不报错 —— 它只是一个地址,解引用才是未定义行为(这里没有解引用)。", t=tl(S(1)), done=lidx(S(1), '创建裸指针', 'null.is_null()', '通过 *mut', '悬空指针'), kv=KV([['创建 / 比较 / 转换', '安全'], ['解引用', 'unsafe']], ['解引用'])),
    step("指针算术以「元素」为单位:u32 数组 p.add(2) 指向 30,地址比 p 大 8 字节;wrapping_byte_add(4) 才是按字节(大 4 字节);u8 数组同样 add(2) 只差 2 字节;offset_from 得到两个指针之间相差的元素个数(4)。", t=tl(S(2)), done=lidx(S(2), 'p.add(2)', 'byte_add', 'q - p', 'u8 数组'), kv=KV([['add(n)', 'n × size_of::<T>() 字节'], ['byte_add(n)', 'n 字节'], ['offset_from', '元素个数']], ['add(n)'])),
    step("两个 &mut 指向同一个 x:let a = &mut x; let b = &mut x; 报 error[E0499]: cannot borrow `x` as mutable more than once at a time;裸指针是 Copy,p2 = p1 之后两个 *mut 指向同一个值,编译通过,依次修改后 x = 12。别名与读写冲突不再由编译器检查,要自己保证。", t=tl(S(3)), mark=lidx(S(3), 'error[E0499]'), done=lidx(S(3), '两个 *mut'), kv=KV([['两个 &mut', 'E0499'], ['两个 *mut', '编译通过,自己负责']], ['两个 *mut'])),
    step("Box ↔ 裸指针:Box::into_raw 把所有权交给裸指针,Box 不会再 drop;Box::from_raw 把所有权拿回来,离开作用域时正常 drop(打印「Noisy(2) drop」)。从未 from_raw 的 Noisy(1) 泄漏,永远没有它的 drop 输出。", t=tl(S(4)), done=lidx(S(4), 'into_raw', 'from_raw 把', 'Noisy(2) drop'), mark=lidx(S(4), 'Noisy(1)'), kv=KV([['into_raw', '所有权交给裸指针'], ['from_raw', '收回所有权'], ['忘记 from_raw', '泄漏']], ['忘记 from_raw'])),
    step("用裸指针实现双向链表(安全 Rust 里需要 Rc<RefCell<…>> 或 Weak):push_back 用 Box::into_raw 创建节点并连 prev/next;正向遍历 [10, 20, 30, 40],反向遍历 [40, 30, 20, 10],长度 4;Drop 里用 Box::from_raw 逐个收回并释放,打印「DList drop:释放了 4 个节点」。", t=tl(S(5)), done=lidx(S(5), '正向', 'DList drop'), kv=KV([['节点', 'Box::into_raw 创建'], ['Drop', 'Box::from_raw 逐个释放']], ['Drop'])),
]
A = mkart('u121', 121, 'Rust,裸指针,unsafe,指针算术,真实验证,动画演示',
    '用真实运行验证裸指针:创建与比较安全、解引用 unsafe;悬空指针只是地址;add 以元素为单位、byte_add 以字节为单位;两个 &mut 报 E0499 而两个 *mut 可以并存;Box::into_raw / from_raw 与泄漏;用裸指针实现带正确 Drop 的双向链表。',
    '裸指针和引用差在哪?什么时候需要它?这篇用小实验把裸指针的安全部分与 unsafe 部分分开验证:创建、比较、算术、别名、Box 往返,最后用它写一个会正确释放的双向链表。',
    [('元素为单位', 'p.add(n) 前进的单位(u32 数组 add(2) 是 8 字节)'), ('E0499 对 0', '两个 &mut 与两个 *mut 指向同一个值时的编译错误数'), ('4 个节点', 'DList 的 Drop 通过 Box::from_raw 释放的节点数')],
    [('创建与解引用', '<p>unsafe 的边界见<a href="rust-unsafe-boundary.html">unsafe 的安全边界</a>。</p>'), ('指针算术', None), ('引用与裸指针的别名', None), ('Box 与裸指针互转', '<p>Box 的内存布局见<a href="rust-box-rc-arc-layout.html">Box、Rc、Arc 的内存布局</a>。</p>'), ('裸指针链表', '<p>安全的引用计数方案见<a href="rust-weak-cycles.html">Weak&lt;T&gt; 解决循环引用</a>。</p>')],
    steps, [ENV_U, '没有验证:裸指针别名的 Stacked/Tree Borrows 规则(需要 Miri)、重复 from_raw 的双重释放后果(UB,不演示)、NonNull 与 PhantomData 的协变与 dropck、悬空指针解引用的实际现象'], '裸指针')
