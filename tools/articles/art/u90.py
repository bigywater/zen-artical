from lib import *
import re
S = SS('u90')
R = J('u90')
tm, tr, tw = (int(x) for x in re.search(r'Mutex:\s+4 个线程各持锁 50 ms,总耗时约 (\d+) ms.*?\n.*?约 (\d+) ms.*?\n.*?约 (\d+) ms', R['par']).groups())
bm = float(re.search(r'Mutex\s+4 线程 × 200 万次读:\s+([\d.]+) ms', R['bench']).group(1)); br = float(re.search(r'RwLock 4 线程 × 200 万次读:\s+([\d.]+) ms', R['bench']).group(1)); rr = round(br / bm, 1)
steps = [
    step(f"4 个线程各持锁 50 ms:Mutex 一次只让一个线程进入,总耗时约 {tm} ms(串行);RwLock 的读锁允许多个读者同时持有,总耗时约 {tr} ms(并行);RwLock 的写锁仍然互斥,总耗时约 {tw} ms。", t=tl(S(1)), done=lidx(S(1), 'Mutex:', 'RwLock 读', 'RwLock 写'), b=bars([['Mutex(4×50ms)', tm, f'{tm} ms'], ['RwLock 读(4×50ms)', tr, f'{tr} ms'], ['RwLock 写(4×50ms)', tw, f'{tw} ms']], tw + 20, cur=[1], done=[0, 2]), kv=KV([['Mutex', f'约 {tm} ms,串行'], ['RwLock 读', f'约 {tr} ms,并行'], ['RwLock 写', f'约 {tw} ms,串行']], ['RwLock 读'])),
    step("读写互斥关系:持有写锁时 try_read 与 try_write 都得到 WouldBlock;持有读锁时 try_read 成功、try_write 得到 WouldBlock;Mutex 被持有时 try_lock 得到 WouldBlock,释放后成功。", t=tl(S(2)), done=lidx(S(2), '持有读锁时', '释放后'), mark=lidx(S(2), '持有写锁时', 'Mutex 持有时'), kv=KV([['写锁', '排斥读者和写者'], ['读锁', '只排斥写者']], ['读锁'])),
    step("同一线程重复加锁会死锁而不是报错:子线程拿到第一把锁后再 lock() 第二次,主线程再等 300 ms 只得到 Err(Timeout),主线程的 try_lock 也拿不到(锁被卡住的那个线程占着)。Mutex 不是可重入的。", t=tl(S(3)), mark=lidx(S(3), 'Timeout', 'try_lock'), done=lidx(S(3), '拿到第一把锁'), kv=KV([['同线程二次 lock', '死锁,不报错'], ['Mutex', '不可重入']], ['同线程二次 lock'])),
    step(f"临界区很小时 RwLock 反而更慢:4 个线程各读一个 u64 共 200 万次(release,取 3 次最小),Mutex {bm:g} ms,RwLock {br:g} ms,在这台机器上 RwLock 约慢 {rr} 倍;Mutex<u64> 与 RwLock<u64> 都是 24 字节。RwLock 只在读者长时间持锁时才有优势。", t=tl(S(4)), done=lidx(S(4), 'Mutex  4 线程', 'RwLock 4 线程', 'size_of'), b=bars([['Mutex', bm, f'{bm:g} ms'], ['RwLock', br, f'{br:g} ms']], br, cur=[1], done=[0]), kv=KV([['Mutex', f'{bm:g} ms'], ['RwLock', f'{br:g} ms(约 {rr}×)']], ['RwLock'])),
]
A = mkart('u90', 90, 'Rust,Mutex,RwLock,并发,真实验证,动画演示',
    f'用真实运行对比 Mutex 与 RwLock:4 个线程各持 50 ms,Mutex 约 {tm} ms 串行、RwLock 读约 {tr} ms 并行、写约 {tw} ms;try_lock/try_read/try_write 的互斥关系;同线程重复 lock 死锁;4 线程 × 200 万次极短读,Mutex {bm:g} ms 而 RwLock {br:g} ms。',
    '「读多写少就用 RwLock」是常见建议,但真实数据支持吗?这篇先验证 RwLock 的并行读优势,再验证 try 系列函数、同线程重复加锁的死锁,最后用极短临界区的微基准,看看 RwLock 什么时候反而更慢。',
    [(f'{tm} → {tr}', 'Mutex 与 RwLock 读锁:4 个线程各持 50 ms 的总耗时(ms)'), (f'{rr}×', f'极短临界区下,RwLock 比 Mutex 慢的倍数({br:g} 对 {bm:g} ms)'), ('WouldBlock', 'try_lock / try_read / try_write 在锁被占用时的返回')],
    [('串行与并行', '<p>Mutex 的基础见<a href="rust-mutex-interior-mutability.html">Mutex&lt;T&gt; 与内部可变性</a>。</p>'), ('读写锁的互斥关系', None), ('重复加锁', None), ('极短临界区', '<p>这是 macOS aarch64 上的一次微基准,其它平台与读写比例下结论可能不同;没有测混合读写。毒化的行为见<a href="rust-catch-unwind.html">catch_unwind</a>。</p>')],
    steps, [ENV_U + '。耗时用 release 构建,各取 3 次最小', '没有验证:写者饥饿(读者源源不断时写者能否进入)、parking_lot 的 Mutex/RwLock、Linux 上的表现、读写混合比例下的盈亏平衡点、锁的公平性'], 'Mutex 与 RwLock')
