from lib import *
S = SS('m48')
steps = [
    step("事务的生命周期上限由参数 transactionLifetimeLimitSeconds 控制,getParameter 显示默认值 60 秒;maxTransactionLockRequestTimeoutMillis 是 5 毫秒。", t=tl(S(1)), mark=lidx(S(1), 'transactionLifetimeLimitSeconds: 60'), done=lidx(S(1), 'maxTransactionLockRequestTimeoutMillis: 5'), kv=KV([['transactionLifetimeLimitSeconds', '60 秒'], ['maxTransactionLockRequestTimeoutMillis', '5 ms']], ['transactionLifetimeLimitSeconds'])),
    step("currentOp($currentOp,idleSessions: true)里能看到正在进行的事务:字段有 expiryTime、parameters、readTimestamp、startWallClockTime、timeActiveMicros、timeInactiveMicros、timeOpenMicros;expiryTime 比 startWallClockTime 晚 60.0 秒;parameters 里 autocommit 为 False,readConcern 是 local(隐式默认)。", t=tl(S(2)), mark=lidx(S(2), 'expiryTime - startWallClockTime = 60.0 秒'), done=lidx(S(2), '事务的字段'), kv=KV([['expiryTime', '开始时间 + 60 秒'], ['timeOpenMicros', '事务已打开的时间'], ['autocommit', 'False']], ['expiryTime'])),
    step("把上限调成 5 秒:事务里改了文档 A 之后不再操作,事务外对 A 的 update 被阻塞了 5,357 ms 才完成;事务开始 5.4 s 后再在事务里操作,报 code=251(NoSuchTransaction),带 TransientTransactionError 标签,message 是 Transaction with { txnNumber: 1 } has been aborted.;commit 同样 251;A 的 v 回到 0(事务里的 $inc 被回滚),事务外写入的 w = 1 生效。", t=tl(S(3)), mark=lidx(S(3), '5357 ms', 'code=251', 'commit:code=251'), done=lidx(S(3), '回滚了'), kv=KV([['过期的事务', '被中止,修改回滚'], ['错误', '251 NoSuchTransaction,可重试'], ['事务外的写', '等到事务被中止才能继续']], ['过期的事务'])),
    step("一直在用也会过期:上限 5 秒时每 0.5 秒在事务里操作一次,成功了 15 次、在 7.6 s 时失败 code=251。生命周期从事务开始算起,不会因为有操作而续期;并且中止发生在 5 秒之后的某个时刻(7.6 s),不是准点。", t=tl(S(4)), mark=lidx(S(4), '7.6 s'), done=lidx(S(4), '成功了 15 次'), kv=KV([['生命周期', '从开始算起,操作不续期'], ['这次', '15 次后在 7.6 s 失败(上限 5 s)']], ['生命周期'])),
    step("服务端日志:含 transaction 与 abort 的日志 4 条,msg 是 \"Aborting transaction because it has been running for longer than 'transactionLifetimeLimitSeconds'\"。(随后把参数改回 60。)", t=tl(S(5)), mark=lidx(S(5), 'Aborting transaction'), done=lidx(S(5), 'was: 5'), kv=KV([['日志 msg', 'Aborting transaction because it has been running for longer than …'], ['由谁中止', '服务端后台清理']], ['日志 msg'])),
    step("默认的 60 秒:两个事务同时开始并各改一个文档然后什么也不做。事务 A 在 70 s 时 commit 成功(提交成功,v = 1),也就是已经超过 60 秒还没被中止;事务 B 一直没动,直到 89 s 才从 currentOp 里消失,commit 报 code=251(NoSuchTransaction),文档 _id 3 的 v 仍是 0。60 秒是下限不是准点:服务端的清理任务周期性运行,到点之后、清理之前提交仍可能成功。", t=tl(S(6)), mark=lidx(S(6), '70 s 时 commit 成功', '89 s'), done=lidx(S(6), 'B 的 commit', '记录数'), b=bars([['上限', 60, '60 s'], ['事务 A 提交成功的时刻', 70, '70 s'], ['事务 B 被中止的时刻', 89, '89 s']], 89, mark=[2], done=[0, 1]), kv=KV([['上限', '60 s'], ['A:70 s 提交', '成功'], ['B:被中止', '89 s,commit 报 251']], ['A:70 s 提交'])),
]
A = mkartm('m48', 48, 'MongoDB,事务,transactionLifetimeLimitSeconds,NoSuchTransaction,超时,真实验证,动画演示',
    '实测事务的生命周期上限:默认 60 秒;事务外的写入会等到过期事务被中止(上限调到 5 秒时等了 5,357 ms);过期后继续操作与 commit 都报 251 NoSuchTransaction 且修改回滚;生命周期不因有操作续期;中止不是准点——默认 60 秒的事务 70 秒时仍能提交成功,89 秒才被清理。',
    '事务 60 秒的上限到点之后到底发生什么?是不是准点中止?事务外的写入会被它阻塞多久?这篇用 5 秒和 60 秒两个上限实测。',
    [('60 秒', 'transactionLifetimeLimitSeconds 默认值'), ('70 s 成功,89 s 中止', '默认 60 秒上限下:一个事务在 70 秒时提交仍成功,另一个到 89 秒才被服务端中止'), ('251', '过期事务继续操作或提交的错误码 NoSuchTransaction,带 TransientTransactionError 标签')],
    [('上限', '<p>事务最长存活 60 秒(<code>transactionLifetimeLimitSeconds</code>),<code>currentOp</code> 里的 <code>expiryTime</code> 就是开始时间加 60 秒。</p>'),
     ('过期后', '<p>事务被中止,修改回滚;继续操作或提交都报 251 <code>NoSuchTransaction</code>,带 <code>TransientTransactionError</code>,可以整个重试。</p>'),
     ('阻塞其他写入', '<p>事务改了文档不提交,事务外对同一个文档的写入要等到事务被中止或提交才能完成(上限 5 秒时等了 5.4 秒)。</p>'),
     ('不会续期', '<p>生命周期从事务开始算起,即使一直在操作也会过期。</p>'),
     ('不是准点', '<p>过期事务由后台任务周期性清理:默认 60 秒的事务在 70 秒时提交仍成功,89 秒才被中止。所以别指望“恰好 60 秒”,事务要尽量短。</p>'),
     ('日志', '<p>服务端会记一条 “Aborting transaction because it has been running for longer than transactionLifetimeLimitSeconds”。</p>')],
    steps,
    [ENV_M + '。单节点副本集;为缩短等待,前几节把 transactionLifetimeLimitSeconds 调到 5 秒,最后一节用默认的 60 秒真实等待 89 秒',
     '没有验证:清理任务的执行周期是否固定、与上限的关系(只观察到 5 秒上限在 5.4~7.6 s、60 秒上限在 89 s 中止);长事务对 WiredTiger 缓存与 history store 的占用;maxTimeMS 对事务内操作的作用;分片事务的超时;客户端 withTransaction 的 120 秒重试预算'],
    '事务的 60 秒上限')
