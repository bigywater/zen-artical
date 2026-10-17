from lib import *
S = SS('m58')
steps = [
    step("primary 上先放 60 万个文档(dataSize 121 MB,2 个索引),再加一个新成员:状态依次是 STARTUP(0.01 s)、STARTUP2(0.78 s)、SECONDARY(2.55 s)——initial sync 总共约 2.5 s;同步期间 primary 上并发写入了 278 轮($inc 加 insert)。(前一次运行是 4.1 s,耗时有波动。)", t=tl(S(1)), mark=lidx(S(1), "'SECONDARY'", '总耗时约 2.5 s'), done=lidx(S(1), "'STARTUP'"), kv=KV([['STARTUP', '刚加入'], ['STARTUP2', 'initial sync 进行中(不可读)'], ['SECONDARY', '同步完成'], ['耗时', '121 MB 约 2.5 s']], ['STARTUP2'])),
    step("新成员的 replSetGetStatus 里有 initialSyncStatus(键有 appliedOps、approxTotalBytesCopied、approxTotalDataSize、bytesPerSecond、databases、initialSyncOplogStart 等),method 是 logical,最多允许 10 次失败重试。进度:0.78 s 复制 0.0 / 120.8 MB,1.03 s 15.5 MB,1.28 s 62.0 MB,1.54 s 108.5 MB,1.79 s 120.7 MB——大约 1 秒复制完 121 MB。", t=tl(S(2)), mark=lidx(S(2), '1.79 s', '1.54 s'), done=lidx(S(2), 'method = logical', '0.78 s', '1.03 s'), b=bars([['0.78 s', 0, '0.0 MB'], ['1.03 s', 15.5, '15.5 MB'], ['1.28 s', 62, '62.0 MB'], ['1.54 s', 108.5, '108.5 MB'], ['1.79 s', 120.7, '120.7 MB']], 120.7, mark=[3, 4], done=[0, 1, 2]), kv=KV([['method', 'logical(逐个集合复制文档)'], ['进度字段', 'approxTotalBytesCopied / approxTotalDataSize'], ['失败重试', '最多 10 次']], ['method'])),
    step("新成员日志里 initial sync 的里程碑:Initial sync required → Initial sync started → Starting initial sync attempt → Initial syncer oplog truncation finished → About to abort all running index builders → Writing to the oplog and applying operations until stopTimestamp before initial sync can complete → Finished fetching oplog during initial sync → Initial sync attempt finishing up → Initial sync status and statistics → Initial sync done;从 11:42:41.795 到 11:42:43.447 共约 1.65 s。", t=tl(S(3)), mark=lidx(S(3), 'Initial sync done', 'Writing to the oplog and applying operations'), done=lidx(S(3), 'Initial sync required', 'Initial sync started'), kv=KV([['起点', 'Initial sync required'], ['拉取 oplog 追平', 'Writing to the oplog and applying operations until stopTimestamp'], ['终点', 'Initial sync done']], ['终点'])),
    step("同步完成后 primary 与新成员的数据一致:big 都是 600,000 个、small 1000 个、live 278 个(同步期间并发写入的);dbHash 里 big 的哈希都是 5b2ec3035bfb…,live 的哈希都是 8ede2cb02f76…,完全相同。", t=tl(S(4)), mark=lidx(S(4), '新成员', 'primary'), done=lidx(S(4), 'live=278'), kv=KV([['文档数', '三个集合都相同'], ['dbHash', '逐集合哈希相同'], ['同步期间的写入', '也在新成员上']], ['dbHash'])),
    step("新成员的 oplog 从同步点开始:primary 的 oplog 最早 ts 是 Timestamp(1791776557, 1)、有 1,784 条;新成员最早 ts 是 Timestamp(1791776561, 130)、只有 429 条——它没有同步点之前的历史。", t=tl(S(5)), mark=lidx(S(5), '新成员 oplog 最早'), done=lidx(S(5), 'primary oplog 最早'), kv=KV([['新成员的 oplog', '从同步点开始'], ['后果', '更早的 resume token / 因果读不能在它上面提供']], ['后果'])),
    step("数据量变小,initial sync 并没有快多少:把 big 集合删掉、只剩几千个文档,再加一个成员,2.0 s 就进入 SECONDARY(121 MB 时是 2.5 s)——有约 2 秒的固定开销(启动、选同步源、截断 oplog、拉取 oplog 追平)。", t=tl(S(6)), mark=lidx(S(6), '2.0 s'), done=lidx(S(6), '数据只剩几千个文档'), kv=KV([['121 MB', '2.5 s'], ['几千个文档', '2.0 s'], ['固定开销', '约 2 秒']], ['固定开销'])),
]
A = mkartm('m58', 58, 'MongoDB,initial sync,副本集,新成员,STARTUP2,真实验证,动画演示',
    '实测新成员加入副本集的 initial sync:STARTUP → STARTUP2 → SECONDARY,121 MB 数据约 2.5 秒(logical 方式,约 1 秒复制完);replSetGetStatus 的 initialSyncStatus 给出进度字段;日志里的里程碑;同步期间的并发写入也会到齐,dbHash 一致;新成员的 oplog 从同步点开始。',
    '新节点加入时 initial sync 做了哪几步?怎么看进度?期间的写入会不会丢?这篇给副本集加一个新成员,记录状态、进度、日志,最后用 dbHash 核对数据。',
    [('2.5 s', '121 MB 数据的 initial sync 总耗时(STARTUP2 到 SECONDARY)'), ('dbHash 相同', '同步完成后 primary 与新成员逐集合的哈希完全一致'), ('1,784 对 429 条', 'primary 与新成员的 oplog 条目数:新成员只有同步点之后的历史')],
    [('状态', '<p>新成员依次经过 STARTUP、STARTUP2(正在 initial sync)、SECONDARY。</p>'),
     ('进度', '<p><code>replSetGetStatus</code> 里的 <code>initialSyncStatus</code> 有 <code>approxTotalBytesCopied</code>、<code>approxTotalDataSize</code>、<code>appliedOps</code> 等字段;方式是 logical(逐个集合复制)。</p>'),
     ('日志里程碑', '<p>从 “Initial sync required” 到 “Writing to the oplog and applying operations until stopTimestamp” 再到 “Initial sync done”。</p>'),
     ('一致性', '<p>同步期间 primary 上并发的写入也被带过来,完成后 dbHash 完全相同。</p>'),
     ('oplog 窗口', '<p>新成员的 oplog 只从同步点开始,没有更早的历史,所以更早的 change stream token 在它上面恢复不了。</p>'),
     ('固定开销', '<p>即使数据很少也有约 2 秒的固定开销;数据多时主要是复制数据的时间。</p>')],
    steps,
    [ENV_M + '。单节点副本集加 priority 0、votes 0 的新成员;本机回环,没有网络瓶颈',
     '没有验证:大数据量(GB 级以上)时复制与建索引阶段的耗时分布;fileCopyBased 方式(仅企业版);initial sync 失败重试(failedInitialSyncAttempts)的触发场景;从 secondary 而不是 primary 同步;initial sync 期间对 primary 性能的影响'],
    'initial sync')
