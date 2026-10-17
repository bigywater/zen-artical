from lib import *
import re
S = SS('u108')
R = J('u108')
seq = re.search(r'顺序 await 两个 100 ms:总耗时约 (\d+) ms,poll (\d+) 次', R['join']); jn = re.search(r'join2 同时等两个 100 ms:总耗时约 (\d+) ms,poll (\d+) 次', R['join']); j2 = re.search(r'150 ms 与 50 ms:总耗时约 (\d+) ms.*poll (\d+) 次', R['join'])
steps = [
    step("自己写的 Timer Future:共享状态 Shared { done, waker } 放在 Arc<Mutex<…>> 里,后台线程睡到点后把 done 置 true 并取出 waker 调用 wake();poll 里如果 done 就 Ready,否则把 cx.waker().clone() 存进共享状态再返回 Pending。await 100 ms:实测 100 ms,executor 一共 poll 了 2 次 —— 第 1 次 Pending,被 wake 后第 2 次 Ready。", t=tl(S(1)), done=lidx(S(1), '等 100 ms 的 Timer'), kv=KV([['poll', 'done ? Ready : 保存 waker + Pending'], ['后台线程', 'done = true; waker.wake()']], ['poll'])),
    step(f"顺序 await 两个 100 ms 的 Timer:总耗时约 {seq.group(1)} ms(100 + 100),poll {seq.group(2)} 次;自己写的 join2(同时 poll 两个 Future,都完成才完成)同时等两个 100 ms:总耗时约 {jn.group(1)} ms,结果 (A, B),poll {jn.group(2)} 次。", t=tl(S(2)), done=lidx(S(2), '顺序 await', 'join2 同时等'), b=bars([['顺序 await', int(seq.group(1)), f'{seq.group(1)} ms'], ['join2', int(jn.group(1)), f'{jn.group(1)} ms']], int(seq.group(1)), cur=[1], done=[0]), kv=KV([['顺序', f'约 {seq.group(1)} ms'], ['join2', f'约 {jn.group(1)} ms']], ['join2'])),
    step(f"join2 的 150 ms 与 50 ms:总耗时约 {j2.group(1)} ms(取较长的那个),poll {j2.group(2)} 次 —— 50 ms 的先完成,结果被存进 ra/rb,150 ms 的后完成时一起返回。join 的要点:每次 poll 只重新 poll 还没完成的子 Future,并把已完成的结果暂存起来。", t=tl(S(2)), done=lidx(S(2), '150 ms 与 50 ms'), kv=KV([['总耗时', '取最长的一个'], ['已完成的结果', '暂存直到全部完成']], ['已完成的结果'])),
    step("常见错误:poll 里返回 Pending 却没有保存 waker。把 Timer 里「g.waker = Some(cx.waker().clone())」去掉,后台线程到点只能 wake 一个 None;在另一个线程里 block_on 它,主线程等 600 ms 仍然没完成 —— executor 永远睡着,没有任何错误提示。", t=tl(S(3)), mark=lidx(S(3), '600 ms 过去了'), kv=KV([['没保存 waker', '到点无人可唤醒 → 永远睡着']], ['没保存 waker'])),
    step("waker 会变:同一个 Timer 先用 waker1 poll,再用 waker2 poll(模拟 Future 被移到另一个任务),80 ms 到点后只有 waker2 被唤醒(waker1 = false,waker2 = true)。因为 Timer 每次 poll 都覆盖保存的 waker —— 所以 poll 里每次都要更新 waker,而不是只在第一次保存。", t=tl(S(4)), done=lidx(S(4), 'waker2 被唤醒了吗'), kv=KV([['每次 poll', '都要更新保存的 waker'], ['只保存第一次', '会唤醒错误的任务']], ['每次 poll'])),
]
A = mkart('u108', 108, 'Rust,自定义Future,Timer,join,真实验证,动画演示',
    f'自己写 Timer Future(共享状态 + 保存 waker + 后台线程唤醒)和 join2 组合子:Timer 等 100 ms poll 2 次;顺序 await 两个 100 ms 耗时约 {seq.group(1)} ms 而 join2 约 {jn.group(1)} ms;不保存 waker 会永远睡着;waker 会随 poll 变化必须每次更新。',
    '真正理解 Future,最好的办法是自己写一个。这篇从零写一个定时器 Future 和一个 join 组合子,用 poll 计数和耗时验证它们的行为,并复现两个最常见的错误:忘记保存 waker 与只保存第一次的 waker。',
    [('2 次', '一个 100 ms 的自定义 Timer 被 poll 的次数(Pending 一次、Ready 一次)'), (f'{seq.group(1)} 对 {jn.group(1)} ms', '顺序 await 与 join2 等两个 100 ms 定时器的耗时'), ('永远睡着', '没有保存 waker 的 Future 的结局')],
    [('自己写一个 Timer', '<p>Waker 的细节见<a href="rust-waker.html">Waker 唤醒机制</a>;Pin 见<a href="rust-pin-unpin.html">Pin 与 Unpin</a>。</p>'), ('顺序 await 与 join', None), ('忘记保存 waker', None), ('waker 会变', None)],
    steps, [ENV_U + '。执行器用 Condvar 实现的最小 block_on', '没有验证:Join 子 Future panic 时的行为、join 对 !Unpin 输出的处理、使用 pin-project 的无 unsafe 写法、select 组合子的手写版本、Timer 不用后台线程的实现(需要事件循环)'], '自定义 Future')
