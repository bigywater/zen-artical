from lib import *
S = SS('m60')
steps = [
    step("基线:3 节点,primary 是 9901,w:majority 写入 10 个文档;让两个 secondary 停止拉取 oplog(failpoint),再在旧 primary 上用 w:1 写 5 个文档(_id 100~104):9901 有 15 个文档、_id>=100 的 5 个;9902 与 9903 各只有 10 个、_id>=100 的 0 个。", t=tl(S(1)), mark=lidx(S(1), '节点 9901'), done=lidx(S(1), '节点 9902', '节点 9903'), b=bars([['9901(旧 primary)', 15, '15 个文档'], ['9902', 10, '10 个文档'], ['9903', 10, '10 个文档']], 15, mark=[0], done=[1, 2]), kv=KV([['w:1 写入', '只在旧 primary 上'], ['secondary', '没有这 5 个文档']], ['w:1 写入'])),
    step("旧 primary 崩溃(kill -9),放开 failpoint 后两个 secondary 在 10.6 s 后选出新 primary 9902;新 primary 上用 w:majority 写入 3 个文档(_id 200~202),此时它的集合里 _id>=100 的只有 [200, 201, 202],共 13 个文档——没有那 5 个。", t=tl(S(2)), mark=lidx(S(2), '选出新 primary'), done=lidx(S(2), '_id>=100 的 [200, 201, 202]'), kv=KV([['选主', '10.6 s'], ['新 primary 的数据', '没有 _id 100~104']], ['选主'])),
    step("重启旧 primary:日志里的状态转换是 STARTUP→STARTUP2→RECOVERING→SECONDARY(11:52:38.220),约 1 秒后 oplog 获取器发现与同步源分叉,SECONDARY→ROLLBACK(11:52:39.241),0.48 秒后 ROLLBACK→SECONDARY(11:52:39.725)。轮询 replSetGetStatus 在 0.62 s 第一次看到的已经是 SECONDARY,回滚窗口太短没抓到。", t=tl(S(3)), mark=lidx(S(3), "'SECONDARY'"), done=lidx(S(3), '旧 primary 的状态'), kv=KV([['状态序列', 'STARTUP → STARTUP2 → RECOVERING → SECONDARY → ROLLBACK → SECONDARY'], ['回滚用时', '约 0.5 秒']], ['回滚用时'])),
    step("日志里的回滚记录:Incrementing the rollback ID after unclean shutdown → Oplog fetcher returned error → Starting rollback due to fetcher error → Rollback using 'recoverToStableTimestamp' method → Scheduling rollback → Transition to ROLLBACK → Replica set state transition。回滚用 recoverToStableTimestamp 方式:先回到稳定时间点,再重放。", t=tl(S(4)), mark=lidx(S(4), 'Starting rollback due to fetcher error', "recoverToStableTimestamp", 'Transition to ROLLBACK'), done=lidx(S(4), 'Incrementing the rollback ID', 'Oplog fetcher returned error'), kv=KV([['触发', 'oplog 获取器发现分叉'], ['方式', 'recoverToStableTimestamp'], ['rollback ID', '递增']], ['方式'])),
    step("被回滚的数据没有丢:旧 primary 的 dbpath/rollback/ 下有两个 BSON 文件(集合 UUID 目录下的 removed.<时间>.1.bson 和 local.oplog.rs 下的 removed.<时间>.0.bson);集合那个文件里是 5 个文档 _id 100~104,src 都是 'old-primary-only'——可以人工检查后决定是否重新写入。", t=tl(S(5)), mark=lidx(S(5), "'old-primary-only'"), done=lidx(S(5), 'rollback 目录里的文件'), kv=KV([['位置', 'dbpath/rollback/<集合 UUID>/'], ['内容', '被撤销的文档(BSON)'], ['处理', '人工检查,必要时重新写入']], ['位置'])),
    step("回滚之后三个节点的数据一致:9901、9902、9903 都是 13 个文档、_id>=100 的只有 [200, 201, 202]。w:1 写入的 5 个文档从集合里永远消失(只留在 rollback 文件里)。", t=tl(S(6)), mark=lidx(S(6), '节点 9901'), done=lidx(S(6), '节点 9902', '节点 9903'), kv=KV([['结果', '三个节点一致,13 个文档'], ['丢失的写入', 'w:1 且未复制的 5 个'], ['避免', '重要写入用 w:majority']], ['避免'])),
]
A = mkartm('m60', 60, 'MongoDB,rollback,回滚,副本集,w:1,真实验证,动画演示',
    '实测 rollback:旧 primary 上 w:1 写入的 5 个文档未复制就崩溃,新 primary 选出(10.6 s)后继续写入;旧 primary 重启后 SECONDARY→ROLLBACK→SECONDARY 约 0.5 秒,使用 recoverToStableTimestamp 方式;被回滚的文档保存在 dbpath/rollback/ 的 BSON 文件里,三个节点最终一致。',
    '没复制出去的写入去哪了?这篇在 3 节点副本集上让旧 primary 带着 5 个未复制的 w:1 写入崩溃,看新 primary 的选出、旧 primary 重启后的回滚过程、日志、rollback 目录里的 BSON 文件和最终的数据。',
    [('5 个文档', '旧 primary 上 w:1 写入、未复制就崩溃,被回滚的文档数'), ('约 0.5 秒', '旧 primary 重启后 ROLLBACK 状态持续的时间(日志里 SECONDARY→ROLLBACK→SECONDARY)'), ('rollback/', '被回滚的文档保存的目录,里面是 BSON 文件')],
    [('怎么造出这个场景', '<p>让两个 secondary 停止拉取 oplog,在 primary 上用 <code>w:1</code> 写入 5 个文档(没有任何副本有),再把 primary 杀掉。</p>'),
     ('新 primary', '<p>两个 secondary 在约 10 秒后选出新 primary,继续接受写入,但它没有那 5 个文档。</p>'),
     ('回滚', '<p>旧 primary 重启后 oplog 获取器发现与同步源分叉,进入 ROLLBACK,使用 <code>recoverToStableTimestamp</code> 方式,约 0.5 秒后恢复为 SECONDARY。</p>'),
     ('被回滚的数据', '<p>被撤销的文档保存在 <code>dbpath/rollback/&lt;集合 UUID&gt;/removed.&lt;时间&gt;.bson</code> 里,可以人工检查后再写回。</p>'),
     ('最终一致', '<p>回滚后三个节点都是 13 个文档,w:1 的 5 个文档不在集合里。</p>'),
     ('如何避免', '<p>重要的写入使用 <code>w: majority</code>,已被多数确认的写入不会被回滚。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 副本集;分叉通过 stopReplProducer 与 kill -9 构造;选主耗时每次运行不同(约 10 秒)',
     '没有验证:w:majority 的写入在同样场景下确实不会被回滚(只给出了建议);rollback 文件的大小上限(超过 300 MB 的回滚需要人工干预);各种 rollback 方式(recoverToStableTimestamp 之外);回滚期间对读写的影响;网络分区(而非 kill)造成的分叉'],
    '回滚')
