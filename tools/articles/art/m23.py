from lib import *
S = SS('m23')
steps = [
    step("数据:30,000 个文档,email 有三种情况——字符串 20,000 个、显式 null 5,000 个、字段缺失 5,000 个;inactive 状态 1,500 个(5%)。", t=tl(S(1)), mark=lidx(S(1), 'nullEmail: 5000', 'missing: 5000'), done=lidx(S(1), 'hasEmail: 20000', 'inactive: 1500', 'total: 30000'), kv=KV([['有字符串', '20,000'], ['显式 null', '5,000'], ['字段缺失', '5,000']], ['显式 null'])),
    step("稀疏索引只收录“字段存在”的文档:普通索引 email_full 有 30,000 条,稀疏索引 email_sparse 有 25,000 条(字符串 + 显式 null,缺失的 5,000 个不进);索引大小 401,408 对 385,024 字节。", t=tl(S(2)), mark=lidx(S(2), '稀疏索引条目数 25,000'), done=lidx(S(2), '普通索引条目数 30,000', '索引大小'), b=bars([['普通索引', 30000, '30,000 条'], ['稀疏索引', 25000, '25,000 条']], 30000, mark=[1], done=[0]), kv=KV([['稀疏', '字段存在才收录(null 也算存在)'], ['缺失的文档', '不进索引']], ['稀疏'])),
    step("稀疏索引的陷阱:find({email: null}) 优化器选了普通索引 email_full(10,000 个,null 与缺失都匹配),不会用稀疏索引;用 hint 强制 email_sparse 只返回 5000 个,实际应该有 10000 个——漏了缺失的;find().sort({email: 1}).hint(\"email_sparse\") 只返回 25000 个,实际共 30000 个——排序用稀疏索引也会漏数据。", t=tl(S(3)), mark=lidx(S(3), '5000 vs 实际 10000', '25000 vs 实际 30000'), done=lidx(S(3), 'IXSCAN(email_full)', 'nReturned: 10000'), kv=KV([['优化器', '需要缺失的文档时不选稀疏索引'], ['hint 强制', '漏掉缺失字段的文档'], ['sort + hint', '同样会漏']], ['hint 强制'])),
    step("部分索引只收录满足 partialFilterExpression 的文档:score_inactive({status: inactive})只有 1,500 条、24,576 字节,普通索引 score_all 有 30,000 条、155,648 字节。查询条件蕴含过滤条件(status: inactive, score: 5)才走它;只写 score: 5 是 COLLSCAN,检查 30000 个文档;{status: {$in: [inactive, active]}, score: 5} 也不能用,同样 COLLSCAN。", t=tl(S(4)), mark=lidx(S(4), 'COLLSCAN'), done=lidx(S(4), '部分索引 score_inactive 条目数 1,500', 'IXSCAN(score_inactive)'), b=bars([['score_inactive', 1500, '1,500 条 / 24,576 字节'], ['score_all', 30000, '30,000 条 / 155,648 字节']], 30000, mark=[1], done=[0]), kv=KV([['部分索引', '只含 inactive 的 5%'], ['能用', '查询条件蕴含过滤条件'], ['不能用', '没写 status 或范围更宽']], ['能用'])),
    step("软删除常用法:给“未删除”的文档建唯一索引(partialFilterExpression: {deleted_at: null}):再插入一个未删除、同 email 的文档报 E11000 duplicate key ... dup key: { email: \"a@x.com\" };把 _id 1 软删除后,同 email 的新文档插入成功;再插一个同 email 且已删除的文档也成功。", t=tl(S(5)), mark=lidx(S(5), 'E11000'), done=lidx(S(5), '  true'), kv=KV([['未删除', '唯一'], ['已删除', '可以重复']], ['未删除'])),
    step("partialFilterExpression 的限制(9.0.2 实测):{a: {$exists: true}} 可以;{$or: [{a: 1}, {b: 2}]} 也可以;{a: {$ne: 1}} 报 Expression not supported in partial index: $not;和 sparse 同时指定报 cannot mix \"partialFilterExpression\" and \"sparse\" options。", t=tl(S(6)), mark=lidx(S(6), 'not supported', 'cannot mix'), done=lidx(S(6), 'a_1'), kv=KV([['$exists / $or', '允许'], ['$ne', '不允许($not)'], ['sparse + partial', '不能同时用']], ['$ne'])),
]
A = mkartm('m23', 23, 'MongoDB,部分索引,稀疏索引,partialFilterExpression,sparse,真实验证,动画演示',
    '实测稀疏索引与部分索引:稀疏索引收录字段存在的文档(显式 null 算存在),用 hint 或排序时会漏掉缺失的;部分索引只收录满足过滤条件的文档,体积小得多(24,576 对 155,648 字节),查询必须蕴含过滤条件才能用;软删除场景的唯一部分索引;过滤条件的限制($ne 不行,$or 可以)。',
    '哪些文档会进稀疏索引、哪些进部分索引?优化器什么时候会用、什么时候不会?这篇用 3 万个文档把缺失、null、字符串三种 email 和 5% 的 inactive 状态逐个验证,最后用部分唯一索引做软删除。',
    [('25,000 / 30,000', '稀疏索引与普通索引的条目数:缺失字段的 5,000 个文档不进稀疏索引'), ('24,576 B', '只收录 5% 文档的部分索引大小(同样字段的完整索引是 155,648 B)'), ('5000 对 10000', 'hint 稀疏索引查 {email: null} 得到的数量与实际数量')],
    [('三种 email', '<p>字段有字符串值、显式 <code>null</code>、字段缺失是三种不同情况,稀疏索引、唯一索引、部分索引对它们的处理各不相同。</p>'),
     ('稀疏索引', '<p>只收录字段存在的文档(显式 null 也算存在)。需要缺失的文档时优化器不会选它,硬 <code>hint</code> 或用它排序会漏掉缺失的文档。</p>'),
     ('漏数据', '<p>用 <code>hint("email_sparse")</code> 查 <code>{email: null}</code> 只返回 5000 个(实际 10000),对全集合排序只返回 25000 个(实际 30000)。</p>'),
     ('部分索引', '<p>只收录满足过滤条件的文档,体积小得多;查询条件必须蕴含过滤条件才会用它,没有写 <code>status</code> 条件就是全表扫描。</p>'),
     ('软删除', '<p>只给未删除的文档建唯一索引,已删除的文档可以重复;软删除之后同 email 的新文档可以插入。</p>'),
     ('限制', '<p>9.0.2 里过滤条件可以用 <code>$exists: true</code>、<code>$or</code>,不能用 <code>$ne</code>(<code>$not</code>);不能和 sparse 同时指定。</p>')],
    steps,
    [ENV_M + '。条目数来自 validate({full: true}).keysPerIndex,大小来自 collStats(fsync 之后读)',
     '没有验证:部分索引与复合索引、multikey 的组合;partialFilterExpression 中其它操作符($gt、$type、$and)的蕴含判断细节;参数化查询下部分索引的使用;稀疏复合索引的收录规则(任一字段存在即收录);部分唯一索引在 upsert 下的行为'],
    '部分索引与稀疏索引')
