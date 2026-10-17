from lib import *
S = SS('m27')
steps = [
    step("30 万个文档,查询 {status: \"A\", ts: {$gte: 290000}, user: 1234},status_1、ts_1、user_1 和复合索引 status_1_ts_1 都可用。耗时(9 次中位数):优化器自己选 0.2 ms(选了 user_1,检查 30 个键);hint user_1 0.2 ms;hint status_1_ts_1 1.2 ms;hint ts_1 4.0 ms;hint status_1 29 ms;hint {$natural: 1}(全表)46 ms。", t=tl(S(1)), mark=lidx(S(1), 'hint status_1 ', '$natural: 1', 'hint ts_1'), done=lidx(S(1), '优化器自己选', 'hint user_1', "plan: 'FETCH > IXSCAN(user_1)'"), b=bars([['优化器自己选', 0.2, '0.2 ms'], ['hint user_1', 0.2, '0.2 ms'], ['hint status_1_ts_1', 1.2, '1.2 ms'], ['hint ts_1', 4, '4.0 ms'], ['hint status_1', 29, '29 ms'], ['hint 全表', 46, '46 ms']], 46, mark=[4, 5], done=[0, 1, 2, 3]), kv=KV([['优化器', '选了最快的 user_1'], ['选错索引', '慢 6 ~ 150 倍'], ['全表', '46 ms']], ['优化器'])),
    step("逐个 hint 的检查量:status_1 检查 75,000 个键、75,000 个文档(32 ms);ts_1 10,000 个(4 ms);user_1 30 个(0 ms);status_1_ts_1 2500 个(1 ms)。检查的键数几乎就是耗时的比例。", t=tl(S(2)), mark=lidx(S(2), 'keysExamined: 75000', 'keysExamined: 10000'), done=lidx(S(2), 'keysExamined: 30', 'keysExamined: 2500'), kv=KV([['status_1', '75,000 个键'], ['ts_1', '10,000 个键'], ['status_1_ts_1', '2,500 个键'], ['user_1', '30 个键']], ['user_1'])),
    step("hint 的写法:键模式 {status: 1, ts: 1} 和索引名一样生效(IXSCAN status_1_ts_1,2500 个键);不存在的索引名 \"nope_1\" 报 code 2、hint provided does not correspond to an existing index;键模式方向不同的 {status: -1}(只存在 status_1)同样报错;{$natural: -1} 强制反向全表,检查 300,000 个文档(52 ms)。", t=tl(S(3)), mark=lidx(S(3), 'code: 2', 'hint provided does not correspond', "plan: 'COLLSCAN'"), done=lidx(S(3), "plan: 'FETCH > IXSCAN(status_1_ts_1)'"), kv=KV([['键模式 / 索引名', '都可以'], ['不存在 / 方向不同', 'code 2 报错'], ['$natural: -1', '反向全表']], ['不存在 / 方向不同'])),
    step("hint 的计划不进计划缓存:连续 3 次带 hint(\"ts_1\") 的查询后缓存条目数是 0;连续 3 次不带 hint 的同形状查询后是 1。", t=tl(S(4)), mark=lidx(S(4), '  0', '  1'), done=lidx(S(4), '带 hint', '不带 hint'), b=bars([['带 hint 的查询', 0, '0 个缓存条目'], ['不带 hint 的查询', 1, '1 个缓存条目']], 1, mark=[0], done=[1]), kv=KV([['带 hint', '每次都不走缓存,也不建条目'], ['不带 hint', '建缓存条目']], ['带 hint'])),
    step("hint 用错的代价:按 user 查询本来 0.2 ms;被迫走只有 4 个取值的 status_1 要 114 ms(563 倍),计划检查 300,000 个键和 300,000 个文档只返回 30 个;用 $natural 全表 43 ms(213 倍)。", t=tl(S(5)), mark=lidx(S(5), '563 倍', 'keysExamined: 300000'), done=lidx(S(5), '不 hint 0.2 ms'), b=bars([['不 hint', 0.2, '0.2 ms'], ['hint $natural', 43, '43 ms (213×)'], ['hint status_1', 114, '114 ms (563×)']], 114, mark=[2], done=[0, 1]), kv=KV([['不 hint', '0.2 ms'], ['hint status_1', '114 ms,慢 563 倍'], ['原因', '检查了全部 300,000 个键']], ['原因'])),
    step("hint 也能用在 aggregate({hint})、countDocuments({hint}) 和 update 的 hint 字段上:aggregate 带 hint \"status_1\" 的计划同样检查 300,000 个键;countDocuments({user: 777}, {hint: \"user_1\"}) 返回 30;update 的 explain 带 hint \"status_1\" 检查 300,000 个文档。", t=tl(S(6)), mark=lidx(S(6), 'hint: "status_1"', 'UPDATE'), done=lidx(S(6), 'countDocuments', '  30'), kv=KV([['aggregate', '选项 {hint}'], ['countDocuments', '选项 {hint}'], ['update / delete', '每条语句里的 hint 字段']], ['aggregate'])),
]
A = mkartm('m27', 27, 'MongoDB,hint,强制索引,查询计划,性能,真实验证,动画演示',
    '实测 hint:优化器自己选的 user_1 只要 0.2 ms,hint 到 status_1 要 29 ms、全表 46 ms;键模式与索引名都可以,不存在的索引报错;hint 的计划不进计划缓存;用错 hint 让按 user 的查询慢 563 倍;aggregate、count、update 里的 hint 写法。',
    'hint 什么时候会让查询更慢?这篇给同一条查询逐个强制每个索引,量耗时和检查量,再看 hint 的写法、报错和对计划缓存的影响。',
    [('0.2 对 29 ms', '优化器自己选 user_1 与 hint 到 status_1 的耗时(同一条查询)'), ('563 倍', '按 user 的查询被迫走 status_1 时变慢的倍数'), ('0 个', '带 hint 的查询之后计划缓存里的条目数')],
    [('优化器的选择', '<p>三个条件各有索引时,优化器自己选了最快的 <code>user_1</code>(30 个键、0.2 ms);强制其它索引都更慢:status_1 要检查 75,000 个键。</p>'),
     ('检查量', '<p>耗时几乎正比于检查的键数:30、2500、10,000、75,000 个键分别对应 0、1、4、32 ms。</p>'),
     ('写法与报错', '<p>可以用索引名或键模式;不存在的索引、方向不同的键模式报 code 2;<code>{$natural: 1}</code> / <code>-1</code> 强制正向或反向全表扫描。</p>'),
     ('不进缓存', '<p>带 hint 的查询不建计划缓存条目,每次都按 hint 执行。</p>'),
     ('用错的代价', '<p>本来 0.2 ms 的按 user 查询被迫用 status_1,要检查 300,000 个键,慢 563 倍。</p>'),
     ('其它命令', '<p>aggregate、countDocuments、update / delete 都支持 hint。</p>')],
    steps,
    [ENV_M + '。30 万个文档,查询结果为空,重点比较检查量与耗时;耗时是 pymongo 9 次中位数(慢的 3~5 次)',
     '没有验证:hint 与分片集群、与 sort 的组合;hint 的索引被 hideIndex 之后的行为;索引过滤器(indexFilters)与 hint 的优先级;MongoDB 的 Query Settings(8.0 引入的集群级 hint)的作用;hint 到部分索引时的结果完整性(见部分索引一篇)'],
    'hint 强制索引')
