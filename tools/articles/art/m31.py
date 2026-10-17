from lib import *
S = SS('m31')
steps = [
    step("在 title 和 body 上建文本索引 ft:key 是 { _fts: 'text', _ftsx: 1 },weights { body: 1, title: 1 },default_language 'english',language_override 'language',textIndexVersion 3,collation 是 simple。", t=tl(S(1)), mark=lidx(S(1), "key: { _fts: 'text', _ftsx: 1 }", 'weights'), done=lidx(S(1), "default_language: 'english'", 'textIndexVersion: 3'), kv=KV([['key', '_fts: text,_ftsx: 1'], ['默认权重', 'title 1、body 1'], ['语言', 'english,textIndexVersion 3']], ['key'])),
    step("词干:搜 running 匹配文档 2(Running shoes review);搜 jumped 匹配文档 1(正文是 jumps);搜 foxes 匹配文档 1 和 6(只有 fox);搜 index 匹配 7 和 8(Indexes / indexing / index);搜 queries 匹配 8 和 7(query / queries)。注意搜 ran 只因为文档 2 正文里有字面的 ran 才匹配,它不是 run 的词干变化。", t=tl(S(2)), mark=lidx(S(2), '$search: "ran"', 'jumped', 'foxes'), done=lidx(S(2), 'Running shoes review', 'index'), kv=KV([['词干化', 'jumped → jump,foxes → fox'], ['不规则变化', 'ran 不会变成 run'], ['index / queries', '匹配 Indexes、indexing、query']], ['词干化'])),
    step("停用词与大小写:搜 \"the\" 返回 0 个(停用词不进索引);\"the quick\" 等价于 quick,命中文档 6、1、3;搜 CAFE 匹配 Café guide(大小写、重音都不敏感);{$caseSensitive: true} 搜 CAFE 返回空;{$search: \"cafe\", $diacriticSensitive: true} 仍返回文档 4,因为它正文里有不带重音的 cafe。", t=tl(S(3)), mark=lidx(S(3), '$search: "the"', '$caseSensitive', '$diacriticSensitive'), done=lidx(S(3), '[ 6, 1, 3 ]', '4:Café guide'), kv=KV([['\"the\"', '停用词,0 个结果'], ['大小写 / 重音', '默认都不敏感'], ['$caseSensitive', '改为敏感']], ['\"the\"'])),
    step("多个词按 OR:搜 \"fox lazy\" 命中 1、5、6;引号里是短语:\"quick brown\" 只命中文档 1(The quick brown fox);减号排除:\"quick -fox\" 只剩文档 3(Brown bread recipe)。", t=tl(S(4)), mark=lidx(S(4), '[ 1, 5, 6 ]', "'1:The quick brown fox'", "'3:Brown bread recipe'"), done=lidx(S(4), 'fox lazy', 'quick -fox'), kv=KV([['fox lazy', 'OR:1、5、6'], ['\"quick brown\"', '短语:只有 1'], ['quick -fox', '排除含 fox 的:只剩 3']], ['短语'])),
    step("打分:默认权重下搜 \"quick fox\",按 textScore 排序是 6(3.55)、1(1.33)、3(0.57);把 title 权重设成 10、body 1 重建索引后,6 变成 15.55、1 变成 13.33(标题里有 quick fox),3 仍是 0.57(只在正文里出现 quick)。", t=tl(S(5)), mark=lidx(S(5), "'6:15.55'", "'1:13.33'"), done=lidx(S(5), "'6:3.55'", "'3:0.57'"), b=bars([['文档 6(默认)', 3.55, '3.55'], ['文档 1(默认)', 1.33, '1.33'], ['文档 6(title×10)', 15.55, '15.55'], ['文档 1(title×10)', 13.33, '13.33']], 15.55, mark=[2, 3], done=[0, 1]), kv=KV([['权重', '字段命中得分乘以权重'], ['title 权重 10', '标题命中的文档分数从 3.55 升到 15.55'], ['只在正文命中', '分数不变']], ['权重'])),
    step("限制:同一个集合再建第二个文本索引报错 An equivalent index already exists with a different name and options(一个集合只能有一个文本索引);没有文本索引的集合上 $text 报 text index required for $text query;聚合里 $text 不在第一阶段报 $match with $text is only allowed as the first pipeline stage;explain 里计划是 TEXT_MATCH 加 IXSCAN ft2。", t=tl(S(6)), mark=lidx(S(6), 'An equivalent index already exists', 'text index required', 'only allowed as the first pipeline stage'), done=lidx(S(6), 'TEXT_MATCH'), kv=KV([['文本索引', '一个集合只能一个'], ['$text', '必须有文本索引'], ['聚合', '$text 要在第一阶段']], ['文本索引'])),
]
A = mkartm('m31', 31, 'MongoDB,文本索引,$text,分词,词干,textScore,真实验证,动画演示',
    '实测文本索引:英文词干把 jumped、foxes 归一到 jump、fox;停用词(the)不进索引;大小写与重音默认不敏感;多词按 OR、引号是短语、减号排除;textScore 打分与 title 权重 10 的效果(3.55 升到 15.55);一个集合只能有一个文本索引。',
    '$text 搜索到底怎么分词、怎么打分?这篇用 8 篇短文档验证词干、停用词、短语、排除、权重和限制。',
    [('3.55 → 15.55', '把 title 权重设成 10 后,标题含 quick fox 的文档得分'), ('0 个', '搜停用词 \"the\" 的结果数'), ('1 个', '一个集合上最多能有的文本索引数')],
    [('文本索引', '<p>文本索引的 key 是 <code>{_fts: "text", _ftsx: 1}</code>,默认英文,每个字段权重 1。</p>'),
     ('词干', '<p>搜索词和文档都做词干化:jumped 能匹配 jumps,foxes 能匹配 fox,index 能匹配 Indexes 和 indexing;不规则变化(ran 与 run)不会归一。</p>'),
     ('停用词、大小写与重音', '<p>the 这样的停用词不进索引,搜它返回 0 个;大小写和重音默认都不敏感,可以用 <code>$caseSensitive</code>、<code>$diacriticSensitive</code> 改变。</p>'),
     ('查询语法', '<p>多个词是 OR,引号里是短语,减号排除含该词的文档。</p>'),
     ('打分与权重', '<p>用 <code>{$meta: "textScore"}</code> 取分数并排序;权重让某个字段里的命中得分成倍提高。</p>'),
     ('限制', '<p>一个集合只能有一个文本索引;没有文本索引不能用 <code>$text</code>;聚合里 <code>$text</code> 必须在第一阶段。</p>')],
    steps,
    [ENV_M + '。8 篇短文档,英文;分数取自 textScore',
     '没有验证:其它语言的分词与词干(default_language 为中文时不分词);大量文档上的文本索引大小与性能;textScore 的计算公式;复合文本索引(前缀等值字段);通配符文本索引($**);文本索引在分片集群上的行为;Atlas Search / 全文检索替代方案'],
    '文本索引')
