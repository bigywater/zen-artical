from lib import *
S = SS('m34')
steps = [
    step("10 万个文档,attrs 子文档里随机带 50 个可能键名(k0~k49)中的 3 个,值 v0~v19。通配符索引 attrs.$** 的 key 是 { 'attrs.$**': 1 };validate 显示索引条目 300000(10 万个文档 × 3 个键),_id_ 是 100000。", t=tl(S(1)), mark=lidx(S(1), "'attrs.$**_1': 300000"), done=lidx(S(1), "key: { 'attrs.$**': 1 }"), kv=KV([['attrs.$**', '收录 attrs 下所有子字段'], ['条目数', '300,000(每个文档 3 条)']], ['attrs.$**'])),
    step("查询 attrs 下任意子字段都能走这个索引:find({\"attrs.k17\": \"v5\"}) 是 FETCH > IXSCAN(attrs.$**_1),检查 291 个键、291 个文档;indexBounds 是 $_path [\"attrs.k17\", \"attrs.k17\"] 加值 [\"v5\", \"v5\"]——索引键是(字段路径,值);$in [v5, v6] 检查 605 个键返回 604 个。没有索引的 plain 集合同样查询是 COLLSCAN,检查 100,000 个文档。", t=tl(S(2)), mark=lidx(S(2), "COLLSCAN", "'$_path'"), done=lidx(S(2), 'keysExamined: 291', 'keysExamined: 605'), b=bars([['通配符索引', 291, '检查 291 个文档'], ['无索引(COLLSCAN)', 100000, '检查 100,000 个文档']], 100000, mark=[1], done=[0]), kv=KV([['通配符索引', '一个索引覆盖 50 个键名'], ['indexBounds', '$_path + 值'], ['无索引', '全表']], ['通配符索引'])),
    step("两个条件同时出现(随机选了一个文档里的两个键名,attrs.k33 = v0、attrs.k22 = v7):通配符索引只能用其中一个字段的范围,检查 266 个键、266 个文档才得到 2 个结果;在 attrs.k33 + attrs.k22 上建复合索引的对照集合只检查 2 个键、2 个文档。", t=tl(S(3)), mark=lidx(S(3), 'keysExamined: 266', 'docsExamined: 266'), done=lidx(S(3), 'keysExamined: 2,', 'IXSCAN(attrs.k33_1_attrs.k22_1)'), b=bars([['通配符索引', 266, '检查 266 个键'], ['复合索引', 2, '检查 2 个键']], 266, mark=[0], done=[1]), kv=KV([['通配符索引', '一次只用一个字段'], ['复合索引', '两个条件一起收窄']], ['通配符索引'])),
    step("能做的:{attrs.k17: {$gte: v1}} 加 sort({attrs.k17: 1}) 是 FETCH > IXSCAN(attrs.$**_1)(没有 SORT 阶段),检查 5658 个键;{attrs.k17: {$exists: true}} 也走索引,检查 5945 个键;不能做的:{attrs.k17: {$ne: v5}} 是 COLLSCAN,检查 100,000 个文档;{name: \"item5\"} 不在 attrs 之下,也是 COLLSCAN。", t=tl(S(4)), mark=lidx(S(4), "plan: 'COLLSCAN'"), done=lidx(S(4), 'keysExamined: 5658', 'keysExamined: 5945'), kv=KV([['范围 + 同字段排序', '可以,无 SORT'], ['$exists: true', '可以'], ['$ne', '不行,全表'], ['索引范围之外的字段', '不行']], ['$ne'])),
    step("代价:300,000 条的通配符索引 2,625,536 字节,只对 attrs.k17 的单字段索引(约 6,000 条)376,832 字节;批量插入 10 万个文档,无二级索引 260 ms,带通配符索引 493 ms(1.9 倍)。", t=tl(S(5)), mark=lidx(S(5), '493 ms', '2,625,536'), done=lidx(S(5), '260 ms'), b=bars([['无二级索引插入', 260, '260 ms'], ['带通配符索引插入', 493, '493 ms']], 493, mark=[1], done=[0]), kv=KV([['索引大小', '2.6 MB(300,000 条)对 0.38 MB(单字段)'], ['写入', '1.9 倍'], ['原则', '为用不到的字段建索引是浪费']], ['写入'])),
    step("限制:通配符索引不支持 unique(Index type 'wildcard' does not support the 'unique' option);createIndex({\"$**\": 1}, {wildcardProjection: {...}}) 可以排除路径;整个文档 $** 的集合(2 万个文档,每个 name + 3 个 attrs)索引条目 80000(_id 不收录);{\"$**\": 1, name: 1} 报 Compound wildcard indexes on all fields must also specify 'wildcardProjection' option;{\"attrs.$**\": 1, name: 1} 这样路径加普通字段的复合通配符索引可以建。", t=tl(S(6)), mark=lidx(S(6), 'does not support the', 'must also specify'), done=lidx(S(6), "'$**_1': 80000", 'attrs.$**_1_name_1'), kv=KV([['unique', '不支持'], ['全文档 $**', '要 wildcardProjection(复合时)'], ['attrs.$** + name', '可以']], ['unique'])),
]
A = mkartm('m34', 34, 'MongoDB,通配符索引,wildcard,attrs,动态字段,真实验证,动画演示',
    '实测通配符索引:一个 attrs.$** 覆盖 50 个动态键名(300,000 条索引),查询检查 291 个文档而不是全表 100,000 个;两个条件同时出现只能用一个字段;能做同字段的范围加排序和 $exists: true,不能做 $ne;写入慢 1.9 倍;不支持 unique,复合通配符的要求。',
    '文档的键名不固定(attrs 里每个文档带不同的键)时,通配符索引值得用吗?这篇用 10 万个动态键文档,看它能加速什么、不能加速什么,以及索引大小和写入的代价。',
    [('291 对 100,000', '一个通配符索引下按动态键名查询检查的文档数,对没有索引的全表'), ('266 对 2', '两个动态键条件同时出现时,通配符索引与复合索引检查的键数'), ('1.9 倍', '带通配符索引时批量插入的耗时是无二级索引的倍数')],
    [('一个索引覆盖所有键名', '<p><code>attrs.$**</code> 为 attrs 下的每个子字段生成索引条目(这里每个文档 3 条,共 300,000 条),键是(字段路径,值)。</p>'),
     ('查询', '<p>按任意动态键名的等值、范围、<code>$in</code> 查询都走索引,检查 291 个文档;没有索引时要扫 100,000 个。</p>'),
     ('多个条件', '<p>两个动态键条件同时出现时,通配符索引一次只用一个字段的范围(检查 266 个键);复合索引才能同时收窄(2 个键)。</p>'),
     ('能与不能', '<p>同一字段的范围加排序、<code>$exists: true</code> 可以;否定条件(<code>$ne</code>)与索引覆盖范围之外的字段不行。</p>'),
     ('代价', '<p>300,000 条的通配符索引 2.6 MB,批量插入慢了 1.9 倍。只对真正会查的字段建索引更划算。</p>'),
     ('限制', '<p>不支持 unique;用 <code>wildcardProjection</code> 控制收录哪些路径;复合通配符索引要求指定路径或 projection。</p>')],
    steps,
    [ENV_M + '。10 万个文档,键名随机,值 v0~v19;计划来自 explain("executionStats");写入耗时是一次插入的测量(无二级索引 260 ms,带通配符索引 493 ms)',
     '没有验证:通配符索引上的 $or / $and 组合;数组值与嵌套更深的路径;wildcardProjection 包含(1)与排除(0)混用的限制;分片集合上的通配符索引;通配符索引 vs 多个单字段索引的写入对比;与 sparse / partial 的组合'],
    '通配符索引')
