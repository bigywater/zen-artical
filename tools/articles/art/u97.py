from lib import *
import re
S = SS('u97')
R = J('u97')
tot = re.search(r'总耗时约 (\d+) ms.*poll 了 (\d+) 次', R['basic']); tt, tp = tot.group(1), tot.group(2)
tk = re.search(r'总耗时约 (\d+) ms', R['tokio']).group(1)
steps = [
    step("异步运行时没有魔法。这里用不到 60 行标准库代码写了一个单线程执行器:任务队列(mpsc 通道)+ 每个任务一个 Waker(wake 就是把任务重新放回队列)+ run 循环(取任务、poll,Pending 就放回槽位等唤醒)。再配一个 Sleep Future:第一次 poll 时起一个后台线程,到点调用 waker.wake()。", t=tl(S(1)), done=lidx(S(1), '任务 A 开始'), kv=KV([['执行器', '队列 + poll 循环'], ['Waker', 'wake = 任务重新入队'], ['Sleep', '定时线程到点 wake']], ['Waker'])),
    step(f"3 个任务 A/B/C 分别 sleep 150/50/100 ms:三个任务都在 0 ms 开始,并且都在主线程上(同一线程: true);50 ms 时 B 醒来,100 ms 时 C,约 160 ms 时 A。总耗时约 {tt} ms,不是 150 + 50 + 100 = 300 ms;执行器一共 poll 了 {tp} 次(每个任务 2 次:启动一次、唤醒一次)。", t=tl(S(1)), done=lidx(S(1), '任务 B 睡了', '任务 C 睡了', '任务 A 睡了', '总耗时'), b=bars([['串行(150+50+100)', 300, '300 ms'], ['实测(交错)', int(tt), f'{tt} ms']], 300, cur=[1], done=[0]), kv=KV([['线程', '1 个(主线程)'], ['总耗时', f'约 {tt} ms'], ['poll 次数', tp]], ['总耗时'])),
    step("唤醒的路径(用日志标出):任务第一次被 poll → 内层 Future 返回 Pending,同时克隆了 waker 交给「定时器线程」→ 执行器此时队列为空,在 recv 上睡眠 → 30 ms 后定时器线程调用 wake() → 任务被重新放进队列 → 执行器醒来再 poll 一次,任务继续并结束。一共 poll 了 2 次。", t=tl(S(2)), done=lidx(S(2), '任务开始', '定时器线程 wake()', '任务被再次 poll', 'executor 退出'), mark=lidx(S(2), 'Pending'), kv=KV([['Pending 时', '把 waker 交给事件源'], ['事件发生', 'wake() → 入队 → 再 poll']], ['事件发生'])),
    step("执行器只有一个线程,任务里的阻塞调用会卡住所有任务:阻塞任务调用 thread::sleep(200) 期间,异步任务 sleep(20).await 本该 20 ms 后醒来,实际要等阻塞任务结束(约 200 ms)后才开始(「异步任务开始」出现在 200 ms),约 230 ms 才醒来。", t=tl(S(3)), mark=lidx(S(3), '异步任务开始', '异步任务醒来'), done=lidx(S(3), '阻塞任务'), kv=KV([['任务里 thread::sleep', '卡住整个执行器'], ['异步任务', '约 230 ms 才醒']], ['任务里 thread::sleep'])),
    step(f"对照 tokio(current_thread 单线程运行时,从 crates.io 下载):同样 3 个任务 sleep 150/50/100 ms,总耗时约 {tk} ms,与手写执行器({tt} ms)一致。运行时的核心职责:管理任务队列、提供 waker、把 I/O / 定时器事件转成 wake。手写版本里的定时器是「一个 sleep 一个线程」,tokio 用一个定时器轮,这一点没有展开验证。", t=tl(S(4)), done=lidx(S(4), 'tokio'), kv=KV([['手写执行器', f'约 {tt} ms'], ['tokio current_thread', f'约 {tk} ms']], ['tokio current_thread'])),
]
A = mkart('u97', 97, 'Rust,async,运行时,executor,waker,真实验证,动画演示',
    f'用不到 60 行标准库代码写一个单线程执行器(任务队列 + Waker + poll 循环 + 定时线程),验证异步运行时做了什么:3 个任务在同一线程交错运行,总耗时约 {tt} ms 而非 300 ms,poll {tp} 次;Pending → wake → 重新入队 → 再 poll 的完整路径;任务里 thread::sleep 卡住整个执行器;与 tokio current_thread({tk} ms)对照。',
    '说到异步运行时,很多人只会 #[tokio::main]。这篇自己写一个最小的执行器,把「任务队列、waker、poll 循环、定时器唤醒」这四个部件都亲手实现并跑通,再用它证明为什么异步任务里不能阻塞。',
    [('60 行', '一个能交错运行异步任务的单线程执行器的代码量'), (f'{tt} ms', '3 个 sleep 分别 150/50/100 ms 的任务总耗时(不是 300)'), ('卡住', '任务里调用 thread::sleep 时整个执行器的表现')],
    [('执行器与交错运行', '<p>Future 与 Poll 的基础见<a href="rust-future-poll.html">Future 与 Poll</a>。</p>'), ('唤醒的路径', '<p>Waker 的细节见<a href="rust-waker.html">Waker 唤醒机制</a>。</p>'), ('阻塞会卡住执行器', '<p>更多见<a href="rust-blocking-in-async.html">阻塞代码混入异步任务</a>。</p>'), ('对照 tokio', '<p>tokio 的调度见<a href="rust-tokio-scheduling.html">Tokio 任务调度</a>。tokio 1.x 从 crates.io 下载(需要联网)。</p>')],
    steps, [ENV_U + '。手写执行器只用标准库;tokio 为 current_thread 运行时', '没有验证:多线程执行器的任务窃取、真实 I/O 的就绪通知(epoll/kqueue)、tokio 定时器的内部实现、手写版本在上万个任务下的开销、JoinHandle 与结果返回'], '异步运行时')
