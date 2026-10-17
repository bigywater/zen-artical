from lib import *
S = SS('m52')
steps = [
    step("健康的 3 节点副本集上各读关注读到的都是 'old';延迟(500 次 _id 读的中位数):local 0.15 ms,available 0.10 ms,majority 0.09 ms,snapshot 0.10 ms,linearizable 4.81 ms(p99 8.05 ms)——只有 linearizable 明显更慢,因为要确认自己仍是 primary 且多数节点同意。", t=tl(S(1)), mark=lidx(S(1), 'linearizable  读到'), done=lidx(S(1), 'local  ', 'available', 'majority  ', 'snapshot'), b=bars([['local', 0.15, '0.15 ms'], ['available', 0.1, '0.10 ms'], ['majority', 0.09, '0.09 ms'], ['snapshot', 0.1, '0.10 ms'], ['linearizable', 4.81, '4.81 ms']], 4.81, mark=[4], done=[0, 1, 2, 3]), kv=KV([['local / available / majority / snapshot', '约 0.1 ms'], ['linearizable', '约 4.8 ms,要多数确认']], ['linearizable'])),
    step("构造“写入 primary 但还没被多数确认”的窗口:kill 两个 secondary,在 primary 因看不到多数而降级前(约 10 秒)用 w:1 把 v 改成 \"NEW\"。读关注 local 读到 'NEW',majority 读到 'old'(还没被多数确认);linearizable 加 max_time_ms=3000 等了 3,002 ms,报 ExecutionTimeout(code 50);同时发起的 w:majority 写等不到多数,WTimeoutError(code 64)。", t=tl(S(2)), mark=lidx(S(2), 'readConcern local', 'readConcern majority', 'linearizable(max_time_ms', 'WTimeoutError'), done=lidx(S(2), '已 kill 两个 secondary'), kv=KV([['local', '读到 NEW(自己的写入)'], ['majority', '读到 old'], ['linearizable', '等不到多数,超时 code 50'], ['w:majority 写', '超时 code 64']], ['majority'])),
    step("10 秒后 primary 因看不到多数降级(isWritablePrimary = False);在这个已降级的节点上 local 读 'NEW',majority 读 'old'——这次写入没有被多数确认。", t=tl(S(3)), mark=lidx(S(3), 'readConcern majority', 'isWritablePrimary = False'), done=lidx(S(3), 'readConcern local'), kv=KV([['降级后', 'local 仍能读到 NEW'], ['majority', '读 old,因为还没被多数确认']], ['降级后'])),
    step("恢复两个 secondary 后重新选出 primary,“NEW” 被复制出去(这次它被多数确认了):local 与 majority 都读到 'NEW'。(随后的 w:majority 写的 x: 1 也在,w:majority 超时不等于写入失败。)", t=tl(S(4)), mark=lidx(S(4), 'readConcern majority'), done=lidx(S(4), 'readConcern local'), kv=KV([['恢复后', 'NEW 被多数确认'], ['majority', '读到 NEW'], ['超时的 w:majority 写', '最终也生效']], ['恢复后'])),
    step("snapshot 读关注:事务外的 find 带 readConcern snapshot 在这台 9.0.2 上也能执行,返回 {'_id': 1, 'v': 'NEW', 'x': 1};在事务里 snapshot 读同样返回这个文档。", t=tl(S(5)), mark=lidx(S(5), '事务外'), done=lidx(S(5), '事务内'), kv=KV([['事务外 find + snapshot', '可以执行'], ['事务内', 'snapshot 读']], ['事务外 find + snapshot'])),
    step("默认读关注:getDefaultRWConcern 的 defaultReadConcern 是 { level: 'local' };explain 里能看到命令带的读关注:find 加 .readConcern(\"majority\") 的 explain().command.readConcern 是 { level: 'majority' }。", t=tl(S(6)), mark=lidx(S(6), "level: 'majority'"), done=lidx(S(6), "level: 'local'"), kv=KV([['默认', 'local'], ['集群默认', 'getDefaultRWConcern 可看可改'], ['单次', '.readConcern(...)']], ['默认'])),
]
A = mkartm('m52', 52, 'MongoDB,读关注,readConcern,majority,linearizable,副本集,真实验证,动画演示',
    '实测读关注 local、majority、snapshot、linearizable:健康时 local / majority / snapshot 都约 0.1 ms,linearizable 约 4.8 ms;构造“写入 primary 但未被多数确认”时 local 读到 NEW、majority 读到 old、linearizable 超时(code 50);恢复后 majority 也读到 NEW。',
    '读关注到底决定读到什么?majority 为什么读不到刚写的数据?linearizable 代价多大?这篇在 3 节点副本集上先测健康时的延迟,再 kill 两个 secondary 制造“未被多数确认”的窗口,逐个读关注对比。',
    [('NEW 对 old', 'primary 上 w:1 写入、未被多数确认时,local 与 majority 读到的值'), ('4.8 对 0.1 ms', 'linearizable 与其它读关注的单次读延迟'), ('code 50', 'linearizable 在多数不可用时 max_time_ms 超时的错误码')],
    [('健康时', '<p>local、available、majority、snapshot 的读延迟几乎一样(约 0.1 ms);linearizable 要确认仍是 primary 且被多数认可,约 4.8 ms。</p>'),
     ('未被多数确认的写入', '<p>kill 两个 secondary 后,primary 上 <code>w:1</code> 写入的值,<code>local</code> 读得到,<code>majority</code> 读到旧值,<code>linearizable</code> 等不到多数而超时(code 50)。</p>'),
     ('primary 降级后', '<p>10 秒后 primary 因看不到多数而降级;local 读仍然是 NEW,majority 仍是 old。</p>'),
     ('恢复之后', '<p>secondary 恢复、写入被复制到多数后,majority 读也看到了 NEW。w:majority 超时的写入最终也生效。</p>'),
     ('snapshot', '<p>事务里的默认读;事务外 find 指定 snapshot 在这个版本上也能执行。</p>'),
     ('默认值', '<p>默认读关注是 <code>local</code>,集群可通过 <code>setDefaultRWConcern</code> 修改,单次读可用 <code>.readConcern()</code> 覆盖。</p>')],
    steps,
    [ENV_M + '。3 个 mongod 组成的副本集;未确认窗口通过 kill -9 两个 secondary 构造(约 10 秒内要完成读写)',
     '没有验证:majority 读在 secondary 上的延迟(需要等 commit point 前进);读关注 available 在分片集群上返回孤儿文档的行为;afterClusterTime 配合因果一致性(下一篇);回滚后 local 读到的数据被撤销(后面 rollback 一篇);snapshot 的 atClusterTime 参数'],
    '读关注')
