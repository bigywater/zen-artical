from lib import *
S = SS('p19')
steps = [
    step("基准:4.7 MiB 的页面(4 万行表格),lxml.html.fromstring 加 xpath 数出 40000 个链接,单次解析约 89 ms(5 次中位数)。一个 asyncio 爬虫如果在协程里直接做这件事,事件循环就在这 89 ms 里不干别的。", t=tl(S(1)), done=lidx(S(1), '每次 89 ms'), kv=KV([['页面', '4.7 MiB,4 万行表格'], ['单次解析', '约 89 ms'], ['链接数', '40000']], ['单次解析'])),
    step("20 个并发抓取、抓完立刻解析,用一个每 10 ms 醒一次的“心跳”任务测事件循环被卡多久。直接在协程里解析:20 个页面共 1776 ms,心跳只跑了 7 次,最大延迟 1293 ms(这段时间所有其它协程包括网络读写都没动;多次运行的最大延迟在 657–1293 ms 之间),超过 50 ms 的 3 次。放进线程池(run_in_executor(None, …)):1518 ms,心跳 118 次,最大延迟 15 ms;放进 4 个进程的进程池:557 ms,心跳 67 次,最大延迟 13 ms。线程池里循环不再被卡住,但总耗时几乎没变(1518 对 1776 ms),进程池才真正并行。", t=tl(S(2)), done=lidx(S(2), 'run_in_executor(None', 'ProcessPoolExecutor(4)'), mark=lidx(S(2), '直接在协程里解析'), b=bars([['协程里直接解析:心跳最大延迟 ms', 1293, '1293'], ['线程池:最大延迟 ms', 15, '15'], ['进程池:最大延迟 ms', 13, '13'], ['线程池总耗时 ms', 1518, '1518'], ['进程池总耗时 ms', 557, '557']], 1800, mark=[0], done=[1, 2, 4]), kv=KV([['直接解析', '事件循环被卡 1293 ms'], ['线程池', '不卡了,但总耗时 1518 ms'], ['进程池', '557 ms,真正并行']], ['进程池'])),
    step("在协程里直接调用同步的 requests.get(服务器每个请求停 0.1 秒),10 个“并发”任务:共 1079 ms,服务器同时处理的峰值只有 1——它们其实是一个接一个跑的;心跳整整一次都没醒,最大延迟 1069 ms。换成 aiohttp:112 ms,峰值 10;asyncio.to_thread(requests.get, …):114 ms,峰值 10,心跳最大延迟都是 2 ms。", t=tl(S(3)), done=lidx(S(3), 'aiohttp:', 'asyncio.to_thread'), mark=lidx(S(3), '协程里直接 requests.get'), b=bars([['协程里直接 requests.get ms', 1079, '1079'], ['aiohttp ms', 112, '112'], ['to_thread(requests.get) ms', 114, '114']], 1100, mark=[0], done=[1, 2]), kv=KV([['协程里直接 requests.get', '1079 ms,峰值 1,事件循环被卡'], ['aiohttp', '112 ms,峰值 10'], ['to_thread(requests.get)', '114 ms,峰值 10']], ['协程里直接 requests.get'])),
    step("asyncio 的调试模式(PYTHONASYNCIODEBUG=1)会在某次回调超过 slow_callback_duration(默认 0.1 秒)时在 stderr 上记一条警告:一个协程里 time.sleep(0.35),得到 Executing <Task finished name='Task-1' coro=<main() …> … took 0.352 seconds。进程退出码是 0,这是警告而不是异常,不会让程序失败,需要自己去看日志。", t=tl(S(4)), done=lidx(S(4), 'took 0.352 seconds'), kv=KV([['开启方式', 'PYTHONASYNCIODEBUG=1'], ['阈值', 'slow_callback_duration 默认 0.1 秒'], ['输出', 'stderr 警告,退出码 0']], ['输出'])),
]
A = mkartp('p19', 19, '爬虫,asyncio,事件循环,阻塞调用,lxml,run_in_executor,进程池,Python,真实验证,动画演示',
    '用心跳任务测 asyncio 事件循环被卡的时间:20 个页面抓完后直接在协程里用 lxml 解析,事件循环最大延迟 1293 ms;放进线程池后降到 15 ms 但总耗时几乎不变(1518 ms),进程池才真正并行(557 ms);协程里直接 requests.get 让 10 个“并发”请求变成串行(1079 ms,服务器峰值 1)。',
    'asyncio 爬虫最隐蔽的性能问题是:在协程里放了一个同步的耗时调用。事件循环被卡住,所有其它协程(包括网络收发)一起停。这篇用一个心跳任务量化这种“卡住”,并对比线程池、进程池、to_thread 几种办法。',
    [('1293 ms', '直接在协程里解析 20 个大页面时,事件循环的最大延迟(心跳任务测得)'), ('557 ms', '同样的 20 个页面,解析放进 4 个进程的进程池后的总耗时(线程池 1518 ms)'), ('峰值 1', '协程里直接调用同步的 requests.get 时,服务器看到的并发峰值——10 个“并发”变成串行')],
    [('一次解析要多久', '<p>4.7 MiB 的页面一次解析约 89 ms;如果每个页面抓完立刻在协程里同步解析,20 个页面就是 20 次连续的 89 ms,事件循环被卡住,期间别的页面的数据也收不进来。</p>'),
     ('把解析挪出事件循环', '<p>心跳任务显示:直接解析时最大延迟 1293 ms(多次运行 657–1293 ms),放进线程池后只剩 15 ms,进程池 13 ms。但线程池对 CPU 密集的 lxml 解析几乎没有加速(总耗时 1518 ms 对 1776 ms),进程池才让 4 个核心真正并行(557 ms)。线程池为什么没有加速,下一批文章会单独看(lxml 与 GIL);进程池要付序列化页面内容的代价,这里没有拆开测。</p>'),
     ('同步的网络调用', '<p>在 <code>async def</code> 里直接写 <code>requests.get(...)</code> 是最典型的错误:服务器看到的并发峰值只有 1,10 个请求花了 1079 ms,事件循环整段时间没有醒过一次。换成 <code>aiohttp</code> 或者 <code>asyncio.to_thread(requests.get, …)</code> 都能恢复 10 个并发(约 112–114 ms)。</p>'),
     ('怎么发现', '<p>asyncio 调试模式会在回调超过 <code>slow_callback_duration</code>(默认 0.1 秒)时在 stderr 上打一条 <code>Executing … took … seconds</code> 的警告。它不抛异常、不改变退出码,所以要把日志看起来。</p>')],
    steps,
    [ENV_P + '。页面是 4 万行表格(4.7 MiB),解析用 lxml.html.fromstring 加 xpath("count(//a)");心跳任务每 10 ms 醒一次,延迟 = 实际醒来时间 − 预期时间;进程池是 4 个进程并预先预热;aiohttp 3.14.3;每种做法跑一次(心跳延迟每次运行会有明显差异,直接解析的最大延迟我见到过 657 到 1293 ms)',
     '没有验证:线程池为什么没有加速 lxml 解析(是否 lxml 在解析期间释放了 GIL,下一批文章单独测);进程池里序列化页面的开销;uvloop 下的表现;解析结果很大时返回值的传输成本;用 asyncio.to_thread 之外的其它非阻塞化办法(如异步解析库);Python 自由线程构建'],
    '事件循环里的阻塞调用')
