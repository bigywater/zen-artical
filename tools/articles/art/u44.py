from lib import *
S = SS('u44')
steps = [
    step("标准 Iterator 做不到「每次返回的引用都借自迭代器自己」:type Item = &mut [i32] 没有生命周期可用,报错说 associated type `Iterator::Item` is declared without lifetime parameters,so using a borrowed type for them requires that lifetime to come from the implemented type,note 还直说「you can't create an `Iterator` that borrows each `Item` from itself」;写成 &'static mut 然后返回 self.buf 的切片,报 lifetime may not live long enough。", t=tl(S(1)), mark=lidx(S(1), 'declared without lifetime parameters', 'lifetime may not live long enough'), kv=KV([['Iterator::Item', '不带生命周期'], ['借自自己', '做不到']], ['借自自己'])),
    step("GAT(泛型关联类型)让关联类型自己带生命周期参数:type Item<'a> where Self: 'a;,next<'a>(&'a mut self) -> Option<Self::Item<'a>>。WindowsMut 每次返回借自 &mut self 的、相邻重叠的可修改窗口:w[1] += w[0] 逐窗口累加,输出窗口 [1, 3]、[3, 6]、[6, 10],最终数据 [1, 3, 6, 10]。这种「借出式迭代器」在标准 Iterator 上无法表达。", t=tl(S(2)), done=lidx(S(2), '窗口', '最终数据'), kv=KV([['GAT', 'type Item<\'a>'], ['借出式迭代器', '每个元素借自 &mut self']], ['GAT'])),
    step("GAT 也可以带类型参数:trait Family { type Of<T>; ... },VecFamily 把 T 包成 Vec<T>、OptFamily 包成 Option<T>。同一个泛型函数 demo<F: Family> 对两个实现分别输出 VecFamily:(\"[1]\", \"[\\\"x\\\"]\") 与 OptFamily:(\"Some(1)\", \"Some(\\\"x\\\")\")。", t=tl(S(3)), done=lidx(S(3), 'Family'), kv=KV([['type Of<T>', '关联类型带类型参数'], ['用途', '抽象「容器族」']], ['type Of<T>'])),
    step("定义带生命周期的 GAT 时必须写 where Self: 'a:漏写会报 error: missing required bound on `Item`(note:this bound is currently required to ensure that impls have maximum flexibility,并且提到这个要求仍在征求反馈,issue #87479)。", t=tl(S(4)), mark=lidx(S(4), 'missing required bound'), kv=KV([['漏写 where Self: \'a', 'missing required bound on `Item`']], ['漏写 where Self: \'a'])),
]
A = mkart('u44', 44, 'Rust,GAT,泛型关联类型,借出式迭代器,真实验证,动画演示',
    '用真实编译验证 GAT:标准 Iterator 无法表达借自自身的 Item(报错说明);用 type Item<\'a> 写出借出式迭代器 WindowsMut(重叠的可修改窗口,最终数据 [1, 3, 6, 10]);带类型参数的 GAT 抽象容器族;漏写 where Self: \'a 的报错。',
    'GAT 是近几年才稳定的特性,解决的是「关联类型需要带参数」的问题。这篇用最典型的场景 —— 借出式迭代器 —— 验证它:没有 GAT 时标准 Iterator 为什么做不到,有了 GAT 怎么写,以及它的另一种用法(带类型参数的容器族)。',
    [('type Item<\'a>', 'GAT:关联类型自己带生命周期参数'), ('[1, 3, 6, 10]', '借出式迭代器逐窗口修改后的最终数据'), ('where Self: \'a', '定义带生命周期的 GAT 时必须写的约束')],
    [('为什么标准 Iterator 不行', '<p>Iterator 的基础见<a href="rust-iterator-trait.html">Iterator Trait</a>;关联类型的基础见<a href="rust-associated-type.html">Associated Type</a>。</p>'), ('GAT 的借出式迭代器', None), ('带类型参数的 GAT', None), ('where Self: \'a', None)],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:GAT 与 dyn Trait 的关系、GAT 在 HRTB(for<\'a>)约束下的使用限制、标准库是否已有借出式迭代器的 trait(没有查)、与 async trait 的关系'], 'GAT')
