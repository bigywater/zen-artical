from lib import *
S = SS('m54')
steps = [
    step("10 万个文档(每个约 230 字节)的默认 find:共 3 条命令(1 个 find + 2 个 getMore),第一批 101 个,之后的 getMore 每批是 70,538 个和 29,361 个——后续批次按 16 MiB 的大小上限装,不是固定个数;总共读到 100,000 个。", t=tl(S(1)), mark=lidx(S(1), '[70538, 29361]'), done=lidx(S(1), '第一批 101 个', '总共读到 100,000'), kv=KV([['第一批', '101 个'], ['后续批次', '最多约 16 MiB(这里 70,538 个)'], ['命令数', '1 个 find + 2 个 getMore']], ['第一批'])),
    step("batch_size 越小往返越多:读完 10 万个文档(去掉 pad 字段,5 次中位数)batch_size=10 要 10,001 条命令、944 ms;100 要 1,001 条、140 ms;1,000 要 101 条、62 ms;10,000 要 11 条、54 ms;默认 3 条、55 ms。", t=tl(S(2)), mark=lidx(S(2), '            10', '           100'), done=lidx(S(2), '          1000', '         10000', '默认'), b=bars([['batch_size 10', 10001, '10,001 条 / 944 ms'], ['100', 1001, '1,001 条 / 140 ms'], ['1,000', 101, '101 条 / 62 ms'], ['默认', 3, '3 条 / 55 ms']], 10001, mark=[0, 1], done=[2, 3]), kv=KV([['batch_size 10', '往返 10,001 次,944 ms'], ['默认', '3 次,55 ms'], ['原则', '批太小白白增加往返']], ['原则'])),
    step("没读完的游标占着服务端资源:serverStatus().metrics.cursor.open.total 读之前是 0,开了一个游标只读第一条后是 1,cur.close() 之后回到 0。", t=tl(S(3)), mark=lidx(S(3), "total: Long('1')"), done=lidx(S(3), "total: Long('0')"), kv=KV([['没读完的游标', 'open.total = 1'], ['close()', '释放,回到 0']], ['没读完的游标'])),
    step("游标空闲超时:cursorTimeoutMillis 默认 600000(10 分钟),为观察调到 3000。用不带会话的 OP_MSG 开 5 个游标,各自只在一个空闲时间点 getMore 一次:空闲 2.0 s 成功;空闲 5.0 s、8.0 s、12.0 s、20.0 s 都失败,code=43(CursorNotFound)——超过超时后被后台回收。对照:pymongo 的游标绑定在隐式会话上,空闲 15 秒后仍可继续读(由会话超时管理,默认 30 分钟)。", t=tl(S(4)), mark=lidx(S(4), 'code=43', '空闲  5.0 s'), done=lidx(S(4), '空闲  2.0 s', '会话超时管理'), b=bars([['空闲 2 s', 2, '成功'], ['空闲 5 s', 5, 'CursorNotFound'], ['空闲 20 s', 20, 'CursorNotFound'], ['会话里的游标 15 s', 15, '仍可读']], 20, mark=[1, 2], done=[0, 3]), kv=KV([['cursorTimeoutMillis', '默认 10 分钟'], ['不带会话的游标', '空闲超时被回收,code 43'], ['会话里的游标', '由会话超时(30 分钟)管理']], ['cursorTimeoutMillis'])),
    step("noCursorTimeout:no_cursor_timeout=True 的游标空闲 8 秒(超过 3 秒的游标超时)后仍可继续读;serverStatus 里 noTimeout 为 1、total 为 1;关闭游标后把 cursorTimeoutMillis 改回 600000(was 是 3000)。这种游标要自己 close,否则一直占着。", t=tl(S(5)), mark=lidx(S(5), 'noTimeout: Long'), done=lidx(S(5), '仍可继续读', 'was'), kv=KV([['noCursorTimeout', '不会被超时回收'], ['代价', '必须自己 close']], ['noCursorTimeout'])),
    step("游标不是快照:按 k 排序遍历 20,000 个文档时,另一个线程把已经读过的文档的 k 改大,共读到 21,500 个,其中同一个 _id 重复出现 1,500 次(不同 _id 仍是 20,000 个)——被改到后面的文档又被读了一遍。", t=tl(S(6)), mark=lidx(S(6), '重复出现 1,500 次'), done=lidx(S(6), '共读到 21,500 个'), b=bars([['文档数', 20000, '20,000'], ['读到的次数', 21500, '21,500']], 21500, mark=[1], done=[0]), kv=KV([['遍历期间的修改', '游标看得到'], ['结果', '同一个文档可能读到两次'], ['要一致', '用 snapshot 读关注或事务']], ['结果'])),
]
A = mkartm('m54', 54, 'MongoDB,游标,batchSize,getMore,cursorTimeoutMillis,noCursorTimeout,真实验证,动画演示',
    '实测游标:第一批 101 个、后续批次按 16 MiB 装(70,538 个);batch_size=10 读 10 万个文档要 10,001 条命令 944 ms,默认 3 条 54 ms;不带会话的游标空闲超时被回收(code 43),会话里的游标不受影响,noCursorTimeout 不会超时;遍历期间被修改的文档会被重复读到(1,500 次)。',
    '游标一批多少个?batchSize 设小了会怎样?10 分钟超时到底怎么回事?遍历时别人改数据会读到什么?这篇把这些逐个验证。',
    [('101 个', 'find 返回的第一批文档数;之后的 getMore 最多约 16 MiB'), ('944 对 55 ms', 'batch_size=10 与默认批次读完 10 万个文档的耗时'), ('code 43', '空闲超时后 getMore 返回的 CursorNotFound')],
    [('批次', '<p>第一批 101 个文档,之后每个 <code>getMore</code> 装满 16 MiB 为止;10 万个文档只要 1 个 find 加 2 个 getMore。</p>'),
     ('batchSize', '<p>批次太小增加往返:10 要 10,001 条命令(944 ms),默认 3 条命令(55 ms)。</p>'),
     ('占服务端资源', '<p>没读完的游标计在 <code>metrics.cursor.open</code> 里,<code>close()</code> 后释放。</p>'),
     ('空闲超时', '<p>不绑定会话的游标空闲超过 <code>cursorTimeoutMillis</code> 后会被后台回收,再 getMore 报 43 CursorNotFound;每次 getMore 都会重置空闲计时。绑定在会话上的游标(驱动默认)由会话超时管理。</p>'),
     ('noCursorTimeout', '<p>不会被超时回收,但要自己关闭。</p>'),
     ('不是快照', '<p>遍历期间的修改游标看得到:被改到后面的文档会再读一次,遍历结果可能重复或遗漏。</p>')],
    steps,
    [ENV_M + '。单节点;游标超时用手写的 OP_MSG 客户端(不带 lsid)演示;重复次数每次运行都不同(这次 1,500)',
     '没有验证:超时回收线程的执行周期(只观察到超时 3 秒时 5 秒空闲就失败);会话超时(logicalSessionTimeoutMinutes)过期后会话里的游标;分片集群上 mongos 游标的超时;tailable 游标的超时;批次大小对内存的影响(服务端与客户端)'],
    '游标')
