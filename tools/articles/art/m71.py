from lib import *
S = SS('m71')
steps = [
    step("3 个分片,uid 每 10000 一段:sh0 [MinKey, 10000)、sh1 [10000, 20000)、sh2 [20000, MaxKey),共 30,000 个文档。pipeline 带分片键条件时 mongos 只发给相关分片:$match uid = 15000 → shards = [sh1];uid < 5000 → [sh0];这两种 explain 里都没有 splitPipeline——整条 pipeline 在那一个分片上跑完。", t=tl(S(1)), mark=lidx(S(1), 'uid = 15000', '[0, 5000)'), done=lidx(S(1), '块分布'), kv=KV([['uid = 15000', '只访问 sh1,无 splitPipeline'], ['uid < 5000', '只访问 sh0,无 splitPipeline']], ['uid = 15000'])),
    step("没有分片键条件的 $group 要访问 sh0、sh1、sh2 全部三个分片,explain 的 splitPipeline 把它拆成两段:shardsPart = [$group](每个分片先做部分分组),mergerPart = [$mergeCursors, $group](把各分片的游标合并后再做一次分组)。后面接 $sort 时,$sort 在 mergerPart 里。", t=tl(S(2)), mark=lidx(S(2), '$group by city  ', '然后 $sort'), done=lidx(S(2), '$group by city  '), kv=KV([['shardsPart', '[$group]'], ['mergerPart', '[$mergeCursors, $group]'], ['再加 $sort', '[$mergeCursors, $group, $sort]']], ['mergerPart'])),
    step("部分分组把传输的数据量压到最低:每个分片扫描 10,000 个文档,只返回 50 个文档(city 取值 50 个)给合并阶段——3 个分片一共 150 个文档,而不是 30,000 个。", t=tl(S(3)), mark=lidx(S(3), 'sh0', 'sh1', 'sh2'), done=lidx(S(3), 'sh0'), b=bars([['sh0 扫描', 10000, '10,000'], ['sh0 返回', 50, '50'], ['sh1 返回', 50, '50'], ['sh2 返回', 50, '50']], 10000, mark=[1, 2, 3], done=[0]), kv=KV([['每个分片扫描', '10,000 个文档'], ['每个分片返回', '50 个文档'], ['合并阶段收到', '150 个文档']], ['每个分片返回'])),
    step("$sort + $limit 5:shardsPart 里是 {$sort: {sortKey: {amount: -1, uid: 1}, limit: 5}}——limit 被并进了每个分片上的排序,各分片只需要保留前 5 个;mergerPart = [$mergeCursors, $limit],$mergeCursors 带着同样的 sort 做有序归并,再取前 5。", t=tl(S(4)), mark=lidx(S(4), 'shardsPart[0]', 'mergerPart    ='), done=lidx(S(4), '$sort amount'), kv=KV([['shardsPart', '$sort(sortKey + limit: 5)'], ['mergerPart', '$mergeCursors(sort)+ $limit']], ['shardsPart'])),
    step("$group 后接 $lookup(到未分片的 cities)时,$lookup 排在 mergerPart 里:[$mergeCursors, $group, $lookup]。$group + $merge 同样,$merge 在 mergerPart 末尾;$match uid < 5000 + $out 只命中一个分片(sh0),没有 splitPipeline,整条 pipeline 在 sh0 上执行。", t=tl(S(5)), mark=lidx(S(5), '$group + $lookup', '$match + $out', '$group + $merge'), done=lidx(S(5), '$group + $lookup'), kv=KV([['$lookup', 'mergerPart'], ['$merge', 'mergerPart 末尾'], ['$match(分片键)+ $out', '只命中 sh0,无 splitPipeline']], ['$lookup'])),
    step("拆分方式决定耗时:只有 $group 是 3.9 ms;在 $group 前面加 $sort(按 uid 排整个集合)是 18 ms,此时 explain 显示 shardsPart = [$sort, $project],mergerPart = [$mergeCursors, $group]——$group 不再能在分片上预先分组,30,000 个文档的排序结果都要交给合并阶段。", t=tl(S(6)), mark=lidx(S(6), '只有 $group', '后一种的拆分'), done=lidx(S(6), '只有 $group'), b=bars([['只有 $group', 3.9, '3.9 ms'], ['$sort 在 $group 前', 18, '18 ms']], 18, mark=[1], done=[0]), kv=KV([['只有 $group', '3.9 ms'], ['$sort 在 $group 前', '18 ms'], ['$group 在哪里', 'mergerPart']], ['$sort 在 $group 前'])),
]
A = mkartm('m71', 71, 'MongoDB,分片,聚合,mergerPart,shardsPart,explain,真实验证,动画演示',
    '实测 3 分片集群上聚合 pipeline 的拆分:带分片键条件只命中相关分片、无 splitPipeline;$group 拆成分片上的部分分组 + 合并阶段的 $mergeCursors/$group(每个分片扫描 10,000 个文档只返回 50 个);$sort+$limit 把 limit 并进分片排序;$lookup/$merge 在 mergerPart;$sort 放在 $group 前面时耗时从 3.9 ms 变成 18 ms。',
    '分片集群上的聚合是怎么跑的?哪些阶段在分片上执行,哪些在合并阶段?这篇用 explain 的 splitPipeline 逐个情形看。',
    [('50', '每个分片返回给合并阶段的文档数(扫描 10,000 个)'), ('[sh1]', '$match uid = 15000 只访问一个分片,无 splitPipeline'), ('3.9 → 18 ms', '$sort 放在 $group 前面之后的耗时')],
    [('带分片键条件', '<p>$match 里有分片键条件时,mongos 只把 pipeline 发给相关分片(<code>uid = 15000</code> 只命中 sh1,<code>uid &lt; 5000</code> 只命中 sh0),explain 里没有 <code>splitPipeline</code>,整条 pipeline 在那个分片上执行。</p>'),
     ('splitPipeline', '<p>没有分片键条件的 <code>$group</code> 访问全部 3 个分片:<code>shardsPart = [$group]</code>,<code>mergerPart = [$mergeCursors, $group]</code>;随后的 <code>$sort</code> 也在 mergerPart。</p>'),
     ('部分分组', '<p>每个分片扫描 10,000 个文档,只返回 50 个分好组的文档,合并阶段一共收到 150 个,而不是 30,000 个。</p>'),
     ('$sort + $limit', '<p><code>limit</code> 被并进分片上的 <code>$sort</code>(<code>limit: 5</code>);mergerPart 里 <code>$mergeCursors</code> 带着同样的 sort 做有序归并,再 <code>$limit</code>。</p>'),
     ('$lookup / $merge / $out', '<p>$group 之后的 <code>$lookup</code> 和 <code>$merge</code> 排在 mergerPart 里;<code>$match uid &lt; 5000</code> + <code>$out</code> 只命中 sh0,在该分片上整条执行。</p>'),
     ('耗时', '<p>只有 <code>$group</code> 的聚合 3.9 ms;<code>$group</code> 前面加 <code>$sort</code> 后拆分变成 shardsPart = [$sort, $project],<code>$group</code> 整个落到合并阶段,耗时 18 ms。</p>')],
    steps,
    [ENV_M + '。3 个分片(各为单节点副本集),30,000 个文档,块用 split 与 moveChunk 手工分布;耗时是单机本地的数字',
     '没有验证:合并阶段具体由 mongos 还是某个分片执行(这个版本的 explain 输出里没有 mergeType 字段,本文没有去确认);$out/$merge 写入分片集合时的行为;allowDiskUse 与内存上限在合并阶段的表现;$lookup 到分片集合;$setWindowFields/$bucketAuto 等阶段的拆分;多用户并发时的耗时'],
    '分片集群上的聚合拆分')
