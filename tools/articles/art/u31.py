from lib import *
S = SS('u31')
steps = [
    step("Rc 循环引用会泄漏:没有循环时(b1 → a1)离开作用域,两个节点都被 drop(drop b1、drop a1);有循环(a2 → b2 → a2)时,两个节点的强引用数都是 2,块结束后只会减到 1,永远到不了 0,drop a2 / drop b2 从没出现 —— 内存没有被释放。Rust 的内存安全不包括「不泄漏」。", t=tl(S(1)), mark=lidx(S(1), '强引用数 = 2', '它们泄漏了'), done=lidx(S(1), 'drop b1', 'drop a1'), kv=KV([['无循环', '两个都 drop'], ['有循环', '计数卡在 1,不 drop']], ['有循环'])),
    step("Weak 不增加强引用计数、不阻止释放:Rc::downgrade 之后 strong_count = 1、weak_count = 1;weak.upgrade() 返回 Option<Rc<T>>,数据还在时是 Some(临时 Rc 用完就释放,strong_count 仍是 1);drop(strong) 时打印 drop 数据,之后 upgrade() = None。", t=tl(S(2)), done=lidx(S(2), 'strong_count', 'upgrade'), mark=lidx(S(2), 'drop 数据', 'None'), kv=KV([['Weak', '不拥有数据'], ['upgrade()', '数据在 → Some,已释放 → None']], ['upgrade()'])),
    step("树:父节点用 Rc 拥有孩子,孩子用 Weak 指回父节点,就没有循环。挂接前 leaf 的父节点是 None,挂接后是 Some(\"branch\");此时 branch:strong = 1、weak = 1,leaf:strong = 2(自己与 branch 的 children)、weak = 0。branch 离开作用域时先 drop branch,leaf 的父节点变成 None,leaf 的 strong_count 回到 1,最后 drop leaf —— 全部释放。", t=tl(S(3)), done=lidx(S(3), 'drop branch', 'drop leaf'), mark=lidx(S(3), 'branch:strong'), kv=KV([['拥有方向', 'Rc(父 → 子)'], ['回指方向', 'Weak(子 → 父)']], ['回指方向'])),
]
A = mkart('u31', 31, 'Rust,Weak,Rc,循环引用,内存泄漏,真实验证,动画演示',
    '用真实运行验证 Weak:Rc 互指形成循环时计数卡在 1、Drop 永不执行(泄漏);Weak 不增加强引用计数,upgrade() 在数据释放后返回 None;父 Rc 子 Weak 的树能完整释放。',
    '引用计数有一个经典缺陷:循环引用会让计数永远不归零。Rust 没有垃圾回收器,所以这是真泄漏。这篇用带 Drop 的节点把泄漏「看见」,再用 Weak 把循环打断,并验证计数与 upgrade 的行为。',
    [('2 → 1 就停', '有循环的节点,块结束后强引用数只从 2 降到 1,永远到不了 0'), ('None', '数据释放后 weak.upgrade() 的返回值'), ('Rc 向下 Weak 向上', '树结构避免循环的惯用做法')],
    [('Rc 循环泄漏', None), ('Weak 的行为', None), ('用 Weak 打断循环', '<p>RefCell 的作用见<a href="rust-refcell-runtime-borrow.html">RefCell&lt;T&gt; 运行时借用检查</a>;Rc 的基本行为见<a href="rust-rc-shared-ownership.html">Rc&lt;T&gt;</a>。</p>')],
    steps, [ENV_U + '。泄漏通过 Drop 不打印来观察,没有测内存占用', '没有验证:Arc 与 Weak 在多线程里的 upgrade 竞态、图结构更多的拥有方案(slotmap、arena)、Weak::new 的 0 开销、泄漏检测工具'], 'Weak')
