from lib import *
S = SS('m43')
steps = [
    step("没有唯一索引:16 个线程同时对同一个条件 {k: i} 做 upsert,共 300 轮(每轮所有线程用同一个 k)。结果文档总数 632(应为 300),有 227 个 k 被重复插入,最多重复 5 份,客户端没有收到任何错误。upsert 不是原子的“查不到才插入”,没有唯一索引就挡不住。", t=tl(S(1)), mark=lidx(S(1), '文档总数 632'), done=lidx(S(1), '错误数 0'), b=bars([['期望的文档数', 300, '300'], ['实际文档数', 632, '632']], 632, mark=[1], done=[0]), kv=KV([['无唯一索引', '并发 upsert 会重复插入'], ['重复', '300 个 k 里 227 个被重复,最多 5 份'], ['错误', '客户端一个都看不到']], ['无唯一索引'])),
    step("在 k 上建唯一索引再来一遍:300 轮 × 16 个线程后文档总数正好 300,客户端收到的错误数是 0——重复被索引挡住,而 E11000 也没有露给客户端。服务端对“条件是唯一键等值”的 upsert 遇到 E11000 时会自动重试。", t=tl(S(2)), mark=lidx(S(2), '客户端收到的错误数 0'), done=lidx(S(2), '文档总数 300'), kv=KV([['唯一索引', '文档数正好 300'], ['客户端错误', '0(服务端自动重试)']], ['唯一索引'])),
    step("自动重试不管用的情形:upsert 条件是 {a: ?},唯一索引在 b 上,$setOnInsert 给所有文档同一个 b=\"same\"。3 轮 × 16 个线程后只有 1 个文档,客户端收到 32 个 DuplicateKeyError(Plan executor error during update :: caused by :: E11000 duplicate key)。这时必须由应用处理。", t=tl(S(3)), mark=lidx(S(3), '错误数 32'), done=lidx(S(3), '文档数 1'), kv=KV([['条件不含唯一键', '服务端不自动重试'], ['结果', '32 个 E11000 露给客户端']], ['条件不含唯一键'])),
    step("应用层做法:条件是 {k, tag: \"x\"}(多了一个非唯一字段)时服务端同样不自动重试,捕获到 DuplicateKeyError 22 次;对每个错误改用 upsert=False 再更新一次,22 次都成功;最终文档数 60(60 个 k)。", t=tl(S(4)), mark=lidx(S(4), '22 次'), done=lidx(S(4), '60 个 k'), kv=KV([['捕获 DuplicateKeyError', '22 次'], ['再 update(不 upsert)', '22 次都成功'], ['最终', '60 个文档']], ['再 update(不 upsert)'])),
    step("findOneAndUpdate 做取号器:16 个线程各取 100 次 $inc,共 1600 个编号,不同的有 1600 个,最小 1,最大 1600——无重复无缺口。", t=tl(S(5)), mark=lidx(S(5), '1600 个编号'), done=lidx(S(5), '无重复无缺口'), kv=KV([['findOneAndUpdate + $inc', '原子,返回更新后的值'], ['1600 次', '1600 个不同编号']], ['findOneAndUpdate + $inc'])),
    step("$setOnInsert 只在插入时生效:第一次 upsert 返回 upsertedCount: 1、matchedCount: 0,文档带 created: 'first';第二次同一个条件 upsert,文档变成 { k: 1, created: 'first', v: 2 }——v 更新了,created 保持第一次的值。", t=tl(S(6)), mark=lidx(S(6), "created: 'first', v: 2", 'upsertedCount: 1'), done=lidx(S(6), 'matchedCount: 0'), kv=KV([['$setOnInsert', '只在插入时设置'], ['upsertedCount', '1 表示这次插入了']], ['$setOnInsert'])),
]
A = mkartm('m43', 43, 'MongoDB,upsert,并发,唯一索引,E11000,findOneAndUpdate,真实验证,动画演示',
    '实测并发 upsert:没有唯一索引时 16 线程 300 轮产生 632 个文档(227 个 k 重复);有唯一索引时文档数正好 300,服务端自动重试所以客户端看不到 E11000;条件不含唯一键时 E11000 会露给应用;捕获后改普通更新可行;findOneAndUpdate + $inc 取号无重复。',
    '并发 upsert 会不会重复插入?E11000 什么时候会露给应用?这篇用 16 个线程在同一个条件上并发 upsert,对比有无唯一索引,并给出应用层的处理办法。',
    [('632 对 300', '没有唯一索引时并发 upsert 后的文档数与应有的文档数'), ('0', '有唯一索引时客户端看到的 E11000 次数(服务端自动重试)'), ('1600', '16 个线程各 100 次 findOneAndUpdate + $inc 取得的不同编号数')],
    [('没有唯一索引', '<p>upsert 不是原子的“不存在才插入”:并发时多个线程都查不到,各自插入,300 个 k 里 227 个被重复,最多 5 份,而且没有任何错误。</p>'),
     ('有唯一索引', '<p>唯一索引挡住重复,文档数正好 300;对条件是唯一键等值的 upsert,服务端遇到 E11000 会自动重试一次,客户端看不到错误。</p>'),
     ('E11000 从哪来', '<p>条件不包含唯一键(例如多了别的字段,或唯一键值由 <code>$setOnInsert</code> 给出)时,服务端不重试,E11000 会作为 <code>DuplicateKeyError</code> 返回给应用。</p>'),
     ('应用层重试', '<p>捕获 DuplicateKeyError,改成不 upsert 的更新再来一次(此时文档已被别人插入)。</p>'),
     ('取号器', '<p><code>findOneAndUpdate</code> 加 <code>$inc</code> 是原子的,1600 次得到 1600 个不同的编号。</p>'),
     ('$setOnInsert', '<p>只在发生插入时设置字段,已存在时保持原值。</p>')],
    steps,
    [ENV_M + '。16 个线程用 Barrier 同步出手,重复/错误数每次运行都不同(这次 632、227、22、32)',
     '没有验证:服务端自动重试的精确条件(版本文档里的限制);分片集群与副本集下的并发 upsert;事务里的 upsert 与 WriteConflict(下面事务篇);upsert 配合 _id 的情形;多字段唯一索引上的 upsert 重试'],
    '并发 upsert 与唯一索引')
