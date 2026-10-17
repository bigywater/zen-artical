from lib import *
S = SS('u11')
steps = [
    step("没有 derive 的 struct P:println!(\"{:?}\", a) 报 error[E0277]: `P` doesn't implement `Debug`,a.clone() 报 error[E0599]: no method named `clone` found。两个错误都带建议:consider annotating `P` with `#[derive(Debug)]`。", t=tl(S(1)), mark=lidx(S(1), 'error[E0277]', 'error[E0599]'), kv=KV([['Debug', 'E0277'], ['clone', 'E0599']], ['Debug'])),
    step("加上 #[derive(Debug, Clone, PartialEq, Default)] 就都能用了:{:?} 单行打印、{:#?} 分行打印、克隆后 a == b 为 true、P::default() 得到全零/空串的 P { x: 0, y: 0, name: \"\" }。", t=tl(S(2)), done=lidx(S(2), 'P {', 'true'), kv=KV([['{:?} / {:#?}', '单行 / 分行'], ['Default', '各字段取默认值']], ['{:?} / {:#?}'])),
    step("derive 生成的是普通的 impl:用 -Z unpretty=expanded 展开 #[derive(Debug, Clone, PartialEq)],得到 impl ::core::fmt::Debug for P(调用 debug_struct_field2_finish)、impl ::core::clone::Clone for P(逐字段 clone)、impl ::core::cmp::PartialEq for P(fn eq 是 self.x == other.x && self.y == other.y)。派生宏就是自动写这些代码。", t=tl(S(3)), mark=lidx(S(3), 'impl ::core'), kv=KV([['Clone', '逐字段 clone'], ['PartialEq', '逐字段 ==']], ['PartialEq'])),
    step("derive(Copy) 要求所有字段都是 Copy:字段是 String 时报 error[E0204]: the trait `Copy` cannot be implemented for this type。derive(PartialOrd) 按字段声明顺序做字典序比较:Ver{1,9} < Ver{2,0} 为 true,Ver{2,1} < Ver{2,0} 为 false;枚举按变体顺序比:Low < High 为 true,Mid.partial_cmp(&Low) 是 Some(Greater)。", t=tl(S(4)), mark=lidx(S(4), 'error[E0204]'), done=lidx(S(4), 'true', 'false', 'Some'), kv=KV([['Copy', '字段全是 Copy 才行'], ['PartialOrd', '按字段顺序字典序']], ['PartialOrd'])),
    step("泛型结构体 W<T> 上的 derive(Clone) 会给 T 加约束 T: Clone:W { v: 5 } 能 clone,W { v: NoClone } 不能 —— error[E0599]: the method `clone` exists for struct `W<NoClone>`, but its trait bounds were not satisfied(trait bound `NoClone: Clone` was not satisfied)。即使字段本身从不需要 clone T,这个约束也存在;编译器建议手写 impl 来避免多余的约束。", t=tl(S(5)), mark=lidx(S(5), 'error[E0599]'), kv=KV([['derive 对泛型', '自动加 T: Trait 约束']], ['derive 对泛型'])),
]
A = mkart('u11', 11, 'Rust,derive,Trait,宏展开,真实验证,动画演示',
    '用真实编译验证 derive:没有 derive 的结构体不能 {:?}(E0277)、不能 clone(E0599);derive 之后的输出;用 -Z unpretty=expanded 展开看到的 Debug/Clone/PartialEq 实际代码;Copy 要求字段全是 Copy(E0204)、PartialOrd 的字典序;泛型 derive 自动加 T: Trait 约束。',
    'derive 是 Rust 里最常写的一行属性。这篇不只讲「它能做什么」,而是把它展开:没有它编译器怎么报错、有了它输出什么、它到底生成了哪些 impl 代码、哪些情况下它不能用、对泛型它悄悄加了什么约束。',
    [('E0277', '没有 derive(Debug) 就打印时的错误'), ('展开', '-Z unpretty=expanded 可以看到 derive 生成的 impl 代码'), ('T: Trait', '泛型结构体上 derive 自动加的约束')],
    [('没有 derive', None), ('加上 derive', None), ('derive 生成的代码', '<p>展开用的是 <code>RUSTC_BOOTSTRAP=1 rustc -Z unpretty=expanded</code>:在稳定版编译器上打开了只有 nightly 才有的 -Z 选项,仅用于观察。过程宏的执行阶段见<a href="rust-proc-macro-phases.html">过程宏的执行阶段</a>,derive 宏的实现见<a href="rust-derive-macro-codegen.html">Derive 宏如何生成代码</a>。</p>'), ('Copy 与 PartialOrd', None), ('泛型上的 derive', None)],
    steps, [ENV_U + '。展开输出省略了 prelude 导入等固定行;错误信息为原样的 rustc 1.98.1 输出', '没有验证:Hash 与 Eq 的派生、Ord 与 PartialOrd 的一致性、derive 在 enum 上的展开(只展开了 struct)、手写 impl 与 derive 的性能差别'], 'derive 展开')
