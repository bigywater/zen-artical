from lib import *
S = SS('m18')
steps = [
    step("queryPlanner(默认)模式不执行查询:db.t.find({a: 5, b: {$gte: 500}}) 的输出键只有 explainVersion、queryPlanner、queryShapeHash、command、serverInfo、serverParameters、ok,没有 executionStats(hasExecutionStats: false);赢家是 FETCH > IXSCAN(a_1_b_1),落选的是 FETCH > IXSCAN(b_1) 和 FETCH > IXSCAN(a_1)。", t=tl(S(1)), mark=lidx(S(1), 'hasExecutionStats: false', 'rejected'), done=lidx(S(1), "plan: 'FETCH > IXSCAN(a_1_b_1)'"), kv=KV([['queryPlanner', '不执行,只选计划'], ['赢家', 'a_1_b_1'], ['落选', 'b_1、a_1']], ['queryPlanner'])),
    step("executionStats 模式真的执行:返回 500 条(nReturned 500),检查 500 个键、500 个文档,耗时 0 ms;执行树沿 inputStage 展开是 FETCH(nReturned 500,works 501,advanced 500)和 IXSCAN(同样的 500 / 501 / 500)——works 比 advanced 多 1 是最后一次发现没有更多结果。", t=tl(S(2)), mark=lidx(S(2), 'works: 501', 'keysExamined: 500'), done=lidx(S(2), "stage: 'FETCH'", "stage: 'IXSCAN'"), kv=KV([['nReturned', '500'], ['keysExamined / docsExamined', '500 / 500(索引很精确)'], ['works', '501 = 500 个结果 + 1 次结束']], ['works'])),
    step("allPlansExecution 把落选候选计划的试跑统计也给出来:三个候选计划都只试跑到 works 101,各自 nReturned 分别是 101(赢家)、0 和 50,每个计划都检查了 101 个键、101 个文档——赢家在同样的 101 次 works 里返回得最多。", t=tl(S(3)), mark=lidx(S(3), 'nReturned: 101', 'nReturned: 0', 'nReturned: 50'), done=lidx(S(3), 'works: 101'), b=bars([['a_1_b_1(赢家)', 101, '101 条'], ['a_1', 50, '50 条'], ['b_1', 0, '0 条']], 101, mark=[1, 2], done=[0]), kv=KV([['候选计划', '3 个'], ['试跑', '每个 101 次 works'], ['谁返回得多', '谁赢']], ['候选计划'])),
    step("explain 不会真的修改数据:对 update 做 explain(a:5, b:505, $set z),阶段是 UPDATE,nWouldModify 100,docsExamined 100;对 delete {a: 5} 做 explain,阶段是 BATCHED_DELETE,nWouldDelete 1000;之后 countDocuments 仍是 100000,有 z 字段的文档是 0 个。", t=tl(S(4)), mark=lidx(S(4), "stage: 'UPDATE'", "stage: 'BATCHED_DELETE'"), done=lidx(S(4), '100000', '有 z 字段的 0 个'), kv=KV([['update 的 explain', 'nWouldModify 100'], ['delete 的 explain', 'nWouldDelete 1000'], ['数据', '一个都没改、没删']], ['数据'])),
    step("aggregate 的 explain:{$match: {a: 5, b: {$gte: 500}}} 加 {$group: {_id: \"$a\", n: {$sum: 1}}} 整个被下推进查询引擎,输出里没有 stages 字段,计划是 GROUP > PROJECTION_COVERED > IXSCAN(a_1_b_1),docsExamined 是 0——a 和 b 都在索引里,覆盖查询。", t=tl(S(5)), mark=lidx(S(5), 'GROUP > PROJECTION_COVERED', 'docsExamined: 0'), done=lidx(S(5), '没有 stages 字段'), kv=KV([['pipeline', '$match + $group 下推成一个计划'], ['PROJECTION_COVERED', '只读索引'], ['docsExamined', '0']], ['PROJECTION_COVERED'])),
    step("三种模式的信息量逐级增加:queryPlanner 的输出里没有 executionStats(false);executionStats 里的键是 executionSuccess、nReturned、executionTimeMillis、executionTimeMicros、totalKeysExamined、totalDocsExamined、executionStages;explain(true)(等价于 allPlansExecution)多出一个 allPlansExecution。", t=tl(S(6)), mark=lidx(S(6), "allPlans_extra: [ 'allPlansExecution' ]", 'queryPlanner_has_executionStats: false'), done=lidx(S(6), "'executionStages'", "'totalDocsExamined'"), kv=KV([['queryPlanner', '计划,不执行'], ['executionStats', '+ 实际执行统计'], ['allPlansExecution', '+ 候选计划的试跑统计']], ['executionStats'])),
]
A = mkartm('m18', 18, 'MongoDB,explain,queryPlanner,executionStats,allPlansExecution,真实验证,动画演示',
    '同一条查询在 explain 的三种模式下看到的信息:queryPlanner 只选计划不执行,executionStats 执行并给出键数、文档数和每个阶段的 works,allPlansExecution 再给出落选计划的试跑统计;update / delete 的 explain 不修改数据;aggregate 的 pipeline 被整个下推并成为覆盖查询。',
    'explain 的 queryPlanner、executionStats、allPlansExecution 有什么区别?哪一种会真的执行?这篇用 10 万个文档和三个候选索引,在同一条查询上把三种模式的输出逐个拆开,再验证 update / delete / aggregate 的 explain。',
    [('3 个候选', '同一条查询有 a_1、b_1、a_1_b_1 三个候选计划,allPlansExecution 里各试跑了 101 次 works'), ('500 / 500', 'executionStats 里这条查询检查的键数 / 文档数,等于返回的 500 条'), ('不修改数据', '对 update 和 delete 做 explain 之后,文档数仍是 100000')],
    [('queryPlanner', '<p>默认模式只做计划选择,不执行查询,输出里没有 executionStats;能看到赢家(这里是复合索引 <code>a_1_b_1</code>)和落选的计划。</p>'),
     ('executionStats', '<p>真的执行查询,给出 <code>nReturned</code>、<code>totalKeysExamined</code>、<code>totalDocsExamined</code> 和每个阶段的 works / advanced。</p>'),
     ('allPlansExecution', '<p>在 executionStats 之上多出 <code>allPlansExecution</code>:每个候选计划试跑的统计,可以看到赢家在同样的 works 里返回得最多。</p>'),
     ('写操作的 explain', '<p>对 update、delete 做 explain 只给出会修改 / 删除多少文档(<code>nWouldModify</code>、<code>nWouldDelete</code>),数据不变。</p>'),
     ('aggregate', '<p>aggregate 的 explain 里 <code>$match</code> 与 <code>$group</code> 可以一起下推,整个 pipeline 成为一个计划;字段都在索引里时还是覆盖查询。</p>'),
     ('三种模式的差别', '<p>queryPlanner &lt; executionStats &lt; allPlansExecution,信息量逐级增加;<code>explain(true)</code> 等价于 allPlansExecution。</p>')],
    steps,
    [ENV_M + '。数据是 10 万个文档(a = i % 100,b = i % 1000),候选索引 a_1、b_1、a_1_b_1;所有输出来自 mongosh 的 explain',
     '没有验证:分片集群上的 explain 输出(shards 字段);explain 里 slot-based 执行(SBE)与经典引擎的字段差异(这里的 find 走经典引擎,aggregate 下推后的 queryPlan 层级不同);executionTimeMillis 在慢查询上的精度;explain 对计划缓存的影响;queryShapeHash 的用途'],
    'explain 三种模式')
