from lib import *
S = SS('u66')
steps = [
    step("Peekable 先看一眼再决定:创建后源已产出 0 个;peek → Some(1) 时源已产出 1 个(peek 其实把下一个元素从源里拉出来缓存了);再 peek 仍是 Some(1),源没有再被拉。", t=tl(S(1)), done=lidx(S(1), '刚创建', 'peek -> Some(1)', '再 peek'), kv=KV([['peek', '从源拉一个并缓存'], ['再 peek', '不再拉']], ['peek'])),
    step("next 先返回缓存的值:next → Some(1)(源仍然只产出过 1 个),下一次 next → Some(2)(源产出 2 个)。peek_mut 可以改缓存的元素:改成 99 后 next 返回 Some(99)。Peekable<Range<i32>> 是 16 字节,比 Range<i32> 的 8 字节多出缓存槽。", t=tl(S(1)), done=lidx(S(1), 'next -> Some(1)', 'next -> Some(2)', 'peek_mut', 'size_of'), kv=KV([['next', '先吐缓存'], ['peek_mut', '可改缓存元素'], ['体积', '16 对 8 字节']], ['next'])),
    step("peek 返回 Option<&Item>,持有它时不能再 next:let first = it.peek().unwrap(); it.next(); println!(first) 报 error[E0499]: cannot borrow `it` as mutable more than once at a time。", t=tl(S(2)), mark=lidx(S(2), 'error[E0499]'), kv=KV([['持有 peek 的引用', '不能同时 next']], ['持有 peek 的引用'])),
    step("词法分析:\"12+345*6\" 用 peekable + next_if(是数字就吃)得 [\"12\",\"+\",\"345\",\"*\",\"6\"],分隔符没有被误吃。", t=tl(S(3)), done=lidx(S(3), 'peekable + next_if'), kv=KV([['peekable + next_if', '12 + 345 * 6']], ['peekable + next_if'])),
    step("对照 take_while:it.by_ref().take_while(是数字) 读到 \"12\",剩下的是 \"345*6\" —— 分隔符 '+' 被 take_while 吃掉丢弃了。next_if_eq(&'a') 命中得 Some('a'),next_if_eq(&'z') 不命中得 None 且不消费,剩余 \"b\"。", t=tl(S(3)), mark=lidx(S(3), 'take_while'), done=lidx(S(3), 'next_if_eq'), kv=KV([['take_while', '丢掉第一个不满足的元素'], ['next_if', '不消费不满足的']], ['take_while'])),
    step("inspect 在链中间观察而不改变结果:(1..=5) 经 filter(奇数) 与 map(平方),输出 [源] 1 → [filter 之后] 1 → [map 之后] 1,偶数元素在 filter 处就被丢掉,看不到后两层输出;最终结果 [1, 9, 25]。再次印证逐元素交错执行。", t=tl(S(4)), done=lidx(S(4), '[map 之后]', '结果'), kv=KV([['inspect', '只读观察'], ['结果', '[1, 9, 25]']], ['inspect'])),
    step("inspect 的闭包参数是 &Item:想在里面修改元素 **x += 1 报 error[E0594]: cannot assign to `**x`, which is behind a `&` reference。要改元素用 map。", t=tl(S(4)), mark=lidx(S(4), 'error[E0594]'), kv=KV([['inspect 里改元素', 'E0594']], ['inspect 里改元素'])),
]
A = mkart('u66', 66, 'Rust,Iterator,peekable,inspect,真实验证,动画演示',
    'peek 会从源里拉出一个元素缓存(创建时 0 个、peek 后 1 个,再 peek 不再拉),next 先吐缓存;持有 peek 引用时 next 报 E0499;用 next_if 写词法分析不误吃分隔符,take_while 则吃掉了第一个不满足的元素;inspect 只读观察(修改报 E0594),并印证逐元素交错执行。',
    '写解析器经常需要「看一眼下一个元素再决定」,调试迭代器链又需要「看一眼中间的值」。Peekable 和 inspect 分别解决这两件事。这篇用计数器验证 peek 的真实行为,用词法分析对比 take_while,并用 inspect 看清链的执行顺序。',
    [('1 个', 'peek 一次后源已产出的元素数(创建时是 0)'), ('E0499', '持有 peek 返回的引用时再 next'), ('E0594', '在 inspect 里修改元素')],
    [('peek 的真实行为', None), ('peek 的借用', None), ('词法分析', '<p>iterator 的惰性见<a href="rust-iterator-lazy.html">Iterator 的惰性执行</a>。</p>'), ('inspect', '<p>dbg! 宏本身见<a href="rust-dbg-macro.html">dbg! 宏的实现方式</a>。</p>')],
    steps, [ENV_U, '没有验证:Peekable 对 DoubleEndedIterator(next_back)的行为、peek 在带副作用的源上的更多影响、dbg! 与 inspect 搭配的输出差异'], 'peekable / inspect')
