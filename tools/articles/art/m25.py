from lib import *
S = SS('m25')
steps = [
    step("查询 {a: 3, b: 8}(20 万个文档,a 有 5 个取值不挑,b 有 1000 个取值很挑)有 a_1 和 b_1 两个候选索引。allPlansExecution 里两个候选各试跑 101 次 works:IXSCAN(b_1) > FETCH 返回 101 条,IXSCAN(a_1) > FETCH 只返回 1 条;赢家是 b_1,落选的是 a_1。", t=tl(S(1)), mark=lidx(S(1), 'nReturned: 1,', "winner: 'FETCH > IXSCAN(b_1)'"), done=lidx(S(1), 'nReturned: 101', 'works: 101'), b=bars([['b_1', 101, '101 次 works 返回 101 条'], ['a_1', 1, '101 次 works 返回 1 条']], 101, mark=[1], done=[0]), kv=KV([['试跑', '每个候选计划跑一小段'], ['比较', '同样 works 里谁返回得多'], ['赢家', 'b_1']], ['比较'])),
    step("试跑的上限是服务端参数:internalQueryPlanEvaluationMaxResults 101(最多取 101 条结果)、internalQueryPlanEvaluationWorks 10000(最多 works 次数)、internalQueryPlanEvaluationCollFraction 0.3(不超过集合文档数的 30%);plan cache 相关的 internalQueryCacheEvictionRatio 10、internalQueryCacheWorksGrowthCoefficient 2。", t=tl(S(2)), mark=lidx(S(2), 'MaxResults: 101', 'CollFraction: 0.3'), done=lidx(S(2), 'Works: 10000', 'EvictionRatio: 10'), kv=KV([['MaxResults', '101 条结果'], ['Works', '10000 次'], ['CollFraction', '集合的 30%'], ['plan cache', 'EvictionRatio 10、GrowthCoefficient 2']], ['MaxResults'])),
    step("把 internalQueryPlanEvaluationMaxResults 调成 10:同一条查询,b_1 的试跑只跑了 10 次 works、返回 10 条,a_1 同样只跑 10 次、返回 1 条——试跑在第一个计划返回 10 条时结束,其余候选陪跑到同样的 works。", t=tl(S(3)), mark=lidx(S(3), 'nReturned: 10', 'works: 10'), done=lidx(S(3), 'was: 101', 'was: 10'), kv=KV([['MaxResults=10', '试跑缩短到 10 次 works'], ['陪跑', '其它候选跑到同样的 works']], ['陪跑'])),
    step("没有阻塞排序的计划更占便宜:{a: 3} 按 c 排序,候选是 c_1(按 c 的索引顺序扫、边扫边过滤 a)和 a_1(取出 a=3 的再内存 SORT)。试跑 497 次 works:c_1 返回 101 条,a_1 + FETCH + SORT 返回 0 条——SORT 是阻塞阶段,要读完全部才会出第一条;赢家是 c_1。加了 limit(10) 之后赢家仍是 c_1,只检查 56 个键。", t=tl(S(4)), mark=lidx(S(4), 'nReturned: 0', 'IXSCAN(a_1) > FETCH > SORT'), done=lidx(S(4), 'nReturned: 101', 'keysExamined: 56'), b=bars([['c_1(按索引顺序,无 SORT)', 101, '497 次 works 返回 101 条'], ['a_1 + SORT', 0, '497 次 works 返回 0 条']], 101, mark=[1], done=[0]), kv=KV([['SORT', '阻塞,试跑期间出不来结果'], ['c_1 的赢面', '边扫边出结果'], ['limit 10', '只检查 56 个键']], ['SORT'])),
    step("一个计划在试跑里就扫完全部结果,直接获胜:查询 {c: 5000, a: {$gte: 0}} 只有 2 条结果,c_1 候选 3 次 works 就返回了 2 条(到达末尾),a_1 候选 3 次 works 返回 0 条;赢家是 c_1。", t=tl(S(5)), mark=lidx(S(5), 'nReturned: 2', "winner: 'FETCH > IXSCAN(c_1)'"), done=lidx(S(5), 'works: 3'), kv=KV([['结果很少', '试跑几次 works 就结束'], ['返回得多的赢', 'c_1 返回 2 条']], ['结果很少'])),
    step("试跑选出的计划在完整执行里的表现:对 {a: 3, b: 8} 逐个 hint,a_1 要 16 ms,b_1 0.5 ms,c_1 135 ms(扫整个 c 索引);不 hint 让优化器选是 0.3 ms,选中了最快的 b_1。", t=tl(S(6)), mark=lidx(S(6), 'hint(c_1)', 'hint(a_1)'), done=lidx(S(6), 'hint(b_1)', '不 hint'), b=bars([['hint a_1', 16, '16 ms'], ['hint b_1', 0.5, '0.5 ms'], ['hint c_1', 135, '135 ms'], ['不 hint', 0.3, '0.3 ms']], 135, mark=[0, 2], done=[1, 3]), kv=KV([['最快', 'b_1,0.5 ms'], ['优化器', '0.3 ms,选了 b_1'], ['最慢', 'c_1,135 ms']], ['优化器'])),
]
A = mkartm('m25', 25, 'MongoDB,查询优化器,计划竞选,allPlansExecution,计划试跑,真实验证,动画演示',
    '实测候选计划的试跑:每个候选计划最多取 101 条结果或 10000 次 works,同样的 works 里谁返回得多谁赢(b_1 返回 101 条,a_1 只返回 1 条);参数调成 10 后试跑缩短;SORT 阻塞,没有阻塞排序的计划更占便宜;结果很少时几次 works 就结束;最后验证选中的 b_1 在完整执行里确实最快。',
    '候选计划各试跑多少文档?谁来决定赢家?这篇用 allPlansExecution 看每个候选的 nReturned 和 works,改参数看试跑如何缩短,并验证排序阻塞和结果很少时的情形。',
    [('101', '每个候选计划试跑最多取的结果数(internalQueryPlanEvaluationMaxResults 默认值)'), ('101 对 1', '同样 101 次 works 里,b_1 与 a_1 候选各返回的条数'), ('0.3 ms', '不 hint 时优化器选中的 b_1 的实际耗时(c_1 是 135 ms)')],
    [('试跑', '<p>一条查询有多个候选索引时,每个候选计划试跑一小段,看同样的 works 里谁返回的结果更多。b_1 返回 101 条而 a_1 只返回 1 条,所以 b_1 赢。</p>'),
     ('试跑的上限', '<p>由参数控制:最多取 101 条结果(<code>internalQueryPlanEvaluationMaxResults</code>)、最多 10000 次 works,或不超过集合的 30%。</p>'),
     ('改参数', '<p>把 MaxResults 调成 10,试跑在第一个计划返回 10 条时结束,其它候选陪跑到同样的 works。</p>'),
     ('阻塞排序', '<p>内存 SORT 要读完所有输入才会输出第一条,试跑期间返回 0 条;按索引顺序扫的计划边扫边出结果,在竞选里更占便宜。</p>'),
     ('结果很少', '<p>某个计划几次 works 就把所有结果返回完,试跑立刻结束,它直接获胜。</p>'),
     ('验证', '<p>逐个 hint 的完整耗时是 16 / 0.5 / 135 ms,优化器自己选的 0.3 ms,选中了最快的计划。</p>')],
    steps,
    [ENV_M + '。20 万个文档(a = i % 5,b = i % 1000,c = i × 7919 mod 100003);候选计划的试跑统计来自 allPlansExecution;参数用 setParameter 临时修改并改回',
     '没有验证:试跑的打分公式(productivity 加奖励)的具体权重;计划缓存的 works 增长系数在重选时的作用(下一篇);多个候选计划在 SBE 引擎里的竞选;index intersection;试跑期间数据变化的影响;在试跑结果误导优化器时(完整执行远慢于试跑印象)的真实案例'],
    '计划竞选')
