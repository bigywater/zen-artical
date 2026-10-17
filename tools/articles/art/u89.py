from lib import *
import re
S = SS('u89')
R = J('u89')
arr = re.search(r'到达顺序\(生产者编号\): (\d+)', R['multi']).group(1)
per = re.search(r'处理的任务数: (\[.*?\])', R['pool']).group(1)
bn = {k: float(v) for k, v in re.findall(r'^(unbounded|sync1024|sync1)\s+100 万条\s+([\d.]+) ms', R['bench'], re.M)}
u, s1, s1k = bn['unbounded'], bn['sync1'], bn['sync1024']; r1 = round(s1 / u)
steps = [
    step(f"多生产者:给每个线程 tx.clone() 一个发送端,3 个生产者各发 4 条,接收端共收到 12 条。每个生产者自己的序号 0,1,2,3 都按发送顺序到达(三个 true),但生产者之间交错:这次到达顺序(生产者编号)是 {arr}。", t=tl(S(1)), done=lidx(S(1), '共收到 12', '生产者 0', '生产者 1', '生产者 2'), mark=lidx(S(1), '到达顺序'), kv=KV([['同一生产者', '保序'], ['不同生产者', '交错,每次可能不同']], ['不同生产者'])),
    step("忘记 drop 原始的 tx:子线程发完就结束了(它那份 tx2 已 drop),但主线程手里还有 tx,第二次 recv_timeout(200ms) 得到 Err(Timeout) 而不是 Disconnected;drop(tx) 之后才得到 Err(Disconnected)。所以 for v in rx 的循环要结束,必须所有发送端(包括 clone 的原件)都被 drop。", t=tl(S(2)), mark=lidx(S(2), 'Timeout'), done=lidx(S(2), 'Ok(1)', 'Disconnected'), kv=KV([['还有一个 tx 活着', 'Timeout(会一直等)'], ['全部 drop', 'Disconnected']], ['还有一个 tx 活着'])),
    step("单消费者:Receiver 没有 clone,rx.clone() 报 error[E0599]: no method named `clone` found for struct `Receiver<T>`;让两个线程同时引用 rx 报 error[E0277]: `Receiver<i32>` cannot be shared between threads safely(Receiver 不是 Sync)。", t=tl(S(3)), mark=lidx(S(3), 'error[E0599]', 'error[E0277]'), kv=KV([['rx.clone()', 'E0599'], ['多线程共享 &rx', 'E0277:不是 Sync']], ['多线程共享 &rx'])),
    step(f"确实需要多消费者时,用 Arc<Mutex<Receiver>>:4 个工作线程争抢 20 个任务,每个任务恰好被处理一次(true),各线程处理的任务数是 {per}。锁只在 recv 的那一瞬间持有,处理任务时不持锁。", t=tl(S(4)), done=lidx(S(4), '处理了 20 个任务', '工作线程各处理'), kv=KV([['任务', '20 个,各处理一次'], ['4 个线程', per]], ['4 个线程'])),
    step("sync_channel(2):有界通道,已发 2 个后 try_send 第 3 个得到 Err(TrySendError::Full(..));另一个线程里的 send 被阻塞,等接收端 100 ms 后取走一个才继续,实测阻塞了约 100 毫秒。容量 0 是会合通道:没有接收者在等时 try_send 也是 Full,接收者在等时 send 才成功。", t=tl(S(5)), done=lidx(S(5), '被阻塞了约 100', '接收者在等时 send 成功'), mark=lidx(S(5), 'Full'), kv=KV([['满了', 'send 阻塞 / try_send 得 Full'], ['容量 0', '会合:必须有人在收']], ['满了'])),
    step(f"吞吐量(1 个生产者 + 1 个消费者,100 万个 u32,release,取 3 次最小):无界 channel {u:g} ms,sync_channel(1024) {s1k:g} ms,sync_channel(1) {s1:g} ms —— 容量为 1 时每条消息都要线程切换等待,比无界慢约 {r1} 倍。", t=tl(S(6)), done=lidx(S(6), 'unbounded', 'sync1024'), mark=lidx(S(6), 'sync1  '), b=bars([['无界 channel', u, f'{u:g} ms'], ['sync_channel(1024)', s1k, f'{s1k:g} ms'], ['sync_channel(1)', s1, f'{s1:g} ms']], s1, done=[0, 1], cur=[2]), kv=KV([['无界', f'{u:g} ms'], ['有界 1024', f'{s1k:g} ms'], ['有界 1', f'{s1:g} ms(约 {r1}×)']], ['有界 1'])),
]
A = mkart('u89', 89, 'Rust,mpsc,多生产者,sync_channel,真实验证,动画演示',
    f'用真实运行验证 mpsc:多生产者 clone 发送端、单生产者内保序、不同生产者交错;忘记 drop 原 tx 会让接收端一直等;Receiver 不能 clone 且不是 Sync;用 Arc<Mutex<Receiver>> 实现多消费者;sync_channel 的阻塞与会合;吞吐量无界 {u:g} ms、容量 1 的有界通道 {s1:g} ms。',
    'mpsc 的名字就是「多生产者、单消费者」。这篇验证多生产者之间的顺序保证、单消费者的限制与变通、忘记 drop 发送端的经典死等,以及有界通道的阻塞与吞吐量差别。',
    [('保序', '同一个生产者的消息到达顺序不变(不同生产者交错)'), (f'{r1}×', f'sync_channel(1) 比无界 channel 慢的倍数(100 万条)'), ('E0599', 'Receiver 调用 clone')],
    [('多个生产者', '<p>通道的基本语义见<a href="rust-channel-message-passing.html">Channel 消息传递</a>。</p>'), ('忘记 drop 发送端', None), ('单消费者的限制', '<p>Sync 的含义见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>'), ('多消费者的变通', None), ('有界通道', None), ('吞吐量', '<p>数字是本机 release 实测的最小值,只测了 1 个生产者 1 个消费者;更多线程时的竞争没有测。</p>')],
    steps, [ENV_U, '没有验证:crossbeam-channel / flume 的性能与功能对比、多个生产者同时竞争时的吞吐量、通道里消息很大时的内存、sync_channel 的公平性、async 通道(见异步部分)'], 'mpsc')
