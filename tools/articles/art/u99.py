from lib import *
import re
S = SS('u99')
R = J('u99')
dist = re.findall(r'线程 (ThreadId\(\d+\))\s+完成了 (\d+) 个任务', R['dist'])
mv = re.search(r'有 (\d+) 个在运行过程中换过', R['migrate']).group(1)
first = re.search(r'\[\s*(\d+) ms\] ticker 第 1 次', R['starve']).group(1); first_m = re.search(r'\[\s*(\d+) ms\] ticker 第 1 次', R['multi']).group(1)
steps = [
    step("多线程运行时(4 个工作线程,tokio 1.x 从 crates.io 下载):1000 个任务每个做一点 CPU 工作再 yield,最终分布在全部 4 个线程上:" + '、'.join(f'{t} 完成 {n} 个' for t, n in dist) + "。任务数大致均匀,但并不平均。", t=tl(S(1)), done=lidx(S(1), '线程 ThreadId', '共 4 个'), b=bars([[t, int(n), n] for t, n in dist], max(int(n) for t, n in dist) + 20, done=list(range(len(dist)))), kv=KV([[t, f'{n} 个任务'] for t, n in dist], [dist[0][0]])),
    step(f"同一个任务不绑定线程:16 个任务各在 20 个 yield 点记录当前线程 id,其中 {mv} 个任务在运行过程中换过工作线程(被其它工作线程偷走或重新分配)。所以 async 任务里不要依赖线程本地存储,跨 await 的数据要 Send。", t=tl(S(2)), done=lidx(S(2), '换过工作线程'), kv=KV([['16 个任务', f'{mv} 个换过线程']], ['16 个任务'])),
    step(f"current_thread 运行时只有一个线程,任务里 150 ms 的纯 CPU 计算(没有 await)期间,ticker 任务本该每 20 ms 打印一次,却一次也没有运行:第 1 次在 {first} ms(计算结束后)才出现,之后才恢复每 20-30 ms 一次。这是「协作式调度」:任务不 await,调度器就拿不回线程。", t=tl(S(3)), mark=lidx(S(3), '计算结束', 'ticker 第 1 次'), done=lidx(S(3), '开始 150 ms'), kv=KV([['ticker 第 1 次', f'{first} ms(应是 20 ms)'], ['原因', '计算期间没有 await,没有让出点']], ['ticker 第 1 次'])),
    step(f"同样的程序放在多线程运行时(2 个工作线程):ticker 在计算期间照常运行,第 1 次在 {first_m} ms,每 20-30 ms 一次,共 5 次都在计算结束(150 ms)之前。多线程运行时能缓解,但不能消除问题:所有工作线程都被占满时同样会饿死。", t=tl(S(4)), done=lidx(S(4), 'ticker 第 1 次', 'ticker 第 5 次'), kv=KV([['多线程', f'ticker 第 1 次在 {first_m} ms']], ['多线程'])),
    step("spawn_blocking 把阻塞/CPU 密集的工作放到专门的阻塞线程池:即使是 current_thread 运行时,150 ms 的 thread::sleep 也在另一个线程上执行(线程 id 与运行时线程不同),ticker 全程每 20-30 ms 一次,没有被拖慢。", t=tl(S(5)), done=lidx(S(5), 'ticker 第 1 次', '阻塞任务在线程'), kv=KV([['spawn_blocking', '独立的阻塞线程池'], ['ticker', '不受影响']], ['spawn_blocking'])),
]
A = mkart('u99', 99, 'Rust,tokio,调度,工作窃取,真实验证,动画演示',
    f'下载 tokio 验证任务调度:4 工作线程运行时上 1000 个任务分布在全部 4 个线程;同一任务的多次 poll 可能换线程(16 个里 {mv} 个);current_thread 里 150 ms 无 await 计算让 ticker 推迟到 {first} ms;多线程运行时里 ticker 在 {first_m} ms 就开始;spawn_blocking 不占用运行时线程。',
    'tokio 怎么把任务分给工作线程?一个任务会固定在一个线程上吗?一个不 await 的计算会拖垮什么?这篇用 4 个小程序观察 tokio 调度的真实行为,再看 spawn_blocking 怎么避开这些问题。',
    [('4 个线程', '1000 个任务分布的工作线程数'), (f'{first} ms', 'current_thread 里 ticker 本该在 20 ms 出现,实际出现的时间'), (f'{mv}/16', '运行过程中换过工作线程的任务数')],
    [('任务在工作线程间的分布', '<p>手写执行器见<a href="rust-async-runtime.html">Async Runtime 做了什么</a>。</p>'), ('任务会迁移', None), ('单线程上的饿死', '<p>更多见<a href="rust-blocking-in-async.html">阻塞代码混入异步任务</a>。</p>'), ('多线程运行时的表现', None), ('spawn_blocking', None)],
    steps, [ENV_U + '。tokio 1.x(rt、rt-multi-thread、time、macros),release 构建', '没有验证:tokio 的 LIFO 槽与全局队列的细节、任务窃取的具体策略(只观察到迁移)、coop 预算对只做 I/O 的任务的影响、任务数远多于线程数时的延迟分布、所有工作线程都被占满时的饥饿'], 'tokio 调度')
