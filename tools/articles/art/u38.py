from lib import *
S = SS('u38')
steps = [
    step("参数位置的 impl Trait 是匿名的泛型参数:show_impl(x: impl Display) 与 show_generic<T: Display>(x: T) 行为一样(输出 [5] [5] [hi] [1.5])。机器码也一样:分别为 i32 调用它们的包装函数 via_impl 与 via_generic,汇编里 _via_impl = _via_generic,且都尾调用同一个实例 len_generic::<i32> —— LLVM 把 len_impl::<i32> 与 len_generic::<i32> 合并成了一个函数体。", t=tl(S(1)), done=lidx(S(1), '[5]', '别名行'), kv=KV([['impl Display 参数', '= 匿名泛型'], ['机器码', '与显式泛型相同']], ['机器码'])),
    step("返回位置的 impl Trait 隐藏具体类型:evens 返回 impl Iterator<Item = u32>(调用方只知道它是迭代器,输出 [0, 2, 4, 6, 8]),adder 返回 impl Fn(i32) -> i32(adder(5)(3) = 8);type_name 能看到真正的类型 Filter<Range<u32>, 闭包>。但整个函数只能返回同一个具体类型:if 返回 1、else 返回 \"one\" 报 error[E0308]: `if` and `else` have incompatible types,并建议改成 Box<dyn Display>(改写后输出 1 one)。", t=tl(S(2)), mark=lidx(S(2), 'error[E0308]'), done=lidx(S(2), '[0, 2, 4', 'adder(5)(3)', '1 one'), kv=KV([['返回 impl Trait', '隐藏类型,但只能是一种'], ['需要多种', 'Box<dyn Trait>']], ['返回 impl Trait'])),
    step("返回的 impl Trait 里藏着对参数的借用时,edition 2021 与 2024 不同:fn doubled(v: &Vec<u32>) -> impl Iterator<Item = u32> 在 2021 里报 error[E0700]: hidden type for `impl Iterator<Item = u32>` captures lifetime that does not appear in bounds(要显式写 + 'a);在 2024 里直接编译通过,输出 [2, 4, 6] —— 2024 默认捕获所有在作用域内的生命周期。", t=tl(S(3)), mark=lidx(S(3), 'error[E0700]'), done=lidx(S(3), '[2, 4, 6]'), kv=KV([['edition 2021', 'E0700,要写 + \'a'], ['edition 2024', '默认捕获,通过']], ['edition 2024'])),
    step("参数位置的 impl Trait 没有名字,所以不能用 turbofish 指定:f::<i32>(5) 报 error[E0107]: function takes 0 generic arguments but 1 generic argument was supplied,note 里写着「`impl Trait` cannot be explicitly specified as a generic argument」。需要显式指定类型时,用具名的泛型参数。", t=tl(S(4)), mark=lidx(S(4), 'error[E0107]'), kv=KV([['impl Trait 参数', '不能 turbofish']], ['impl Trait 参数'])),
]
A = mkart('u38', 38, 'Rust,impl Trait,泛型,edition,真实验证,动画演示',
    '用真实编译验证 impl Trait:参数位置等价于匿名泛型(机器码被 LLVM 合并);返回位置隐藏具体类型但只能返回一种(E0308,可改 Box<dyn>);返回值借用参数时 edition 2021 报 E0700、2024 默认捕获通过;impl Trait 参数不能 turbofish(E0107)。',
    'impl Trait 是日常最常写的泛型语法糖。这篇验证它在参数位置和返回位置各自的真实含义、一个让人意外的限制(只能返回一种类型)、edition 2024 对生命周期捕获的改动,以及它不能做什么。',
    [('E0308', '返回位置的 impl Trait 不能在分支里返回不同类型'), ('E0700', 'edition 2021:返回的 impl Trait 捕获了未声明的生命周期(2024 默认通过)'), ('E0107', 'impl Trait 参数不能用 turbofish 指定')],
    [('参数位置', None), ('返回位置', '<p>需要运行时选择不同类型时用 trait 对象,见<a href="rust-trait-object-dynamic-dispatch.html">Trait Object 与动态分发</a>。</p>'), ('生命周期的捕获', '<p>edition 2024 在 if let 临时值上的另一处变化见<a href="rust-if-let-let-else.html">if let 与 let else</a>。</p>'), ('不能指定', None)],
    steps, [ENV_U + '。第三节分别用 --edition=2021 与 --edition=2024 编译同一份源码', '没有验证:use<..> 精确捕获语法、返回 impl Future(async fn 的展开)、impl Trait 在 trait 方法返回位置(RPITIT)'], 'impl Trait')
