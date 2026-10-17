from lib import *
S = SS('u105')
steps = [
    step("drop 掉 JoinHandle 不会取消任务:任务 A 的 JoinHandle 立刻被 drop,50 ms 后它仍然打印「任务 A 跑完了」(在后台继续跑,变成 detached)。要取消必须调用 abort():任务 B 被 abort 后,h.await 得到 Err(JoinError::Cancelled),「任务 B 跑完了」从未出现。", t=tl(S(1)), done=lidx(S(1), '任务 A 跑完了'), mark=lidx(S(1), '任务 B abort', 'Cancelled'), kv=KV([['drop(JoinHandle)', '不取消,任务继续'], ['abort()', '取消,await 得 Cancelled']], ['abort()'])),
    step("取消只发生在 await 点:任务在 200 ms 的同步循环里,主任务 50 ms 时调用 h.abort(),但任务要一直跑到约 200 ms 循环结束、走到第一个 await 的位置,h.await 才返回 Err(true)(is_cancelled)—— abort 不能打断同步代码。", t=tl(S(2)), mark=lidx(S(2), 'h.abort()', 'h.await 返回'), done=lidx(S(2), '任务开始', '同步循环结束'), kv=KV([['abort() 的时刻', '50 ms'], ['实际取消生效', '约 200 ms(下一个 await)']], ['实际取消生效'])),
    step("取消不会回滚已执行的副作用:转账分两步(先扣 A 的 40,再 await 100 ms,然后加到 B),30 ms 的 timeout 在两步之间取消了它:A = 60、B = 0,合计 60,凭空少了 40。取消点之前的修改已经生效。", t=tl(S(3)), mark=lidx(S(3), 'A = 60,账户 B = 0'), kv=KV([['两步之间被取消', 'A = 60,B = 0,合计 60(丢了 40)']], ['两步之间被取消'])),
    step("取消安全的写法:先 await,等条件满足后一次性修改(拿到两把锁一起改)。同样 30 ms 的 timeout 取消了它,A = 100、B = 0,合计仍是 100 —— 取消时什么都没改。要点是把有副作用的步骤放在最后一个 await 之后。", t=tl(S(3)), done=lidx(S(3), '换新账户'), kv=KV([['先 await,后一次性修改', '取消时无副作用']], ['先 await,后一次性修改'])),
    step("锁会随 Future 一起释放:tokio Mutex 的 guard 在 async 块里被持有跨 500 ms 的 sleep,30 ms 时 timeout 取消了这个 Future,guard 随之 drop,之后立刻 try_lock 成功。取消不会造成死锁。", t=tl(S(4)), done=lidx(S(4), 'try_lock'), kv=KV([['被取消的 Future 持有的 guard', '随 Future drop 释放']], ['被取消的 Future 持有的 guard'])),
    step("Drop 里不能 await:impl Drop 里写 tokio::time::sleep(…).await 报 error[E0728]: `await` is only allowed inside `async` functions and blocks。drop 是同步函数,所以取消时的异步清理(关闭连接、发送告别消息)不能写在 Drop 里,要提供显式的 async close 方法或交给后台任务。", t=tl(S(5)), mark=lidx(S(5), 'error[E0728]'), kv=KV([['Drop::drop', '同步函数,不能 await']], ['Drop::drop'])),
]
A = mkart('u105', 105, 'Rust,Future,取消,drop,tokio,真实验证,动画演示',
    'tokio 验证 Future 取消:drop JoinHandle 不取消、abort() 才取消;abort 只在 await 点生效(同步循环要跑完);取消不回滚副作用(转账丢 40)而「先 await 后一次性修改」安全;tokio Mutex 的 guard 随 Future 释放;Drop 里不能 await(E0728)。',
    'Rust 的 async 取消没有 finally:Future 被 drop 时,执行到哪一行就停在哪一行。这篇验证取消到底发生在什么时候、之前的修改会不会回滚、锁会不会泄漏、异步清理该放在哪。',
    [('不取消', '仅 drop JoinHandle 时任务的命运(继续在后台运行)'), ('丢 40', '分两步转账被 timeout 取消后账户合计少了多少'), ('E0728', '在 Drop 里 await 的编译错误')],
    [('JoinHandle 与 abort', '<p>Future 与 drop 的基础见<a href="rust-future-poll.html">Future 与 Poll</a>。</p>'), ('取消只发生在 await 点', None), ('副作用不会回滚', '<p>select! 里的取消安全问题见<a href="rust-select-cancellation.html">select! 取消竞争</a>。</p>'), ('锁的释放', None), ('Drop 里不能 await', None)],
    steps, [ENV_U + '。tokio 1.x', '没有验证:tokio_util 的 CancellationToken 与 DropGuard、spawn 的任务 panic 时的传播、AsyncDrop(不稳定)、数据库事务在 Future 被取消时的实际行为、JoinSet 被 drop 时的取消行为'], 'Future 取消与 Drop')
