from lib import *
S = SS('m70')
steps = [
    step("分片键 {uid},手工分成 uid < 1000(在 sh0)和 >= 1000(在 sh1)。在非分片键 email 上建唯一索引失败:code 67,cannot create index with 'unique' or 'prepareUnique' option over { email: 1 } with shard key pattern { uid: 1 } and collation {}——服务端拒绝建一个它没法保证全局唯一的唯一索引。", t=tl(S(1)), mark=lidx(S(1), 'code 67'), done=lidx(S(1), 'create_index'), kv=KV([['分片集合上的 unique', '必须和分片键相关'], ['{email: 1} unique', 'code 67,拒绝']], ['{email: 1} unique'])),
    step("唯一索引必须以分片键为前缀:{uid: 1, email: 1} 的 unique 可以建(uid_1_email_1);把顺序反过来 {email: 1, uid: 1}(分片键不在前缀)同样 code 67 被拒绝。", t=tl(S(2)), mark=lidx(S(2), '{email: 1, uid: 1}', 'code 67'), done=lidx(S(2), 'uid_1_email_1'), kv=KV([['{uid, email} unique', '可以'], ['{email, uid} unique', '拒绝,分片键必须是前缀']], ['{uid, email} unique'])),
    step("这个唯一索引只保证“同一个 uid 下 email 不重复”:同一个 uid、同一个 email → E11000 duplicate key error ... index: uid_1_email_1;不同 uid(在另一个分片)、同一个 email → 成功;同一个分片内不同 uid、同一个 email → 成功。a@x.com 的文档在两个分片上共有 [2, 1] 个——email 在全局并不唯一。", t=tl(S(3)), mark=lidx(S(3), '全局并不唯一', '→ 成功'), done=lidx(S(3), 'E11000'), kv=KV([['同 uid 重复', 'E11000'], ['不同 uid 同 email', '成功,不唯一'], ['结论', '唯一性只限定在 (uid, email) 组合']], ['结论'])),
    step("_id 的唯一性只在单个分片内保证:分片键不是 _id 时,_id = \"same-id\" 的文档在 uid = 10(sh0)和 uid = 1600(sh1)可以各插入一个,各分片上的数量是 [1, 1],经 mongos 查到 2 个;第三个 _id 相同、uid = 20(和第一个同一个分片)被拒绝 E11000。", t=tl(S(4)), mark=lidx(S(4), '[1, 1]', '第二个'), done=lidx(S(4), '第三个'), b=bars([['sh0 上 _id=same-id', 1, '1 个'], ['sh1 上 _id=same-id', 1, '1 个']], 1, mark=[1], done=[0]), kv=KV([['_id 唯一', '只在分片内保证'], ['不同分片', '可以出现相同 _id'], ['建议', '_id 用 ObjectId 或让应用保证']], ['_id 唯一'])),
    step("想要全局唯一,就让唯一字段做分片键(或前缀):分片键 {email: 1} 且 shardCollection 时 unique=True,同样的 email 第二次插入报 E11000(全局唯一);a@x.com 和 z@x.com 分别在 sh0 和 sh1 上,各自数量 [1, 0] 与 [0, 1]。", t=tl(S(5)), mark=lidx(S(5), '全局唯一'), done=lidx(S(5), '[1, 0]'), kv=KV([['唯一字段做分片键', '全局唯一'], ['代价', '分片键不能被更新、基数要高']], ['唯一字段做分片键'])),
    step("哈希分片键不能声明 unique:shardCollection(key={k: \"hashed\"}, unique=True) → code 72,Hashed shard keys cannot be declared unique. It's possible to ensure uniqueness on the hashed field by declaring an additional (non-hashed) unique index on the field.;而 _id 用哈希做分片键时,同一个 _id 哈希后总在同一个分片,重复 _id 报 E11000,于是 _id 实际上是全局唯一的。", t=tl(S(6)), mark=lidx(S(6), 'code 72', '_id 用哈希做分片键'), done=lidx(S(6), 'shardCollection'), kv=KV([['hashed + unique', 'code 72 拒绝'], ['_id 哈希分片', '重复 _id 落在同一分片,E11000']], ['_id 哈希分片'])),
]
A = mkartm('m70', 70, 'MongoDB,分片,唯一索引,shard key,E11000,真实验证,动画演示',
    '实测分片集合上唯一索引的限制:非分片键的 unique 被拒(code 67);必须以分片键为前缀,但这样只保证同一个分片键值下唯一;_id 在分片键不是 _id 时可以在两个分片上重复;让唯一字段做分片键才能全局唯一;哈希分片键不能声明 unique(code 72),_id 哈希分片时 _id 实际全局唯一。',
    '分片之后,唯一索引还管用吗?_id 还是唯一的吗?怎样才能保证 email 全局唯一?这篇在两个分片上逐个情形验证。',
    [('code 67', '分片集合上对非分片键建唯一索引的错误码'), ('[1, 1]', '分片键不是 _id 时,同一个 _id 在两个分片上各有一个'), ('code 72', 'hashed 分片键声明 unique 的错误码')],
    [('不能随便 unique', '<p>分片集合上对非分片键建唯一索引,服务端直接拒绝(code 67),因为每个分片只能保证自己的那一份。</p>'),
     ('必须以分片键为前缀', '<p>唯一索引要以分片键为前缀(<code>{uid, email}</code> 可以,<code>{email, uid}</code> 不行)。</p>'),
     ('前缀方案的含义', '<p><code>{uid, email}</code> 的唯一索引只保证同一个 uid 下 email 不重复;不同 uid(在不同分片)可以有同样的 email。</p>'),
     ('_id', '<p>分片键不是 <code>_id</code> 时,<code>_id</code> 的唯一性只在单个分片内保证,不同分片上可以有相同的 <code>_id</code>。</p>'),
     ('全局唯一', '<p>让需要唯一的字段做分片键(或其前缀),并在 <code>shardCollection</code> 时指定 <code>unique: true</code>。</p>'),
     ('哈希', '<p>哈希分片键不能声明 unique;但 <code>_id</code> 用哈希分片时,相同的 <code>_id</code> 必然落在同一个分片,实际上全局唯一。</p>')],
    steps,
    [ENV_M + '。2 个分片(各为单节点副本集),分片范围手工 split 与 moveChunk 得到',
     '没有验证:chunk 迁移时唯一冲突的处理;分片键后缀的 refineCollectionShardKey;唯一性代理集合的做法(应用层维护一个以唯一字段为分片键的映射集合);事务里跨分片的唯一性检查;MongoDB 对 unique 部分索引在分片集合上的限制'],
    '分片集合上的唯一索引')
