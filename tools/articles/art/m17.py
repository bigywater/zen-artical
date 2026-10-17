from lib import *
S = SS('m17')
steps = [
    step("默认是二进制(逐字节)比较:{n: \"alice\"} 只匹配 'alice',不匹配 'Alice'、'ALICE';排序是大写字母在前、小写在后,带重音的字符排最后:['ALICE', 'Alice', 'Bob', 'Elan', 'Zoe', 'a1', 'a10', 'a2', 'alice', 'arger', 'bob', 'zoe', 'Ärger', 'élan']。", t=tl(S(1)), mark=lidx(S(1), "'alice' ]", "'ALICE', 'Alice', 'Bob'"), done=lidx(S(1), 'find({n: "alice"})'), kv=KV([['默认', '二进制比较'], ['排序', '大写 < 小写 < 带重音字符']], ['默认'])),
    step("查询时指定 collation:locale en、strength 2 时 {n: \"alice\"} 匹配 alice、Alice、ALICE 三个;{n: \"arger\"} 只匹配 arger(strength 2 区分重音);strength 1 则 Ärger 与 arger 都匹配。locale en 的排序:a1、a10、a2、alice、Alice、ALICE、arger、Ärger、bob、Bob、Elan、élan、zoe、Zoe——字母顺序,同一个词小写在前。", t=tl(S(2)), mark=lidx(S(2), "'alice', 'Alice', 'ALICE'", "'Ärger', 'arger'", "'a1',    'a10'"), done=lidx(S(2), "strength: 2", "[ 'arger' ]"), kv=KV([['strength 2', '忽略大小写,区分重音'], ['strength 1', '重音也忽略'], ['locale en 排序', '字母序,小写在前']], ['strength 2'])),
    step("numericOrdering: true 让数字字符串按数值比较:a1、a2、a10(默认会是 a1、a10、a2)。中文姓氏排序:默认按 UTF-8 字节是 刘 张 李 杨 王 赵 陈;collation({locale: \"zh\"}) 是拼音顺序 陈 李 刘 王 杨 张 赵。", t=tl(S(3)), mark=lidx(S(3), "'a1', 'a2', 'a10'", '拼音顺序'), done=lidx(S(3), 'UTF-8 字节'), kv=KV([['numericOrdering', 'a2 < a10'], ['locale zh', '拼音顺序'], ['默认', '按 UTF-8 字节']], ['numericOrdering'])),
    step("索引与 collation:20 万个文档,n 上有普通索引 n_1。用 collation(en, strength 2)查 {n: \"alice77\"}:计划是 COLLSCAN,检查了 200,000 个文档;建了同样 collation 的索引 n_ci 之后,计划变成 FETCH > IXSCAN(n_ci),只检查 1 个键、1 个文档;不带 collation 的查询仍然用 n_1。", t=tl(S(4)), mark=lidx(S(4), 'COLLSCAN', 'totalDocsExamined: 200000'), done=lidx(S(4), 'IXSCAN(n_ci)', 'IXSCAN(n_1)'), b=bars([['collation 查询 + 普通索引', 200000, '检查 200,000 个文档'], ['collation 查询 + 同 collation 索引', 1, '检查 1 个文档']], 200000, mark=[0], done=[1]), kv=KV([['查询 collation 与索引不同', '索引用不上,全表扫描'], ['建同 collation 的索引', 'IXSCAN']], ['查询 collation 与索引不同'])),
    step("耗时(中位数):精确等值(二进制索引)0.2 ms;collation strength 2 + 同 collation 索引 0.3 ms;collation strength 2 但索引 collation 不匹配(全表)28.8 ms;正则 /^alice77$/i 60.1 ms——不区分大小写的查询配上匹配的 collation 索引几乎不比精确查找慢。", t=tl(S(5)), mark=lidx(S(5), '28.8 ms', '60.1 ms'), done=lidx(S(5), '0.2 ms', '0.3 ms'), b=bars([['精确等值 + n_1', 0.2, '0.2 ms'], ['collation + 同 collation 索引', 0.3, '0.3 ms'], ['collation + 索引不匹配', 28.8, '28.8 ms'], ['正则 /i', 60.1, '60.1 ms']], 60.1, mark=[2, 3], done=[0, 1]), kv=KV([['匹配的 collation 索引', '0.3 ms'], ['全表扫描', '28.8 ms'], ['正则 /i', '60.1 ms']], ['匹配的 collation 索引'])),
    step("集合级默认 collation:创建集合 ci 时指定 {locale: en, strength: 2},options 里记录完整的 collation(含 caseLevel: false、numericOrdering: false、version: '57.1' 等);它的 _id_ 和 n_1 索引都继承这个 collation。集合里存着 'Erin11980',用 'eRIN11980' 去查(没有写 collation):ci 集合返回 2 个,普通二进制集合返回 0 个。同样 100,000 个文档上的 n_1 索引:二进制 1,216,512 字节,collation 的 1,421,312 字节(1.17 倍)。", t=tl(S(6)), mark=lidx(S(6), '2 个(ci 集合)', '1.17 倍'), done=lidx(S(6), "version: '57.1'", 'collation: {'), kv=KV([['集合默认 collation', '查询与索引默认继承'], ['索引大小', '1.17 倍(1,421,312 对 1,216,512)']], ['集合默认 collation'])),
]
A = mkartm('m17', 17, 'MongoDB,collation,大小写,索引,排序,真实验证,动画演示',
    '实测 collation:默认二进制比较,strength 2 忽略大小写、strength 1 连重音也忽略,numericOrdering 与 zh 拼音排序;collation 查询用不上不带 collation 的索引(全表检查 200,000 个文档),建同 collation 的索引后只检查 1 个;正则 /i 比全表 collation 更慢;集合级默认 collation 与索引变大 17%。',
    '想做大小写不敏感的查询,用 collation 还是正则?索引还能不能用?这篇用 20 万个名字对比二进制、collation 查询、匹配与不匹配的索引、正则的耗时和计划,并看 collation 对排序和索引大小的影响。',
    [('200,000 → 1', 'collation 查询的检查文档数:索引 collation 不匹配(全表)对匹配的 collation 索引'), ('0.3 ms', '大小写不敏感的等值查询配上同 collation 的索引所需时间(精确查找 0.2 ms)'), ('1.17 倍', '同样数据上 collation 索引相对二进制索引的大小')],
    [('默认二进制', '<p>不指定 collation 时按字节比较:大小写不同是不同的值,排序是大写在前、小写在后、带重音的字符最后。</p>'),
     ('strength', '<p>collation 的 <code>strength: 2</code> 忽略大小写但区分重音,<code>strength: 1</code> 连重音也忽略;locale 决定排序规则。</p>'),
     ('numericOrdering 与 zh', '<p><code>numericOrdering: true</code> 让 a2 排在 a10 前面;<code>locale: "zh"</code> 按拼音排序中文。</p>'),
     ('索引必须匹配', '<p>查询的 collation 必须与索引的 collation 相同才能走索引;否则退化为全表扫描,检查全部 200,000 个文档。</p>'),
     ('耗时', '<p>匹配的 collation 索引下查询 0.3 ms,几乎不比精确查找慢;全表 collation 查询 28.8 ms;正则 <code>/i</code> 60.1 ms,更慢。</p>'),
     ('集合级默认', '<p>创建集合时指定 collation,查询与索引默认继承;collation 索引比二进制索引大约 17%。</p>')],
    steps,
    [ENV_M + '。耗时是 pymongo 单次查询,预热一次后取 9 次(全表扫描和正则 5 次)中位数;数据是固定种子的随机名字',
     '没有验证:其它 locale 的排序(德语、瑞典语等);caseLevel、caseFirst、alternate 等选项;聚合、$group 与 $lookup 里 collation 的传递;复合索引中部分字段指定 collation;多个 collation 的唯一索引;全文索引与 collation 的关系;ICU 版本变化对已有索引的影响(version 字段)'],
    'collation')
