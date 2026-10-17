from lib import *
S = SS('k90')
F1 = [['Add 100 次同一个 key + 1 个别的', 'Len()=2'], ['Get web', '处理中'], ['处理中再 Add web', 'Len()=0(dirty)'], ['Done(web)', 'Len()=1']]
F2 = [['4 个 worker', ''], ['不停 Add hot-key', ''], ['367 次处理', ''], ['同一 key 同时最多', '1'], ['不同 key 同时最多', '4']]
F3 = [['失败 1~12 次', '5ms,10ms,…,10.24s'], ['Forget', '重置,5ms'], ['单纯指数退避', '第 20 次起封顶 1000s'], ['不同 key', '互不影响']]
F4 = [['AddRateLimited ×3', '50ms / 102ms / 202ms'], ['NumRequeues', '3'], ['AddAfter(200ms)', '阻塞 200ms'], ['Forget', '清零']]
PANELS = [('f', 'flow', 'workqueue'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("对同一个 key default/web 连续 Add 100 次、再 Add 一个 default/db:队列长度 Len()=2,重复的被合并;依次取出 default/web、default/db 后 Len()=0。default/web 还在处理(没有调用 Done)时再 Add:Len()=0,不会马上入队,先记为 dirty;调用 Done 之后 Len()=1,之前的 Add 此刻才进入队列。", f=fl(F1, cur=[0, 2], done=[1, 3]), t=tl(S(1), mark=lidx(S(1), '入队 101 次', '还在处理中'), done=lidx(S(1), '调用 Done 之后')), kv=KV([['去重', '同一个 key 在队列里只有一份'], ['处理中再来', '先记 dirty,Done 之后重新入队'], ['key 而不是对象', '队列里放的是 namespace/name,处理时再读缓存']], ['去重'])),
    step("4 个 worker 在 0.5 秒里不停地 Add \"hot-key\" 和另外 3 个 key:共处理 367 次,同一个 key 同时被处理的最大个数是 1(绝不会被两个 worker 同时处理),不同 key 之间同时被处理的最大个数是 4(并行)。", f=fl(F2, cur=[2], done=[3, 4]), t=tl(S(2), done=lidx(S(2), '共处理')), kv=KV([['串行保证', '同一个 key 同一时刻只有一个 worker'], ['并行', '不同 key 可同时处理'], ['控制器可放心', '同一个对象的 reconcile 不会并发']], ['串行保证'])),
    step("DefaultControllerRateLimiter 对同一个 key 连续失败 12 次的等待时间:5ms、10ms、20ms、40ms、80ms、160ms、320ms、640ms、1.28s、2.56s、5.12s、10.24s(每次翻倍),NumRequeues=12;Forget 之后再失败一次又回到 5ms。单纯的指数退避(5ms 起、上限 1000s):第 10 次 2.56s,第 20 次和第 30 次都是 16m40s(封顶)。不同 key 互不影响:5 个新 key 的第一次都是 5ms。", f=fl(F3, cur=[0, 2], done=[1, 3]), t=tl(S(3), mark=lidx(S(3), 'DefaultControllerRateLimiter', '单纯的指数退避'), done=lidx(S(3), 'Forget 之后', '不同 key 互不影响')), kv=KV([['每个 key 单独计数', '失败越多等越久'], ['Forget', '成功后调用,把计数清零'], ['封顶', '上限 1000s,避免无限变长']], ['每个 key 单独计数'])),
    step("基础延迟 50ms 的限速队列:对同一个 key 第 1/2/3 次 AddRateLimited 后 Get 分别阻塞了 50ms / 102ms / 202ms(翻倍),NumRequeues=3;AddAfter(200ms) 后 Get 阻塞了 200ms 才拿到;对 key 调用 Forget 之后 NumRequeues=0。", f=fl(F4, cur=[0, 2], done=[1, 3]), t=tl(S(4), done=lidx(S(4), '基础延迟 50ms', 'AddAfter')), kv=KV([['AddRateLimited', '按限速器给出的延迟再入队'], ['AddAfter', '固定延迟入队'], ['Forget', '重置该 key 的失败计数']], ['AddRateLimited'])),
]
A = mkartk('k90', 90, 'Kubernetes,client-go,workqueue,限速,重试,控制器,真实验证,动画演示',
    '用 client-go v0.36.1 的 workqueue 包做小实验:对同一个 key Add 100 次队列长度只有 1,处理中再 Add 先记为 dirty、Done 之后才重新入队;4 个 worker 绝不会同时处理同一个 key,不同 key 最多并行 4 个;DefaultControllerRateLimiter 对同一个 key 的失败重试按 5ms 翻倍(12 次到 10.24s),Forget 后重置;AddRateLimited 的延迟 50 / 102 / 202ms,AddAfter 精确延迟。',
    '控制器里反复入队同一个对象会不会处理很多次?两个 worker 会不会同时处理同一个对象?失败了多久后重试,一直失败会怎样?这篇用 workqueue 包写 60 行代码,把去重、串行、退避的数字逐个打出来。',
    [('Len()=2', '对同一个 key Add 100 次再加一个别的 key 后的队列长度'), ('同 key 最多 1', '4 个 worker 并发处理时,同一个 key 同时被处理的最大个数'), ('5ms × 2ⁿ', '默认控制器限速器对同一个 key 失败重试的等待时间(12 次到 10.24s)')],
    [('去重与 dirty', '<p>对同一个 key <code>default/web</code> 连续 <code>Add</code> 100 次,再 <code>Add</code> 一个 <code>default/db</code>:队列长度 <code>Len()=2</code>,重复的被合并;取出后 <code>Len()=0</code>。<code>default/web</code> 还在处理(没有 <code>Done</code>)时再 <code>Add</code>:<code>Len()</code> 仍是 0,先记为 dirty;调用 <code>Done</code> 之后 <code>Len()=1</code>,之前的 <code>Add</code> 此刻才进入队列。所以控制器队列里放的是 key(namespace/name),不是对象,处理时再去读缓存拿最新值。</p>'),
     ('同一个 key 串行', '<p>4 个 worker 在 0.5 秒里不停地 <code>Add</code> "hot-key" 和另外 3 个 key:共处理 367 次,同一个 key 同时被处理的最大个数是 1,不同 key 同时被处理的最大个数是 4。控制器因此可以放心写 reconcile:同一个对象不会并发被处理,不同对象可以并行。</p>'),
     ('退避', '<p><code>DefaultControllerRateLimiter</code> 对同一个 key 连续失败 12 次的等待时间是 5ms、10ms、20ms、40ms、80ms、160ms、320ms、640ms、1.28s、2.56s、5.12s、10.24s(每次翻倍),<code>NumRequeues=12</code>;成功后调 <code>Forget</code> 把计数清零,下一次失败又回到 5ms。单纯的指数退避(5ms 起、上限 1000s):第 10 次 2.56s,第 20 次和第 30 次都是 16m40s,已经封顶。不同 key 各自计数,互不影响。</p>'),
     ('延迟入队', '<p>基础延迟 50ms 的限速队列:对同一个 key 第 1/2/3 次 <code>AddRateLimited</code> 后 <code>Get</code> 分别阻塞了 50ms / 102ms / 202ms,<code>NumRequeues=3</code>;<code>AddAfter(200ms)</code> 精确延迟 200ms;<code>Forget</code> 之后 <code>NumRequeues=0</code>。</p>')],
    steps,
    [ENV_K + '。本机 Go 1.27.1 + k8s.io/client-go v0.36.1 的 workqueue 包(Typed 版本),程序在 tools/articles/ktmp/workq/main.go,不需要 Kubernetes 集群;时间由 time.Since 测得,数字略有抖动(例如 102ms / 202ms 会在 ±3ms 范围内);并发实验的 367 次处理数在多次运行中会有变化;每种情形各一次',
     '没有验证:DefaultControllerRateLimiter 里的令牌桶(10 qps、100 burst)与指数退避取最大值的行为;ItemFastSlowRateLimiter;MaxOf 组合限速器;队列的 metrics(depth、adds、latency);ShutDownWithDrain;在真实控制器里 informer 事件回调如何入队'],
    'workqueue', PANELS)
