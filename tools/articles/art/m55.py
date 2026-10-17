from lib import *
S = SS('m55')
steps = [
    step("retryWrites=True(默认):用 failCommand 让服务端在 update 上关掉连接,驱动自动重试一次,update_one 结果 matched 1、modified 1,n 只加了 1(= 1);驱动发出的 update 命令是 [('update', 2, True), ('update', 2, True)]——两次的 txnNumber 都是 2、都带 lsid:重试带着同一个事务号,服务端据此判断是不是重复请求。", t=tl(S(1)), mark=lidx(S(1), "('update', 2, True), ('update', 2, True)"), done=lidx(S(1), 'update_one 的结果', 'txnNumber 相同'), kv=KV([['重试', '驱动自动重发,带同一个 lsid + txnNumber'], ['结果', 'n 只加了 1']], ['重试'])),
    step("retryWrites=False:同样的故障直接抛 AutoReconnect(127.0.0.1:…: connection closed),n 仍是 1(这次故障发生在执行之前,没有加)。", t=tl(S(2)), mark=lidx(S(2), 'AutoReconnect'), done=lidx(S(2), 'n = 1'), kv=KV([['retryWrites=False', '连接断开直接抛错,应用要自己判断'], ['结果不确定', '不知道服务端执行了没有']], ['retryWrites=False'])),
    step("服务端的去重:用手写的 OP_MSG 把同一个 update($inc n)带着同一个 lsid + txnNumber 100 发两次:第一次 nModified=1,库里 n = 1;重发同一个请求返回 nModified=1、retriedStmtIds=[0],库里 n 仍是 1(没有再加);换成 txnNumber 101 的新请求才让 n 变成 2。", t=tl(S(3)), mark=lidx(S(3), '重发同一个请求', 'retriedStmtIds=[0]'), done=lidx(S(3), '第 1 次(txnNumber 100)', '新请求(txnNumber 101)'), b=bars([['txnNumber 100 第 1 次', 1, 'n = 1'], ['txnNumber 100 重发', 1, 'n = 1(没再加)'], ['txnNumber 101', 2, 'n = 2']], 2, mark=[1], done=[0, 2]), kv=KV([['同一个 txnNumber', '重发返回缓存结果,不再执行'], ['retriedStmtIds', '标明哪些语句是重复的']], ['同一个 txnNumber'])),
    step("去重靠 oplog 条目:oplog 里 test.ctr 只有 txnNumber=100(stmtId=0,diff {u: {n: 1}})和 txnNumber=101(stmtId=0,diff {u: {n: 2}})两条,重发没有产生新条目;config.transactions 里该会话的记录 txnNum=101,lastWriteOpTime 指向最后一条。", t=tl(S(4)), mark=lidx(S(4), 'txnNumber=100', 'txnNumber=101', 'config.transactions'), done=lidx(S(4), 'oplog:'), kv=KV([['oplog 条目', 'lsid + txnNumber + stmtId'], ['config.transactions', '记录每个会话最后的 txnNum 与 lastWriteOpTime'], ['重发', '不产生新条目']], ['oplog 条目'])),
    step("insert 的每条语句有 stmtId:一次插入 3 个文档(ordered),第 1 次 n=3;整批重发(同一个 lsid、txnNumber)返回 n=3、retriedStmtIds=[0, 1, 2],集合里仍只有 3 个文档,没有重复键错误。", t=tl(S(5)), mark=lidx(S(5), 'retriedStmtIds=[0, 1, 2]'), done=lidx(S(5), '第 1 次:n=3'), kv=KV([['stmtId', '批里每条语句一个编号'], ['整批重发', '只执行一次']], ['stmtId'])),
    step("哪些可以重试:update_many(multi:true)遇到连接断开不重试,直接抛 AutoReconnect,发出的 update 命令 txnNumber 是 None;delete_one 被重试后成功,发出两次 delete(txnNumber 1)。独立实例(非副本集)上 retryWrites=True 的 insert 成功——驱动检测到不支持就不用;直接带 txnNumber 的命令被拒绝:Transaction numbers are only allowed on a replica set member or mongos。", t=tl(S(6)), mark=lidx(S(6), 'update_many', 'Transaction numbers are only allowed'), done=lidx(S(6), 'delete_one', '独立实例'), kv=KV([['可重试', 'insert / 单文档 update / delete / findAndModify'], ['不可重试', 'multi: true 的 update_many、delete_many'], ['独立实例', '不支持事务号,驱动自动不用']], ['不可重试'])),
]
A = mkartm('m55', 55, 'MongoDB,可重试写入,retryWrites,txnNumber,stmtId,幂等,真实验证,动画演示',
    '实测可重试写入:驱动重试带着同一个 lsid 和 txnNumber,计数器只加 1;服务端靠 oplog 条目上的 lsid / txnNumber / stmtId 去重,手写 OP_MSG 重发同一个请求返回 retriedStmtIds 而不再执行;insert 的整批重发只插入一次;update_many 不可重试;独立实例不支持事务号。',
    '网络断开后重试一次 $inc 会不会加两次?可重试写入是怎么避免重复执行的?这篇用 failpoint 制造连接断开,再手写 OP_MSG 把同一个请求发两次,看服务端的去重。',
    [('n = 1', '连接断开后驱动自动重试一次 $inc,最终计数器的值(没有加两次)'), ('retriedStmtIds', '服务端识别出重发的语句并返回缓存结果时的响应字段'), ('2 条', '两次不同的 txnNumber 对应的 oplog 条目数;重发没有产生新条目')],
    [('驱动重试', '<p>连接中断时驱动自动重发写命令,带着同一个 <code>lsid</code> 和 <code>txnNumber</code>;<code>retryWrites=False</code> 则直接抛错。</p>'),
     ('服务端去重', '<p>同一个 lsid + txnNumber 的重发,服务端不再执行,而是返回之前的结果并带上 <code>retriedStmtIds</code>。</p>'),
     ('靠什么', '<p>靠 oplog 条目里的 <code>lsid</code>、<code>txnNumber</code>、<code>stmtId</code> 和 <code>config.transactions</code> 里每个会话最后的事务号。</p>'),
     ('批量', '<p>批量 insert 的每条语句有自己的 stmtId,整批重发只会执行一次。</p>'),
     ('不能重试的', '<p>multi 的 update 和 delete 不可重试,遇到连接断开直接报错。</p>'),
     ('独立实例', '<p>事务号只允许副本集或 mongos,独立实例上驱动会自动关闭重试写。</p>')],
    steps,
    [ENV_M + '。单节点副本集启用 enableTestCommands 以使用 failCommand;去重演示用手写的 OP_MSG 客户端',
     '没有验证:响应在网络上丢失(服务端已执行)的真实场景(failCommand 的 closeConnection 发生在执行之前,执行后的重发用手写客户端模拟);重试次数与 retryReads;故障切换(primary 变化)时的重试;事务号的保留时间(会话过期后去重信息的清理);分片集群里 mongos 的重试'],
    '可重试写入')
