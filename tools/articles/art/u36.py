from lib import *
S = SS('u36')
steps = [
    step("trait 定义一组方法:Shape 有 area、name 两个必须实现的方法和一个带默认实现的 describe。Circle 只实现必需的两个,describe 用默认实现(「圆 面积 3.14」);Rect 额外覆盖了 describe(「矩形(覆盖了默认实现)」)。漏实现必需方法被拒绝:error[E0046]: not all trait items implemented, missing: `name`。", t=tl(S(1)), mark=lidx(S(1), 'error[E0046]'), done=lidx(S(1), '面积 3.14', '覆盖了默认实现'), kv=KV([['默认方法', '可以不实现,也可以覆盖'], ['漏实现必需方法', 'E0046']], ['漏实现必需方法'])),
    step("调用 trait 方法要求 trait 在作用域内:s.area() 报 error[E0599]: no method named `area` found for struct `Sq`,并提示「trait `Area` which provides `area` is implemented but not in scope; perhaps you want to import it」,建议 use crate::geometry::Area。加上 use geometry::Area 后输出 9。", t=tl(S(2)), mark=lidx(S(2), 'error[E0599]'), done=lidx(S(2), '    9'), kv=KV([['trait 不在作用域', 'E0599'], ['use 之后', '正常调用']], ['trait 不在作用域'])),
    step("trait 还可以有关联常量(const LEGS)、返回 Self 的静态方法(fn new)。泛型函数 make<T: Animal>(n) 用 T::new(n) 构造任意实现者:Dog 有 4 条腿、Bird 有 2 条腿(默认方法 legs 返回 Self::LEGS)。也可以给外部类型实现自己的 trait:为 i32 实现 Double 后 21.double() = 42。", t=tl(S(3)), done=lidx(S(3), '条腿', 'double'), kv=KV([['关联常量 / 静态方法', 'trait 里也能有'], ['为 i32 实现自己的 trait', '允许(trait 是本地的)']], ['为 i32 实现自己的 trait'])),
    step("两个 trait 有同名方法时调用有歧义:Human 同时实现 Pilot 与 Wizard 的 fly,Human.fly() 报 error[E0034]: multiple applicable items in scope,并分别列出两个候选与消歧写法。消歧用完全限定语法:Pilot::fly(&h)(机长广播)、<Human as Wizard>::fly(&h)(施法飞行);如果类型自己有固有方法 fly,h.fly() 优先调用它。", t=tl(S(4)), mark=lidx(S(4), 'error[E0034]'), done=lidx(S(4), '机长广播', '施法飞行', '挥手'), kv=KV([['同名方法', 'E0034'], ['消歧', 'Trait::m(&x) 或 <T as Trait>::m(&x)']], ['同名方法'])),
]
A = mkart('u36', 36, 'Rust,Trait,默认方法,完全限定语法,真实验证,动画演示',
    '用真实编译验证 trait 的定义与实现:默认方法与覆盖、漏实现报 E0046;trait 不在作用域报 E0599;关联常量、静态方法与泛型 T::new;为 i32 实现本地 trait;两个 trait 同名方法的歧义 E0034 与完全限定语法。',
    'trait 是 Rust 抽象的核心。这篇不讲概念,把 trait 的日常规则逐条跑出来:怎么定义与实现、默认方法、为什么要 use、关联常量与静态方法、同名冲突怎么办。每一条都有编译器的原话。',
    [('E0046', '没有实现 trait 的必需方法'), ('E0599', 'trait 没有在作用域内时方法找不到(并建议 use)'), ('E0034', '两个 trait 有同名方法时的歧义')],
    [('定义与实现', None), ('trait 要在作用域内', None), ('关联常量与静态方法', '<p>关联类型见<a href="rust-associated-type.html">Associated Type</a>;trait 约束见<a href="rust-trait-bound.html">Trait Bound</a>。</p>'), ('同名方法与消歧', '<p>能为哪些类型实现哪些 trait 的限制见<a href="rust-orphan-rule-coherence.html">孤儿规则</a>。</p>')],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出', '没有验证:trait 的泛型参数与关联类型的差别(见后续文章)、泛型 trait 的多次实现、trait 对象(见 Trait Object 一篇)、async fn in trait'], 'trait 的定义与实现')
