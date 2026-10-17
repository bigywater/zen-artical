from lib import *
S = SS('u37')
steps = [
    step("泛型函数里用了某个操作,就必须在 T 上声明对应的 trait bound:largest<T>(list: &[T]) 里写 x > m 报 error[E0369]: binary operation `>` cannot be applied to type `&T`,编译器建议「consider restricting type parameter `T` with trait `PartialOrd`」。", t=tl(S(1)), mark=lidx(S(1), 'error[E0369]'), kv=KV([['没有约束', 'E0369']], ['没有约束'])),
    step("加上 T: PartialOrd 后,largest 对 i32、f64、char、&str、String 都能用(输出 5、1.5、z、pear、b);没有实现 PartialOrd 的自定义类型 P 被拒绝:error[E0277]: can't compare `P` with `P`(the trait `PartialOrd` is not implemented for `P`),并指出约束来自 largest,建议 #[derive(PartialOrd)]。", t=tl(S(2)), mark=lidx(S(2), 'error[E0277]'), done=lidx(S(2), 'i32:5', 'String:b'), kv=KV([['满足约束的类型', '都能用'], ['不满足', 'E0277']], ['不满足'])),
    step("多个约束用 + 连接(T: Display + Clone),也可以写进 where 子句(where T: Display + Clone, U: Debug),两种写法等价:show_both 与 show_where 都输出「… / … / 克隆的 …」。约束较多时 where 更清晰。", t=tl(S(3)), done=lidx(S(3), '克隆的'), kv=KV([['T: A + B', '多个约束'], ['where', '同样的意思,更易读']], ['where'])),
    step("按约束有条件地提供方法:impl<T> Pair<T> 里的 new 对所有 T 都有;impl<T: Display + PartialOrd> Pair<T> 里的 show_largest 只有 T 满足约束才存在。Pair::new(NoDisplay, NoDisplay).show_largest() 报 error[E0599]: the method `show_largest` exists for struct `Pair<NoDisplay>`, but its trait bounds were not satisfied,并列出缺的 `NoDisplay: PartialOrd` 与 `NoDisplay: Display`。", t=tl(S(4)), mark=lidx(S(4), 'error[E0599]'), kv=KV([['按约束提供方法', '不满足就没有这个方法']], ['按约束提供方法'])),
    step("约束在编译期解析:同一个泛型函数 add<T: Add<Output = T>>(a, b),被 i32 与 f64 使用时,编译出两份各自的函数:add::<i32> 是 add w0, w1, w0 ; ret,add::<f64> 是 fadd d0, d0, d1 ; ret。这叫单态化,泛型没有运行时开销(代价是代码体积)。", t=tl(S(5)), mark=lidx(S(5), 'add::<'), kv=KV([['add::<i32>', 'add w0, w1, w0'], ['add::<f64>', 'fadd d0, d0, d1']], ['add::<f64>'])),
]
A = mkart('u37', 37, 'Rust,Trait Bound,泛型,单态化,真实验证,动画演示',
    '用真实编译验证 trait bound:泛型里用 > 而没有约束报 E0369(并建议 PartialOrd);加约束后 i32/f64/char/&str/String 都能用,不满足的类型报 E0277;多个约束与 where;impl<T: Display + PartialOrd> 里的方法只对满足约束的类型存在(E0599);add<T> 单态化出两份机器码。',
    'trait bound 是泛型的「入场券」:告诉编译器 T 至少会什么。这篇用真实报错验证它的几个关键行为:什么时候必须写、不满足时报什么、多个约束与 where 的写法、按约束有条件地提供方法,以及它在机器码层面意味着什么。',
    [('E0369', '泛型里用了没声明的操作'), ('E0599', '按约束提供的方法在不满足约束的类型上不存在'), ('2 份', 'add<T> 为 i32 与 f64 各生成一份机器码')],
    [('为什么需要约束', None), ('满足与不满足', None), ('多个约束与 where', None), ('有条件的方法', '<p>写法 <code>impl Trait</code> 参数与约束是等价的,见<a href="rust-impl-trait.html">impl Trait 参数与返回值</a>。</p>'), ('单态化', '<p>单态化的详细代价见<a href="rust-monomorphization.html">泛型单态化</a>与<a href="rust-static-vs-dynamic-dispatch.html">静态分发与动态分发性能对比</a>。</p>')],
    steps, [ENV_U + '。汇编为 --emit=asm -O 的 aarch64 输出', '没有验证:关联类型约束(Iterator<Item = T>)、高阶 trait bound(for<\'a>)、约束的 ?Sized、泛型的代码体积膨胀的量化'], 'trait bound')
