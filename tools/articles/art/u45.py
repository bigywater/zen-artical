from lib import *
S = SS('u45')
steps = [
    step("supertrait:trait Pretty: Display 表示实现 Pretty 的前提是已经实现了 Display,所以 Pretty 的默认方法里可以直接 format!(\"{}\", self):Name 实现 Display 与 Pretty 后输出「★ rust ★」。没实现 Display 就想实现 Pretty,报 error[E0277]: `Plain` doesn't implement `std::fmt::Display`,note:required by a bound in `Pretty`。", t=tl(S(1)), mark=lidx(S(1), 'error[E0277]'), done=lidx(S(1), '★ rust ★'), kv=KV([['trait Pretty: Display', '实现 Pretty 先要有 Display'], ['缺 Display', 'E0277']], ['缺 Display'])),
    step("泛型约束里只写子 trait,就自动拥有所有 supertrait 的方法:Person: Named + Aged,greet<T: Person> 里既能用 Person 自己的 intro(),也能直接调用 name()(输出「你好 Ann,30 岁(也能直接用 name():Ann)」),不需要再写 T: Named + Aged。", t=tl(S(2)), done=lidx(S(2), '你好 Ann'), kv=KV([['T: Person', '自动包含 Named + Aged']], ['T: Person'])),
    step("trait 对象向上转型(trait upcasting)可以用了:&dyn Person 直接传给需要 &dyn Named 的函数(输出 Ann),Box<dyn Person> 也能转成 Box<dyn Named>。通过 &dyn Person 既能调用 id()(7)又能调用 supertrait 的 name()。(编译通过说明本机 rustc 1.98 已支持 upcasting。)", t=tl(S(3)), done=lidx(S(3), 'id() = 7', '向上转型', 'Box<dyn Person>'), kv=KV([['&dyn Person → &dyn Named', '允许'], ['Box<dyn Person> → Box<dyn Named>', '允许']], ['&dyn Person → &dyn Named'])),
    step("两个 supertrait 有同名方法时,在子 trait 里直接 self.hello() 有歧义:error[E0034]: multiple applicable items in scope(candidate #1 在 A,candidate #2 在 B),编译器给出 A::hello(&self) 与 B::hello(&self) 两种消歧写法。写成 format!(\"{} {}\", A::hello(self), B::hello(self)) 就行,输出 A B。", t=tl(S(4)), mark=lidx(S(4), 'error[E0034]'), done=lidx(S(4), 'A B'), kv=KV([['同名方法', 'E0034'], ['消歧', 'A::hello(self) / B::hello(self)']], ['同名方法'])),
]
A = mkart('u45', 45, 'Rust,Supertrait,Trait,trait upcasting,真实验证,动画演示',
    '用真实编译验证 supertrait:trait Pretty: Display 的默认方法可以用 Display、缺 Display 报 E0277;泛型约束只写子 trait 即包含所有 supertrait 的方法;trait 对象向上转型(&dyn Person → &dyn Named、Box 同理)在 rustc 1.98 可用;两个 supertrait 同名方法的 E0034 与消歧。',
    'supertrait 是「trait 的继承」:一个 trait 要求实现者先实现另一个。这篇用真实编译逐条验证它的规则:要求怎么体现、泛型约束里的传递、trait 对象能不能向上转型(这个能力在近几个版本才稳定),以及同名方法的歧义。',
    [('E0277', '没有实现 supertrait 就实现子 trait 的错误'), ('upcasting', '&dyn Person → &dyn Named 在 rustc 1.98 可用'), ('E0034', '两个 supertrait 同名方法时的歧义')],
    [('supertrait 的要求', None), ('约束里的传递', None), ('trait 对象向上转型', '<p>trait 对象的基础见<a href="rust-trait-object-dynamic-dispatch.html">Trait Object 与动态分发</a>。</p>'), ('同名方法', '<p>类似的歧义在<a href="rust-trait-definition.html">Trait 定义与实现</a>里也出现过。</p>')],
    steps, [ENV_U + '。upcasting 的可用性只验证了本机的 rustc 1.98.1', '没有验证:supertrait 带泛型参数、supertrait 与关联类型的交互、dyn A + B 的多 trait 对象(只允许一个非 auto trait)、upcasting 在 Rc/Arc 上的行为'], 'supertrait')
