from lib import *
S = SS('s8')
steps = [
    step("2.19 默认的调度器配置:SCHEDULER = core.scheduler.Scheduler,优先级队列 SCHEDULER_PRIORITY_QUEUE = pqueues.DownloaderAwarePriorityQueue,内存队列 LifoMemoryQueue,磁盘队列 PickleLifoDiskQueue,起始请求另用 FifoMemoryQueue / PickleFifoDiskQueue,去重 RFPDupeFilter。没设 JOBDIR 时,一个种子页加 20 个子页共 21 个请求全部走内存队列(enqueued/memory = 21);设了 JOBDIR,同样 21 个请求全进磁盘队列(enqueued/disk = 21),一个都没进内存。", t=tl(S(1)), mark=lidx(S(1), 'DownloaderAware', '不设 JOBDIR', 'JOBDIR=<目录>'), done=lidx(S(1), 'SCHEDULER ', 'MEMORY', 'DISK', 'DUPEFILTER'), kv=KV([['优先级队列', 'DownloaderAwarePriorityQueue'], ['内存 / 磁盘队列', 'LIFO(起始请求 FIFO)'], ['无 JOBDIR', '21 个全进内存'], ['有 JOBDIR', '21 个全进磁盘']], ['有 JOBDIR'])),
    step("Request.priority 数值大的先出队:一个种子页的回调里一次性产生 12 个请求(序号:优先级),并发 1 时服务器收到的顺序是 7:10 3:10 5:5 1:5 9:1 8:1 11:0 10:0 4:0 0:0 6:-3 2:-3——先按优先级从 10 到 -3,同一优先级内后产生的先出(后进先出)。负数优先级排在最后。", t=tl(S(2)), mark=lidx(S(2), '服务器收到的顺序'), done=lidx(S(2), '产生顺序'), kv=KV([['优先级 10', '最先,且 7 在 3 前面(LIFO)'], ['优先级 0', '11 10 4 0(也是后进先出)'], ['优先级 -3', '最后']], ['优先级 10'])),
    step("同优先级内的顺序由 SCHEDULER_MEMORY_QUEUE 决定:改成 scrapy.squeues.FifoMemoryQueue,同样 12 个请求的顺序变成 3:10 7:10 1:5 5:5 8:1 9:1 0:0 4:0 10:0 11:0 2:-3 6:-3——优先级的先后不变,每档内部变成先产生先出。", t=tl(S(3)), mark=lidx(S(3), '服务器收到的顺序'), kv=KV([['LifoMemoryQueue(默认)', '同优先级后产生的先出'], ['FifoMemoryQueue', '同优先级先产生的先出'], ['优先级本身', '都是大的先出']], ['FifoMemoryQueue'])),
    step("设了 JOBDIR 后,callback 是 lambda 的请求不能序列化(pickle 要求回调是 spider 的方法):它退回内存队列,stats 里 scheduler/unserializable = 1、enqueued/memory = 1、enqueued/disk = 3(含种子)。默认日志里没有任何提示,要设 SCHEDULER_DEBUG=1 才会打 WARNING “Unable to serialize request … is not an instance method”。更要命的是出队顺序:服务器收到 mem-p-1 disk-p9 disk-p5——优先级 -1 的内存请求排在优先级 9、5 的磁盘请求之前,因为 next_request() 总是先问内存队列、空了才问磁盘队列,两个队列之间不比较优先级。", t=tl(S(4)), mark=lidx(S(4), 'mem-p-1 disk-p9', 'unserializable'), done=lidx(S(4), 'SCHEDULER_DEBUG'), kv=KV([['不可序列化的请求', '退回内存队列(scheduler/unserializable)'], ['提示', '默认无日志;SCHEDULER_DEBUG=1 才警告'], ['出队顺序', '先内存、后磁盘,优先级不跨队列比较']], ['出队顺序'])),
    step("默认的 DownloaderAwarePriorityQueue 给每个域名(下载 slot)建一个子队列,每次挑正在下载请求最少的域名出队,所以优先级只在同一个域名内有效:并发 1,域名 A 的 3 个请求优先级 0,域名 B 的 3 个请求优先级 100,服务器收到的顺序是 B2 A2 B1 A1 B0 A0——A 和 B 轮流,优先级 100 并没有让 B 的请求全排在前面;换成 ScrapyPriorityQueue,顺序是 B2 B1 B0 A2 A1 A0,全局按优先级。", t=tl(S(5)), mark=lidx(S(5), 'DownloaderAwarePriorityQueue(默认)'), done=lidx(S(5), 'ScrapyPriorityQueue'), kv=KV([['DownloaderAware(默认)', 'B2 A2 B1 A1 B0 A0:域名轮流'], ['ScrapyPriorityQueue', 'B2 B1 B0 A2 A1 A0:全局优先级'], ['含义', '默认队列下 priority 只在域名内部有效']], ['DownloaderAware(默认)'])),
    step("DownloaderAwarePriorityQueue 不支持 CONCURRENT_REQUESTS_PER_IP:设成 2 时进程直接退出码 1,抛 ValueError: \"<class 'scrapy.pqueues.DownloaderAwarePriorityQueue'>\" does not support CONCURRENT_REQUESTS_PER_IP,一个请求都没发出。要用按 IP 限制就得把 SCHEDULER_PRIORITY_QUEUE 换回 ScrapyPriorityQueue。", t=tl(S(6)), mark=lidx(S(6), 'ValueError'), done=lidx(S(6), 'CONCURRENT_REQUESTS_PER_IP=2'), kv=KV([['CONCURRENT_REQUESTS_PER_IP=2', '启动即 ValueError,退出码 1'], ['已发请求', '0 个'], ['解决', '换回 ScrapyPriorityQueue']], ['CONCURRENT_REQUESTS_PER_IP=2'])),
]
A = mkarts('s8', 8, 'Scrapy,调度器,队列,优先级,JOBDIR,DownloaderAwarePriorityQueue,真实验证,动画演示',
    '实测 Scrapy 2.19 的调度队列:有 JOBDIR 时 21 个请求全进磁盘队列;priority 大的先出、同优先级默认后进先出;不可序列化的请求退回内存队列(默认无日志)并因“内存先于磁盘”打乱优先级;默认的 DownloaderAwarePriorityQueue 让优先级只在域名内有效,且与 CONCURRENT_REQUESTS_PER_IP 冲突。',
    '请求在调度器里排成什么队、先出哪个?这篇把内存队列、磁盘队列和优先级队列一层层拆开:priority 怎么排序、同优先级怎么出、JOBDIR 里装不下的请求去哪了,以及 2.19 默认换成的 DownloaderAwarePriorityQueue 对优先级的影响。',
    [('21 → 0', '设了 JOBDIR 之后 21 个请求中进内存队列的个数(全部进磁盘)'), ('B2 A2 B1 A1…', '默认优先级队列在 A(0)、B(100) 两个域名间的出队顺序(轮流)'), ('0 条', '不可序列化的请求在默认日志里的提示(SCHEDULER_DEBUG=1 才有)')],
    [('默认配置', '<p>调度器由三层组成:优先级队列(2.19 默认 <code>DownloaderAwarePriorityQueue</code>)管优先级和域名,内存/磁盘队列(默认后进先出)管同优先级内的顺序,起始请求另用先进先出的队列。</p>'),
     ('priority', '<p><code>Request.priority</code> 越大越先出队,同优先级内由内存队列的类型决定顺序。</p>'),
     ('改变同优先级顺序', '<p>把 <code>SCHEDULER_MEMORY_QUEUE</code>(和磁盘队列)换成 FIFO 版本即可。</p>'),
     ('JOBDIR 与不可序列化请求', '<p>启用 <code>JOBDIR</code> 后请求先尝试进磁盘队列,失败(比如回调是 lambda)才退回内存队列;出队时先内存后磁盘,两者之间不比较优先级。</p>'),
     ('按域名分队', '<p><code>DownloaderAwarePriorityQueue</code> 每个域名一个子队列,选下载中请求最少的域名出队;优先级只在域名内部起作用。</p>'),
     ('与按 IP 限制冲突', '<p>它不支持 <code>CONCURRENT_REQUESTS_PER_IP</code>,设了就在启动时抛 <code>ValueError</code>。</p>')],
    steps,
    [ENV_Y + '。并发 1 时,由一个种子页的回调一次性产生所有请求,保证它们同时在队列里再按调度器规则出队;服务器记录收到请求的顺序;第五节用 127.0.0.1 与 localhost 当作两个域名',
     '没有验证:磁盘队列的文件格式与大小(见 JOBDIR 那篇);真实多域名爬取下 DownloaderAwarePriorityQueue 对吞吐的影响(本机一个服务器,看不出差别);优先级队列对 start 请求的细节(只在上一篇用顺序验证过);自定义 Scheduler 子类;MarshalFifoDiskQueue 等其它磁盘队列类的差别'],
    '调度队列')
