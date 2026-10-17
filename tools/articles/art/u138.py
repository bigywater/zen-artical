from lib import *
import re
S = SS('u138')
R = J('u138'); W = R['wait']
def g(k):
    m = re.search(r'循环 (\d+) 次,消耗 CPU 时间 ([\d.]+) ms', W[k]); return int(m.group(1)), float(m.group(2))
bl, bc = g('busy'); kl, kc = g('blocking'); pl, pc = g('poll')
steps = [
    step("set_nonblocking(true) 之后,accept 在没有客户端时立刻返回 Err(WouldBlock)(约 3 µs);对没有数据的连接 read 也立刻 WouldBlock(约 6 µs);对端发 2 字节后 read 得到 Ok(2);对端关闭后 read 得到 Ok(0)(EOF)。非阻塞的意思是「现在没有就告诉我,不要等」。", t=tl(S(1)), done=lidx(S(1), '没有客户端时 accept', '没有数据时 read', '对端发 2 字节', '对端关闭后'), kv=KV([['没有数据', 'Err(WouldBlock),几微秒内返回'], ['有数据', 'Ok(n)'], ['对端关闭', 'Ok(0)']], ['没有数据'])),
    step(f"等一个 300 ms 之后才到的数据,三种等法的代价(release):非阻塞 + 空转循环循环了 {bl:,} 次,进程消耗 CPU 时间 {bc} ms(300 ms 里一个核心基本被占满);阻塞式 read 只调用 1 次,CPU 时间 {kc} ms;非阻塞 + poll(2) 等待就绪,循环 {pl} 次,CPU 时间 {pc} ms。忙等把等待变成了烧 CPU。", t=tl(S(2)), done=lidx(S(2), 'blocking', 'poll'), mark=lidx(S(2), 'busy'), b=bars([['忙等 CPU 时间', bc, f'{bc} ms'], ['阻塞 read', max(kc, 0.1), f'{kc} ms'], ['poll', max(pc, 0.1), f'{pc} ms']], bc, cur=[0], done=[1, 2]), kv=KV([['忙等', f'{bl:,} 次循环,CPU {bc} ms'], ['阻塞 read', f'CPU {kc} ms'], ['poll', f'CPU {pc} ms']], ['忙等'])),
    step("非阻塞的价值在于一个线程同时盯着多个连接:poll(2) 同时监视 3 个 socket,客户端 0、1、2 分别在 120、40、80 ms 发数据,一个线程(ThreadId(1))按就绪的先后顺序处理:client1(约 40 ms)、client2(约 80 ms)、client0(约 120 ms)。没有每连接一个线程。", t=tl(S(3)), done=lidx(S(3), 'client1'), kv=KV([['poll 监视多个 fd', '谁就绪处理谁'], ['线程数', '1']], ['线程数'])),
    step("非阻塞标志属于同一个打开的 socket,不属于某个 TcpStream 值:只对 a 调用 set_nonblocking(true),用 try_clone 出来的 b 去 read,立刻得到 Err(WouldBlock) —— 克隆也跟着变成非阻塞了。混用阻塞与非阻塞的克隆会出乎意料。", t=tl(S(4)), done=lidx(S(4), '只对 a 调用'), kv=KV([['a.set_nonblocking', '克隆 b 也变非阻塞']], ['a.set_nonblocking'])),
]
A = mkart('u138', 138, 'Rust,非阻塞IO,poll,TCP,真实验证,动画演示',
    f'用回环 TCP 与真实 libc poll 验证非阻塞 IO:WouldBlock 几微秒返回;等 300 ms 的数据,忙等循环 {bl:,} 次烧 {bc} ms CPU,阻塞 read {kc} ms,poll {pc} ms;一个线程用 poll 按就绪顺序服务 3 个连接;非阻塞标志被 try_clone 的克隆共享。',
    '非阻塞 IO 不是「更快」,而是「不用等」。这篇验证它的返回形式、忙等的真实代价、用 poll 在一个线程里同时盯多个连接,以及一个容易踩的克隆共享陷阱。',
    [(f'{bc} ms', '忙等 300 ms 消耗的 CPU 时间(poll 只要 ' + str(pc) + ' ms)'), (f'{bl:,} 次', '忙等循环在 300 ms 里空转的次数'), ('1 个线程', 'poll 同时服务 3 个连接所用的线程数')],
    [('WouldBlock', '<p>阻塞式 TCP 见<a href="rust-tcp-listener-stream.html">TCP Listener 与 TcpStream</a>。</p>'), ('忙等与 poll 的代价', '<p>CPU 时间通过 clock_gettime(CLOCK_PROCESS_CPUTIME_ID) 读取;poll 通过 extern 声明直接调用 libc,没有使用 mio。</p>'), ('一个线程服务多个连接', '<p>异步运行时在这个基础上封装,见<a href="rust-async-runtime.html">Async Runtime 做了什么</a>。</p>'), ('克隆共享非阻塞标志', None)],
    steps, [ENV_U + '。poll 在 macOS 上可用;没有使用 kqueue / epoll / mio', '没有验证:kqueue 与 epoll 的性能对比、边沿触发与水平触发、大量连接(上万)时 poll 的开销、非阻塞 connect、写方向的 WouldBlock(发送缓冲区满)'], '非阻塞 IO')
