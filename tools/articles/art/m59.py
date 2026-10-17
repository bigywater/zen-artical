from lib import *
S = SS('m59')
steps = [
    step("复制延迟 = primary 的 optimeDate - secondary 的 optimeDate(replSetGetStatus)。持续写入下取 10 个样本,两个 secondary(9902、9903)的延迟都在 0~2 秒之间(optimeDate 是秒精度);hello 里的 lastWrite.lastWriteDate 与 majorityWriteDate 是客户端估算 staleness 的依据。", t=tl(S(1)), mark=lidx(S(1), '0~2'), done=lidx(S(1), 'lastWrite', 'majorityWrite'), kv=KV([['健康时', '0~2 秒'], ['计算方式', 'primary.optimeDate − secondary.optimeDate'], ['hello.lastWrite', '客户端估算 staleness 的数据']], ['健康时'])),
    step("用 failpoint stopReplProducer 让 9902 停止拉取 oplog,primary 继续写:停止后 5 s、35 s、65 s、95 s 时,9902 的延迟是 5 s、35 s、65 s、95 s——延迟随时间线性增长;另一个 secondary 9903 始终约 1 s。", t=tl(S(2)), mark=lidx(S(2), '停止拉取后    95 s', '停止拉取后    65 s'), done=lidx(S(2), '停止拉取后     5 s', '停止拉取后    35 s'), b=bars([['5 s', 5, '延迟 5 s'], ['35 s', 35, '延迟 35 s'], ['65 s', 65, '延迟 65 s'], ['95 s', 95, '延迟 95 s']], 95, mark=[3], done=[0, 1, 2]), kv=KV([['被停的 secondary', '延迟 = 停止的时间'], ['正常的 secondary', '约 1 s']], ['被停的 secondary'])),
    step("从 secondary 读,不设 maxStalenessSeconds:50 次读按 9902 19 次、9903 31 次分摊,其中读到明显落后(比 primary 少 5 次以上更新)的值 19 次——正是打到被停的 9902 的那些。", t=tl(S(3)), mark=lidx(S(3), '19 次'), done=lidx(S(3), '50 次 secondary 读'), kv=KV([['读分布', '两个 secondary 轮流'], ['旧值', '19 次,全是被停的那台']], ['旧值'])),
    step("加 maxStalenessSeconds=90:驱动估算每台 secondary 的 staleness,延迟约 95 s 的 9902 被排除,50 次读 49 次打到 9903、只有 1 次打到 9902、读到旧值 1 次——驱动对 staleness 的估算有滞后(靠心跳),刚越过 90 秒时还可能有少量请求漏进去。", t=tl(S(4)), mark=lidx(S(4), "'9902': 1"), done=lidx(S(4), "'9903': 49"), b=bars([['不设 maxStaleness', 19, '旧值 19 / 50'], ['maxStalenessSeconds=90', 1, '旧值 1 / 50']], 19, mark=[0], done=[1]), kv=KV([['不设', '19 次旧值'], ['maxStalenessSeconds=90', '1 次旧值'], ['原因', '驱动的 staleness 估算靠心跳,有滞后']], ['maxStalenessSeconds=90'])),
    step("maxStalenessSeconds 有下限:取 30 时读失败,ConfigurationError: maxStalenessSeconds must be at least 90. maxStalenessSeconds is set to 30.;取 90 可以。(它还不能小于 heartbeat + 10 秒。)", t=tl(S(5)), mark=lidx(S(5), 'must be at least 90'), done=lidx(S(5), 'max_staleness=90'), kv=KV([['下限', '90 秒'], ['错误', 'ConfigurationError(在选择服务器时抛出)']], ['下限'])),
    step("放开 failpoint 后 secondary 追上很快:延迟从约 95 秒经 3.0 s 降到 0——积压的 oplog 被批量拉取并应用。", t=tl(S(6)), mark=lidx(S(6), '3.0 s'), done=lidx(S(6), '延迟降到 0 s'), kv=KV([['积压 95 秒的 oplog', '3.0 s 追平'], ['追赶速度', '远快于积压形成的速度']], ['追赶速度'])),
]
A = mkartm('m59', 59, 'MongoDB,复制延迟,maxStalenessSeconds,secondary读,副本集,真实验证,动画演示',
    '实测复制延迟与 maxStalenessSeconds:健康时 0~2 秒;用 failpoint 让一个 secondary 停拉 oplog,延迟随时间线性增长到 95 秒;不设 maxStaleness 的 secondary 读 50 次有 19 次读到旧值,maxStalenessSeconds=90 的只有 1 次;下限 90 秒;放开后 3 秒追平。',
    '从 secondary 读会读到多旧的数据?怎么限制?这篇用 failpoint 制造一个落后 95 秒的 secondary,对比不设和设 maxStalenessSeconds 的读,看驱动怎样把它排除在外。',
    [('19 对 1 次', '50 次 secondary 读里读到旧值的次数:不设 maxStalenessSeconds 与设为 90'), ('95 s', '被停止拉取的 secondary 在 95 秒时的延迟(随时间线性增长)'), ('90 秒', 'maxStalenessSeconds 的下限')],
    [('怎么算延迟', '<p>用 <code>replSetGetStatus</code> 里 primary 与 secondary 的 <code>optimeDate</code> 之差;秒级精度,健康时 0~2 秒。</p>'),
     ('落后会累积', '<p>停止拉取的 secondary,延迟等于停止的时长:95 秒后延迟 95 秒。</p>'),
     ('不加限制', '<p>读偏好是 secondary 时,请求在两个 secondary 间分摊,落后的那台贡献了 19 次旧值读。</p>'),
     ('maxStalenessSeconds', '<p>设 90 后驱动排除 staleness 超过 90 秒的节点,50 次读只有 1 次漏到旧节点(估算靠心跳,有滞后)。</p>'),
     ('下限', '<p>最小 90 秒,也不能小于心跳间隔 + 10 秒;设 30 会报 ConfigurationError。</p>'),
     ('追赶', '<p>恢复拉取后积压的 oplog 批量应用,95 秒的积压 3 秒追平。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 副本集,enableTestCommands 用于 failpoint;落后通过 stopReplProducer 构造(不是真实的负载过高);旧值次数每次运行不同',
     '没有验证:真实的写负载过高、磁盘慢造成的延迟;flow control(流控)对延迟的限制;secondary 读加 w:majority 的写;maxStalenessSeconds 在分片集群(mongos)里的行为;staleness 的估算公式的精确细节'],
    '复制延迟与 maxStalenessSeconds')
