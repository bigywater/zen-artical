from lib import *
S = SS('m5')
steps = [
    step("hello 命令里服务端告诉客户端的上限:maxBsonObjectSize 16777216(= 16 × 1024 × 1024),maxMessageSizeBytes 48000000,maxWriteBatchSize 100000。", t=tl(S(1)), mark=lidx(S(1), 'maxBsonObjectSize: 16777216'), done=lidx(S(1), 'maxMessageSizeBytes', 'maxWriteBatchSize'), kv=KV([['maxBsonObjectSize', '16,777,216 字节'], ['maxMessageSizeBytes', '48,000,000'], ['maxWriteBatchSize', '100,000']], ['maxBsonObjectSize'])),
    step("刚好 16,777,216 字节(16 MiB)的文档能插入(32 ms),读回来字符串长度 16,777,194;只多 1 个字节(16,777,217),insert_one 抛 WriteError:object to insert too large. size in bytes: 16777217, max size: 16777216,错误码 10334——这个错误是服务端返回的。", t=tl(S(2)), mark=lidx(S(2), '多 1 字节'), done=lidx(S(2), '文档编码后', 'insert_one 成功'), kv=KV([['刚好 16,777,216', '成功'], ['多 1 字节', '服务端返回 10334'], ['含义', '上限是整个 BSON 文档的字节数']], ['含义'])),
    step("用原始 insert 命令把超限文档放进 documents 数组:超 1 字节和超 1024 字节都是 n=0,writeErrors 里是同样的 10334(命令本身不抛异常,要看回复);超 16 KiB 时 pymongo 在客户端就抛 DocumentTooLarge(BSON document too large (16793685 bytes) - the connected server supports BSON document sizes up to 16793598 bytes)。集合里最后只有最开始的那 1 个文档。", t=tl(S(3)), mark=lidx(S(3), '超 1 字节', '超 1024 字节', 'DocumentTooLarge'), done=lidx(S(3), '集合里最后'), kv=KV([['writeErrors', '逐文档的错误,命令本身不抛'], ['超 16 KiB', '客户端按命令体上限 16793598 拒绝'], ['集合里', '仍只有 1 个文档']], ['writeErrors'])),
    step("update 把文档撑过 16 MiB:14 MiB 的文档用 $concat 把字符串拼成两倍,报 RCString too large. Requires size=29360128 < limit=16777216,文档仍是 14.000 MiB;换成每次 $push 1 MiB 字符串,第 16 次报 Resulting document after update is larger than 16777216,数组里还剩 15 个元素。", t=tl(S(4)), mark=lidx(S(4), 'RCString too large', '第 16 次'), done=lidx(S(4), '14.000', 'n: 15'), kv=KV([['$concat 超限', 'RCString too large'], ['$push 超限', 'Resulting document after update is larger than 16777216'], ['失败后', '文档保持原样']], ['$push 超限'])),
    step("嵌套深度:二分查找得到,内嵌 179 层的文档能插入,180 层失败,错误是 cannot insert document :: caused by :: object exceeds 180 levels of nesting;内嵌 250 层则是更底层的 BSONObj exceeds maximum nested object depth;服务端参数 maxBSONDepth 是 200。这台 9.0.2 上限是 180,不是常说的 100。", t=tl(S(5)), mark=lidx(S(5), '180 层失败', 'exceeds 180 levels', '内嵌 250 层', 'maxBSONDepth: 200'), done=lidx(S(5), '内嵌 100 层: 成功'), kv=KV([['能插入', '内嵌 179 层'], ['插入失败', '内嵌 180 层:exceeds 180 levels of nesting'], ['BSON 解析上限', 'maxBSONDepth = 200']], ['插入失败'])),
    step("聚合产生超过 16 MiB 的文档:20 个 1 MiB 的字符串 $group 后 $push 进一个数组,mongosh 取回的文档有 20 个元素、20,971,714 字节(> 16 MiB,返回给客户端没有被拒绝);同一个 pipeline 后面接 $out 写进集合则失败:Serializing Document failed :: caused by :: Size 20971714 exceeds maximum 16793600。", t=tl(S(6)), mark=lidx(S(6), 'exceeds maximum 16793600'), done=lidx(S(6), '[ 20, 20971714, true ]', 'bytes: 20971520'), kv=KV([['中间 / 返回的文档', '可以超过 16 MiB'], ['写进集合', '超过 16793600 字节就失败'], ['建议', '用 $sum 等累加器代替 $push 全部']], ['写进集合'])),
]
A = mkartm('m5', 5, 'MongoDB,16MB,文档大小,嵌套深度,maxBsonObjectSize,真实验证,动画演示',
    '实测 MongoDB 的文档大小与嵌套深度上限:maxBsonObjectSize 是 16,777,216 字节,刚好等于的文档能插入、多 1 字节被服务端用错误码 10334 拒绝;update 撑过上限的报错;嵌套深度在 9.0.2 上限是 180 层;聚合里 $push 出的文档可以超过 16 MiB 返回客户端,但写进集合会失败。',
    '16MB 的上限到底卡在哪一步?嵌套深度的上限是多少?这篇构造刚好 16 MiB 的文档,逐字节增加,看 insert、update 和聚合在哪一步报什么错,并用二分查找确认嵌套深度的上限。',
    [('16,777,216', 'maxBsonObjectSize:刚好这么大的文档能插入,多 1 字节就报 10334'), ('180 层', '9.0.2 上能插入的最大嵌套深度是 179 层内嵌,180 层失败(maxBSONDepth 参数是 200)'), ('20,971,714', '聚合返回的文档可以大于 16 MiB,写进集合时才报 Size … exceeds maximum 16793600')],
    [('上限是多少', '<p><code>hello</code> 返回 <code>maxBsonObjectSize</code> 16,777,216 字节,整个 BSON 文档(含所有键名和结尾)不能超过它。</p>'),
     ('刚好与多 1 字节', '<p>刚好 16 MiB 的文档能插入;多 1 字节服务端返回错误码 10334 <code>object to insert too large</code>。</p>'),
     ('原始命令', '<p>直接用 <code>insert</code> 命令时,超限文档在回复的 <code>writeErrors</code> 里,命令本身不抛异常;超出命令体上限(16793598)时驱动在客户端就拒绝。</p>'),
     ('update 撑大', '<p><code>$push</code> 把文档撑过上限时报 <code>Resulting document after update is larger than 16777216</code>,文档保持原样;聚合表达式里拼出过大的字符串则报 <code>RCString too large</code>。</p>'),
     ('嵌套深度', '<p>在这台 9.0.2 上,二分查找得到内嵌 179 层可以插入、180 层失败(<code>object exceeds 180 levels of nesting</code>);更深的文档连 BSON 本身都拒绝(参数 <code>maxBSONDepth</code> 是 200)。常说的 100 层与此不同,以实测为准。</p>'),
     ('聚合产生大文档', '<p>聚合的结果文档可以超过 16 MiB 返回给客户端(实测 20,971,714 字节),但写进集合(<code>$out</code>)时超过 16793600 字节就失败。需要汇总时尽量用累加器而不是 <code>$push</code> 全部元素。</p>')],
    steps,
    [ENV_M + '。文档大小用 bson.encode 精确构造;嵌套深度用二分查找',
     '没有验证:GridFS 绕过 16MB 的做法;分片集群上的限制;索引键超长的限制(见索引一篇);$push 在 100MB 内存限制处的行为;mongosh 取回超大文档的内存开销;其它版本的嵌套深度(手册写的 100 层与这台实测的 180 层不同,没有核对原因)'],
    '16MB 与嵌套深度')
