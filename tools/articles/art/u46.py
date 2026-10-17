from lib import *
S = SS('u46')
steps = [
    step("只实现 Iterator 的 next,就免费得到一大堆默认方法:Countdown 只写了 next,却能 collect([5, 4, 3, 2, 1])、filter + map + sum(220)、zip、max/min/count/last、fold/any/all/position、skip + step_by + take_while 组合(输出 [18, 14, 10, 6])等。这就是默认方法的价值:最小的必需接口,最大的免费能力。", t=tl(S(1)), done=lidx(S(1), 'collect', 'map + filter', 'zip', 'max', 'fold', 'take_while'), kv=KV([['必须实现', 'next'], ['免费获得', 'map、filter、sum、zip、fold…']], ['免费获得'])),
    step("实现者可以覆盖默认方法:Slow 沿用默认的 count_all(逐个调用 next_value 来数),count_all = 1000 时调用了 next_value 1001 次;Fast 覆盖了 count_all,直接返回剩余个数,next_value 调用 0 次。PartialEq 也是同样的设计:Q 只实现 eq,Q(1) != Q(2) 用的是 trait 提供的默认方法 ne。", t=tl(S(2)), mark=lidx(S(2), '默认实现', '覆盖实现'), kv=KV([['默认 count_all', 'next_value 1001 次'], ['覆盖 count_all', 'next_value 0 次']], ['覆盖 count_all'])),
    step("默认方法互相依赖要小心:is_even 默认写成 !self.is_odd(),is_odd 默认写成 !self.is_even(),实现者一个都没覆盖(impl Parity for N {})—— 编译没有任何警告,运行时无限递归,程序被信号终止(退出码 -6),stderr 第一行是「thread 'main' has overflowed its stack」。这类「至少覆盖一个」的约定编译器看不出来,要靠文档写清楚。", t=tl(S(3)), mark=lidx(S(3), '运行:退出码'), kv=KV([['互相调用的默认方法', '编译通过,运行时栈溢出']], ['互相调用的默认方法'])),
    step("默认方法也在 vtable 里:通过 Vec<Box<dyn Greeter>> 调用 greet,Plain 没覆盖,用默认实现(「你好,小明!」);Formal 覆盖了,用自己的版本(「王先生 您好,欢迎光临。」)—— 动态分发时按实际类型选择覆盖版本或默认版本。", t=tl(S(4)), done=lidx(S(4), '你好,小明', '欢迎光临'), kv=KV([['dyn 调用默认方法', '覆盖了用覆盖版,没覆盖用默认版']], ['dyn 调用默认方法'])),
]
A = mkart('u46', 46, 'Rust,Trait,默认方法,Iterator,真实验证,动画演示',
    '用真实运行验证 trait 的默认方法:只实现 Iterator::next 就获得 collect、map、filter、sum、zip、fold 等;覆盖默认 count_all 让 next_value 调用从 1001 次降到 0 次;PartialEq 只需 eq;两个互相依赖的默认方法都不覆盖会在运行时栈溢出(退出码 -6);通过 dyn 调用时覆盖版与默认版按类型选择。',
    '默认方法让 trait 的「必须实现」降到最小,把其余功能免费送给实现者。这篇验证它的几个行为:最小实现换来多少免费能力、覆盖默认实现能省多少工作、一个编译器查不出来的陷阱(互相依赖的默认方法),以及它在 trait 对象里怎么分发。',
    [('1001 → 0', '覆盖 count_all 后 next_value 的调用次数'), ('-6', '互相依赖的默认方法都没覆盖时,程序因栈溢出终止的退出码'), ('1 个', 'Iterator 的必须实现方法(next),其余都是默认方法')],
    [('最小实现', '<p>Iterator 的更多内容见<a href="rust-iterator-trait.html">Iterator Trait</a>与<a href="rust-custom-iterator.html">自定义 Iterator</a>。</p>'), ('覆盖默认实现', None), ('互相依赖的默认方法', None), ('trait 对象里的默认方法', '<p>trait 定义的基础见<a href="rust-trait-definition.html">Trait 定义与实现</a>。</p>')],
    steps, [ENV_U + '。曾尝试用耗时比较默认与覆盖实现,结果被优化器折叠成常数、不可信,所以改用调用次数', '没有验证:默认方法的单态化与内联、在覆盖实现里调用「被覆盖的默认实现」的写法(Rust 没有 super 调用)、默认方法与 specialization'], '默认方法')
