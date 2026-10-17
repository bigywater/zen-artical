from lib import *
S = SS('u52')
steps = [
    step("Iterator 只有一个必需方法 next():每次返回 Some(item),耗尽后返回 None —— 对 vec 的 iter() 连续调用 5 次得到 Some(10) Some(20) Some(30) None None。for 循环就是反复调用 next 直到 None(手写 while let Some(x) = it.next() 效果相同);map 这样的适配器本身也是迭代器。迭代器要推进自己的状态,所以变量必须是 mut:let it = v.iter(); it.next(); 报 error[E0596]: cannot borrow `it` as mutable。", t=tl(S(1)), mark=lidx(S(1), 'error[E0596]'), done=lidx(S(1), 'Some(10)', '元素', 'Some(11)'), kv=KV([['必需方法', 'next() -> Option<Item>'], ['耗尽', '返回 None']], ['必需方法'])),
    step("size_hint 给出剩余长度的 (下界, 上界):v.iter() 是 (5, Some(5));map 保持 (5, Some(5));filter 变成 (0, Some(5)) —— 过滤后数量未知,下界只能是 0;chain 相加得 (10, Some(10));take(2) 得 (2, Some(2));无穷的 (0..) 是 (usize::MAX, None)。ExactSizeIterator::len 要求精确:v.iter().len() = 5,消耗一个之后是 4。", t=tl(S(2)), mark=lidx(S(2), 'filter'), done=lidx(S(2), 'size_hint', 'len'), kv=KV([['filter', '(0, Some(5))'], ['无穷迭代器', '上界 None']], ['filter'])),
    step("双端迭代器可以从两头取:next = Some(1)、next_back = Some(6);by_ref().take(2) 只消耗前 2 个(得 [2, 3]),迭代器之后还能继续用(剩下 [4, 5]);nth(2) 跳过前 2 个并返回第 3 个(Some(3)),接着 next 得 Some(4)。empty 迭代器耗尽后再调用 next 仍是 None(这是 empty 的行为;Iterator 的约定并不保证所有迭代器耗尽后都继续返回 None,需要保证用 fuse())。", t=tl(S(3)), done=lidx(S(3), 'next_back', 'by_ref', 'nth', '耗尽后'), kv=KV([['by_ref()', '只消耗一部分,迭代器还能继续用'], ['next_back', '双端迭代器从尾部取']], ['by_ref()'])),
    step("自己造迭代器的现成工具:iter::from_fn(闭包返回 Option)得到 [1, 4, 9, 16];iter::successors(Some(1u32), |&x| x.checked_mul(10)) 一直乘 10 直到溢出,得 [1, 10, …, 1000000000](10 个);repeat_with 反复调用闭包得 [3, 6, 9, 12];once(0).chain(1..3) 得 [0, 1, 2]。", t=tl(S(4)), done=lidx(S(4), 'from_fn', 'successors', 'repeat_with', 'once'), kv=KV([['from_fn / successors', '不写 struct 也能造迭代器']], ['from_fn / successors'])),
]
A = mkart('u52', 52, 'Rust,Iterator,size_hint,真实验证,动画演示',
    '用真实运行验证 Iterator trait:只有 next() 是必需的、耗尽返回 None、迭代器本身要 mut(E0596);size_hint 在 map/filter/chain/take/无穷迭代器上的上下界;next_back、by_ref、nth;from_fn、successors、repeat_with、once 现成工具。',
    'Iterator 是 Rust 里使用最频繁的 trait,整个 for 循环与几十个适配器都建立在它的 next() 上。这篇从最底层验证它的约定:next 与 None、状态与 mut、size_hint 的上下界、双端与部分消耗,以及不写 struct 就能造迭代器的几个函数。',
    [('next()', 'Iterator 唯一必须实现的方法'), ('(0, Some(5))', 'filter 之后 size_hint:下界为 0'), ('E0596', '迭代器变量没写 mut 就调用 next')],
    [('next 与 for', '<p>for 循环的展开见<a href="rust-for-loop-desugar.html">for 循环如何转换成 Iterator</a>;适配器的惰性见<a href="rust-iterator-lazy.html">Iterator 的惰性执行</a>。</p>'), ('size_hint 与 ExactSizeIterator', None), ('双端、by_ref、nth', None), ('现成工具', '<p>自己实现 Iterator 见<a href="rust-custom-iterator.html">自定义 Iterator</a>。</p>')],
    steps, [ENV_U, '没有验证:FusedIterator 与 fuse() 的实际作用(只在文字里说明)、size_hint 对 collect 预分配的影响、TrustedLen、Iterator::rev 对非双端迭代器的限制'], 'Iterator')
