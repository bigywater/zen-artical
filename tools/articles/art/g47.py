from lib import *
S = SS('g47')
steps = [
    step("大量连接都阻塞在 Read 上(macOS,网络轮询器用 kqueue):100 条 TCP 连接,服务端每条一个 goroutine 阻塞在 Read:NumGoroutine = 102,线程创建数 5 → 5,goroutine 状态是 [IO wait]×101;2000 条连接:NumGoroutine = 2002,线程创建数 5 → 12,状态 [IO wait]×2001;lsof 看到本进程只有一个 KQUEUE 描述符(4u),不随连接数增长。", t=tl(S(1)), done=lidx(S(1), '100 条 TCP 连接'), mark=lidx(S(1), '2000 条 TCP 连接', 'KQUEUE'), b=bars([['100 连接:新增线程', 0, '0'], ['2000 连接:新增线程', 7, '7'], ['2000 连接:goroutine', 2002, '2002']], 2002, done=[0], mark=[1, 2]), kv=KV([['100 条连接', '线程 5 → 5,状态 [IO wait]'], ['2000 条连接', '线程 5 → 12(多了 7 个),goroutine 2002'], ['内核对象', '一个 kqueue 描述符,管全部连接']], ['内核对象'])),
    step("同样是“阻塞读”,走不走网络轮询器差别很大:200 个 goroutine 各读一个 pipe。通过 os.Pipe 的读端(os.File 把它注册进轮询器)Read:线程创建数 5 → 6,状态 [IO wait]×200;直接对阻塞的描述符调用 syscall.Read:线程创建数 5 → 203,状态 [syscall]×200——每个阻塞的系统调用占一个线程。", t=tl(S(2)), done=lidx(S(2), 'os.Pipe'), mark=lidx(S(2), 'syscall.Read'), b=bars([['os.Pipe:新增线程', 1, '+1'], ['syscall.Read:新增线程', 198, '+198']], 198, done=[0], mark=[1]), kv=KV([['os.Pipe + Read', '[IO wait]×200,线程 +1'], ['syscall.Read(阻塞 fd)', '[syscall]×200,线程 +198'], ['原因', '前者由轮询器等待,后者每个阻塞调用占住一个线程']], ['原因'])),
    step("读写超时靠轮询器里的定时器:SetReadDeadline(100ms) 之后 Read:101 ms 后返回,错误是 read tcp 127.0.0.1:64775->127.0.0.1:64774: i/o timeout,err.(net.Error).Timeout() 为 true。", t=tl(S(3)), mark=lidx(S(3), 'SetReadDeadline'), kv=KV([['SetReadDeadline(100ms)', '101 ms 后返回 i/o timeout'], ['错误类型', 'net.Error,Timeout() 为 true']], ['SetReadDeadline(100ms)'])),
]
A = mkartg('g47', 47, 'Go,netpoller,网络轮询器,kqueue,IO,真实验证,动画演示',
    '在 Go 1.27.1(macOS,kqueue)里验证网络轮询器:2000 条 TCP 连接各有一个 goroutine 阻塞在 Read 上,线程数只从 5 增加到 12,goroutine 状态是 [IO wait],进程里只有一个 KQUEUE 描述符;同样 200 个阻塞读,走 os.Pipe 只多 1 个线程,直接 syscall.Read 阻塞描述符多 198 个线程([syscall] 状态);读超时由轮询器的定时器实现。',
    'Go 里“一个连接一个 goroutine”的写法能撑起几万个连接,关键在网络轮询器:阻塞的网络 IO 并不真的阻塞一个线程。这篇用线程数和 goroutine 状态验证:连接多了线程不增长,而绕开轮询器的阻塞系统调用则一个占一个线程。',
    [('5 → 12', '2000 个阻塞在 Read 上的网络 goroutine 把线程数推高到的范围'), ('+1 vs +198', '200 个 goroutine 读 pipe:通过 os.File 走轮询器与直接 syscall.Read 的新增线程数'), ('1 个', '本进程持有的 kqueue 描述符数,与连接数无关')],
    [('连接多了线程不多', '<p>服务端每个连接一个 goroutine,在 <code>Read</code> 里“阻塞”时实际是把这个描述符登记到轮询器(macOS 上是 kqueue,Linux 上是 epoll),然后 goroutine 挂起,线程去跑别的 goroutine;数据到达时轮询器唤醒它。goroutine 的状态显示为 <code>[IO wait]</code>,而不是占着线程的 <code>[syscall]</code>。进程里只有一个 kqueue 描述符。线程从 5 涨到 12 是调度与别的原因,我没有逐个解释这 7 个线程。</p>'),
     ('绕开轮询器就占线程', '<p>对照实验里,把 pipe 描述符直接交给 <code>syscall.Read</code>(阻塞模式),每个阻塞的调用占住一个线程(线程数 +198);而 <code>os.Pipe()</code> 返回的 <code>os.File</code> 显然走了轮询器(状态是 <code>[IO wait]</code>,我没有读 <code>os</code> 包里把描述符设为非阻塞并注册的代码),同样的 200 个阻塞读只多一个线程。结论:想让大量阻塞 IO 便宜,要用 <code>net</code> 与 <code>os.File</code> 这类封装,而不是自己 <code>syscall</code>。普通磁盘文件不能被轮询,读写它们仍然是阻塞系统调用(本文没有试)。</p>'),
     ('超时', '<p><code>SetReadDeadline</code> 把超时时刻交给运行时的定时器;到点后阻塞的 <code>Read</code> 返回 <code>i/o timeout</code>,错误实现了 <code>net.Error</code> 且 <code>Timeout()</code> 为真。实测 100 ms 的超时 101 ms 后返回。</p>')],
    steps,
    [ENV_G + '。macOS 上网络轮询器用 kqueue(lsof 里的 KQUEUE 描述符是实测),Linux 上是 epoll,没有测;线程数用 pprof 的 threadcreate 计数(创建过的线程总数,不是当前线程);goroutine 状态来自 pprof goroutine profile 的 debug=2 标题行;所有连接在同一进程内的本地回环上',
     '没有验证:Linux 上的 epoll 行为、轮询器内部结构(netpollWaiters、边缘触发等)、普通文件与终端的读写是否走轮询器、百万连接时 kqueue 的扩展性、SetReadDeadline 在高并发下的精度、5 → 12 中新增的 7 个线程的来源'],
    '网络轮询器')
