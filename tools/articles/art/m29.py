from lib import *
S = SS('m29')
steps = [
    step("20 万个文档,a、b、c 各有单字段索引。find({$or: [{a: 5}, {b: 17}]}) 的计划是 SUBPLAN > FETCH > OR[IXSCAN(a_1) | IXSCAN(b_1)]:两个分支各走自己的索引,合并后再 FETCH;检查 240 个键、240 个文档,返回 240 个。", t=tl(S(1)), mark=lidx(S(1), 'OR[IXSCAN(a_1) | IXSCAN(b_1)]'), done=lidx(S(1), 'keysExamined: 240', 'nReturned: 240'), kv=KV([['每个分支', '走自己的索引'], ['OR 阶段', '合并并去重'], ['检查量', '240 个键 = 200 + 40']], ['每个分支'])),
    step("只要有一个分支没有可用索引,整个 $or 退化成全表扫描:d 上没有索引,find({$or: [{a: 5}, {d: 17}]}) 的计划是 SUBPLAN > COLLSCAN,检查 200,000 个文档只返回 202 个。", t=tl(S(2)), mark=lidx(S(2), 'COLLSCAN', 'docsExamined: 200000'), done=lidx(S(2), 'nReturned: 202'), b=bars([['两个分支都有索引', 240, '检查 240 个文档'], ['一个分支没有索引', 200000, '检查 200,000 个文档']], 200000, mark=[1], done=[0]), kv=KV([['一个分支没索引', '整个 $or 全表扫描'], ['原因', '那个分支只能靠扫描,干脆整个扫']], ['一个分支没索引'])),
    step("$or 之外有别的条件:find({c: 7, $or: [{a: 5}, {b: 17}]}) 的计划是 FETCH > OR[IXSCAN(a_1) | IXSCAN(b_1)],检查 240 个键(c: 7 在 FETCH 后过滤,返回 0);建了 {c, a} 和 {c, b} 两个复合索引后,计划变成 FETCH > OR[IXSCAN(c_1_a_1) | IXSCAN(c_1_b_1)],检查 0 个键——外层条件被分配进每个分支的索引。", t=tl(S(3)), mark=lidx(S(3), 'c_1_a_1', 'keysExamined: 0'), done=lidx(S(3), 'OR[IXSCAN(a_1) | IXSCAN(b_1)]', 'keysExamined: 240'), b=bars([['单字段索引', 240, '检查 240 个键'], ['{c,a} + {c,b} 复合索引', 0, '检查 0 个键']], 240, mark=[1], done=[0]), kv=KV([['外层条件', '要分配进每个分支'], ['复合索引 {c, a}', '让 c 和 a 一起走索引']], ['外层条件'])),
    step("$or + sort:有 {a, d} 和 {b, d} 两个复合索引时,find({$or: [{a: 5}, {b: 17}]}).sort({d: 1}) 的计划是 SUBPLAN > FETCH > SORT_MERGE[IXSCAN(a_1_d_1) | IXSCAN(b_1_d_1)],各分支按 d 有序读出再归并,没有 SORT;删掉 {b, d} 索引后变成 SUBPLAN > SORT > FETCH > OR[IXSCAN(b_1) | IXSCAN(a_1_d_1)],出现了内存 SORT。", t=tl(S(4)), mark=lidx(S(4), 'SORT_MERGE', 'SUBPLAN > SORT > FETCH'), done=lidx(S(4), 'keysExamined: 240'), kv=KV([['每个分支都能按 d 有序', 'SORT_MERGE,没有 SORT'], ['有一个分支不能', 'OR 之后再 SORT']], ['每个分支都能按 d 有序'])),
    step("两个分支命中同一个文档时只返回一次:{a: 5} 命中 200 个,{b: 35} 命中 40 个(其中 40 个同时满足 a: 5);并集 200。计划 OR[IXSCAN(a_1) | IXSCAN(b_1)] 检查 240 个键(两边之和)、只 FETCH 200 个文档、返回 200 个——去重发生在 FETCH 之前;{$or: [{a: 5}, {a: 5, b: 3}]} 第二个分支被第一个包含,优化器直接化简成 FETCH > IXSCAN(a_1),检查 200 个键。", t=tl(S(5)), mark=lidx(S(5), 'keysExamined: 240', 'docsExamined: 200', '200 + 40'), done=lidx(S(5), "plan: 'FETCH > IXSCAN(a_1)'"), kv=KV([['键数', '两边之和 240'], ['文档数', '去重后 200'], ['被包含的分支', '被化简掉']], ['文档数'])),
    step("同一字段上的 $or 与 $in:find({$or: [{a: 5}, {a: 6}, {a: 7}]}) 和 find({a: {$in: [5, 6, 7]}}) 的计划都是 FETCH > IXSCAN(a_1),检查 601 个键、600 个文档;耗时都是 0.9 ms。不同字段:一条 $or 查询 0.6 ms,应用端拆成两条查询再合并 0.7 ms。", t=tl(S(6)), mark=lidx(S(6), '同一字段', '不同字段'), done=lidx(S(6), '$in', 'keysExamined: 601'), kv=KV([['同一字段的 $or', '被化简成 $in,计划一样'], ['不同字段', '一条 $or 与两条查询差不多']], ['同一字段的 $or'])),
]
A = mkartm('m29', 29, 'MongoDB,$or,索引,SORT_MERGE,explain,真实验证,动画演示',
    '实测 $or 如何用索引:每个分支都有索引时各走各的并由 OR 阶段去重;一个分支没有索引整个 $or 全表扫描(240 对 200,000 个文档);外层条件要有对应的复合索引才分配进每个分支;$or 加 sort 在每个分支都能有序时用 SORT_MERGE;同一字段的 $or 与 $in 计划相同。',
    '$or 的每个分支各走哪个索引?一个分支没有索引会怎样?加了 sort 和别的条件之后呢?这篇用 20 万个文档和 explain 逐个情形验证。',
    [('240 对 200,000', '$or 每个分支都有索引与有一个分支没有索引时检查的文档数'), ('SORT_MERGE', '每个分支的索引都能按排序字段有序时,$or + sort 不需要内存排序'), ('240 → 200', '两个分支重叠时检查的键数与最终返回的文档数,去重发生在 FETCH 之前')],
    [('各走各的', '<p>每个分支有可用索引时,<code>$or</code> 的计划是 <code>OR[IXSCAN | IXSCAN]</code>,各自按自己的索引读,合并后再 FETCH 并去重。</p>'),
     ('一个分支没有索引', '<p>只要有一个分支用不上索引,整个 <code>$or</code> 退化为 <code>COLLSCAN</code>,检查全部 200,000 个文档。</p>'),
     ('外层条件', '<p><code>$or</code> 之外的条件要靠对应的复合索引(<code>{c, a}</code>、<code>{c, b}</code>)分配进每个分支;只有单字段索引时是 FETCH 后过滤。</p>'),
     ('$or + sort', '<p>每个分支的索引都能按排序字段有序时,用 <code>SORT_MERGE</code> 归并,不需要 SORT 阶段;有一个分支不能就退化成 OR 之后再 SORT。</p>'),
     ('去重', '<p>两个分支命中同一个文档只会返回一次;键数是两边之和,FETCH 的文档数是并集。被另一个分支包含的分支会被化简掉。</p>'),
     ('同一字段', '<p>同一个字段上的多个 <code>$or</code> 分支和 <code>$in</code> 的计划一样,耗时也一样。</p>')],
    steps,
    [ENV_M + '。20 万个文档;计划来自 explain("executionStats");耗时是 pymongo 的 9 次中位数',
     '没有验证:$or 在聚合 $match 里的行为;嵌套的 $or / $and;分支很多(几十个)时的计划与规划开销;$or 里含 $regex、$text 分支;SBE 引擎下 $or 的计划表示差异;三个以上分支其中某个分支结果极多时的合并开销'],
    '$or 查询的索引使用')
