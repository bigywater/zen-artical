from lib import *
S = SS('u96')
steps = [
    step("调用 async fn 只是创建一个 Future:hello() 之后打印「拿到了 Future(1 字节),函数体还没有运行」,函数体里的「hello() 的函数体开始执行」一行没有出现。", t=tl(S(1)), done=lidx(S(1), '调用 hello()', '拿到了 Future'), kv=KV([['hello()', '只创建 Future,不执行']], ['hello()'])),
    step("poll 才推进它:第一次 poll 时函数体开始执行,打印「hello() 的函数体开始执行」,因为里面没有 await,一次 poll 就完成,返回 Ready(42)。这里的 poll 用的是 Waker::noop() 构造的 Context(标准库自带的空 waker)。", t=tl(S(1)), done=lidx(S(1), '第一次 poll', '函数体开始执行', 'Ready(42)'), kv=KV([['poll', '推进状态机'], ['返回值', 'Poll::Ready(42)']], ['poll'])),
    step("手写 Future:Countdown { left: 3 } 的 poll 前三次返回 Pending(每次先 cx.waker().wake_by_ref() 请求再被 poll),第 4 次返回 Ready;循环里一共 poll 了 4 次,最终得到 4。Pending 的意思是「现在没完成,条件满足时我会通过 waker 通知你」。", t=tl(S(2)), done=lidx(S(2), 'Ready', '最终得到'), mark=lidx(S(2), 'Pending'), kv=KV([['Pending', '没完成,会通过 waker 通知'], ['Ready(v)', '完成并交出结果']], ['Pending'])),
    step("await 把 Pending 向上传:job() 里依次 step(\"A\", 2).await 和 step(\"B\", 1).await,每次外层被 poll,都从上次停下的位置继续:第 1 次 poll 打印「A 开始」后 Pending;第 2 次直接 Pending(A 内部还在等);第 3 次「A 结束」「B 开始」后 Pending;第 4 次「B 结束」后返回 Ready(\"全部完成\")。", t=tl(S(3)), done=lidx(S(3), 'A 开始', 'A 结束', 'B 开始', 'B 结束', 'Ready'), mark=lidx(S(3), '→ Pending'), kv=KV([['外层 poll 次数', '4'], ['每次从哪继续', '上次停下的 await 处']], ['每次从哪继续'])),
    step("Future 被 drop 而从未 poll:drop(work(\"never\")) 什么也不打印,函数体永远不会运行;poll 过一次再 drop:先打印「work(half) 开始」,drop Future 时里面的局部变量 Noisy(half) 立刻被析构(打印「Noisy(half) 被 drop」),后半段「结束」永远不会运行。", t=tl(S(4)), done=lidx(S(4), 'work(half) 开始', 'Noisy(half) 被 drop'), kv=KV([['没 poll 就 drop', '函数体一行都不运行'], ['poll 一半后 drop', '局部变量立即析构']], ['poll 一半后 drop'])),
    step("忘记 .await:async fn g() { f(); } 里 f() 返回的 Future 没人用,编译器警告 warning: unused implementer of `Future` that must be used,note 写「futures do nothing unless you `.await` or poll them」。", t=tl(S(5)), mark=lidx(S(5), 'warning: unused implementer', 'futures do nothing'), kv=KV([['f();', 'unused_must_use 警告']], ['f();'])),
]
A = mkart('u96', 96, 'Rust,Future,Poll,async,真实验证,动画演示',
    '用手写的 poll 循环(Waker::noop())验证 Future 与 Poll:async fn 只创建 Future 不执行;第一次 poll 才运行;手写 Countdown 返回 3 次 Pending 后 Ready;await 把 Pending 向上传并从停下处继续(外层 poll 4 次);没 poll 就 drop 则函数体不运行,poll 一半就 drop 则局部变量立即析构;忘记 await 的警告。',
    'Rust 的 async 不是魔法:Future 就是一个被 poll 的状态机。这篇不借助任何运行时,自己写 poll 循环,把「惰性」「Pending 与 Ready」「await 向上传 Pending」「drop 一个 Future」都亲眼跑出来。',
    [('0 行', '调用 async fn 但没 poll 时,函数体执行的输出行数'), ('4 次', 'job() 里两个 await 总共需要的外层 poll 次数'), ('Waker::noop()', '本文用来手动 poll 的空 waker(标准库自带)')],
    [('Future 是惰性的', None), ('手写一个 Future', '<p>async runtime 做的事见<a href="rust-async-runtime.html">Async Runtime 做了什么</a>。</p>'), ('await 向上传 Pending', '<p>async fn 生成的状态机见<a href="rust-async-await-state-machine.html">async/await 状态机</a>。</p>'), ('drop 一个 Future', '<p>取消语义见<a href="rust-future-cancel-drop.html">Future 取消与 Drop</a>。</p>'), ('忘记 await', None)],
    steps, [ENV_U + '。poll 用 Waker::noop(),没有使用任何异步运行时', '没有验证:真正的 waker 唤醒(放在 Waker 一篇)、Pin 的作用(放在 Pin 与 Unpin 一篇)、async 块与 async fn 在类型上的区别、Poll::Pending 但不调用 waker 时会发生什么'], 'Future 与 Poll')
