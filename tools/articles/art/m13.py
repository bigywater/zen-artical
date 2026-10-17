from lib import *
S = SS('m13')
steps = [
    step("expireAfterSeconds=5 的 TTL 索引,100 个文档插入时 createdAt = 当前时间。文档在 5 秒时就已过期,但直到 59.0 秒才一次性消失;TTL 后台线程运行时刻是 59.0 s 和 119.2 s,相隔 60.2 s。getParameter 确认 ttlMonitorSleepSecs 默认是 60。", t=tl(S(1)), mark=lidx(S(1), '59.0, 0', '[59.0, 119.2]', '实际在 59.0 s'), done=lidx(S(1), 'ttlMonitorSleepSecs: 60', '已插入 100 个文档'), b=bars([['过期时间', 5, '5 s'], ['实际删除', 59, '59.0 s(第一次 TTL 线程运行)']], 59, mark=[1], done=[0]), kv=KV([['TTL 线程', '每 60 s 运行一次'], ['过期', '5 s 就已经“可以删”'], ['实际被删', '59.0 s 第一次运行时']], ['TTL 线程'])),
    step("哪些文档会被删(监控间隔调到 1 秒):一小时前的 BSON 日期、一小时前日期在内的日期数组(最小的那个已过期)都被删掉;留下的是 iso 格式的字符串日期、毫秒整数、null、缺失字段、日期数组里两个都没过期的、未来的日期。TTL 只认 BSON 日期类型(或日期数组)。", t=tl(S(2)), mark=lidx(S(2), '还留下'), done=lidx(S(2), 'was: 60'), kv=KV([['BSON 日期', '到期被删'], ['日期数组', '最早的日期到期就删'], ['字符串 / 数字 / null / 缺失', '永远不过期']], ['BSON 日期'])),
    step("expireAfterSeconds=0 加未来时间:三个文档的 expireAt 分别是 +3 s、+6 s、+9 s,剩余文档数在 3.1 s 变成 2、6.1 s 变成 1、9.2 s 变成 0——每个文档到自己指定的时刻才被删(监控间隔 1 秒)。", t=tl(S(3)), mark=lidx(S(3), '(3.1, 2)', '(9.2, 0)'), done=lidx(S(3), '三个文档'), kv=KV([['expireAfterSeconds: 0', '字段值就是过期时刻'], ['用途', '每个文档自己定过期时间']], ['expireAfterSeconds: 0'])),
    step("collMod 在线改 TTL:先建成 expireAfterSeconds=3600,20 个 30 秒前创建的文档 3 秒后还在;collMod 把它改成 2,返回 expireAfterSeconds_old: 3600、expireAfterSeconds_new: 2;再等 3.5 秒文档全部被删(剩 0 个)。getIndexes 里 c_1 的 expireAfterSeconds 已是 2。", t=tl(S(4)), mark=lidx(S(4), 'expireAfterSeconds_new: 2', '剩 0 个'), done=lidx(S(4), 'expireAfterSeconds=3600', 'expireAfterSeconds: 2'), kv=KV([['collMod', '直接修改已有 TTL 索引'], ['已有文档', '立刻按新规则判断'], ['不需要重建索引', '']], ['collMod'])),
    step("serverStatus().metrics.ttl 记录 TTL 线程的统计:passes、deletedDocuments、deletedKeys、examinedDocuments、durationMicros 等(这里 passes 28、deletedDocuments 125);ttlMonitorSleepSecs 是运行时用 setParameter 改的,重启之后又回到 60。", t=tl(S(5)), mark=lidx(S(5), 'passes', 'deletedDocuments', 'ttlMonitorSleepSecs: 60'), done=lidx(S(5), 'durationMicros', 'examinedDocuments'), kv=KV([['metrics.ttl', 'passes / deletedDocuments / …'], ['setParameter', '运行时可改,重启不保留']], ['metrics.ttl'])),
    step("一次过期很多:20 万个文档同时过期(监控间隔 1 秒),0.5 s 时还有 200,000,1.6 s 时已是 0;TTL 线程只运行了 1 轮就删除了 200,000 个文档。(文档很小,没有观察到分批。)", t=tl(S(6)), mark=lidx(S(6), '(1.6, 0)', 'TTL 线程运行了'), done=lidx(S(6), '(0.5, 200000)'), kv=KV([['200,000 个文档', '1 轮、约 1.6 s 内删完'], ['注意', '文档小;大文档或有很多索引时会更慢(未测)']], ['200,000 个文档'])),
]
A = mkartm('m13', 13, 'MongoDB,TTL索引,过期,ttlMonitorSleepSecs,collMod,真实验证,动画演示',
    '实测 TTL 索引的过期时机:5 秒过期的文档要等到每 60 秒运行一次的 TTL 线程(实测 59.0 s 和 119.2 s)才被删;只有 BSON 日期(或日期数组)会过期;expireAfterSeconds 为 0 配合未来时间可让每个文档自己定过期时刻;collMod 在线改过期时间;20 万个过期文档一轮删完。',
    'TTL 索引说“过期时间到了就删”,实际什么时候才真的删?哪些类型的字段会被它删?这篇用 5 秒过期的索引观察实际删除的时刻,再验证字段类型、collMod 和大批量过期。',
    [('59.0 s', '5 秒过期的文档实际被删的时刻——等到第一次 TTL 线程运行'), ('60.2 s', 'TTL 线程两次运行相隔的时间(ttlMonitorSleepSecs 默认 60)'), ('200,000', '一轮 TTL 删除的文档数(文档很小)')],
    [('什么时候删', '<p>TTL 索引不是定时器,而是后台线程每 <code>ttlMonitorSleepSecs</code>(默认 60 秒)扫描一轮。5 秒过期的文档等到第一轮运行(59.0 s)才被删,第二轮在 119.2 s。</p>'),
     ('哪些字段', '<p>只有 BSON 日期(以及日期数组)会过期;字符串形式的日期、毫秒整数、null、缺失字段都不会。日期数组里最早的日期到期,文档就会被删。</p>'),
     ('按文档指定过期时间', '<p><code>expireAfterSeconds: 0</code> 配合一个存着过期时刻的字段,每个文档在自己指定的时刻之后才会被删。</p>'),
     ('collMod', '<p>用 <code>collMod</code> 的 <code>index</code> 选项可以直接修改已有 TTL 索引的 <code>expireAfterSeconds</code>,已有文档立即按新规则判断。</p>'),
     ('统计', '<p><code>serverStatus().metrics.ttl</code> 给出 TTL 线程运行了多少轮、删了多少文档;<code>ttlMonitorSleepSecs</code> 可以运行时用 <code>setParameter</code> 调整,重启后恢复默认。</p>'),
     ('大批量', '<p>20 万个小文档同时过期,一轮就删完了(约 1.6 s,含统计间隔)。</p>')],
    steps,
    [ENV_M + '。TTL 线程的运行时刻是每 0.25 秒轮询 serverStatus().metrics.ttl.passes 得到的,精度约 0.25 s;为观察方便,后面几节把 ttlMonitorSleepSecs 调成 1 秒',
     '没有验证:副本集上 secondary 如何复制 TTL 删除(由 primary 执行);大文档或多索引集合上 TTL 删除对前台写入的影响;时序集合与分片集合上的 TTL;expireAfterSeconds 极大值的上限;TTL 线程在 primary 降级时的行为;删除发生时锁与 ticket 的占用'],
    'TTL 索引')
