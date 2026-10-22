from lib import *
S = SS('v63')
steps = [
    step("时钟偏移。调用方进程时钟正常,下游进程的 SDK 时钟加上固定偏移(模拟机器时钟不同步),每种偏移 100 个请求。时钟同步:下游 span 比父 span 先开始的 0 个、后结束的 0 个,表观网络耗时(下游开始 − 调用方开始)中位数 0.93 ms。下游快 5 ms:后结束的 100 个,表观网络耗时 5.97 ms;快 20 ms:100 个,20.36 ms;快 100 ms:100 个,100.45 ms。下游慢 5 ms:先开始的 99 个,表观网络耗时 −4.66 ms;慢 20 ms:99 个,−18.96 ms。父子关系(parent_id)不受时钟影响,变的是时间轴上的位置。", t=tl(S(1)), mark=lidx(S(1), '-5 ms', '-20 ms', '+100 ms'), done=lidx(S(1), '0(同步)', '+5 ms', '+20 ms'), b=bars([['同步:表观网络耗时 ms', 0.93, '0.93'], ['快 20 ms:表观网络耗时 ms', 20.36, '20.36'], ['快 100 ms:表观网络耗时 ms', 100.45, '100.45'], ['慢 20 ms:子比父先开始的请求', 99, '99 / 100']], 101, done=[0], mark=[1, 2, 3]), kv=KV([['下游快', '子 span 比父 span 后结束(100 / 100)'], ['下游慢', '子 span 比父 span 先开始(99 / 100)'], ['parent_id', '不受时钟影响']], ['下游慢'])),
    step("忘记 detach 造成串线。只有 1 个线程的线程池处理 6 个请求,每个请求先 attach 一个带新根 span 的请求上下文。正确 detach:本该是根 span 却带着父 span 的请求有 0 个,6 个请求出现 6 个 trace。忘记 detach:5 个请求的根 span 带着父 span(父是上一个请求),6 个互不相干的请求并成了 1 个 trace。", t=tl(S(2)), mark=lidx(S(2), '(b)忘记'), done=lidx(S(2), '(a)正确'), b=bars([['正确 detach:trace 数', 6, '6'], ['忘记 detach:trace 数', 1, '1'], ['忘记 detach:带父 span 的根', 5, '5 / 6']], 6, done=[0], mark=[1, 2]), kv=KV([['正确 detach', '6 个请求 6 个 trace'], ['忘记 detach', '5 个请求的根 span 挂在上一个请求下面,并成 1 个 trace']], ['忘记 detach'])),
    step("异步任务比父 span 活得久。请求里 fire-and-forget 起一个 200 ms 的后台任务,请求自己约 10 ms 就结束。request span 15.2 ms;background span 是 request 的子 span,耗时 207.4 ms,比 request 晚结束 192.4 ms。按根 span 的耗时统计,这次请求是 15.2 ms;按 trace 里最晚的 span 结束时间减最早的开始时间统计是 207.6 ms,两者之比 13.6 倍。", t=tl(S(3)), mark=lidx(S(3), 'request span'), done=lidx(S(3), 'request span'), b=bars([['根 span 耗时 ms', 15.2, '15.2'], ['background span 耗时 ms', 207.4, '207.4'], ['整个 trace 的跨度 ms', 207.6, '207.6']], 210, mark=[0], done=[1, 2]), kv=KV([['根 span', '15.2 ms'], ['整个 trace 的跨度', '207.6 ms'], ['background', '是 request 的子 span,晚结束 192.4 ms']], ['整个 trace 的跨度'])),
    step("导出时丢了 span。每个 trace 5 个 span(根 → 2 个中间 → 各 1 个叶子),2000 个 trace,导出器随机丢弃 span。丢弃概率 0%:2000 个完整。1%:完整 1893 个,有孤儿 span(父 span 丢了)的 66 个,只丢了叶子的 41 个。5%:完整 1529、有孤儿 289、只丢叶子 182。20%:完整 634、有孤儿 886、只丢叶子 479;另有 1 个 trace 一个 span 都没收到。丢弃概率是按 span 算的,一个 trace 5 个 span,完整的比例比 1 减去丢弃概率低得多。", t=tl(S(4)), mark=lidx(S(4), '20%', '5%'), done=lidx(S(4), '0%  ', '1%  '), b=bars([['1%:完整的 trace', 1893, '1893 / 2000'], ['5%:完整的 trace', 1529, '1529 / 2000'], ['20%:完整的 trace', 634, '634 / 2000'], ['20%:有孤儿的 trace', 886, '886 / 2000']], 2000, done=[0], mark=[1, 2, 3]), kv=KV([['丢 1% 的 span', '1893 完整,66 有孤儿'], ['丢 5%', '1529 完整,289 有孤儿'], ['丢 20%', '634 完整,886 有孤儿']], ['丢 20%'])),
]
A = mkartv('v63', 63, '微服务,可观测性,链路追踪,时钟偏移,span,真实验证,动画演示',
    '实测 span 树错乱的原因:下游时钟快或慢 20 ms,子 span 就在 100 / 100 个请求里晚结束、或在 99 / 100 个请求里比父 span 先开始;忘记 detach 让 6 个请求并成 1 个 trace;后台任务让整个 trace 的跨度(207.6 ms)是根 span 耗时(15.2 ms)的 13.6 倍;每个 span 丢 5% 时只有 1529 / 2000 个 trace 完整。',
    'trace 的瀑布图为什么会出现子 span 比父 span 先开始?为什么一个请求的耗时在不同地方不一样?为什么多个请求被并进同一个 trace?丢一点 span 会让多少 trace 残缺?这篇用 OpenTelemetry Python SDK 逐项复现。',
    [('99 / 100', '下游时钟比调用方慢 20 ms 时,子 span 比父 span 先开始的请求数(下游快 20 ms 时是 100 / 100 个比父 span 晚结束)'), ('1 个 trace', '线程池里忘记 detach 时,6 个互不相干的请求一共出现的 trace 数(正确 detach 是 6 个)'), ('1529 / 2000', '每个 span 被丢弃概率为 5% 时,5 个 span 的 trace 里完整的个数')],
    [('时钟偏移', '<p>父子关系由 parent_id 决定,不受时钟影响,但时间轴上的位置、表观网络耗时都会错位。</p>'),
     ('忘记 detach', '<p>线程池线程复用,没 detach 的上下文留在线程里,后面的请求都挂到它下面。</p>'),
     ('异步任务', '<p>后台任务比父 span 活得久,根 span 的耗时和整个 trace 的跨度差很多。</p>'),
     ('丢 span', '<p>丢掉非叶子 span 会产生孤儿 span;完整的 trace 比例按 span 数的幂次下降。</p>')],
    steps,
    [ENV_V + '。OpenTelemetry Python SDK 1.45.1;时钟偏移是把下游进程里 opentelemetry.sdk.trace.time_ns 加上固定偏移得到的(不是真的两台机器,也没有用 NTP 或抖动);随机丢弃用固定种子的伪随机数,每个概率只跑了一次;线程池实验只有 1 个线程',
     '没有验证:追踪后端(Jaeger、Tempo 等)对时钟偏移的校正功能,以及它们怎么显示孤儿 span;真实机器之间时钟偏差的典型大小和 NTP 的精度;异步任务里 span 结束时机的正确写法(例如 link 代替 parent);Java / Go SDK 里同类的串线问题'],
    'span 树与时钟')
