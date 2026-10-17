from lib import *
S = SS('m50')
steps = [
    step("打开 change stream,插入 _id 1、2 并更新 _id 1:收到 insert(_id 1)、insert(_id 2)、update(_id 1)三个事件;事件的键是 _id、clusterTime、documentKey、fullDocument、ns、operationType、wallTime;前两个 insert 来自同一次批量写入,clusterTime 都是 Timestamp(…, 20),但它们的 resume token 不同;update 的 clusterTime 是 (…, 21)。", t=tl(S(1)), mark=lidx(S(1), 'update  ns', 'clusterTime=Timestamp(1791775093, 21)'), done=lidx(S(1), 'insert  ns', '事件的键'), kv=KV([['事件', '_id(resume token)、operationType、ns、documentKey、clusterTime…'], ['批量写入', '同一个 clusterTime,token 不同']], ['事件'])),
    step("resume token 的 _data 是十六进制串(总长 83 字节),第 1 个字节 0x82 是类型,后 8 字节解码出来就是 clusterTime:Timestamp(1791775093, 20)、Timestamp(1791775093, 20)、Timestamp(1791775093, 21),都与事件的 clusterTime 相等(True)——token 里编码了 oplog 位置。", t=tl(S(2)), mark=lidx(S(2), '相等: True', '总长 83 字节'), done=lidx(S(2), '0x82'), kv=KV([['首字节', '0x82,类型'], ['后 8 字节', 'clusterTime(秒 + 序号)'], ['总长', '83 字节']], ['后 8 字节'])),
    step("resumeAfter:读完前 2 个事件后“崩溃”,用第 2 个事件的 token 重新打开,收到 1 个事件 update 1,正是原来的第 3 个事件,不丢不重;之后的新写入(insert 3)也能收到。", t=tl(S(3)), mark=lidx(S(3), 'update 1', 'insert 3'), done=lidx(S(3), '从第 2 个事件的 token 继续'), kv=KV([['resumeAfter 第 2 个事件的 token', '从第 3 个事件继续'], ['不丢不重', '正好衔接']], ['resumeAfter 第 2 个事件的 token'])),
    step("startAtOperationTime:用 hello 拿到的 operationTime=Timestamp(1791775096, 1)(当时最后一次写入的时间)开始,收到 [3, 100, 101]——含该时间点的那次写入(_id=3)和之后的写入。", t=tl(S(4)), mark=lidx(S(4), '[3, 100, 101]'), done=lidx(S(4), 'operationTime'), kv=KV([['startAtOperationTime', '从一个时间点开始'], ['含', '该时间点的那次写入']], ['startAtOperationTime'])),
    step("空闲 stream 的 token 也会前进(postBatchResumeToken):stream 监视 test.t,往其它集合写 1000 条之后(本 stream 没有任何事件),stream 的 resume_token 从 826ACC5179000000032B… 变成 …05…,前进了(True),这样恢复时不会回到很久以前。", t=tl(S(5)), mark=lidx(S(5), 'token 前进了: True'), done=lidx(S(5), 'token 前'), kv=KV([['空闲 stream', 'resume_token 仍随 oplog 前进'], ['好处', '恢复时不会因 token 太旧而失败']], ['空闲 stream'])),
    step("token 的位置不在某个节点的 oplog 窗口里时恢复失败:新加入的成员做完 initial sync(2 s),它的 oplog 最早一条 ts 是 Timestamp(1791775102, 6),比 primary 的 (1791775093, 1) 晚;在这个新成员上(secondary 读偏好)用最旧事件的 token(clusterTime (1791775093, 20))恢复,报 code=286 ChangeStreamHistoryLost:Resume of change stream was not possible, as the resume point may no longer be in the oplog;在 primary 上用同一个 token 恢复成功。", t=tl(S(6)), mark=lidx(S(6), 'code=286', '在新成员'), done=lidx(S(6), '在 primary 上用同一个旧 token 恢复', 'oplog 最早一条 ts'), b=bars([['primary 的 oplog 起点', 0, '(…093, 1)'], ['token 的位置', 0, '(…093, 20)'], ['新成员的 oplog 起点', 9, '(…102, 6) 更晚']], 9, mark=[2], done=[0, 1]), kv=KV([['token', '编码 oplog 位置'], ['oplog 窗口', '比 token 位置更晚'], ['结果', '286 ChangeStreamHistoryLost']], ['结果'])),
]
A = mkartm('m50', 50, 'MongoDB,change stream,resume token,oplog,ChangeStreamHistoryLost,真实验证,动画演示',
    '实测 change stream 的 resume token:_data 是 83 字节的十六进制串,首字节 0x82 后 8 字节就是 clusterTime;用第 2 个事件的 token 恢复从第 3 个事件继续,不丢不重;空闲 stream 的 token 也随 oplog 前进;token 的位置不在节点的 oplog 窗口里(新成员 oplog 起点更晚)时恢复报 286 ChangeStreamHistoryLost。',
    'change stream 的 resume token 里有什么?断线后怎么恢复才不丢不重?token 太旧会怎样?这篇解码 token、实测 resumeAfter 与 startAtOperationTime,并用刚做完 initial sync 的新成员构造出 oplog 窗口不够的情形。',
    [('0x82 + 8 字节', 'resume token 的编码:首字节类型,后 8 字节就是 clusterTime'), ('286', 'token 对应的位置不在 oplog 窗口里时的错误码 ChangeStreamHistoryLost'), ('不丢不重', '用第 2 个事件的 token 恢复后从第 3 个事件继续')],
    [('事件与 token', '<p>每个事件的 <code>_id</code> 就是 resume token。同一次批量写入的多个事件 clusterTime 相同,但 token 不同。</p>'),
     ('token 编码了 oplog 位置', '<p><code>_data</code> 的首字节 0x82 后面 8 个字节就是 clusterTime(秒加序号),实测与事件的 <code>clusterTime</code> 完全一致。</p>'),
     ('恢复', '<p>用 <code>resumeAfter</code> 传第 N 个事件的 token,从第 N+1 个事件继续,不丢不重;<code>startAtOperationTime</code> 则从一个时间点开始(含该时间点的写入)。</p>'),
     ('空闲 stream', '<p>没有匹配事件时,stream 的 <code>resume_token</code> 仍随 oplog 前进(postBatchResumeToken),所以用它恢复不会因 token 太旧而失败。</p>'),
     ('token 太旧', '<p>token 对应的位置不在节点的 oplog 里就无法恢复:新加入的成员 oplog 只从同步点开始,用旧 token 在它上面恢复报 286。</p>'),
     ('怎么避免', '<p>要及时保存最新的 token,并保证 oplog 窗口(见后面 oplog 窗口一篇)足够覆盖消费者可能停机的时间。</p>')],
    steps,
    [ENV_M + '。单节点副本集(oplog 128 MB),第 6 节再加一个 priority 0 的成员',
     '没有验证:primary 自己的 oplog 被覆盖后的恢复失败(我试图把 128 MB 的单节点 oplog 写到约 976 MB,最早的条目始终没有被截断,原因没有查明,所以改用新成员构造);分片集群上的 change stream token(包含各分片的位置);startAfter 与 invalidate 事件;预镜像(changeStreamPreAndPostImages)的 token'],
    'change stream 的 resume token')
