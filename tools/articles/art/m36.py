from lib import *
S = SS('m36')
steps = [
    step("20 万个文档,a 上有索引:find({a: 1234}) 可见时是 FETCH > IXSCAN(a_1),检查 40 个文档;hideIndex(\"a_1\") 返回 { hidden_old: false, hidden_new: true } 之后,同一条查询变成 COLLSCAN,检查 200,000 个文档;unhideIndex 之后立刻又是 IXSCAN。耗时(9 次中位数):可见 0.2 ms,隐藏 28 ms,取消隐藏 0.3 ms。", t=tl(S(1)), mark=lidx(S(1), "plan: 'COLLSCAN'", 'hidden_new: true', '隐藏 28 ms'), done=lidx(S(1), "plan: 'FETCH > IXSCAN(a_1)'", 'hidden_new: false'), b=bars([['可见', 0.2, '0.2 ms'], ['隐藏', 28, '28 ms'], ['取消隐藏', 0.3, '0.3 ms']], 28, mark=[1], done=[0, 2]), kv=KV([['隐藏', '优化器不再考虑它'], ['代价', '0.2 ms → 28 ms,瞬间可逆'], ['取消隐藏', '立刻恢复']], ['隐藏'])),
    step("getIndexes 里隐藏的索引带 hidden: true('a_1 (hidden)');$indexStats 里 a_1 的 accesses.ops 在隐藏期间是 0,又查两次 a 之后仍是 0;取消隐藏后查一次 a,ops 变成 1。", t=tl(S(2)), mark=lidx(S(2), "ops: Long('1')"), done=lidx(S(2), "a_1 (hidden)", "ops: Long('0')"), kv=KV([['hidden: true', 'getIndexes 里的标记'], ['访问计数', '隐藏期间不增加'], ['取消隐藏', '重新计数']], ['访问计数'])),
    step("隐藏的索引仍然被维护:隐藏 a_1 后插入 2 个 a=999999 的文档,validate 显示 _id_、a_1、b_1、u_1 都是 200002 条;取消隐藏后立刻 find({a: 999999}) 返回 2 个,计划是 FETCH > IXSCAN(a_1),检查 2 个键。", t=tl(S(3)), mark=lidx(S(3), 'keysExamined: 2'), done=lidx(S(3), "a_1': 200002", '  2'), kv=KV([['隐藏期间的写入', '照常写进索引'], ['取消隐藏', '不用重建,立刻可用']], ['隐藏期间的写入'])),
    step("对隐藏的索引用 hint:hint(\"a_1\") 和 hint({a: 1}) 都报 code 2,message 以 hint provided does not correspond to an existing index 结尾——隐藏的索引对 hint 也是“不存在”。", t=tl(S(4)), mark=lidx(S(4), 'code: 2'), done=lidx(S(4), 'does not correspond to an existing index'), kv=KV([['hint 隐藏的索引', 'code 2 报错'], ['原因', '对计划器它不存在']], ['hint 隐藏的索引'])),
    step("隐藏不改变索引的约束作用:隐藏唯一索引 u_1 后插入重复的 u=5 仍报 E11000 duplicate key ... dup key: { u: 5 };隐藏的 TTL 索引 c_ttl 上插入 10 个已过期文档,4 秒后剩余 0 个——TTL 照常删除。", t=tl(S(5)), mark=lidx(S(5), 'E11000', '剩余: 0 个'), done=lidx(S(5), 'hidden_new: true'), kv=KV([['隐藏的唯一索引', '仍然拒绝重复'], ['隐藏的 TTL 索引', '仍然过期文档'], ['影响的只是', '优化器是否选它']], ['隐藏的唯一索引'])),
    step("限制:hideIndex(\"_id_\") 报 can't hide _id index;不存在的索引名报 cannot find index nope for ns test.t;hideIndex 会清空该集合的计划缓存:隐藏前有 1 个缓存条目,hideIndex(\"b_1\") 之后是 0。", t=tl(S(6)), mark=lidx(S(6), "can't hide _id index", 'cannot find index', '[ 1, 0 ]'), done=lidx(S(6), '隐藏前缓存条目数'), kv=KV([['_id 索引', '不能隐藏'], ['计划缓存', '隐藏 / 取消隐藏会清空']], ['_id 索引'])),
]
A = mkartm('m36', 36, 'MongoDB,隐藏索引,hideIndex,索引,计划器,真实验证,动画演示',
    '实测隐藏索引:hideIndex 之后优化器不再考虑它(0.2 ms 变成 28 ms 全表扫描),unhideIndex 立刻恢复;隐藏的索引仍然被维护(隐藏期间写入的数据取消隐藏后立即可查),唯一与 TTL 约束照常工作,hint 视其为不存在,$indexStats 不再计数。',
    '不确定能不能删一个索引?隐藏它!这篇验证隐藏索引的行为:查询计划、访问计数、写入维护、唯一与 TTL 约束、hint 以及限制,说明它为什么是“删除索引前的安全开关”。',
    [('0.2 → 28 ms', '同一条查询在索引可见与被隐藏时的耗时'), ('200002', '隐藏期间插入后每个索引仍然被维护的条目数'), ('0 个', '隐藏的 TTL 索引上 4 秒后剩余的过期文档数(TTL 照常工作)')],
    [('隐藏与可见', '<p>隐藏后优化器不再考虑这个索引,同一条查询从 <code>IXSCAN</code> 变成 <code>COLLSCAN</code>(0.2 ms 变 28 ms);取消隐藏立刻恢复,不需要重建。</p>'),
     ('可观测', '<p><code>getIndexes</code> 里有 <code>hidden: true</code>;<code>$indexStats</code> 的访问计数在隐藏期间不增长,可以用来评估“如果删掉它会怎样”。</p>'),
     ('仍被维护', '<p>隐藏的索引照常随写入更新:隐藏期间插入的文档,取消隐藏后马上可以用索引查到。</p>'),
     ('hint', '<p>隐藏的索引对 <code>hint</code> 也相当于不存在,报 code 2。</p>'),
     ('约束照常', '<p>隐藏的唯一索引仍然拒绝重复,隐藏的 TTL 索引仍然过期文档;隐藏只影响优化器。</p>'),
     ('限制', '<p>不能隐藏 <code>_id</code> 索引;隐藏与取消隐藏都会清空该集合的计划缓存。</p>')],
    steps,
    [ENV_M + '。20 万个文档;耗时是 pymongo 的 9 次中位数;TTL 监控间隔调到 1 秒',
     '没有验证:隐藏索引对内存/磁盘空间的节省(它并不节省);副本集上 hideIndex 的传播;隐藏部分索引或多键索引;隐藏索引后长时间观察线上流量的流程;分片集合上的 hideIndex'],
    '隐藏索引')
