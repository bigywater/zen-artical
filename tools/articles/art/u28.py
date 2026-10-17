from lib import *
import re
S = SS('u28')
_m = re.findall(r'每次约 ([\d.]+) ns', '\n'.join(S(3))); _a, _b = float(_m[0]), float(_m[1])
ratio = _a / _b
steps = [
    step("Box<T> 把值放到堆上:Box<i32> 本身只是一个 8 字节的指针(i32 是 4 字节)。局部 i32 在栈上(0x16f…),Box 里的 i32 在堆上(0x1011…),两个地址相差上千 MiB;*boxed + 1 自动解引用得 6。", t=tl(S(1)), done=lidx(S(1), 'size_of', '*boxed'), kv=KV([['Box<i32>', '8 字节的指针'], ['值', '在堆上']], ['Box<i32>'])),
    step("递归类型必须有限大小:enum List { Cons(i32, List), Nil } 报 error[E0072]: recursive type `List` has infinite size,并建议「insert some indirection (e.g., a `Box`, `Rc`, or `&`)」。写成 Cons(i32, Box<List>) 就行:一个 3 个节点的链表 sum = 6,而 size_of::<List>() 只有 16 字节,与链表有多长无关。", t=tl(S(2)), mark=lidx(S(2), 'error[E0072]'), done=lidx(S(2), 'sum = 6'), kv=KV([['没有 Box', 'E0072(无限大)'], ['有 Box', 'List 16 字节']], ['有 Box'])),
    step(f"移动 Box 只复制 8 字节的指针:release 构建下,按值传递并返回一个 1 MiB 的数组 [u8; N],每次约 {_a:,.0f} ns(复制了 1 MiB);传递并返回 Box<[u8; N]> 每次约 {_b:.1f} ns —— 差了约 {ratio:,.0f} 倍。大对象要频繁移动时,装进 Box 是个简单的办法。", t=tl(S(3)), b=bars([['传 [u8; 1 MiB]', _a, f'{_a:,.0f} ns'], ['传 Box<[u8; 1 MiB]>', _b, f'{_b:.1f} ns']], _a, mark=[0], done=[1]), kv=KV([['数组', f'约 {_a/1000:.0f} µs'], ['Box', f'约 {_b:.0f} ns']], ['Box'])),
    step("Box 离开作用域时 drop 并释放堆内存:用计数分配器观察,Box 存在时 alloc +1、dealloc +0;离开作用域后 dealloc +1(先记下数字再打印,因为 println! 本身也会分配)。", t=tl(S(4)), mark=lidx(S(4), '离开作用域后'), kv=KV([['创建 Box', 'alloc +1'], ['离开作用域', 'dealloc +1']], ['离开作用域'])),
]
A = mkart('u28', 28, 'Rust,Box,堆分配,递归类型,真实验证,动画演示',
    f'用真实编译与计时验证 Box<T>:Box 是 8 字节的指针、值在堆上;递归类型没有 Box 报 E0072、有 Box 的链表 size_of 恒为 16 字节;移动 1 MiB 数组约 {_a/1000:.0f} µs 而移动 Box 约 {_b:.0f} ns;Box 离开作用域时 dealloc 一次。',
    'Box<T> 是最简单的智能指针:把一个值放到堆上,拥有它,离开作用域时释放。这篇验证它的三个典型用途:让大对象便宜地移动、让递归类型有限大小、以及它的释放时机,每一条都有真实数字。',
    [('E0072', '递归类型无限大小,需要 Box 打断'), (f'≈ {ratio:,.0f} 倍', f'移动 Box 相对移动 1 MiB 数组的速度({_b:.0f} ns vs {_a/1000:.0f} µs)'), ('8 字节', 'Box<T> 本身的大小(指针)')],
    [('Box 是什么', None), ('递归类型', '<p>链表等递归结构的更多讨论(为什么 LinkedList 通常不是首选)见<a href="rust-linkedlist-not-default.html">LinkedList 为什么通常不是首选</a>。</p>'), ('移动的成本', '<p>计时用 release 与 black_box,数字是单次运行结果。内存布局见<a href="rust-box-rc-arc-layout.html">Box、Rc、Arc 的内存布局</a>。</p>'), ('Box 的释放', None)],
    steps, [ENV_U + '。计时为 release 构建', 'Box<dyn Trait>(见 Trait Object 一篇)、Box<[T]> 与 Vec 的转换、栈溢出时 Box 的作用(只在移动成本上验证了 Box,没有验证栈上放不下的大数组的情形)'], 'Box<T>')
