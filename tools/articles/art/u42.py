from lib import *
S = SS('u42')
steps = [
    step("不是所有 trait 都能做成 dyn Trait。带泛型方法的 trait(fn visit<T: Debug>(&self, t: T))不行:Box<dyn Visitor> 报 error[E0038]: the trait `Visitor` is not dyn compatible(note:for a trait to be dyn compatible it needs to allow building a vtable)—— vtable 里的槽位数必须固定,而泛型方法有无穷多个实例。注意 rustc 1.98 的措辞是 dyn compatible,就是以前说的「对象安全」(object safe)。", t=tl(S(1)), mark=lidx(S(1), 'error[E0038]'), kv=KV([['泛型方法', 'E0038(not dyn compatible)']], ['泛型方法'])),
    step("返回 Self 的方法(fn dup(&self) -> Self)与没有 self 的关联函数(fn make() -> Self)同样让 trait 不 dyn compatible,都是 E0038:对象擦掉了具体类型,Self 的大小与构造方式都不知道。对 make,编译器给出两条出路:加 &self 把它变成方法,或者「constraining `make` so it does not apply to trait objects」。", t=tl(S(2)), mark=lidx(S(2), 'error[E0038]'), kv=KV([['返回 Self', 'E0038'], ['无 self 的关联函数', 'E0038']], ['返回 Self'])),
    step("supertrait 要求 Sized 也不行:trait Shape: Clone(Clone 要求 Self: Sized,返回 Self)使 Shape 不能做成 dyn Shape,同样 E0038。", t=tl(S(3)), mark=lidx(S(3), 'error[E0038]'), kv=KV([['trait Shape: Clone', 'E0038']], ['trait Shape: Clone'])),
    step("用 where Self: Sized 把不适合对象的方法排除出去:scaled(&self, k) -> Self where Self: Sized 与泛型的 describe 都加了这个子句,trait 其余部分仍可做成对象。具体类型 Sq 可以调用全部方法(scaled(2.0).area() = 16、describe(\"sq\") = sq: 4),而 Box<dyn Shape> 只有 area(输出 9)。在 dyn 上调用被排除的方法报错:the `scaled` method cannot be invoked on a trait object。", t=tl(S(4)), mark=lidx(S(4), 'cannot be invoked on a trait object'), done=lidx(S(4), '具体类型可以用', 'dyn 上只有'), kv=KV([['where Self: Sized', '方法只对具体类型存在'], ['dyn 上调用', '报错']], ['where Self: Sized'])),
    step("常见的变通:要克隆 trait 对象,提供一个返回 Box<dyn Shape> 的 box_clone,再为 Box<dyn Shape> 实现 Clone:a.clone() 得到的对象 area 同为 9。", t=tl(S(5)), done=lidx(S(5), '克隆出的'), kv=KV([['box_clone', '手动实现对象的克隆']], ['box_clone'])),
]
A = mkart('u42', 42, 'Rust,Trait Object,dyn兼容,对象安全,真实验证,动画演示',
    '用真实编译验证哪些 trait 不能做成 dyn Trait(现在叫 dyn compatible,E0038):泛型方法、返回 Self、没有 self 的关联函数、supertrait 带 Sized(Clone);用 where Self: Sized 排除个别方法使其余部分仍可做成对象;用 box_clone 变通克隆 trait 对象。',
    '为什么有的 trait 能写成 dyn Trait,有的不行?这篇把「对象安全」(现在官方叫 dyn compatible)的几条规则逐条编译:每一条都有真实的 E0038 报错,再看 where Self: Sized 如何把不兼容的方法单独排除,以及克隆 trait 对象的惯用做法。',
    [('E0038', 'the trait is not dyn compatible'), ('4 种', '本篇验证的不兼容情形:泛型方法、返回 Self、无 self 的关联函数、Clone 之类的 Sized supertrait'), ('where Self: Sized', '把方法排除出 trait 对象的接口')],
    [('泛型方法', None), ('返回 Self 与无 self 的函数', None), ('supertrait 的 Sized', None), ('where Self: Sized', '<p>vtable 的结构见<a href="rust-trait-object-dynamic-dispatch.html">Trait Object 与动态分发</a>。</p>'), ('克隆 trait 对象', None)],
    steps, [ENV_U + '。错误信息为原样的 rustc 1.98.1 输出(措辞「dyn compatible」是该版本的新叫法)', '没有验证:带关联类型/关联常量的 trait 的 dyn 兼容性(含 Iterator 的 dyn Iterator<Item = T>)、dyn Trait 的 upcasting、async fn in trait 是否 dyn 兼容'], 'dyn 兼容')
