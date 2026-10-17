from lib import *
S = SS('u110')
steps = [
    step("指针本身的大小:Box<u64>、Rc<u64>、Arc<u64> 都是 8 字节(一个指针);指向 dyn Debug、str、切片时变成 16 字节的胖指针(Box<dyn Debug>、Rc<str>、Arc<[u32]>、Box<[u8]> 都是 16);Option<Box>、Option<Rc>、Option<Arc> 仍是 8 字节(空指针优化)。Vec<u8> 与 String 是 24 字节(指针 + 容量 + 长度)。", t=tl(S(1)), done=lidx(S(1), 'Box<u64> 8', 'Box<dyn Debug> 16', 'Box<[u8]> 16', 'Option<Box<u64>> 8', 'Vec<u8> 24'), kv=KV([['Box / Rc / Arc', '8 字节'], ['dyn / str / 切片', '16 字节胖指针'], ['Option<…>', '仍是 8 字节']], ['dyn / str / 切片'])),
    step("堆上实际分配(用全局分配器记录 Layout):Box<u64> 分配 8 字节;Rc<u64> 和 Arc<u64> 都是 24 字节 = 8 字节数据 + 16 字节计数器(strong 与 weak 各 8 字节),都是 1 次分配;Rc<[u8; 100]> 是 120 字节(116 补到 8 的倍数);Rc<str> 从 \"hello\" 创建也是 24 字节、1 次分配 —— 字符串与计数器在同一块内存里。Box<()> 零大小类型,0 次分配。", t=tl(S(2)), done=lidx(S(2), 'Box<u64>(8', 'Rc<u64>', 'Arc<u64>', 'Rc<[u8; 100]>', 'Rc<str>', 'Box<()>'), b=bars([['Box<u64>', 8, '8 B'], ['Rc<u64>', 24, '24 B'], ['Arc<u64>', 24, '24 B']], 26, done=[0, 1, 2]), kv=KV([['Box<u64>', '8 字节'], ['Rc<u64> / Arc<u64>', '24 字节 = 16 计数器 + 8 数据']], ['Rc<u64> / Arc<u64>'])),
    step("偷看计数器(unsafe,只用于观察):Rc::as_ptr 指向数据,往前读 16 字节就是 (strong, weak)。Rc::new 后是 (1, 1) —— weak 从 1 开始,代表「所有强引用合起来」持有的一个隐式弱引用;clone 一次变 (2, 1);downgrade 一次变 (2, 2)(而 weak_count() 公开返回 1,扣掉了隐式的那一个)。Arc 的布局相同,clone 后 (2, 1)。", t=tl(S(3)), done=lidx(S(3), 'Rc::new', 'clone 一次', 'downgrade', 'Arc 同样'), kv=KV([['Rc::new', '(strong 1, weak 1)'], ['clone', '(2, 1)'], ['downgrade', '(2, 2)']], ['downgrade'])),
    step("两个 Rc 都 drop 之后 Weak::upgrade() 返回 None:数据已销毁,但内存块还在,因为计数器还要被 Weak 读取。", t=tl(S(3)), mark=lidx(S(3), 'drop 两个 Rc'), kv=KV([['强引用为 0', '数据 drop'], ['弱引用仍在', '内存块保留']], ['弱引用仍在'])),
    step("用 Drop 与分配器统计证明:创建 Rc + Weak 后存活堆块 +1;drop 最后一个强引用时 Noisy::drop 被调用(数据销毁),但存活堆块仍是 +1(内存块还在);drop 最后一个 Weak 之后才归还,变成 +0。数据的销毁与内存的释放是两个时刻。", t=tl(S(4)), done=lidx(S(4), 'Noisy::drop', '创建 Rc + Weak 后', 'drop 最后一个强引用后', 'drop 最后一个 Weak 后'), kv=KV([['最后一个强引用', 'drop 数据'], ['最后一个 Weak', '释放内存块']], ['最后一个 Weak'])),
]
A = mkart('u110', 110, 'Rust,Box,Rc,Arc,内存布局,真实验证,动画演示',
    '用真实运行验证 Box、Rc、Arc 的内存布局:指针 8 字节、胖指针 16 字节、Option 不增加大小;堆块大小(Box<u64> 8、Rc/Arc<u64> 24 = 16 计数器 + 8 数据;Rc<str> 单块分配);偷看 (strong, weak) 计数器;数据在最后一个强引用 drop,内存块在最后一个 Weak 才释放。',
    'Rc 比 Box 多占多少内存?计数器放在哪里?Weak 为什么能在数据销毁后继续存在?这篇用 size_of、全局分配器的 Layout 记录、直接读堆内存和 Drop 计数,把 Box / Rc / Arc 的内存布局量出来。',
    [('24 字节', 'Rc<u64> / Arc<u64> 在堆上的分配大小(Box<u64> 是 8)'), ('16 字节', 'Rc / Arc 前面的 strong + weak 计数器'), ('1 次', 'Rc<str> 从 &str 创建时的堆分配次数')],
    [('指针本身', '<p>Box 的基础见<a href="rust-box-heap.html">Box&lt;T&gt; 与堆分配</a>。</p>'), ('堆块的大小', None), ('计数器', '<p>Rc 的行为见<a href="rust-rc-shared-ownership.html">Rc&lt;T&gt;</a>,Weak 见<a href="rust-weak-cycles.html">Weak&lt;T&gt;</a>。</p>'), ('数据与内存块的释放时机', None)],
    steps, [ENV_U + '。偷看计数器用的是 unsafe 指针读取,依赖当前标准库的内存布局(RcBox 的字段顺序),不是稳定保证', '没有验证:Arc 的原子计数器的内存序、Rc<dyn Trait> 的块布局(vtable 在胖指针里,没有在堆块里)、Box<dyn> 的 drop 路径、其它平台的大小与对齐'], 'Box、Rc、Arc 布局')
