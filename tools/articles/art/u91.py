from lib import *
import re
S = SS('u91')
R = J('u91')
cpu = re.search(r'CPU 时间约 (\d+) ms', R['queue']).group(1); wall = re.search(r'墙钟时间约 (\d+) ms', R['queue']).group(1)
steps = [
    step("Condvar 的标准用法:Mutex<bool> 保护条件,等待方 while !*ready { ready = cv.wait(ready).unwrap(); },另一个线程 100 ms 后置 true 并 notify_one。等待方实测等了约 100 ms 后继续。wait 要传入锁的 guard,醒来后返回重新拿到锁的 guard。", t=tl(S(1)), done=lidx(S(1), '等到条件为真'), kv=KV([['wait(guard)', '释放锁并睡眠,醒来重新拿锁'], ['while !条件', '醒来后重新检查']], ['while !条件'])),
    step("wait 期间锁是释放的:子线程正在 wait 时,主线程 try_lock 成功(true);主线程把值设为 7 并 notify_one,子线程醒来读到 7。如果 wait 不释放锁,主线程永远没法改条件。", t=tl(S(2)), done=lidx(S(2), 'try_lock 成功', '读到 7'), kv=KV([['wait 期间', '锁被释放'], ['醒来读到', '7']], ['wait 期间'])),
    step("通知会丢失:先 notify_one 后 wait,条件变量本身不记住通知,带超时的 wait_timeout 超时了(timed_out = true)。所以条件必须放在 Mutex 保护的状态里。", t=tl(S(3)), mark=lidx(S(3), '先 notify 后 wait'), kv=KV([['先 notify 后 wait', '通知丢失,只能超时']], ['先 notify 后 wait'])),
    step("正确写法:先把 bool 置 true 再 notify,之后 wait_timeout_while(…, |ready| !*ready) 立刻发现条件已满足,没有超时(timed_out = false,条件 = true)。状态变量让「先通知后等待」也安全。", t=tl(S(3)), done=lidx(S(3), '先通知(置 true)'), kv=KV([['bool + wait_while', '先通知后等待也安全']], ['bool + wait_while'])),
    step("5 个线程都在 wait:notify_one 只唤醒 1 个,notify_all 唤醒 5 个。", t=tl(S(4)), done=lidx(S(4), 'notify_one'), b=bars([['notify_one 唤醒', 1, '1'], ['notify_all 唤醒', 5, '5']], 6, cur=[0], done=[1]), kv=KV([['notify_one', '1 个'], ['notify_all', '5 个']], ['notify_all'])),
    step(f"用 Condvar 做阻塞队列:生产者每 50 ms 放一个,消费者在队列空时睡眠。收到 0..9 全部 10 个,墙钟时间约 {wall} ms,而整个进程的 CPU 时间只有约 {cpu} ms —— 消费者不是忙等,而是真的睡着了。", t=tl(S(5)), done=lidx(S(5), '收到'), kv=KV([['墙钟时间', f'约 {wall} ms'], ['进程 CPU 时间', f'约 {cpu} ms']], ['进程 CPU 时间'])),
]
A = mkart('u91', 91, 'Rust,Condvar,条件变量,并发,真实验证,动画演示',
    f'用真实运行验证 Condvar:wait 释放锁并睡眠、醒来重新检查条件;wait 期间 try_lock 成功;先通知后等待会丢通知(wait_timeout 超时),用 bool 状态变量修复;notify_one 唤醒 1 个、notify_all 唤醒 5 个;阻塞队列墙钟约 {wall} ms 而 CPU 约 {cpu} ms。',
    '条件变量总让人困惑:为什么 wait 要传 guard?为什么要用 while?通知会丢吗?notify_one 和 notify_all 差在哪?这篇每个问题都用一个真实运行的小实验回答。',
    [('1 对 5', 'notify_one 与 notify_all 在 5 个等待线程中各唤醒的线程数'), ('通知丢失', '先 notify 后 wait,没有状态变量时的结局'), (f'约 {cpu} ms', f'阻塞队列跑了约 {wall} ms 墙钟时间所用的进程 CPU 时间')],
    [('标准用法', '<p>Mutex 的基础见<a href="rust-mutex-vs-rwlock.html">Mutex 与 RwLock</a>。</p>'), ('wait 释放锁', None), ('通知会丢', '<p>虚假唤醒(spurious wakeup)是 while 循环的另一个理由,这次实验没有复现出来。</p>'), ('notify_one 与 notify_all', None), ('阻塞队列', '<p>通道封装了这个模式,见<a href="rust-channel-message-passing.html">Channel 消息传递</a>。</p>')],
    steps, [ENV_U + '。进程 CPU 时间通过 clock_gettime(CLOCK_PROCESS_CPUTIME_ID) 读取', '没有验证:虚假唤醒(没有复现)、Condvar 配多个 Mutex 的 panic、wait_timeout 的精度、notify 的顺序与公平性、parking_lot::Condvar'], 'Condvar')
