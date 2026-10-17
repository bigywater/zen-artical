from lib import *
S = SS('m74')
steps = [
    step("另一个连接(appName = slowfind)跑 find,filter 是 {$where: \"sleep(1000) || true\"}、limit 1;在这个连接里用 $currentOp 聚合阶段看到它:op = query、ns = test.t、active = true、planSummary = COLLSCAN、microsecs_running = 802,569、desc = conn10,command 字段里能看到完整的 find 命令。不去管它,该查询总共跑了 2.6 秒才正常返回(不止一次 sleep——服务端对不止一个文档做了评估)。", t=tl(S(1)), mark=lidx(S(1), '找到 1 个', '"op": "query"', 'command = '), done=lidx(S(1), '总共跑了'), kv=KV([['op / ns', 'query / test.t'], ['planSummary', 'COLLSCAN'], ['microsecs_running', '802,569(0.8 秒时看到)'], ['不管它的总耗时', '2.6 秒']], ['microsecs_running'])),
    step("killOp:同样的查询在 0.8 秒时拿到 opid = 26625,db.adminCommand({killOp: 1, op: 26625}) 返回 {info: 'attempting to kill op', ok: 1};受害者的连接几乎立刻(0.0 秒后,不杀要 2.6 秒)收到错误 code = 11601、codeName = Interrupted,errmsg 以 Executor error during find command: test.t :: caused by :: wasm epoch interrupt: kill pending 开头。", t=tl(S(2)), mark=lidx(S(2), 'killOp 返回', '受害者在 killOp 之后'), done=lidx(S(2), '找到 opid'), b=bars([['不杀', 2.6, '2.6 秒'], ['killOp 之后', 0, '0.0 秒']], 2.6, mark=[1], done=[0]), kv=KV([['killOp 返回', 'attempting to kill op, ok: 1'], ['受害者收到', '11601 Interrupted'], ['返回时间', 'killOp 后约 0.0 秒']], ['受害者收到'])),
    step("两类 JS 操作都能被打断:$where 里正在 sleep 的 find,killOp 之后 0.00 秒结束,错误 11601 Interrupted;aggregate 里用 $function 做 30 万次累加的 JS 计算循环,killOp 之后同样 0.00 秒结束、11601 Interrupted。", t=tl(S(3)), mark=lidx(S(3), 'where_sleep', 'scan_sort'), done=lidx(S(3), 'where_sleep'), kv=KV([['$where + sleep', 'killOp 后 0.00 秒,Interrupted'], ['$function 的 JS 循环', 'killOp 后 0.00 秒,Interrupted']], ['$function 的 JS 循环'])),
    step("不想靠人去杀,就用 maxTimeMS:同样的 find 加 maxTimeMS = 1000,1.02 秒后服务端自己中止,错误是 code = 50、codeName = MaxTimeMSExpired(不是 11601),errmsg 同样带着 wasm epoch interrupt。", t=tl(S(4)), mark=lidx(S(4), 'maxTimeMS = 1000'), done=lidx(S(4), 'maxTimeMS = 1000'), kv=KV([['maxTimeMS', '1000'], ['返回时间', '1.02 秒'], ['错误', '50 MaxTimeMSExpired']], ['错误'])),
    step("用 $currentOp 加 $match 找长时间运行的操作:3 个并发的 sleep 查询在 1.5 秒时,{active: true, secs_running: {$gte: 1}, op: 'query'} 找到 3 个(worker0、worker1、worker2,secs_running 都是 1)。{idleCursors: true} 能看到没拉完的游标:type = idleCursor,ns = test.t,nDocsReturned = 10,noCursorTimeout = false,originatingCommand = {find: 't'}。", t=tl(S(5)), mark=lidx(S(5), 'secs_running ≥ 1', 'idleCursors'), done=lidx(S(5), 'secs_running ≥ 1'), kv=KV([['secs_running ≥ 1 的 query', '3 个'], ['idleCursors', '1 个:nDocsReturned = 10']], ['secs_running ≥ 1 的 query'])),
    step("所有查询结束之后,$currentOp(allUsers)仍返回 8 条:Checkpointer 和 JournalFlusher 两个后台线程(op = none)、几个连接上 admin.$cmd 的 command(包括各个 worker/victim 连接,command 字段是空的)、以及 ns = admin.$cmd.aggregate 的那一条——就是这次 $currentOp 自己。", t=tl(S(6)), mark=lidx(S(6), 'Checkpointer', 'JournalFlusher', 'admin.$cmd.aggregate'), done=lidx(S(6), 'conn6'), kv=KV([['后台线程', 'Checkpointer、JournalFlusher'], ['连接上挂着的命令', '5 条 admin.$cmd'], ['$currentOp 自己', 'admin.$cmd.aggregate']], ['$currentOp 自己'])),
]
A = mkartm('m74', 74, 'MongoDB,currentOp,killOp,maxTimeMS,Interrupted,真实验证,动画演示',
    '实测 $currentOp 与 killOp:另一个连接里的慢 find 能看到完整命令、planSummary 与 microsecs_running;killOp 之后 0.0 秒收到 11601 Interrupted(不杀要 2.6 秒),$where 的 sleep 与 $function 的 JS 循环都能打断;maxTimeMS = 1000 在 1.02 秒后以 50 MaxTimeMSExpired 中止;$currentOp 也会列出后台线程和它自己。',
    '线上有个操作卡住了,怎么找到它、怎么杀掉它、杀掉之后客户端看到什么?maxTimeMS 又是怎么回事?这篇逐个验证。',
    [('11601', 'killOp 之后客户端收到的错误码(Interrupted),约 0.0 秒返回'), ('50', 'maxTimeMS 到期的错误码 MaxTimeMSExpired,1.02 秒后返回'), ('2.6 秒', '不杀的话这条 $where 查询的总耗时')],
    [('$currentOp', '<p><code>$currentOp</code> 聚合阶段列出进行中的操作:<code>op</code>、<code>ns</code>、<code>planSummary</code>、<code>microsecs_running</code>,还有完整的 <code>command</code>。</p>'),
     ('killOp', '<p><code>killOp</code> 用 <code>opid</code> 杀操作,返回 <code>attempting to kill op</code>;受害者很快收到 <code>11601 Interrupted</code>。</p>'),
     ('能被打断的', '<p><code>$where</code> 里的 <code>sleep</code> 和 <code>$function</code> 里的 JS 计算循环,<code>killOp</code> 之后都立刻结束。</p>'),
     ('maxTimeMS', '<p><code>maxTimeMS</code> 让服务端自己到点中止,错误码是 <code>50 MaxTimeMSExpired</code>,不是 11601。</p>'),
     ('过滤', '<p>用 <code>$match</code> 按 <code>secs_running</code> 找长时间运行的操作;<code>idleCursors: true</code> 能看到空闲的游标。</p>'),
     ('看到自己', '<p>空闲时 <code>$currentOp</code> 也有后台线程(Checkpointer、JournalFlusher)、连接上的命令和它自己这一条。</p>')],
    steps,
    [ENV_M + '。单机 mongod,20 万个文档的集合;用 $where 的 sleep(1000) 和 $function 的 JS 循环造“慢操作”',
     '没有验证:killOp 对正在等锁、正在写盘(checkpoint)、正在提交事务的操作;killOp 对分片集群(mongos 上的 opid 格式 shard:opid);currentOp 的 idleConnections/idleSessions 选项;权限(inprog、killop)要求;killOp 对 getMore 与游标的行为;killSessions 与 killAllSessions;JS 引擎是 wasm 的细节只从错误信息里看到了 "wasm epoch interrupt"'],
    'currentOp 与 killOp')
