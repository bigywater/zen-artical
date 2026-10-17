from lib import *
S = SS('s38')
steps = [
    step("JOBDIR 的内容:并发 2、40 个页面每个 0.1 s,启动 1.5 秒后按一次 Ctrl-C(SIGINT):优雅停止,finish_reason = shutdown,这次下载了 18 个页面(加起始页),scheduler 入队 41、出队 19,还有 22 个请求留在磁盘队列里。JOBDIR 里留下:requests.queue/<域名-哈希>/0/q00000(10,510 字节,磁盘队列文件,存着剩下的请求)和 info.json(73 字节)、requests.queue/active.json(18 字节,记录每个槽的优先级状态)、requests.seen(902 字节 = 41 个指纹 × 22 字节)、spider.state(135 字节)。", t=tl(S(1)), mark=lidx(S(1), 'q00000', 'active.json', 'requests.seen', 'spider.state'), done=lidx(S(1), 'finish_reason=shutdown'), kv=KV([['requests.queue/', '磁盘队列:剩下的请求(10,510 字节)'], ['active.json', '队列的优先级状态'], ['requests.seen', '去重指纹:41 × 22 = 902 字节'], ['spider.state', 'self.state 的 pickle']], ['requests.queue/'])),
    step("第 2 次运行用同一个 JOBDIR 接着跑:finish_reason = finished,下载了剩下的 22 个页面,没有一个重复(两次合计 40 次请求、40 个不同页面、重叠 0 个);起始页没有重发——我自己写的 start() 里的 Request 没带 dont_filter,在 requests.seen 里已经有了,被过滤(dupefilter/filtered = 1)。结束后 requests.queue 里只剩 2 字节的 active.json,requests.seen 仍是 902 字节,spider.state 长到 267 字节。", t=tl(S(2)), mark=lidx(S(2), '第 2 次', '两次合计'), kv=KV([['续跑', '只取磁盘队列里剩下的请求'], ['重叠页面', '0 个(不重复抓)'], ['起始页', '自己写的 start() 被去重过滤'], ['队列文件', '抓完后清空']], ['续跑'])),
    step("self.state 是一个字典,JOBDIR 里的 spider.state 把它 pickle 起来,两次运行之间保留:第 1 次 page 回调 18 次、第 2 次 22 次,最后 spider.state 里 count = 40、urls 列表有 40 个元素——计数是累加的,不是重新开始的。", t=tl(S(3)), mark=lidx(S(3), 'spider.state'), kv=KV([['self.state', '字典,存放在 spider.state 文件'], ['两次运行', '累加:18 + 22 = 40'], ['限制', '值必须能 pickle']], ['self.state'])),
    step("已经抓完的 JOBDIR 再跑:我自己写的 start() 里的起始请求被 requests.seen 过滤,服务器收到 0 个请求(dupefilter/filtered = 1);换成默认的 start_urls 写法(自带 dont_filter = True)则起始页重发,服务器收到 1 个请求 /,起始页上 40 个子链接全被过滤(dupefilter/filtered = 40)。想“定期重新开始”要让起始请求带 dont_filter,并清掉 requests.seen。", t=tl(S(4)), mark=lidx(S(4), '第 3 次', '第 4 次'), kv=KV([['自己写的 start()', '起始请求被过滤,0 个请求'], ['默认 start_urls', '起始页重发,子链接全过滤'], ['dont_filter', '决定起始请求在续跑时是否重发']], ['dont_filter'])),
    step("kill -9 中途杀掉:没有机会优雅关闭。JOBDIR 里只有 requests.queue/…/q00000(10,510 字节)和 0 字节的 requests.seen(指纹还在缓冲区里没落盘),没有 active.json 也没有 spider.state。恢复时等于从头开始:又下载了 40 个页面,和 kill 前下载的 22 个重叠 22 个,没丢页面(不同页面共 40 个),但重复抓了 22 个。优雅停止(一次 SIGINT)才保证状态写全。", t=tl(S(5)), mark=lidx(S(5), 'requests.seen', 'kill -9 前下载了'), kv=KV([['kill -9 后的 JOBDIR', 'seen 为 0 字节,没有 active.json、spider.state'], ['恢复', '等于重头开始'], ['代价', '重复抓了 22 个页面,没丢页面']], ['kill -9 后的 JOBDIR'])),
    step("请求不能序列化时:meta 里放 threading.Lock(),40 个子请求全部 pickle 失败,scheduler/unserializable = 40、enqueued/memory = 40(只有起始页进了磁盘,enqueued/disk = 1)。Ctrl-C 中断后恢复:第 1 次下载了 16 个页面,恢复后下载 0 个——内存队列里没落盘的 24 个请求随进程消失,而它们的指纹已经写进了 requests.seen,所以永远不会再被抓到。默认日志里只有一条 stats,很容易漏掉。", t=tl(S(6)), mark=lidx(S(6), 'unserializable', '恢复后又下载 0 个'), kv=KV([['meta 里有不能 pickle 的对象', '请求退回内存队列'], ['中断后', '内存队列里的请求丢失'], ['指纹', '已进 requests.seen,不会再抓'], ['发现方式', 'scheduler/unserializable 统计']], ['meta 里有不能 pickle 的对象'])),
]
A = mkarts('s38', 38, 'Scrapy,JOBDIR,暂停恢复,requests.queue,requests.seen,spider.state,真实验证,动画演示',
    '实测 JOBDIR:Ctrl-C 后留下 requests.queue/ 磁盘队列、active.json、requests.seen(41 × 22 字节)、spider.state;续跑 22 个页面零重复,self.state 累加(18 + 22 = 40);自己写的 start() 起始请求在续跑时被去重,默认 start_urls 会重发;kill -9 会丢掉 requests.seen 内容,恢复等于重头抓(重叠 22 个);meta 里放不能 pickle 的对象会让 24 个请求在中断时永久丢失。',
    '给爬虫加 JOBDIR 就能暂停和恢复,可是磁盘上到底存了什么?续跑会不会重复或遗漏?kill -9 呢?起始请求会不会重发?请求里有不能序列化的东西又怎样?这篇把每种中断方式都做一遍,数清楚丢了多少、重了多少。',
    [('0 个', 'Ctrl-C 后续跑,两次运行重叠的页面数(40 个页面一个不重复)'), ('0 字节', 'kill -9 后 requests.seen 的大小(指纹还在缓冲区)'), ('24 个', 'meta 里放不能 pickle 的对象,中断后永久丢失的请求数(40 个里只下载了 16 个)')],
    [('JOBDIR 里有什么', '<p><code>requests.queue/</code> 存磁盘队列,<code>active.json</code> 记录队列状态,<code>requests.seen</code> 是已见请求的指纹(每个 22 字节),<code>spider.state</code> 是 <code>self.state</code> 的 pickle。</p>'),
     ('续跑', '<p>优雅停止(一次 Ctrl-C)后用同一个 JOBDIR 再运行,只处理磁盘队列里剩下的请求,不重复已完成的页面,<code>self.state</code> 的内容继续累加。</p>'),
     ('state', '<p><code>self.state</code> 里的值必须能 pickle,适合存计数、游标等。</p>'),
     ('起始请求', '<p>自己写 <code>start()</code> 且不加 <code>dont_filter</code> 时,续跑里起始请求被 <code>requests.seen</code> 过滤;默认 <code>start_urls</code> 自带 <code>dont_filter=True</code>,会重发。</p>'),
     ('强制杀死', '<p>kill -9 不会写 <code>requests.seen</code> 和 <code>spider.state</code>,恢复等于重头开始,重复抓取但不会丢页面。</p>'),
     ('不能序列化的请求', '<p>请求(含 meta、回调)不能 pickle 时只进内存队列,中断即丢,指纹却已入库,这些页面不会再被抓。</p>')],
    steps,
    [ENV_Y + '。站点 40 个页面各 0.1 s,并发 2,先进先出的内存与磁盘队列;用 subprocess.Popen 启动 scrapy runspider,1.5 秒后发 SIGINT 或 SIGKILL;文件大小来自 JOBDIR 目录列表。每次运行的页面数有几个的抖动(18 或 22 取决于发信号的时机)',
     '没有验证:JOBDIR 与 DownloaderAwarePriorityQueue 的多槽子目录(这里只有一个槽);Windows 上的信号;二次 Ctrl-C 强制退出时的状态;requests.seen 的 flush 时机(只看到 kill -9 时是 0 字节,没有读缓冲策略的源码);JOBDIR 里的 spider.state 与多进程同时使用同一个 JOBDIR 的冲突;大规模(百万请求)磁盘队列的体积'],
    '暂停与恢复')
