from lib import *
S = SS('m79')
steps = [
    step("空闲的 mongod:serverStatus.queues.execution.read.normalPriority 是 out 0、available 10、totalTickets 10,write.normalPriority 同样是 10 个;相关参数 executionControlConcurrencyAdjustmentAlgorithm = throughputProbing,executionControlConcurrentReadTransactions / WriteTransactions = 128(上限)。9.0.2 里 ticket 数从 10 开始,由吞吐探测自己调。", t=tl(S(1)), mark=lidx(S(1), 'read.normalPriority', 'write.normalPriority', '参数:'), done=lidx(S(1), 'read.normalPriority'), kv=KV([['read ticket', 'out 0 / available 10 / total 10'], ['write ticket', 'total 10'], ['算法', 'throughputProbing'], ['参数上限', '128']], ['算法'])),
    step("一个 sleep(300) 的慢读单独跑要 683~1003 ms(基线,第一次含预热)。40 个并发同时开始:最快 822 ms、中位数 1808 ms、最慢 3052 ms,全部做完共 3057 ms;采样到 out 最大 = 11、queueLength 最大 = 29——同时只有约 10 个在跑,其余排队,耗时呈一波一波的台阶(600~3000 ms 各档都有)。结束后 totalTickets 变成 9,addedToQueue +32。", t=tl(S(2)), mark=lidx(S(2), '40 个并发', '耗时分布'), done=lidx(S(2), '单个慢读的耗时'), b=bars([['单个', 700, '~700 ms'], ['40 并发 最快', 822, '822 ms'], ['40 并发 中位数', 1808, '1808 ms'], ['40 并发 最慢', 3052, '3052 ms']], 3052, mark=[3], done=[0, 1, 2]), kv=KV([['out 最大', '11'], ['queueLength 最大', '29'], ['最慢 / 最快', '3052 / 822 ms'], ['结束后 totalTickets', '9']], ['queueLength 最大'])),
    step("throughputProbing 会自己调:64 个线程持续发慢读 30 秒,每 3 秒取一次——totalTickets 是 11、11、11、12、12、12、13、13、13、13(out 与之相同,queueLength 51~53)。涨得很慢,30 秒后也只有 13,远没到 128。", t=tl(S(3)), mark=lidx(S(3), '(秒, totalTickets'), done=lidx(S(3), '(秒, totalTickets'), b=bars([['3 秒', 11, '11'], ['15 秒', 12, '12'], ['30 秒', 13, '13']], 13, mark=[2], done=[0, 1]), kv=KV([['3 秒', 'totalTickets 11'], ['15 秒', '12'], ['30 秒', '13,queueLength 51']], ['30 秒'])),
    step("固定并发:executionControlConcurrencyAdjustmentAlgorithm 改成 fixedConcurrentTransactions。读 ticket 设成 4 被拒:code 2 BadValue: Concurrent read transactions limit must be greater than or equal to 5.;设成 5 通过(was: 128),totalTickets = 5。16 个并发慢读:out 最大 = 5、queueLength 最大 = 11,最快 686 ms、中位数 2044 ms、最慢 2736 ms,分布成约 4 档台阶。", t=tl(S(4)), mark=lidx(S(4), 'code 2 BadValue', '=5:', '16 个并发', '耗时分布'), done=lidx(S(4), 'fixedConcurrentTransactions'), kv=KV([['设成 4', 'BadValue,必须 ≥ 5'], ['设成 5', 'totalTickets = 5'], ['16 并发 out 最大', '5'], ['最慢', '2736 ms']], ['设成 4'])),
    step("同样的 16 个并发,ticket 放大到 128:out 最大 = 16、queueLength 最大 = 0,最快 679 ms、中位数 982 ms、最慢 1197 ms,全部做完共 1198 ms(ticket = 5 时是 2737 ms)——没有排队,耗时只剩操作本身。", t=tl(S(5)), mark=lidx(S(5), '16 个并发', '耗时分布'), done=lidx(S(5), 'was'), b=bars([['ticket = 5 总耗时', 2737, '2737 ms'], ['ticket = 128 总耗时', 1198, '1198 ms']], 2737, mark=[1], done=[0]), kv=KV([['out 最大 / queueLength 最大', '16 / 0'], ['最慢', '1197 ms(ticket=5 时 2736 ms)'], ['总耗时', '1198 ms']], ['总耗时'])),
    step("serverStatus 的排队统计(两次 burst 前后的增量):ticket = 5 时 addedToQueue +13、removedFromQueue +13、totalTimeQueuedMicros +14,479,520、finishedProcessing +32,排队的操作平均排队约 1114 ms;ticket = 128 时全是 +0,没有排队。", t=tl(S(6)), mark=lidx(S(6), 'ticket = 5', 'ticket = 128'), done=lidx(S(6), 'ticket = 5'), kv=KV([['ticket = 5', 'addedToQueue +13,平均排队 1114 ms'], ['ticket = 128', '+0,没有排队']], ['ticket = 5'])),
]
A = mkartm('m79', 79, 'MongoDB,WiredTiger,ticket,并发,executionControl,throughputProbing,真实验证,动画演示',
    '实测 9.0.2 的读写 ticket:初始 10 个、由 throughputProbing 缓慢调整(64 线程持续 30 秒只涨到 13);40 个并发慢读最快 822 ms、最慢 3052 ms 且排队 29 个;改成固定并发后 ticket 下限为 5(设 4 返回 BadValue),16 并发总耗时 2737 ms,放大到 128 后 1198 ms 且不排队。',
    'WiredTiger 的读写 ticket 是什么?9.0 里还是 128 吗?并发超过 ticket 数时排队有多严重?这篇用 serverStatus 的 queues 对着真实排队验证。',
    [('10', '空闲时 read / write 的 totalTickets(上限参数 128)'), ('29', '40 个并发慢读时 queueLength 的最大值'), ('2737 → 1198 ms', '16 个并发慢读,ticket 5 与 128 的总耗时')],
    [('初始 ticket', '<p>9.0.2 的 <code>queues.execution.read/write.normalPriority</code> 初始 <code>totalTickets</code> 是 10,<code>executionControlConcurrentReadTransactions</code> 等参数是上限 128。</p>'),
     ('排队', '<p>40 个并发慢读时只有约 10 个同时在跑,<code>queueLength</code> 最大 29,最慢的操作比最快的多等了两秒多。</p>'),
     ('throughputProbing', '<p>持续高负载下 ticket 数自己调整,但很慢:30 秒内只从 11 涨到 13。</p>'),
     ('固定并发', '<p>改成 <code>fixedConcurrentTransactions</code> 后读 ticket 不能低于 5;设成 5 时 16 个并发慢读排队、总耗时 2737 ms。</p>'),
     ('放大 ticket', '<p>ticket 放大到 128,同样的负载没有排队,总耗时 1198 ms。</p>'),
     ('排队统计', '<p>ticket = 5 时 <code>addedToQueue +13</code>,平均排队约 1114 ms;ticket = 128 时全是 0。</p>')],
    steps,
    [ENV_M + '。单机 mongod;用 $where 里 sleep(300) 的 find 占住 ticket,不是真实的磁盘/CPU 负载',
     '没有验证:真实 CPU 或磁盘密集负载下 throughputProbing 如何调整(sleep 的操作吞吐随并发线性增长,可能与真实负载不同);写 ticket 的行为;低优先级 ticket(lowPriority)与 deprioritization;同一个 find 为什么单独跑要 700 ms 以上(sleep(300) 的 JS 谓词被多次评估,没有进一步确认);旧版本 wiredTigerConcurrentReadTransactions 参数与 128 的默认值;在 Linux 多核机器上的结果'],
    'WiredTiger ticket')
