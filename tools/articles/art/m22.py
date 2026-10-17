from lib import *
S = SS('m22')
steps = [
    step("在 {a: 1, b: 1} 上建复合索引后:{_id: 1, a: [1,2,3], b: \"x\"}(一个数组加一个标量)插入成功,{_id: 2, a: 1, b: [\"x\",\"y\"]} 也成功——每个文档里最多只能有一个被索引字段是数组。", t=tl(S(1)), mark=lidx(S(1), 'a_1_b_1'), done=lidx(S(1), 'insertedId: 1', 'insertedId: 2'), kv=KV([['一个数组 + 一个标量', '允许'], ['限制', '同一个文档里复合索引的字段最多一个是数组']], ['限制'])),
    step("两个字段同时是数组:insertOne({a: [1,2], b: [\"x\",\"y\"]}) 报 code 171,message 是 cannot index parallel arrays [b] [a];updateOne 把 b 改成数组让 a、b 同时是数组,同样报 171(Plan executor error during update :: caused by :: cannot index parallel arrays);集合里仍只有 _id 1 和 2 两个原来的文档。", t=tl(S(2)), mark=lidx(S(2), 'code: 171', 'parallel arrays'), done=lidx(S(2), '_id: 1, a: [ 1, 2, 3 ]', '_id: 2'), kv=KV([['code 171', 'CannotIndexParallelArrays'], ['insert / update', '都被拒绝'], ['笛卡尔积', '索引不会这样展开']], ['code 171'])),
    step("已经有“两个数组”的文档时建这个索引会失败:集合 u 里 _id 1 的 a、b 都是数组,createIndex({a: 1, b: 1}) 报 code 171、codeName CannotIndexParallelArrays、Index build failed ... collection scan stopped;getIndexes 里只有 _id_。", t=tl(S(3)), mark=lidx(S(3), 'CannotIndexParallelArrays', 'Index build failed'), done=lidx(S(3), "'_id_'"), kv=KV([['建索引', '扫描到并行数组时失败'], ['结果', '索引没有建出来']], ['建索引'])),
    step("路径不同才是不同的数组:索引 {x.a: 1, x.b: 1} 上,{x: [{a:1,b:2},{a:3,b:4}]} 插入成功——a 和 b 来自同一个数组 x,只算一个数组;{x: [{a: [1,2], b: [3,4]}]} 里 x.a 与 x.b 都是数组里的数组,报 cannot index parallel arrays [b] [a]。", t=tl(S(4)), mark=lidx(S(4), 'cannot index parallel arrays'), done=lidx(S(4), 'insertedId: 1'), kv=KV([['同一个数组的两个子字段', '算一个数组,允许'], ['各自是数组', '并行数组,拒绝']], ['同一个数组的两个子字段'])),
    step("办法一:拆成两个单字段索引 a_1、b_1(各自 multikey)。a、b 都是数组的集合 v 上,find({a: 3, b: 2}) 用 a_1,检查 6000 个键、6000 个文档,返回 1714(b 的条件在 FETCH 后过滤);直接建 {a: 1, b: 1} 复合索引失败(Index build failed)。", t=tl(S(5)), mark=lidx(S(5), 'Index build failed', 'keysExamined: 6000'), done=lidx(S(5), "'a_1', 'b_1'", 'IXSCAN(a_1)'), kv=KV([['两个单字段索引', '各自 multikey,可以建'], ['查询', '只用一个索引,另一个条件过滤'], ['复合索引', '建不出来']], ['两个单字段索引'])),
    step("办法二:把 a、b 的组合展开成 pairs 子文档数组,在 pairs.a + pairs.b 上建复合索引,查询用 $elemMatch:find({pairs: {$elemMatch: {a: 3, b: 2}}}) 只检查 1714 个键、1714 个文档,返回 1714;代价是索引条目变多——30,000 个文档的 pairs.a_1_pairs.b_1 索引有 120,000 条(每个文档 2 × 2 = 4 个子文档)。", t=tl(S(6)), mark=lidx(S(6), 'keysExamined: 1714', '120000'), done=lidx(S(6), 'IXSCAN(pairs.a_1_pairs.b_1)'), b=bars([['办法一:a_1 单字段索引', 6000, '检查 6000 个键'], ['办法二:pairs 复合索引', 1714, '检查 1714 个键']], 6000, mark=[1], done=[0]), kv=KV([['办法二', '$elemMatch + 复合索引,界限精确'], ['代价', '索引条目 120,000(文档的 4 倍)']], ['办法二'])),
]
A = mkartm('m22', 22, 'MongoDB,并行数组,复合索引,multikey,CannotIndexParallelArrays,真实验证,动画演示',
    '实测两个数组字段的复合索引:同一文档里最多一个被索引字段是数组,两个都是数组时插入、更新报 171(cannot index parallel arrays),已有这种文档时建索引失败;同一数组的两个子字段不算并行;拆成单字段索引或展开成子文档数组两种办法的检查键数对比。',
    '为什么两个数组字段的复合索引会报错?这篇用真实的错误逐个验证哪些情况允许、哪些拒绝,再对比两种绕开办法的查询代价。',
    [('171', '并行数组的错误码 CannotIndexParallelArrays,插入、更新、建索引都会触发'), ('6000 → 1714', '办法一(单字段索引)与办法二(pairs 子文档复合索引)检查的键数,返回都是 1714'), ('120,000', '展开成 pairs 后 30,000 个文档的复合索引条目数(每个文档 4 条)')],
    [('一个数组可以', '<p>复合索引里同一个文档最多只有一个被索引的字段是数组;一个数组加一个标量没问题。</p>'),
     ('两个数组不行', '<p>插入或更新让两个字段同时是数组,报 171 <code>cannot index parallel arrays</code>。索引不会展开成笛卡尔积,这样条目数会爆炸。</p>'),
     ('已有数据', '<p>集合里已经有这样的文档时,建索引直接失败,索引不会被创建。</p>'),
     ('路径决定', '<p>同一个数组的两个子字段(<code>x.a</code>、<code>x.b</code>,x 是数组)只算一个数组;各自是数组才是并行数组。</p>'),
     ('办法一', '<p>拆成两个单字段 multikey 索引,查询只能用其中一个,另一个条件在 FETCH 后过滤(检查 6000 个键)。</p>'),
     ('办法二', '<p>把组合展开成子文档数组,用 <code>$elemMatch</code> 查询,界限精确(1714 个键),代价是索引条目是文档数的 4 倍。</p>')],
    steps,
    [ENV_M + '。所有错误信息来自真实的 mongod;数据是固定公式生成的 30,000 个文档',
     '没有验证:并行数组检查在 $set 到子文档数组时的所有路径;分片键或唯一索引上的并行数组;wildcard 索引对此的放宽;展开成 pairs 之后更新一个元素的写放大;三个数组字段的组合'],
    '两个数组字段的复合索引')
