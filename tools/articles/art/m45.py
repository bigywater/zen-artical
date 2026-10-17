from lib import *
S = SS('m45')
steps = [
    step("ordered(默认)按顺序执行,遇到第一个错误就停下:10 个文档,第 5 个(下标 4)的 _id 与已有的 _id 1 重复,nInserted = 4,writeErrors 只有一个 (4, 11000, E11000 duplicate key ...);集合里只有 _id 0、1、2、3,后面 5 个没有插。", t=tl(S(1)), mark=lidx(S(1), 'nInserted = 4', '[0, 1, 2, 3]'), done=lidx(S(1), 'writeErrors'), kv=KV([['ordered', '第一个错误就停'], ['nInserted', '4(下标 0~3)'], ['后面的 5 个', '不执行']], ['ordered'])),
    step("unordered(ordered=False)出错的跳过,其余照常执行:先放入 _id 1、2,再插入 10 个文档(其中下标 1、2 与已有的重复,下标 4、7 的 _id 被换成 1、2 也重复):nInserted = 6,writeErrors 的 index 是 [1, 2, 4, 7],4 个错误一起返回;集合里是 _id [0, 1, 2, 3, 5, 6, 8, 9]。", t=tl(S(2)), mark=lidx(S(2), '[1, 2, 4, 7]'), done=lidx(S(2), 'nInserted = 6', '[0, 1, 2, 3, 5, 6, 8, 9]'), kv=KV([['unordered', '错误的跳过,其余继续'], ['writeErrors', '所有错误一起返回'], ['nInserted', '6']], ['unordered'])),
    step("有依赖的混合操作:ordered 的 [insert a, update a] 先插入再更新,n = 11;ordered 的 [update b, insert b] 按顺序先 update(什么也没匹配到,matched 0)再 insert,n = 1;同样的 [update b, insert b] 用 unordered 则 matched 1、n = 11,顺序不再保证。实际发出的命令:unordered 是 insert、update、delete(同类操作分组,插入排在更新前);ordered 是 update、insert、delete(原顺序)。", t=tl(S(3)), mark=lidx(S(3), 'unordered [update b, insert b]', "('insert', 1), ('update', 1)"), done=lidx(S(3), 'ordered   [insert a, update a]', 'ordered   [update b, insert b]', "('update', 1), ('insert', 1)"), kv=KV([['ordered', '严格按顺序,每次类型变化换一条命令'], ['unordered', '同类操作分组,顺序不保证'], ['有依赖', '必须用 ordered']], ['有依赖'])),
    step("批次拆分:250,000 个文档的 insert_many 被拆成 3 条 insert 命令 [100000, 100000, 50000](maxWriteBatchSize 是 100,000);ordered 493 ms,unordered 476 ms,拆分方式相同。", t=tl(S(4)), mark=lidx(S(4), '[100000, 100000, 50000]'), done=lidx(S(4), 'ordered', 'unordered'), kv=KV([['maxWriteBatchSize', '100,000'], ['250,000 个文档', '3 条命令'], ['ordered / unordered', '拆分相同']], ['maxWriteBatchSize'])),
    step("耗时(插入 5 万个文档,5 次中位数):ordered 105 ms,unordered 102 ms——单节点上差别很小。", t=tl(S(5)), mark=lidx(S(5), 'unordered 102 ms'), done=lidx(S(5), 'ordered 105 ms'), b=bars([['ordered', 105, '105 ms'], ['unordered', 102, '102 ms']], 105, mark=[1], done=[0]), kv=KV([['单节点', 'ordered 与 unordered 几乎一样快']], ['单节点'])),
    step("BulkWriteError.details 的键:nInserted、nMatched、nModified、nRemoved、nUpserted、upserted、writeConcernErrors、writeErrors;writeErrors[0] 的键:code、errmsg、index、keyPattern、keyValue、op;这里 code=11000、index=1、keyValue={'_id': 1}。", t=tl(S(6)), mark=lidx(S(6), 'writeErrors[0] 的键'), done=lidx(S(6), 'details 的键'), kv=KV([['details', 'nInserted … writeErrors …'], ['writeErrors[i]', 'code / index / keyValue / op'], ['index', '在这一批里的下标']], ['writeErrors[i]'])),
]
A = mkartm('m45', 45, 'MongoDB,bulkWrite,ordered,unordered,批量写入,真实验证,动画演示',
    '实测 bulkWrite 的 ordered 与 unordered:ordered 在第一个错误处停止(nInserted 4),unordered 跳过错误继续(nInserted 6,4 个错误一起返回);混合操作的顺序在 unordered 下不再保证;25 万个文档拆成 3 条命令(maxWriteBatchSize 100,000);单节点上耗时几乎一样。',
    'bulkWrite 的 ordered 和 unordered 差在哪?出错时会怎样?操作之间有依赖时能不能用 unordered?这篇用带重复键的批量插入和混合操作逐个验证,还看了批次拆分。',
    [('4 对 6', '同样的批量插入遇到重复键时,ordered 与 unordered 已插入的文档数'), ('3 条', '25 万个文档的批量插入被拆成的 insert 命令数'), ('105 / 102 ms', '5 万个文档的 ordered / unordered 插入耗时')],
    [('ordered', '<p>默认 ordered:按顺序执行,第一个错误处停止,后面的操作不会执行;<code>writeErrors</code> 里只有那一个错误。</p>'),
     ('unordered', '<p><code>ordered=False</code>:出错的操作被跳过,其余照常执行,所有错误一起在 <code>writeErrors</code> 里返回。</p>'),
     ('操作依赖', '<p>混合操作之间有依赖(先插入再更新)就必须用 ordered;unordered 下驱动会把同类操作分组,插入排在更新之前,顺序不再保证。</p>'),
     ('批次拆分', '<p>一次 bulk 超过 <code>maxWriteBatchSize</code>(100,000)会拆成多条命令,25 万个文档拆成 100000 + 100000 + 50000 三条。</p>'),
     ('耗时', '<p>单节点上 ordered 和 unordered 的耗时几乎一样(105 对 102 ms)。</p>'),
     ('错误详情', '<p><code>BulkWriteError.details</code> 里有各类计数和 <code>writeErrors</code>,每个错误带 code、index、keyValue、op 等字段。</p>')],
    steps,
    [ENV_M + '。命令序列通过 pymongo 的 CommandListener 记录',
     '没有验证:分片集群上 unordered 的并行效果;副本集 w:majority 下两者的耗时差别;超过 48 MB 消息上限的拆分(这里只验证了文档数拆分);带事务的 bulkWrite;驱动之外的 mongosh bulkWrite 与新的 client.bulkWrite 命令'],
    'bulkWrite 的 ordered 与 unordered')
