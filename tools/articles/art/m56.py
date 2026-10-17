from lib import *
S = SS('m56')
steps = [
    step("插入重复的 _id:mongosh 里 e.name 是 MongoServerError,code 11000,message 是 E11000 duplicate key error collection: test.a index: _id_ dup key: { _id: 1 },keyPattern { _id: 1 },keyValue { _id: 1 };pymongo 抛 DuplicateKeyError,code 11000,e.details 的键是 code、errmsg、index、keyPattern、keyValue。", t=tl(S(1)), mark=lidx(S(1), "code: 11000", 'DuplicateKeyError.code = 11000'), done=lidx(S(1), 'keyPattern: { _id: 1 }', 'keyValue: { _id: 1 }'), kv=KV([['code', '11000'], ['message', '集合名 + 索引名 + dup key'], ['keyPattern / keyValue', '哪个索引、哪个值']], ['keyPattern / keyValue'])),
    step("不同索引上的 E11000:email 唯一索引冲突,index=email_1,dup key { email: \"a@x.com\" };复合唯一索引 org_seq 冲突,dup key { org: \"o1\", seq: 1 },keyPattern { org: 1, seq: 1 };嵌套字段 profile.phone 冲突,index=profile.phone_1,dup key { profile.phone: \"111\" },keyValue { 'profile.phone': '111' }。", t=tl(S(2)), mark=lidx(S(2), 'org_seq', 'profile.phone_1'), done=lidx(S(2), 'email_1'), kv=KV([['单字段', '{ email: \"…\" }'], ['复合', '{ org: \"o1\", seq: 1 }'], ['嵌套', '{ profile.phone: \"111\" }']], ['复合'])),
    step("一个文档同时违反两个唯一索引时,一次只报一个:第 1 次报的是 {email: 1};把 email 改掉再试,第 2 次报的才是 {org: 1, seq: 1}。", t=tl(S(3)), mark=lidx(S(3), '第 2 次报的是'), done=lidx(S(3), '第 1 次报的是'), kv=KV([['同时违反两个', '一次只报先检查到的那个'], ['处理', '修一个再试,可能还有下一个']], ['同时违反两个'])),
    step("很长的字符串键:5000 个字符的唯一字符串重复插入,errmsg 只有 230 字符,dup key 部分被截断成 162 字符加省略号;但 keyValue.s 仍是完整的 5000 个字符——程序要读 keyValue,不要解析 message。", t=tl(S(4)), mark=lidx(S(4), 'keyValue.s 长度 5000'), done=lidx(S(4), 'errmsg 长度 230'), kv=KV([['errmsg', '被截断(230 字符)'], ['keyValue', '完整(5000 字符)']], ['keyValue'])),
    step("“插入或取回已存在的”:捕获 DuplicateKeyError,用 e.details['keyValue'] 去查已有的文档。第一次插入新 email 返回 ('created', ObjectId…),第二次同一个 email 返回 ('existing', 同一个 ObjectId)。", t=tl(S(5)), mark=lidx(S(5), "('existing'"), done=lidx(S(5), "('created'"), kv=KV([['keyValue', '直接用作查询条件'], ['模式', '先插入,冲突了再查']], ['keyValue'])),
    step("批量与更新里的 E11000:insertMany(unordered)插入 [3, 1, 4, 2],已有 1、2:writeErrors 是 (下标 1, 11000, {k: 1}) 和 (下标 3, 11000, {k: 2}),nInserted 为 2;update 把 k=3 改成已有的 1 报 code 11000(errmsg 以 Plan executor error during update :: caused by :: E11000 开头);findOneAndUpdate 同样 code 11000、keyValue {k: 2}。", t=tl(S(6)), mark=lidx(S(6), 'writeErrors', 'Plan executor error during update', 'keyValue: { k: 2 }'), done=lidx(S(6), 'code: 11000'), kv=KV([['insertMany', 'writeErrors 逐个列出下标与 keyValue'], ['update / findOneAndUpdate', '同样的 11000']], ['insertMany'])),
]
A = mkartm('m56', 56, 'MongoDB,E11000,重复键,唯一索引,keyPattern,keyValue,真实验证,动画演示',
    '实测 E11000 错误里的信息:code 11000、message 里的集合名 + 索引名 + dup key,以及 keyPattern 与 keyValue;单字段、复合、嵌套字段上的形状;同时违反两个唯一索引一次只报一个;长键在 message 里被截断而 keyValue 完整;批量与更新里的写法和“插入或取回”模式。',
    '收到 E11000 duplicate key error 时,里面到底有什么信息?哪个索引冲突了、冲突的值是什么、能不能直接用?这篇把各种情形下的错误内容都打出来。',
    [('11000', 'E11000 重复键错误的错误码'), ('230 对 5000', '长字符串键冲突时 message 的长度与 keyValue 里完整值的长度'), ('一次一个', '一个文档违反两个唯一索引时一次只报一个')],
    [('错误内容', '<p>message 含集合名、索引名和 <code>dup key</code>;结构化字段 <code>keyPattern</code> 与 <code>keyValue</code> 指出是哪个索引、哪个值。</p>'),
     ('索引类型', '<p>单字段、复合、嵌套字段的 dup key 形状各不相同,但 <code>keyValue</code> 的键始终对应索引的键。</p>'),
     ('同时违反', '<p>违反多个唯一索引时一次只报一个,修好再试可能遇到下一个。</p>'),
     ('长键', '<p>message 会被截断(230 字符),<code>keyValue</code> 保持完整,程序应读结构化字段。</p>'),
     ('取回已存在的', '<p>先插入,冲突了就用 <code>keyValue</code> 查已有的文档,是常见的“获取或创建”写法。</p>'),
     ('批量与更新', '<p>批量写入的 <code>writeErrors</code> 逐个列出下标、code 和 keyValue;update 与 findOneAndUpdate 也是同样的 11000。</p>')],
    steps,
    [ENV_M + '。单节点;错误内容来自 mongosh 与 pymongo',
     '没有验证:分片集群上 E11000 的 keyValue 是否相同;副本集 secondary 上应用 oplog 时遇到重复键的处理;collation 唯一索引的 dup key 显示原值还是排序键;TTL、部分索引的冲突信息;老版本里 E11000 的 message 格式'],
    'E11000 错误信息')
