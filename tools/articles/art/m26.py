from lib import *
S = SS('m26')
steps = [
    step("10 万个文档(a 只有前 10 个是 0,其余是 1;b = i % 5),a_1、b_1、c_1 三个索引。刚建好时 planCacheStats 是空的([]);第 1 次执行 find({a: 0, b: 2}) 后出现 1 个条目:isActive: false,works 11,cachedPlan 是 FETCH > IXSCAN(a_1),createdFromQuery 记着 {a: 0, b: 2};第 2 次执行同一个形状后 isActive 变成 true。", t=tl(S(1)), mark=lidx(S(1), 'isActive: true', 'isActive: false'), done=lidx(S(1), '[]', "plan: 'FETCH > IXSCAN(a_1)'", 'works: Long'), kv=KV([['第 1 次', '产生 inactive 条目(works 11)'], ['第 2 次', '确认后变 active'], ['条目内容', '计划 + 创建时的 works + 查询']], ['第 2 次'])),
    step("同一个形状、不同常量用同一个条目:再执行 {a: 0, b: 4}、{a: 0, b: 3} 后缓存条目数仍是 1;换形状才是新条目——加一个 c 条件 {a: 0, b: 2, c: 7} 和加排序 {a: 0, b: 2}.sort({c: 1}) 各一个,条目数变成 3。", t=tl(S(2)), mark=lidx(S(2), '加了 c 条件', '  3'), done=lidx(S(2), '同形状不同常量', '  1'), kv=KV([['形状相同', '常量不同也共用一个条目'], ['加条件 / 加排序', '新条目']], ['形状相同'])),
    step("explain 能看到计划是否来自缓存:对 {a: 0, b: 1} 再执行一次后 explain().queryPlanner.winningPlan.isCached 是 true。", t=tl(S(3)), mark=lidx(S(3), 'true'), done=lidx(S(3), 'isCached'), kv=KV([['isCached', 'true 表示计划来自缓存']], ['isCached'])),
    step("缓存的计划在别的常量上变慢时被重选:缓存的是 a_1(a=0 只有 10 个文档),换成 a=1(占 99.99%)时 profiler 记录 replanned: true,replanReason 是 \"cached plan was less efficient than expected: expected trial execution to take 11 works but it took at least 110 works\";新计划是 IXSCAN { b: 1 };条目里的计划变成 FETCH > IXSCAN(b_1)(works 22),createdFromQuery 是 {a: 1, b: 2}。", t=tl(S(4)), mark=lidx(S(4), 'replanned: true', 'replanReason', "createdFrom: '{\"a\":1,\"b\":2}'"), done=lidx(S(4), 'setProfilingLevel(2)', "planSummary: 'IXSCAN { b: 1 }'"), kv=KV([['重选条件', '实际 works 超过缓存时 works 的 10 倍'], ['这里', '11 works 对 110 works'], ['重选后', '改用 b_1']], ['重选条件'])),
    step("索引变化清空缓存:之前 3 个条目;创建索引 c_1_b_1 之后 0 个;重新执行两次同一个查询后又有 1 个;hideIndex(\"c_1_b_1\") 之后再次变成 0 个。", t=tl(S(5)), mark=lidx(S(5), '创建索引 c_1_b_1', 'hideIndex'), done=lidx(S(5), '缓存条目数(之前)', '重新执行两次后'), b=bars([['创建索引前', 3, '3 个条目'], ['创建索引后', 0, '0 个'], ['重新执行两次后', 1, '1 个'], ['hideIndex 后', 0, '0 个']], 3, mark=[1, 3], done=[0, 2]), kv=KV([['createIndex', '清空该集合的缓存'], ['hideIndex', '也清空']], ['createIndex'])),
    step("缓存条目的字段:version、queryHash、planCacheShapeHash、planCacheKey、isActive、works、reads、timeOfCreation、createdFromQuery、cachedPlan、creationExecStats、candidatePlanScores、indexFilterSet、estimatedSizeBytes、solutionHash、host;候选分数 [2.18, 1.18],创建时两个候选各试跑 11 works;getPlanCache().clear() 之后条目数 0。", t=tl(S(6)), mark=lidx(S(6), 'candidatePlanScores', 'creationWorks', 'clear()'), done=lidx(S(6), 'keys', 'planCacheShapeHash'), kv=KV([['candidatePlanScores', '创建时各候选的分数'], ['creationExecStats', '试跑统计'], ['clear()', '手动清空']], ['candidatePlanScores'])),
]
A = mkartm('m26', 26, 'MongoDB,计划缓存,planCache,replan,planCacheStats,真实验证,动画演示',
    '实测计划缓存:第一次执行产生 inactive 条目、第二次确认后变 active;同形状不同常量共用一个条目;换常量让缓存计划变慢(11 works 变成至少 110 works)时 profiler 记录 replanned 并重选;创建或隐藏索引会清空缓存;条目里的字段与手动清理。',
    '计划缓存什么时候建立、什么时候失效重选?这篇用 $planCacheStats 看条目的生命周期,构造一个数据倾斜的查询触发 replan,再验证索引变化和手动清理。',
    [('inactive → active', '缓存条目第 1 次执行后是 inactive,第 2 次执行同一形状才变 active'), ('11 → 110', '触发重选的 works:预期 11 次,实际至少 110 次(10 倍)'), ('3 → 0', '创建一个新索引后该集合的计划缓存条目数')],
    [('条目的生命周期', '<p>第一次执行产生一个 <code>isActive: false</code> 的条目,记录计划与创建时的 works;同一形状第二次执行后才变成 active。</p>'),
     ('按形状缓存', '<p>缓存按查询形状存放,常量不同共用一个条目;加条件或加排序是新的形状,各有各的条目。</p>'),
     ('是否来自缓存', '<p>explain 的 <code>winningPlan.isCached</code> 为 true 表示计划来自缓存。</p>'),
     ('重选', '<p>缓存的计划在新常量上比预期慢很多(works 超过缓存时的 10 倍)时会重选:profiler 记录 <code>replanned: true</code> 和原因,条目被换成新计划。</p>'),
     ('失效', '<p>创建索引、隐藏索引会清空该集合的缓存条目;<code>getPlanCache().clear()</code> 可以手动清空。</p>'),
     ('条目里有什么', '<p>除了计划本身,还有创建时的执行统计、候选计划的分数、查询哈希、估计大小等。</p>')],
    steps,
    [ENV_M + '。缓存条目来自 $planCacheStats;重选通过 profiler(级别 2)的 replanned 与 replanReason 观察,profiler 里的 keysExamined 只对应第一批结果',
     '没有验证:internalQueryCacheEvictionRatio 与 internalQueryCacheWorksGrowthCoefficient 对重选阈值的精确作用;缓存条目数上限与淘汰;副本集 secondary 上的计划缓存是否独立;重启、dropIndex、collMod 对缓存的影响;SBE 引擎的计划缓存;索引过滤器(indexFilter)的作用'],
    '计划缓存')
