from lib import *
S = SS('u84')
steps = [
    step("const _: () = assert!(size_of::<Header>() == 8, \"…\"); 在编译期求值:#[repr(C)] struct Header { tag: u8, len: u32 } 确实是 8 字节,断言通过,程序编译运行,打印 size = 8。", t=tl(S(1)), done=lidx(S(1), 'size = 8'), kv=KV([['条件为真', '编译通过,无运行期代价']], ['条件为真'])),
    step("把条件改成 == 6:编译失败,error[E0080]: evaluation panicked: Header 必须是 6 字节,指向断言所在的行。断言消息就是你写的字符串。", t=tl(S(1)), mark=lidx(S(1), 'error[E0080]'), kv=KV([['条件为假', 'E0080:evaluation panicked']], ['条件为假'])),
    step("断言通过时没有任何运行期痕迹:有 const 断言与没有断言的函数 f(x) = x + 1,-O 下汇编都是 2 行,逐行相同。", t=tl(S(2)), done=lidx(S(2), '逐行相同'), kv=KV([['汇编', '两版本逐行相同(2 行)']], ['汇编'])),
    step("泛型里的断言写在关联常量里:impl<const N: usize> Buf<N> { const OK: () = assert!(N.is_power_of_two()) },new() 里 let () = Self::OK 触发求值。Buf::<8>::new() 通过,打印「Buf::<8> 创建成功」。", t=tl(S(3)), done=lidx(S(3), 'Buf::<8> 创建成功'), kv=KV([['关联常量 OK', '被使用时才求值']], ['关联常量 OK'])),
    step("实例化 Buf::<6> 时才失败:error[E0080]: evaluation panicked: N 必须是 2 的幂,附带 note「erroneous constant encountered」与「the above error was encountered while instantiating `fn Buf::<6>::new`」。没被用到的 N 不会触发。", t=tl(S(3)), mark=lidx(S(3), 'error[E0080]', 'instantiating'), kv=KV([['Buf::<6>', '单态化时报错'], ['note', 'instantiating fn Buf::<6>::new']], ['Buf::<6>'])),
    step("表达式位置可用 inline const:fn first_n<const N: usize>() { const { assert!(N > 0 && N <= 4, \"…\") }; [0; N] }。first_n::<3>() 得 [0, 0, 0];first_n::<9>() 编译失败,evaluation panicked: N 必须在 1..=4,note 指出实例化的是 `fn first_n::<9>`。", t=tl(S(4)), done=lidx(S(4), '[0, 0, 0]'), mark=lidx(S(4), 'error[E0080]', 'first_n::<9>'), kv=KV([['const { assert!(…) }', '每个实例化各检查一次']], ['const { assert!(…) }'])),
    step("另一种写法:const _: [(); 0 - (cond) as usize] = []; 条件为真时长度为 0 通过,条件为假时 0 - 1 下溢,报 error[E0080]: attempt to compute `0_usize - 1_usize`, which would overflow —— 能拦住,但错误消息不说明真正的问题,不如 assert! 清楚。", t=tl(S(5)), mark=lidx(S(5), 'error[E0080]', 'overflow'), kv=KV([['数组长度技巧', '能拦住,消息不可读']], ['数组长度技巧'])),
]
A = mkart('u84', 84, 'Rust,编译期断言,const,assert,真实验证,动画演示',
    '用真实编译验证编译期断言:const _: () = assert!(...) 条件为假时 E0080: evaluation panicked,消息就是自定义字符串;通过时汇编与无断言逐行相同;泛型关联常量与 inline const 块在实例化时才失败,note 指出 instantiating 哪个实例;数组长度下溢技巧也能拦截但消息不可读。',
    '把不变量检查从运行期挪到编译期:结构体大小、泛型参数范围……这篇用 const assert、关联常量和 inline const 块验证它们什么时候求值、报什么错、有没有运行期成本。',
    [('E0080', '常量求值失败的错误码'), ('0 行', '通过的 const 断言给汇编增加的行数(逐行相同)'), ('instantiating', '泛型断言失败时 note 里指出具体实例的关键词')],
    [('const 断言', None), ('零运行期成本', None), ('泛型里的断言', None), ('inline const 块', None), ('数组长度技巧', '<p>布局相关的例子见<a href="rust-struct-alignment-padding.html">Struct 对齐与 Padding</a>。</p>')],
    steps, [ENV_U + '。汇编用 rustc --emit=asm -O', '没有验证:static_assertions crate 的宏(没有下载使用)、const fn 里更复杂的断言(循环、字符串比较)、assert_eq! 在 const 里的使用(当前稳定版可能受限,未测)、debug_assert! 的区别'], '编译期断言')
