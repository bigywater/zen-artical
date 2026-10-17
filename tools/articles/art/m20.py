from lib import *
S = SS('m20')
steps = [
    step("20 万个文档、email 上有索引:find({email}, {email: 1, _id: 0}) 的计划是 PROJECTION_COVERED > IXSCAN(email_1),检查 1 个键、0 个文档;投影里带着 _id(默认)则是 PROJECTION_SIMPLE > FETCH > IXSCAN,多读了 1 个文档——索引里不存 _id;再多要 name(不在索引里)也要 FETCH。", t=tl(S(1)), mark=lidx(S(1), "PROJECTION_SIMPLE > FETCH", 'docsExamined: 1'), done=lidx(S(1), "PROJECTION_COVERED > IXSCAN(email_1)", 'docsExamined: 0'), kv=KV([['覆盖查询', '查询条件和返回字段都在索引里,_id 要去掉'], ['带 _id', '要 FETCH 文档'], ['索引外的字段', '要 FETCH 文档']], ['覆盖查询'])),
    step("把 _id 也放进索引(email_id = {email: 1, _id: 1})后,hint 它查 {email: ...}、投影 {email: 1}(带 _id)也变成 PROJECTION_COVERED,docsExamined 0;复合索引 age_1_city_1 覆盖 find({age: 30, city: \"c10\"}, {age: 1, city: 1, _id: 0}):检查 500 个键、0 个文档。", t=tl(S(2)), mark=lidx(S(2), 'IXSCAN(email_id)'), done=lidx(S(2), 'IXSCAN(age_1_city_1)', 'keysExamined: 500'), kv=KV([['索引含 _id', '投影带 _id 也能覆盖'], ['复合索引 age + city', '覆盖这两个字段的查询']], ['索引含 _id'])),
    step("count 与聚合也能覆盖:aggregate [{$match: {age: 30}}, {$group: {_id: \"$city\", n: {$sum: 1}}}] 的计划是 GROUP > PROJECTION_COVERED > IXSCAN(age_1_city_1),检查 2500 个键、0 个文档;换成按 name 分组,需要 name,变成 GROUP > FETCH > IXSCAN,读 2500 个文档;count({age: 30}) 是 COUNT 阶段,检查 2501 个键、0 个文档。", t=tl(S(3)), mark=lidx(S(3), 'GROUP > FETCH', '"COUNT"'), done=lidx(S(3), 'GROUP > PROJECTION_COVERED'), b=bars([['按 city 分组', 0, '读 0 个文档'], ['按 name 分组', 2500, '读 2500 个文档'], ['count({age: 30})', 0, '读 0 个文档']], 2500, mark=[1], done=[0, 2]), kv=KV([['$group 只用索引字段', '覆盖'], ['需要 name', 'FETCH'], ['count', '只数索引键']], ['$group 只用索引字段'])),
    step("数组字段不能覆盖:tags 上的 multikey 索引,find({tags: \"a3\"}, {tags: 1, _id: 0}) 的计划是 PROJECTION_SIMPLE > FETCH > IXSCAN(tags_1),检查 2000 个键、读 2000 个文档——索引里是拆开的数组元素,取不回完整的数组;投影 {k: 1} 当然也要读文档。", t=tl(S(4)), mark=lidx(S(4), 'PROJECTION_SIMPLE > FETCH > IXSCAN(tags_1)'), done=lidx(S(4), 'docsExamined: 2000'), kv=KV([['multikey 索引', '索引里是单个元素'], ['投影 tags', '仍要读文档取原数组']], ['multikey 索引'])),
    step("耗时:返回 age=30 的 2500 个文档,取 age 和 city(覆盖)1.7 ms、docsExamined 0;多取 name(要读文档)2.7 ms、docsExamined 2500。差别不大,因为文档在缓存里;数据多、文档大、缓存放不下时差距会更大(没测)。", t=tl(S(5)), mark=lidx(S(5), 'FETCH 2500', '2.7 ms'), done=lidx(S(5), '1.7 ms'), b=bars([['覆盖', 1.7, '1.7 ms'], ['需要 FETCH', 2.7, '2.7 ms']], 2.7, mark=[1], done=[0]), kv=KV([['覆盖', '1.7 ms,读 0 个文档'], ['FETCH', '2.7 ms,读 2500 个文档'], ['注意', '文档都在缓存里']], ['注意'])),
    step("什么让覆盖失效:查询条件里有索引外的字段(find({age: 30, name: \"name30\"}, {age: 1, _id: 0}))要 FETCH,检查 2500 个键、读 2500 个文档只返回 1 个;而排序字段 city 在复合索引里,find({age: 30}, {age: 1, _id: 0}).sort({city: 1}) 仍然是 PROJECTION_COVERED > IXSCAN,不需要 SORT 阶段。", t=tl(S(6)), mark=lidx(S(6), 'name: "name30"'), done=lidx(S(6), 'sort({city: 1})', 'PROJECTION_COVERED'), kv=KV([['条件里有索引外字段', 'FETCH 后再过滤'], ['排序字段在索引里', '覆盖,且不用 SORT']], ['条件里有索引外字段'])),
]
A = mkartm('m20', 20, 'MongoDB,覆盖查询,索引,explain,totalDocsExamined,真实验证,动画演示',
    '实测覆盖查询:投影去掉 _id 且字段都在索引里时 totalDocsExamined 为 0;带 _id、取索引外字段、条件里有索引外字段、数组(multikey)字段都要 FETCH;把 _id 放进索引后带 _id 也能覆盖;count 与 $group 也能覆盖。',
    'totalDocsExamined 怎么变成 0?这篇在 20 万个文档上用 explain 一个个验证:要去掉 _id、字段都在索引里,以及什么情况下覆盖失效。',
    [('0', '覆盖查询的 docsExamined(投影 {email: 1, _id: 0})'), ('2500 → 0', 'find({age: 30}) 取 age + city 时读文档数从需要 name 时的 2500 降到 0'), ('1.7 / 2.7 ms', '覆盖查询与需要 FETCH 的查询的耗时')],
    [('覆盖的条件', '<p>查询条件和返回的字段都在同一个索引里,并且投影去掉 <code>_id</code>(索引里不存 <code>_id</code>),就是 <code>PROJECTION_COVERED</code>,<code>docsExamined</code> 为 0。</p>'),
     ('_id 与复合索引', '<p>把 <code>_id</code> 放进索引,带 <code>_id</code> 的投影也能覆盖;复合索引覆盖对它所含字段的查询。</p>'),
     ('count 与聚合', '<p><code>count</code> 走 COUNT 阶段只数索引键;聚合只用到索引字段时,<code>$group</code> 也是覆盖的。</p>'),
     ('数组字段', '<p>数组字段上的 multikey 索引里存的是拆开的元素,取不回完整的数组,所以不能覆盖。</p>'),
     ('耗时', '<p>覆盖查询读 0 个文档,耗时 1.7 ms;需要 FETCH 读 2500 个文档,2.7 ms。文档在缓存里时差别有限。</p>'),
     ('什么让覆盖失效', '<p>条件里有索引外的字段、要返回索引外的字段,都要 FETCH;排序字段在索引里则不影响覆盖,还省掉了 SORT。</p>')],
    steps,
    [ENV_M + '。20 万个文档(email、name、age、city、100 字节 pad);计划来自 explain("executionStats")',
     '没有验证:sparse 或 partial 索引上的覆盖条件;collation 索引的覆盖(索引键不能还原原字符串);聚合 $project 里的表达式是否阻碍覆盖;分片集群上的覆盖查询(需要包含分片键);文档在缓存之外(冷数据)时覆盖与 FETCH 的耗时差距'],
    '覆盖查询')
