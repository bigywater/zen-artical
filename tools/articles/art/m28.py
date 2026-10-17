from lib import *
S = SS('m28')
steps = [
    step("数据:big 150,000 个文档(每个约 1 KB,dataSize 147.5 MB),small 50,000 个(约 50 MB),按没有索引的字段 k 排序。getParameter:allowDiskUseByDefault 是 true(9.0.2 的默认),internalQueryMaxBlockingSortMemoryUsageBytes 是 104857600(100 MiB)。", t=tl(S(1)), mark=lidx(S(1), 'allowDiskUseByDefault: true', '104857600'), done=lidx(S(1), 'MB(big 的 dataSize)'), kv=KV([['排序内存上限', '104,857,600 字节(100 MiB)'], ['allowDiskUseByDefault', 'true(默认)'], ['big 的大小', '147.5 MB']], ['排序内存上限'])),
    step("把 allowDiskUseByDefault 设为 false(旧版本的默认行为):对 big 无索引排序报 code 292,Sort exceeded memory limit of 104857600 bytes, but did not opt in to external sorting.;50 MB 的 small 排序没超限,返回 50000 个。", t=tl(S(2)), mark=lidx(S(2), 'code: 292', 'exceeded memory limit'), done=lidx(S(2), '50000', 'was: true'), kv=KV([['超 100 MiB 且没开 allowDiskUse', 'code 292'], ['50 MB', '没超,正常']], ['超 100 MiB 且没开 allowDiskUse'])),
    step("加 allowDiskUse 之后排序成功:explain 里 SORT 阶段 usedDisk: true、spills: 2、spilledBytes: 155,400,000、memLimit: 104,857,600,nReturned 150000,执行 337 ms。", t=tl(S(3)), mark=lidx(S(3), 'usedDisk: true', 'spills: 2', 'spilledBytes'), done=lidx(S(3), 'nReturned: 150000'), kv=KV([['usedDisk', 'true'], ['spills', '2 次溢出'], ['spilledBytes', '155,400,000']], ['usedDisk'])),
    step("耗时(3 次中位数,去掉 pad 字段只传小文档):small 50,000 个不排序 30 ms,排序 46 ms(内存);big 150,000 个不排序 97 ms,排序 144 ms(溢出磁盘,约 150 MB 的排序数据)。排序的额外代价是 16 ms 和 47 ms。", t=tl(S(4)), mark=lidx(S(4), 'big(150,000 个)'), done=lidx(S(4), 'small(50,000 个)'), b=bars([['small 不排序', 30, '30 ms'], ['small 内存排序', 46, '46 ms'], ['big 不排序', 97, '97 ms'], ['big 溢出磁盘排序', 144, '144 ms']], 144, mark=[3], done=[0, 1, 2]), kv=KV([['内存排序', '+16 ms(50 MB)'], ['溢出磁盘排序', '+47 ms(150 MB)']], ['溢出磁盘排序'])),
    step("sort + limit 只保留前 N 个(top-k):即使 allowDiskUseByDefault 仍是 false,db.big.find().sort({k: 1}).limit(100) 也成功返回 100 个;explain 里 SORT 阶段 usedDisk: false,limit 100。", t=tl(S(5)), mark=lidx(S(5), 'usedDisk: false', 'limit: 100'), done=lidx(S(5), '  100'), kv=KV([['sort + limit', '只在内存里保留前 N 个'], ['不会超限', '不需要 allowDiskUse']], ['sort + limit'])),
    step("k 上有索引时按 k 排序直接沿索引读,计划是 FETCH > IXSCAN(k_1),没有 SORT 阶段,allowDiskUseByDefault 仍是 false 也返回全部 150000 个(87 ms);读取全部文档(去掉 pad)有索引的排序 155 ms(上一节无索引溢出磁盘是 144 ms)——索引排序省内存,但不一定更快。最后把参数改回 true。", t=tl(S(6)), mark=lidx(S(6), 'FETCH > IXSCAN(k_1)', '  150000'), done=lidx(S(6), 'allowDiskUseByDefault: true', 'was: false', '有索引的排序读取'), kv=KV([['有索引', '没有 SORT 阶段'], ['内存上限', '不再相关'], ['耗时', '不一定比溢出磁盘排序短']], ['有索引'])),
]
A = mkartm('m28', 28, 'MongoDB,排序,100MB内存限制,allowDiskUse,SORT,真实验证,动画演示',
    '实测内存排序的 100 MiB 限制:9.0.2 默认 allowDiskUseByDefault 为 true,关掉之后 147.5 MB 的无索引排序报 code 292;allowDiskUse 时 SORT 阶段溢出 2 次共 155,400,000 字节仍成功;sort + limit 是 top-k 不会超限;有索引则没有 SORT 阶段。',
    '排序数据超过 100MB 会怎样?这篇用 150 MB 的集合在 allowDiskUseByDefault 开关两种状态下对比,再看 limit 和索引如何避开这个限制。',
    [('100 MiB', '阻塞排序的内存上限(internalQueryMaxBlockingSortMemoryUsageBytes = 104,857,600)'), ('292', 'allowDiskUseByDefault 为 false、没传 allowDiskUse 时超限的错误码'), ('2 次', '150 MB 排序溢出磁盘的次数(spilledBytes 155,400,000)')],
    [('限制与参数', '<p>阻塞排序(无索引可用的 <code>SORT</code> 阶段)最多用 100 MiB 内存。9.0.2 里 <code>allowDiskUseByDefault</code> 默认为 true,超过就自动溢出磁盘。</p>'),
     ('关掉默认', '<p>关掉 <code>allowDiskUseByDefault</code>(旧版本的默认行为)后,超过上限报 code 292 <code>did not opt in to external sorting</code>,没超的小集合排序正常。</p>'),
     ('allowDiskUse', '<p>传 <code>allowDiskUse</code> 后排序溢出磁盘:explain 里 SORT 阶段 <code>usedDisk: true</code>、<code>spills: 2</code>。</p>'),
     ('耗时', '<p>150 MB 的溢出磁盘排序比不排序多 47 ms;50 MB 的内存排序多 16 ms。</p>'),
     ('sort + limit', '<p>带 limit 的排序只保留前 N 个,不会超限,<code>usedDisk: false</code>。</p>'),
     ('索引', '<p>排序字段有索引时没有 SORT 阶段,不受内存上限影响;不过读取全部文档的总耗时不一定更短(155 ms 对 144 ms)。</p>')],
    steps,
    [ENV_M + '。参数用 setParameter 临时修改并改回;耗时用 pymongo 的 3 次中位数,查询去掉 pad 字段以减少传输',
     '没有验证:aggregate 里 $sort、$group 各自的内存限制与溢出(各 100 MiB);spill 文件的位置(_tmp 目录)与磁盘空间不足时的行为;分片集群上 mongos 合并排序的内存;不同文档大小下 spills 次数与上限的关系;allowDiskUse 对并发的影响'],
    '内存排序限制')
