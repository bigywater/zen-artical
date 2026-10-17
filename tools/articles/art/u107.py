from lib import *
S = SS('u107')
steps = [
    step("Waker 是「数据指针 + vtable 指针」两个指针,16 字节(size_of::<Waker>() = 16)。vtable 里有 4 个函数:clone、wake、wake_by_ref、drop。给它们装上计数器:创建后全是 0。", t=tl(S(1)), done=lidx(S(1), 'size_of', '创建后'), kv=KV([['Waker', '数据指针 + vtable,16 字节'], ['vtable', 'clone / wake / wake_by_ref / drop']], ['vtable'])),
    step("w.clone() 调用 vtable 的 clone(clone 1);w2.wake_by_ref() 调用 wake_by_ref(wake_by_ref 1,w2 仍然可用);w2.wake() 调用 wake(wake 1)并消耗 w2,所以 drop 仍是 0 —— wake 接管了释放;最后 drop(w) 才让 drop 变成 1。每个 Waker 值恰好经历 wake 或 drop 其中之一。", t=tl(S(1)), done=lidx(S(1), 'w.clone()', 'wake_by_ref()', 'w2.wake()', 'drop(w)'), kv=KV([['clone', '+1 clone'], ['wake_by_ref', '不消耗'], ['wake', '消耗,不再 drop']], ['wake'])),
    step("poll 里 Context 给的是 &Waker(借用),想以后唤醒就必须 clone 一份存起来:Saver 在第 1、2 次 poll 返回 Pending 并 clone 了 waker(clone 计数 1、2),外部事件各调用一次 saved.wake()(wake 计数 1、2),第 3 次 Ready。整个过程 clone 2 / wake 2 / drop 0。", t=tl(S(2)), done=lidx(S(2), 'poll #1', 'poll #2', 'poll #3'), mark=lidx(S(2), '外部事件'), kv=KV([['Pending 时', 'cx.waker().clone() 存起来'], ['事件发生', 'saved.wake()']], ['Pending 时'])),
    step("will_wake:b 是 a 的克隆,a.will_wake(&b) 为 true;另一个有相同数据指针与 vtable 的实例 c 也是 true;noop waker 与自己比较 true,与 a 比较 false。Future 被反复 poll 时,应该先 will_wake 比较,只有 waker 变了才替换保存的那份,省掉不必要的克隆。", t=tl(S(3)), done=lidx(S(3), 'true'), mark=lidx(S(3), 'false'), kv=KV([['同一任务的 waker', 'will_wake → true'], ['不同任务', 'false']], ['同一任务的 waker'])),
    step("Waker 是 Future 与执行器之间的唯一通道:条件满足后调用了 wake 的 Future,执行器 2 次 poll 就拿到「就绪」;条件同样在 50 ms 后满足但忘了调用 wake 的版本,执行器在 500 ms 里没有再 poll 它,最后返回 None —— 任务永远睡下去(无声的挂起,没有任何报错)。", t=tl(S(4)), done=lidx(S(4), '注册并调用了 waker'), mark=lidx(S(4), '没调用 waker'), kv=KV([['调用了 wake', '2 次 poll 完成'], ['忘了 wake', '永远不被再次 poll']], ['忘了 wake'])),
]
A = mkart('u107', 107, 'Rust,Waker,异步,唤醒机制,真实验证,动画演示',
    '用带计数的 vtable 验证 Waker:16 字节(数据指针 + vtable);clone / wake_by_ref / wake / drop 各调用哪个函数(wake 消耗 waker 所以不再 drop);Context 里的 &Waker 要 clone 才能保存;will_wake 的结果;忘了调用 wake 时任务永远睡下去。',
    'Waker 是异步 Rust 里最底层、最容易被忽略的一环:Future 返回 Pending 之后,靠它才能被再次 poll。这篇用自己写的 vtable 把 Waker 的四个操作逐个计数,再演示「忘了 wake」这个无声的挂起。',
    [('16 字节', 'Waker 的大小(数据指针 + vtable 指针)'), ('4 个函数', 'RawWakerVTable 的函数数:clone、wake、wake_by_ref、drop'), ('无声挂起', '条件满足却忘了调用 wake 的 Future 的结局')],
    [('Waker 的 vtable', '<p>手写执行器里 Waker 的用法见<a href="rust-async-runtime.html">Async Runtime 做了什么</a>。</p>'), ('保存 waker', None), ('will_wake', None), ('忘了 wake', '<p>手写完整 Future 见<a href="rust-custom-future.html">自定义 Future</a>。</p>')],
    steps, [ENV_U, '没有验证:Arc<W: Wake> 构造的 Waker 的内存管理细节、跨线程 wake 的数据竞争、RawWaker 的 unsafe 契约被违反时的后果、LocalWaker(不稳定)、虚假唤醒下执行器的行为'], 'Waker')
