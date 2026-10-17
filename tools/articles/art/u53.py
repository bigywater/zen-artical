from lib import *
S = SS('u53')
steps = [
    step("自定义 Iterator 只要一个结构体加一个 next():Fib { a, b } 每次返回当前项并推进状态,checked_add 溢出时返回 None 结束。前 10 项 [0, 1, 1, 2, 3, 5, 8, 13, 21, 34];take_while(< 100) + filter(偶数) 得 [0, 2, 8, 34];count() 得 92 项(u64 溢出之前),last() 是 Some(4660046610375530309)。适配器 take、take_while、filter、count、last 都是免费送的。", t=tl(S(1)), done=lidx(S(1), '前 10 项', '偶数项', '一共有'), kv=KV([['写什么', 'struct + next()'], ['免费得到', 'take、filter、count、last…']], ['免费得到'])),
    step("借用数据的迭代器:struct Pairs<'a, T> { items: &'a [T], i: usize },Item = (&'a T, &'a T),零拷贝地产出相邻元素对。字符串 a、b、c 输出 a-b、b-c;整数 [1, 4, 9, 16] 的差分 map(|(a, b)| b - a) 得 [3, 5, 7]。", t=tl(S(2)), done=lidx(S(2), 'a-b', '差分'), kv=KV([['Item', '(&\'a T, &\'a T) —— 借自源数据'], ['拷贝', '没有']], ['Item'])),
    step("想用 rev() 就要实现 DoubleEndedIterator:只实现 next 的 Count 调用 rev() 报 error[E0277]: the trait bound `Count: DoubleEndedIterator` is not satisfied。补上 next_back 与 size_hint,再写 impl ExactSizeIterator for Count {},就有了 rev()([4, 3, 2, 1, 0])、len()(7)、size_hint()((7, Some(7)));两头同时取:next、next_back、next、next_back 得 Some(0) Some(5) Some(1) Some(4)。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]'), done=lidx(S(3), 'rev:', 'len:', '两头同时取'), kv=KV([['rev()', '需要 DoubleEndedIterator'], ['len()', '需要 ExactSizeIterator + size_hint']], ['rev()'])),
    step("实现 size_hint 是有用的:collect::<Vec<_>> 靠它预分配。没有 size_hint 的迭代器收集 1000 个元素后 capacity = 1024(扩容留下的余量),有精确 size_hint 的则 capacity = 1000(一次分配刚好够)。", t=tl(S(4)), mark=lidx(S(4), 'capacity'), kv=KV([['无 size_hint', 'capacity 1024'], ['有 size_hint', 'capacity 1000']], ['有 size_hint'])),
]
A = mkart('u53', 53, 'Rust,Iterator,自定义迭代器,真实验证,动画演示',
    '用真实运行验证自定义 Iterator:斐波那契迭代器只写 next 就获得 take/filter/count/last;带生命周期的借用型迭代器 Pairs 零拷贝产出相邻元素对;rev 需要 DoubleEndedIterator(E0277)、len 需要 ExactSizeIterator;size_hint 让 collect 的 capacity 从 1024 变成刚好 1000。',
    '自己写迭代器很简单,但要写得好需要几个小知识:结构体里放什么、怎样借用外部数据、要不要实现双端与精确长度、size_hint 的作用。这篇用四个例子逐条验证。',
    [('92 项', '自定义斐波那契迭代器在 u64 溢出前的项数'), ('E0277', '没实现 DoubleEndedIterator 就调用 rev()'), ('1024 → 1000', 'collect 的 capacity:没有与有 size_hint')],
    [('一个结构体加一个 next()', '<p>Iterator 的基本约定见<a href="rust-iterator-trait.html">Iterator Trait</a>。</p>'), ('借用数据', None), ('双端与精确长度', None), ('size_hint 的价值', '<p>让自己的集合也能被 for 遍历,见<a href="rust-into-iterator-three-ways.html">IntoIterator 的三种遍历方式</a>。</p>')],
    steps, [ENV_U, '没有验证:迭代器里使用 impl Trait 返回类型的另一种写法、对 size_hint 实现错误(上下界不一致)的后果、FusedIterator 的实现、Iterator::try_fold 的重写'], '自定义 Iterator')
