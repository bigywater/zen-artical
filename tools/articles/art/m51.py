from lib import *
S = SS('m51')
steps = [
    step("默认情况下各事件带的内容:insert 带完整文档(fullDocument {_id: 2, status: 'new', n: 0});update 只带 updateDescription——updatedFields {status: 'paid'}、removedFields ['n']、truncatedArrays [],没有 fullDocument;replace 带新文档 {_id: 2, status: 'replaced'};delete 只有 documentKey {_id: 2}。", t=tl(S(1)), mark=lidx(S(1), "operationType: 'update'", "operationType: 'delete'"), done=lidx(S(1), "operationType: 'insert'", "operationType: 'replace'"), kv=KV([['insert / replace', '带完整新文档'], ['update', '只带 updateDescription'], ['delete', '只有 documentKey']], ['update'])),
    step("fullDocument: \"updateLookup\":update 事件附带的是“查询那一刻”的当前文档,不是这次修改刚完成时的样子。连续把 n 改成 1 再改成 2,消费者晚一点读取:第一个事件的 updatedFields 是 {n: 1},updateLookup 取回的 fullDocument.n 却是 2;第二个事件 {n: 2},fullDocument.n 也是 2——n=1 那个中间状态丢了。", t=tl(S(2)), mark=lidx(S(2), "updatedFields={'n': 1};updateLookup 取回的 fullDocument.n = 2", '丢了'), done=lidx(S(2), "updatedFields={'n': 2}"), b=bars([['事件 1:updatedFields n=1', 2, 'fullDocument.n = 2'], ['事件 2:updatedFields n=2', 2, 'fullDocument.n = 2']], 2, mark=[0], done=[1]), kv=KV([['updateLookup', '取查询时刻的当前文档'], ['问题', '快速连续修改时看到的是最新状态,不是该次修改的结果']], ['问题'])),
    step("要精确的前后镜像:集合上 collMod changeStreamPreAndPostImages {enabled: true},watch 时 full_document=\"required\"、full_document_before_change=\"required\":两次更新的事件分别是 前镜像 n=2/后镜像 n=10 和 前镜像 n=10/后镜像 n=20,与 updatedFields 严格对应;delete 事件的 fullDocumentBeforeChange 是删除前的完整文档 {_id: 1, status: 'new', n: 20, tags: [1, 2, 3]}。", t=tl(S(3)), mark=lidx(S(3), '前镜像 n = 2,后镜像 n = 10', '前镜像 n = 10,后镜像 n = 20', 'delete 事件'), done=lidx(S(3), 'update 事件'), kv=KV([['required', '没有镜像就报错,不会给你一个过期的'], ['前镜像', 'fullDocumentBeforeChange'], ['后镜像', 'fullDocument']], ['required'])),
    step("在 watch 的 pipeline 里过滤:10 次更新,只想要 status 变成 paid 的:{$match: {operationType: 'update', 'updateDescription.updatedFields.status': 'paid'}}。不带过滤的 stream 收到 10 个事件,带 $match 的收到 4 个,documentKey 是 [0, 3, 6, 9](i % 3 == 0)——过滤在服务端完成。", t=tl(S(4)), mark=lidx(S(4), '带 $match 的 stream 收到 4 个'), done=lidx(S(4), '收到 10 个事件'), b=bars([['不过滤', 10, '10 个事件'], ['$match 过滤', 4, '4 个事件']], 10, mark=[1], done=[0]), kv=KV([['$match', '服务端过滤,少传事件'], ['过滤条件', 'operationType、updateDescription、fullDocument …']], ['$match'])),
    step("insert 事件自带 fullDocument,可以直接 $match fullDocument.kind;$project 能裁剪字段:3 个插入里只收到 kind 为 vip 的 2 个,且只剩 fullDocument.kind、fullDocument.name 和 operationType(big 字段被裁掉);但 $project 去掉 _id 会报错 OperationFailure:Encountered an event whose _id field, which contains the resume token, was modified——_id 就是 resume token,不能动。", t=tl(S(5)), mark=lidx(S(5), 'resume token, was modified'), done=lidx(S(5), '只有 vip 的'), kv=KV([['$match fullDocument.kind', '可以'], ['$project', '裁剪字段'], ['去掉 _id', '报错,_id 是 resume token']], ['去掉 _id'])),
    step("删除集合时 stream 先收到 drop 事件,再收到 invalidate 事件,然后 stream 关闭(stream.alive 为 False);要继续监视必须重新打开(用 startAfter 配合 invalidate 的 token)。", t=tl(S(6)), mark=lidx(S(6), "['drop', 'invalidate']", 'alive = False'), done=lidx(S(6), 'drop 之后收到'), kv=KV([['drop 集合', '事件 drop + invalidate'], ['invalidate 之后', 'stream 关闭']], ['drop 集合'])),
]
A = mkartm('m51', 51, 'MongoDB,change stream,fullDocument,updateLookup,前后镜像,pipeline,真实验证,动画演示',
    '实测 change stream 的事件内容与过滤:update 默认只带 updateDescription;updateLookup 取到的是查询那一刻的文档,快速连续修改会丢掉中间状态;changeStreamPreAndPostImages 加 required 才有精确的前后镜像;pipeline 的 $match 在服务端过滤(10 个事件只收到 4 个);$project 不能去掉 _id;drop 后收到 invalidate。',
    'change stream 的 update 事件里为什么没有整个文档?updateLookup 拿到的是不是修改后的样子?怎么在服务端过滤?这篇逐个验证事件内容、两种镜像方案和 pipeline 过滤。',
    [('fullDocument.n = 2', 'updateLookup 在两次快速修改后,第一个事件(这次修改后 n=1)取回的 n 值——中间状态丢了'), ('10 → 4', '带 $match 的 stream 与不过滤的 stream 收到的事件数'), ('required', '前后镜像的取值:没有镜像就报错而不是给过期的文档')],
    [('各类事件的内容', '<p>insert / replace 带完整文档,update 只带 <code>updateDescription</code>(updatedFields、removedFields、truncatedArrays),delete 只有 <code>documentKey</code>。</p>'),
     ('updateLookup', '<p><code>fullDocument: "updateLookup"</code> 在读取事件时去查当前文档,所以连续修改时看到的是最新状态,不是该次修改后的样子。</p>'),
     ('前后镜像', '<p>集合上打开 <code>changeStreamPreAndPostImages</code> 后,<code>required</code> 能拿到精确的前镜像与后镜像,delete 事件也能拿到删除前的文档。</p>'),
     ('服务端过滤', '<p>watch 的 pipeline 里 <code>$match</code> 在服务端过滤,只把匹配的事件发给客户端。</p>'),
     ('$project', '<p>可以裁剪字段减少传输,但不能改动 <code>_id</code>(它就是 resume token)。</p>'),
     ('drop 与 invalidate', '<p>集合被删除时 stream 依次收到 drop 和 invalidate 然后关闭,需要重新打开。</p>')],
    steps,
    [ENV_M + '。单节点副本集;事件内容通过 pymongo 的 watch 读取',
     '没有验证:预镜像占用的存储与过期策略(changeStreamOptions.preAndPostImages.expireAfterSeconds);showExpandedEvents 下的更多事件类型(createIndexes、modify 等);数据库级与整个部署级的 change stream;分片集群上事件的全局顺序;大量事件时 $match 的性能与 CPU 开销'],
    'change stream 的 pipeline 与 fullDocument')
