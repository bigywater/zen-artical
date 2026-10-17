from lib import *
S = SS('m12')
steps = [
    step("capped 集合 size=4096、max=5,依次插入 _id 1~8:读出来只剩 4、5、6、7、8 五个;stats 里 capped 为 true,max 5,maxSize 4096,count 5,size 130。max 限制文档数,最老的先被挤掉。", t=tl(S(1)), mark=lidx(S(1), 'count: 5'), done=lidx(S(1), '_id: 4', '_id: 8'), kv=KV([['max', '限制文档数(这里 5)'], ['size', '限制总字节数(这里 4096)'], ['先到先挤', '最老的文档先被覆盖']], ['max'])),
    step("size 限制总字节数:size=4096,每个文档 194 字节,连续插入 100 个,集合里的文档数依次是 1、11、21、21、21……稳定在 21 个(size 4074 字节,maxSize 4096);留下的是最后插入的 _id 79 到 99。", t=tl(S(2)), mark=lidx(S(2), 'count: 21', '79, 80'), done=lidx(S(2), '93, 94', '86, 87'), b=bars([['插入 10 个后', 11, '文档数 11'], ['插入 20 个后', 21, '文档数 21'], ['插入 100 个后', 21, '文档数 21(封顶)']], 21, mark=[2], done=[0, 1]), kv=KV([['maxSize', '4096 字节'], ['稳定文档数', '21(194 × 21 = 4074)'], ['留下的', '最新的 _id 79~99']], ['稳定文档数'])),
    step("9.0.2 上实测这些在 capped 集合里都能成功:deleteOne({_id: 91}) 返回 deletedCount: 1;把 _id 92 的字段改成 400 字节(原来 170)matched 1、modified 1;_id 93 大小不变的更新、_id 94 改短、_id 95 用 replaceOne 换成 400 字节的文档都成功。读回来 _id 92 的 pad 长 400,93 是 170,94 是 1,95 是 400(91 已被删除)。不要照搬旧资料里“capped 集合不能删除、不能改大”的说法。", t=tl(S(3)), mark=lidx(S(3), 'deletedCount: 1', '[ [ 92, 400 ]'), done=lidx(S(3), 'matchedCount: 1', 'modifiedCount: 1'), kv=KV([['删除单个文档', '成功(deletedCount 1)'], ['更新变长 / replace 变长', '成功'], ['读回', '92→400,93→170,94→1,95→400']], ['删除单个文档'])),
    step("自然顺序就是插入顺序:sort({$natural: -1}).limit(3) 返回 99、98、97;getIndexes 显示 capped 集合有 _id_ 索引。", t=tl(S(4)), mark=lidx(S(4), '99, 98, 97'), done=lidx(S(4), "'_id_'"), kv=KV([['$natural: -1', '最新的在前'], ['索引', '有 _id_ 索引']], ['$natural: -1'])),
    step("tailable 游标:一个线程用 TAILABLE_AWAIT 一直等,主线程每隔 0.7 秒插入一个文档,游标收到 (距启动的秒数, _id) = (0.0, 0)、(1.0, 1)、(1.7, 2)、(2.4, 3)——新文档一插入就收到。对普通集合请求 tailable 则报错:tailable cursor requested on non capped collection。", t=tl(S(5)), mark=lidx(S(5), '(1.0, 1)', 'tailable cursor requested'), done=lidx(S(5), 'tailable 游标收到'), kv=KV([['TAILABLE_AWAIT', '像 tail -f 一样等新文档'], ['普通集合', '报错:non capped collection']], ['TAILABLE_AWAIT'])),
    step("把 1000 个文档的普通集合 convertToCapped(size=32768):{'ok': 1.0},转换后 capped=True,count=264,maxSize=32768,最早的 _id 是 736、最晚是 999——最老的被丢弃。collMod cappedSize=16384、cappedMax=50 返回 ok,count 暂时还是 264;再插入 1 个文档后 count 立刻变成 50,最早的 _id 是 951。", t=tl(S(6)), mark=lidx(S(6), 'count=50', 'collMod'), done=lidx(S(6), 'convertToCapped', 'count=264,maxSize=32768', '最早的 _id = 736'), kv=KV([['convertToCapped', '保留最新的 264 个'], ['collMod', '在线改大小或文档数'], ['生效', '下一次插入时才裁剪']], ['collMod'])),
]
A = mkartm('m12', 12, 'MongoDB,capped集合,固定大小,tailable,convertToCapped,真实验证,动画演示',
    '实测 capped 集合:max 限制文档数、size 限制字节数,写满后最老的先被覆盖,自然顺序即插入顺序;9.0.2 上删除单个文档和把文档改大都能成功(与旧说法不同);tailable 游标实时收到新文档;convertToCapped 与 collMod 可以在线转换和改大小。',
    'capped 集合写满后覆盖的顺序是什么?还有哪些限制?这篇用 max=5 和 size=4096 的小集合逐步观察,再验证删除、改大文档、tailable 游标、转换和在线改大小。',
    [('21 个', 'size=4096、文档 194 字节的 capped 集合,稳定保留的文档数'), ('能删能改大', '9.0.2 上 capped 集合的 deleteOne 与变长更新都成功,和旧资料里的限制不同'), ('count 264 → 50', 'collMod 把 cappedMax 改成 50 后,下一次插入时集合立刻裁剪到 50')],
    [('max 与 size', '<p>capped 集合有 <code>size</code>(字节)与可选的 <code>max</code>(文档数)两个上限,先到先生效,写满后最老的文档被覆盖。</p>'),
     ('字节上限', '<p>size=4096、每个文档 194 字节时,集合稳定保留 21 个最新的文档。</p>'),
     ('限制要以实测为准', '<p>在这台 9.0.2 上,删除单个文档、把文档改大、replaceOne 变长都成功了。常见资料里“不能删除、不能增长”的说法至少对这个版本不成立(没有逐个版本核对)。</p>'),
     ('自然顺序', '<p>capped 集合的自然顺序就是插入顺序,<code>$natural: -1</code> 可以倒着读最新的;它也带 <code>_id_</code> 索引。</p>'),
     ('tailable 游标', '<p>tailable 游标可以像 <code>tail -f</code> 一样等待新文档,只能用在 capped 集合上,普通集合会报错。</p>'),
     ('转换与在线修改', '<p><code>convertToCapped</code> 把普通集合转成 capped,保留最新的文档;<code>collMod</code> 可以在线改 <code>cappedSize</code>、<code>cappedMax</code>,下一次插入时才裁剪到新上限。</p>')],
    steps,
    [ENV_M + '。每一步都用真实的 mongosh 或 pymongo 命令;tailable 游标用 pymongo 的 TAILABLE_AWAIT',
     '没有验证:capped 集合上 delete 和变长更新从哪个版本开始允许;副本集里 capped 集合的删除如何复制到 oplog;分片集合不能是 capped;TTL 索引不能建在 capped 集合上;capped 集合在 oplog 内部的用法;更大 size 时覆盖的粒度'],
    'capped 集合')
