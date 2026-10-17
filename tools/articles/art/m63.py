from lib import *
S = SS('m63')
steps = [
    step("三种切主方式,一个每 5 ms 用 w:majority 写一次的客户端:A. 在 primary 上 replSetStepDown(优雅):动作之后的最大成功写入间隔只有 0.03 s(平时中位数 11 ms),retryWrites=True 与 False 都没有看到任何错误,确认写入 2,271 条(True)与 2,201 条(False)一条没丢;B. kill -9 primary(默认 electionTimeoutMillis 10 s):最大间隔 10.83 s,没有错误(驱动等到新 primary 后重试),确认的 1,466 条没丢;C. 同样 kill -9 但 electionTimeoutMillis 调成 4000(须大于心跳间隔 2000):最大间隔 4.19 s,没有错误,确认的 1,122 条没丢。", t=tl(S(1)), mark=lidx(S(1), '10.83 s', '4.19 s'), done=lidx(S(1), '0.03 s', '方式 A', '方式 B', '方式 C'), b=bars([['A. replSetStepDown', 0.03, '0.03 s'], ['C. kill -9,election 4 s', 4.19, '4.19 s'], ['B. kill -9,election 10 s', 10.83, '10.83 s']], 10.83, mark=[2], done=[0, 1]), kv=KV([['优雅切主', '约 30 ms,客户端 0 错误'], ['崩溃切主', '约等于 electionTimeoutMillis + 选举'], ['丢失', '三种都是 0 条(w:majority)']], ['丢失'])),
    step("汇总的不可写时间:replSetStepDown(优雅)0.03 s;kill -9 加默认 electionTimeoutMillis 10 s 是 10.83 s;kill -9 加 electionTimeoutMillis 4 s 是 4.19 s。electionTimeoutMillis 越小崩溃切主越快,但必须大于心跳间隔(默认 2 秒),也更容易把网络抖动误判成故障。", t=tl(S(2)), mark=lidx(S(2), 'kill -9,electionTimeoutMillis 10 s', 'kill -9,electionTimeoutMillis 4 s'), done=lidx(S(2), 'replSetStepDown(优雅)'), kv=KV([['replSetStepDown', '0.03 s'], ['4 秒选举超时', '4.19 s'], ['10 秒选举超时', '10.83 s']], ['10 秒选举超时'])),
    step("切主期间的读:primary 被 kill 后 14 秒,两个线程每 0.2 秒各读一次。secondary 读偏好:69 次读、0 次失败、单次最大耗时 5 ms,完全不受影响;primary 读偏好:18 次读、0 次失败,但有一次读阻塞了 10,465 ms(驱动等到新 primary 才返回)。", t=tl(S(3)), mark=lidx(S(3), 'primary 读偏好', '10465 ms'), done=lidx(S(3), 'secondary 读偏好', '69 次读'), b=bars([['secondary 读最大耗时', 5, '5 ms'], ['primary 读最大耗时', 10465, '10,465 ms']], 10465, mark=[1], done=[0]), kv=KV([['secondary 读', '不受影响'], ['primary 读', '阻塞约 10 秒后成功']], ['primary 读'])),
]
A = mkartm('m63', 63, 'MongoDB,stepDown,选举,故障切换,electionTimeoutMillis,副本集,真实验证,动画演示',
    '实测切主期间的不可用时间:replSetStepDown 优雅切主只有约 30 ms,客户端无错误;kill -9 primary 默认约 10.8 秒(electionTimeoutMillis 10 s),调成 4 s 后约 4.2 秒;w:majority 的确认写入一条未丢;切主期间 secondary 读不受影响,primary 读阻塞约 10 秒。',
    '切主期间读写不可用多久?优雅切主和崩溃切主差多少?调小 electionTimeoutMillis 有用吗?写入会不会丢?这篇用一个持续写入的客户端在 3 节点副本集上量三种切主方式的不可写时间。',
    [('0.03 s', 'replSetStepDown 优雅切主时客户端看到的最大写入间隔'), ('10.83 s', 'kill -9 primary(默认 electionTimeoutMillis 10 s)时的不可写时间'), ('0 条', '三种切主方式下 w:majority 确认写入丢失的条数')],
    [('三种切主方式', '<p>优雅切主(<code>replSetStepDown</code>)让 primary 等 secondary 追平后让位,不可写时间只有约 30 ms;kill -9 后 secondary 要等 <code>electionTimeoutMillis</code>(默认 10 秒)才发起选举,不可写时间约 10.8 秒;调到 4 秒则约 4.2 秒。<code>retryWrites</code> 的驱动等到新 primary 出现后重试,客户端没有看到错误,三种方式下 w:majority 确认的写入都没有丢失。</p>'),
     ('汇总与取舍', '<p>0.03 s、4.19 s、10.83 s。<code>electionTimeoutMillis</code> 越小崩溃切主越快,但必须大于心跳间隔(默认 2 秒),调得太小会增加误判。</p>'),
     ('切主期间的读', '<p>secondary 读偏好的读不受影响;primary 读偏好的读会阻塞到新 primary 出现(这里一次读阻塞了 10.5 秒)。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 副本集,本机回环(无网络分区);写入间隔 5 ms、w:majority;kill 与 stepDown 在启动 3 秒后执行',
     '没有验证:graceful stepDown 时 retryWrites=False 也没有看到错误的原因(只观察到现象);网络分区造成的切主(心跳超时的检测时间更复杂);priority 不同时的选举;catch-up 阶段(新 primary 追赶旧 primary 未复制的写入);大事务或长查询存在时 stepDown 的等待与强制关闭连接'],
    '切主期间的不可用时间')
