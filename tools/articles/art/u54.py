from lib import *
S = SS('u54')
steps = [
    step("for 循环对 v、&v、&mut v 迭代出的元素类型不同:for x in &v 得 &String(只读借用),for x in &mut v 得 &mut String(可以原地修改:每个元素 push('!') 之后 v = [\"a!\", \"b!\"]),for x in v 得 String(按值,元素被移出来)。for 先对表达式调用 IntoIterator::into_iter,三种写法对应 Vec 的三个 impl。", t=tl(S(1)), done=lidx(S(1), '&alloc', '&mut', '修改之后'), kv=KV([['&v', '&T'], ['&mut v', '&mut T'], ['v', 'T(按值)']], ['v'])),
    step("for x in v 把 v 的所有权移进了迭代器:循环之后再用 v 报 error[E0382]: borrow of moved value: `v`,note 解释「`into_iter` takes ownership of the receiver `self`, which moves `v`」,并建议改成遍历切片。", t=tl(S(2)), mark=lidx(S(2), 'error[E0382]'), kv=KV([['for x in v', '移动 v,之后不能再用']], ['for x in v'])),
    step("为自己的集合实现 IntoIterator:Bag 写了三个 impl —— for Bag(Item = i32,消费)、for &'a Bag(Item = &'a i32)、for &'a mut Bag(Item = &'a mut i32)。之后 for x in &bag 读(1 2 3)、for x in &mut bag 把每个乘 10(读到 10 20 30)、bag.into_iter().sum() 消费并求和得 60。没有为 &Bag 实现时,for x in &bag 报 error[E0277]: `&Bag` is not an iterator。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]'), done=lidx(S(3), '读 1', '读 10', '消费后求和'), kv=KV([['三个 impl', 'Bag / &Bag / &mut Bag'], ['缺 &Bag 的 impl', 'E0277']], ['三个 impl'])),
    step("其它标准集合:数组按值迭代(edition 2021 起,for s in arr 得 String);BTreeMap 的 &m 迭代得 (&&str, &i32) 键值对引用,按值 m 迭代得 (&str, i32);只改值用 values_mut(改完 {\"k\": 2})。", t=tl(S(4)), done=lidx(S(4), '数组', 'for kv', 'values_mut'), kv=KV([['&map', '(&K, &V)'], ['map', '(K, V)'], ['values_mut()', '只改值']], ['&map'])),
]
A = mkart('u54', 54, 'Rust,IntoIterator,for循环,所有权,真实验证,动画演示',
    '用真实运行验证 IntoIterator 的三种遍历:for x in &v 得 &T、&mut v 得 &mut T、v 得 T(并移动 v,E0382);为自己的集合 Bag 实现三个 IntoIterator impl,缺 &Bag 的 impl 报 E0277;数组按值迭代、BTreeMap 的键值对类型。',
    'for x in v 与 for x in &v 看起来只差一个 &,含义却完全不同。这篇用元素类型的真实打印、所有权的编译报错、以及为自己的集合补齐三种 impl,把 IntoIterator 的三种遍历讲清楚。',
    [('3 个', '为自己的集合实现 IntoIterator 需要的 impl 个数(T、&T、&mut T)'), ('E0382', 'for x in v 之后再使用 v'), ('E0277', '没为 &Bag 实现 IntoIterator 时 for x in &bag 的错误')],
    [('三种遍历', '<p>for 循环的底层展开见<a href="rust-for-loop-desugar.html">for 循环如何转换成 Iterator</a>。</p>'), ('for x in v 之后', None), ('自己的集合', '<p>Iterator 本身见<a href="rust-iterator-trait.html">Iterator Trait</a>。</p>'), ('其它集合', None)],
    steps, [ENV_U + '。类型名用 std::any::type_name 打印', '没有验证:iter() 与 (&v).into_iter() 是否完全等价(只验证了行为)、数组在 edition 2018 里的 into_iter 行为差别、drain、into_iter 对 Vec 的原地优化'], 'IntoIterator')
