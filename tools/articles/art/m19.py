from lib import *
S = SS('m19')
steps = [
    step("数据:300,000 个文档,status 有 5 个取值(等值),ts 单调递增(排序),score 0~999 随机(范围)。查询 {status: \"open\", score: {$gte: 900}},按 ts 倒序;符合条件的共 6000 个。建四个顺序不同的复合索引:E-S-R (status, ts, score)、E-R-S (status, score, ts)、R-E-S (score, status, ts)、S-E-R (ts, status, score),再用 hint 逐个强制。", t=tl(S(1)), mark=lidx(S(1), '6000'), done=lidx(S(1), 'countDocuments'), kv=KV([['E', 'status 等值'], ['S', 'ts 排序'], ['R', 'score 范围'], ['符合条件', '6000 个']], ['E'])),
    step("带 limit(20):E-S-R 的计划是 LIMIT > FETCH > IXSCAN,检查 195 个键、20 个文档(3 ms),没有 SORT;E-R-S 是 FETCH > SORT > IXSCAN,要检查 6000 个键再排序(3 ms);R-E-S 检查 6080 个键(6 ms),同样有 SORT;S-E-R 没有 SORT,但要沿 ts 顺序扫 975 个键(4 ms)。", t=tl(S(2)), mark=lidx(S(2), 'keysExamined: 195', 'keysExamined: 6000', 'keysExamined: 6080', 'keysExamined: 975'), done=lidx(S(2), "plan: 'LIMIT > FETCH > IXSCAN(E-S-R)'"), b=bars([['E-S-R', 195, '195 个键,无 SORT'], ['S-E-R', 975, '975 个键,无 SORT'], ['E-R-S', 6000, '6000 个键 + SORT'], ['R-E-S', 6080, '6080 个键 + SORT']], 6080, mark=[1, 2, 3], done=[0]), kv=KV([['有 limit', '不需要内存排序的索引赢'], ['E-S-R', '195 个键就凑够 20 条'], ['有 SORT 的', '先读完 6000 个键']], ['E-S-R'])),
    step("不带 limit(6000 个结果全部排序):顺序反过来了。E-S-R 没有 SORT,但要沿 status 内部的 ts 顺序扫 60,001 个键才拿到 6000 个符合 score 的(48 ms);E-R-S 只扫 6000 个键、再在内存里排序(7 ms);R-E-S 6080 个键(7 ms);S-E-R 要扫整个 300,000 个键(94 ms)。", t=tl(S(3)), mark=lidx(S(3), 'keysExamined: 60001', 'keysExamined: 300000', 'keysExamined: 6000', 'keysExamined: 6080'), done=lidx(S(3), "plan: 'FETCH > IXSCAN(E-S-R)'"), b=bars([['E-R-S', 6000, '6000 个键 / 7 ms'], ['R-E-S', 6080, '6080 个键 / 7 ms'], ['E-S-R', 60001, '60,001 个键 / 48 ms'], ['S-E-R', 300000, '300,000 个键 / 94 ms']], 300000, mark=[2, 3], done=[0, 1]), kv=KV([['无 limit', '范围字段在排序字段之前的索引更省'], ['E-S-R', '扫的键是结果的 10 倍'], ['内存排序 6000 条', '很便宜']], ['无 limit'])),
    step("pymongo 里量一下耗时(7 次中位数):limit 20 时 E-S-R 0.3 ms、S-E-R 0.5 ms、E-R-S 2.3 ms、R-E-S 2.5 ms;不 limit 时 E-S-R 37 ms、S-E-R 80 ms、E-R-S 9.3 ms、R-E-S 10 ms。同一个索引在两种查询上表现相反。", t=tl(S(4)), mark=lidx(S(4), 'E-S-R', 'S-E-R'), done=lidx(S(4), 'E-R-S', 'R-E-S', '索引'), kv=KV([['limit 20', 'E-S-R 最快(0.3 ms)'], ['无 limit', 'E-R-S 最快(9.3 ms)'], ['结论', 'ESR 规则要结合 limit 判断']], ['结论'])),
    step("不 hint 让优化器自己选:limit 20 选了 E-S-R(LIMIT > FETCH > IXSCAN,195 个键,0 ms);不 limit 也选了 E-S-R(60,001 个键,39 ms)——这次不是最快的:同样的数据 E-R-S 只要 7 ms。优化器靠试跑的前几十次 works 决定计划,不保证全局最优。", t=tl(S(5)), mark=lidx(S(5), '不加 hint,无 limit', 'keysExamined: 60001'), done=lidx(S(5), '不加 hint,limit 20', 'keysExamined: 195'), kv=KV([['有 limit', '选 E-S-R,正好'], ['无 limit', '也选 E-S-R,但不是最快的'], ['原因', '试跑只看最初的 works']], ['无 limit'])),
    step("把范围条件改成等值 {status: \"open\", score: 950} 再按 ts 排序:这时两个等值字段放在前面、排序字段放最后(E-R-S)的计划是 FETCH > IXSCAN(E-R-S),只检查 300 个键、300 个文档,0 ms,没有 SORT;而 E-S-R 要扫 60,001 个键(36 ms)。等值字段在前、排序在最后才是真正的“ES”。", t=tl(S(6)), mark=lidx(S(6), 'hint("E-S-R")', 'keysExamined: 60001'), done=lidx(S(6), 'hint("E-R-S")', 'keysExamined: 300,'), b=bars([['E-S-R', 60001, '60,001 个键 / 36 ms'], ['E-R-S', 300, '300 个键 / 0 ms']], 60001, mark=[0], done=[1]), kv=KV([['全是等值 + 排序', '等值字段全放前面,排序放最后'], ['E-R-S', '300 个键'], ['E-S-R', '60,001 个键']], ['全是等值 + 排序'])),
]
A = mkartm('m19', 19, 'MongoDB,复合索引,ESR,排序,范围查询,explain,真实验证,动画演示',
    '实测复合索引字段顺序(等值、排序、范围):有 limit 20 时 E-S-R 只检查 195 个键最快,不 limit 时 E-S-R 要扫 60,001 个键而 E-R-S 只要 6000 个,反而 E-R-S 更快;优化器无 limit 时仍选了 E-S-R;范围换成等值后等值字段全放前面才是最优。',
    '复合索引的字段顺序到底怎么排?ESR 规则是不是总是对的?这篇用 30 万个文档,四个顺序不同的索引,在带 limit 和不带 limit 的同一条查询上逐个 hint,对比计划、键数和耗时。',
    [('195 对 6000', '带 limit 20 时 E-S-R 与 E-R-S 检查的键数'), ('60,001 对 6000', '不带 limit 时 E-S-R 与 E-R-S 检查的键数(返回 6000 条)'), ('9.3 ms', '不带 limit 时最快的索引 E-R-S 的耗时(E-S-R 要 37 ms)')],
    [('四种顺序', '<p>等值(E)、排序(S)、范围(R)三个字段的不同排列:E-S-R、E-R-S、R-E-S、S-E-R,都用 <code>hint</code> 逐个强制一次。</p>'),
     ('有 limit', '<p>E-S-R 能利用索引顺序直接取排序后的前 20 条,只检查 195 个键;E-R-S 和 R-E-S 要先读完 6000 个键再内存排序。</p>'),
     ('没有 limit', '<p>排序要给出全部 6000 条:E-S-R 虽然没有 SORT,却要扫 60,001 个键才凑够结果;E-R-S 只读 6000 个键,在内存里排序 6000 条很便宜,总耗时更短。</p>'),
     ('耗时', '<p>同一个索引在两种查询上表现相反,说明 ESR 是经验规则,要结合 <code>limit</code> 和结果集大小判断。</p>'),
     ('优化器的选择', '<p>不 hint 时优化器两次都选了 E-S-R;无 limit 时它不是最快的。计划靠试跑最初的一小段 works 来选,不保证全局最优。</p>'),
     ('等值与排序', '<p>当条件全是等值时,把等值字段放前面、排序字段放最后(E-R-S)只需检查 300 个键,E-S-R 要检查 60,001 个。</p>')],
    steps,
    [ENV_M + '。数据是固定公式生成的 30 万个文档(status = 5 个值轮流,score = i * 7919 mod 1000);每个索引用 hint 强制,耗时来自 pymongo 的 7 次中位数,explain 里的 ms 是单次执行',
     '没有验证:其它数据分布下(比如范围条件的选择性很高或很低)结论是否变化;multikey 字段对排序的影响;sort + limit 在 skip 很大时的表现;ESR 在复合范围条件(两个范围字段)下的情形;优化器为什么在无 limit 时选了 E-S-R(只看到结果);降序索引与反向扫描'],
    '复合索引字段顺序')
