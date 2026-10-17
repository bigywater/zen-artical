from lib import *
S = SS('m64')
steps = [
    step("oplog 窗口 = oplog 里最早一条与最晚一条的时间差。db.getReplicationInfo() 给出 logSizeMB: 128(配置的大小)、usedMB: 2.14(已用)、timeDiff: 11(窗口,秒)、tFirst 与 tLast——此时 oplog 才用了 2.14 MB,窗口只有 11 秒(是刚建好集群的历史),并不是 oplog 满了之后的窗口。", t=tl(S(1)), mark=lidx(S(1), 'timeDiff: 11', 'usedMB: 2.14'), done=lidx(S(1), 'logSizeMB: 128'), kv=KV([['logSizeMB', '128(配置的上限)'], ['usedMB', '2.14(已用)'], ['timeDiff', '11 秒(当前窗口)']], ['timeDiff'])),
    step("不同写入每条 oplog 的大小(各 200 次):update_one $inc 一个字段 163 字节/条;replace_one 整个 1 KB 文档 1,153 字节/条;insert_one 1 KB 文档 1,142 字节/条;insert_one 10 KB 文档 10,097 字节/条;delete_one 120 字节/条。小更新只有整体写入的约 1/7,10 KB 文档的插入是它的 62 倍。", t=tl(S(2)), mark=lidx(S(2), 'insert_one 10 KB', 'replace_one'), done=lidx(S(2), 'update_one $inc', 'delete_one'), b=bars([['delete_one', 120, '120 B'], ['update_one $inc', 163, '163 B'], ['insert_one 1 KB', 1142, '1,142 B'], ['replace_one 1 KB', 1153, '1,153 B'], ['insert_one 10 KB', 10097, '10,097 B']], 10097, mark=[4], done=[0, 1, 2, 3]), kv=KV([['小更新 / 删除', '120~163 字节'], ['1 KB 文档的写入', '约 1.1 KB'], ['10 KB 文档的插入', '约 10 KB']], ['小更新 / 删除'])),
    step("按实测字节数估算,持续 1,000 次 / 秒的写入下 oplog 撑多久:小更新(163 字节)0.2 MB/s,128 MB 撑 823 秒、1 GB 撑 6,587 秒、10 GB 撑 18.3 小时;1 KB 文档插入 1.1 MB/s,128 MB 撑 118 秒、1 GB 撑 940 秒、10 GB 撑 2.6 小时;10 KB 文档插入 9.6 MB/s,128 MB 撑 13 秒、1 GB 撑 106 秒、10 GB 撑 0.3 小时。(这是用上一步的实测值做的计算,没有真的写满 oplog。)", t=tl(S(3)), mark=lidx(S(3), '10 KB 文档插入', '1 KB 文档插入'), done=lidx(S(3), '小更新'), kv=KV([['窗口', 'oplog 大小 ÷ 每秒产生的字节'], ['小更新 1000/s', '128 MB ≈ 14 分钟'], ['10 KB 插入 1000/s', '128 MB ≈ 13 秒']], ['窗口'])),
    step("oplog 的 size(逻辑大小)与 storageSize(磁盘上压缩后的大小):collStats 显示 size 4.8 MB、storageSize 0.2 MB、maxSize 128 MB、count 1,030——可压缩的内容在磁盘上小得多。", t=tl(S(4)), mark=lidx(S(4), 'storageSize = 0.2 MB'), done=lidx(S(4), 'collStats'), kv=KV([['size', '4.8 MB(逻辑)'], ['storageSize', '0.2 MB(压缩后)'], ['maxSize', '128 MB']], ['storageSize'])),
    step("在线调整 oplog 大小用 replSetResizeOplog,最小 990 MB:size=100 失败(BSON field 'size' value must be >= 990);size=990 成功(ok=1),collStats 的 maxSize 变成 990 MB。", t=tl(S(5)), mark=lidx(S(5), 'size=100 MB', 'must be >= 990'), done=lidx(S(5), 'size=990 MB'), kv=KV([['最小值', '990 MB'], ['调大', '在线生效']], ['最小值'])),
    step("secondary 短暂离线:停 15 秒期间 primary 持续写入 1 KB 的文档(1,411 条,oplog 新增 1,412 条、1.8 MB);重启后 2.8 s 回到 SECONDARY 并追平,live 集合在两边都是 1,411 条——短暂离线靠 oplog 重放,需要的 oplog 量就是离线期间产生的量;离线时间超过 oplog 窗口就追不上,要重新 initial sync。", t=tl(S(6)), mark=lidx(S(6), '2.8 s'), done=lidx(S(6), 'secondary 离线 15 秒'), kv=KV([['15 秒离线', '1.8 MB oplog,2.8 s 追平'], ['追不上的条件', '离线时间 > oplog 窗口(本文没有实测)']], ['追不上的条件'])),
]
A = mkartm('m64', 64, 'MongoDB,oplog,oplog窗口,replSetResizeOplog,secondary,副本集,真实验证,动画演示',
    '实测 oplog 窗口:getReplicationInfo 的窗口字段;不同写入每条 oplog 的大小(小更新 163 字节、1 KB 插入 1,142 字节、10 KB 插入 10,097 字节);按实测字节估算 128 MB 到 10 GB 的 oplog 在 1,000 次/秒负载下的窗口;size 与压缩后 storageSize;replSetResizeOplog 最小 990 MB;secondary 离线 15 秒后 2.8 秒追平。',
    'oplog 要设多大?secondary 离线多久还能追上?这篇量出各种写入产生的 oplog 字节数,算出不同 oplog 大小的窗口,并实测一次短暂离线后的追赶。',
    [('163 对 10,097 字节', '小更新与 10 KB 文档插入平均每条 oplog 的大小'), ('990 MB', 'replSetResizeOplog 允许的最小值'), ('2.8 s', 'secondary 离线 15 秒后重启到追平所用的时间')],
    [('窗口怎么看', '<p>窗口就是 oplog 里最早与最晚条目的时间差,<code>db.getReplicationInfo()</code> 的 <code>timeDiff</code>;oplog 写满后才反映稳态窗口。</p>'),
     ('写入类型', '<p>小更新(<code>$inc</code>)每条约 163 字节,delete 约 120 字节,1 KB 文档的插入或整个替换约 1.1 KB,10 KB 的插入约 10 KB。写入的类型比条数更决定 oplog 增长速度。</p>'),
     ('窗口估算', '<p>窗口 = oplog 大小 ÷ 每秒产生的字节数:同样 1,000 次/秒,小更新下 128 MB 够 14 分钟,10 KB 插入下只够 13 秒。</p>'),
     ('逻辑大小与磁盘', '<p>collStats 的 size 是逻辑大小,storageSize 是压缩后的磁盘大小。</p>'),
     ('调整', '<p><code>replSetResizeOplog</code> 在线调整,最小 990 MB。</p>'),
     ('追赶', '<p>secondary 离线期间产生了 1.8 MB 的 oplog,重启后 2.8 秒追平;离线时间超过窗口就追不上,要重新 initial sync。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 副本集(oplog 128 MB);第三节是用第二节的实测字节数做的算术,不是实测的窗口',
     '没有验证:oplog 写满回绕后的稳态窗口,以及 secondary 落后超过窗口后“too stale”的表现——我试图把 128 MB 的 oplog 写到 650 MB(3 节点)和 976 MB(单节点),最早的条目始终没有被截断(serverStatus.oplogTruncation.truncateCount 一直是 0,原因没有查明),所以这一点没有演示;oplogMinRetentionHours;大事务对 oplog 的影响;flow control'],
    'oplog 窗口')
