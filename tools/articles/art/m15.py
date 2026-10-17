from lib import *
S = SS('m15')
steps = [
    step("createView(\"paid_orders\", \"orders\", [{$match: {status: \"paid\"}}, {$project: {secret: 0}}]) 之后:getCollectionInfos 里 type 是 view,options 有 viewOn: 'orders' 和完整的 pipeline,info.readOnly 为 true;内部的 system.views 集合里存着 _id: 'test.paid_orders'、viewOn、pipeline——视图只是一条存下来的 pipeline,没有任何数据。", t=tl(S(1)), mark=lidx(S(1), "_id: 'test.paid_orders'", "type: 'view'", "readOnly: true"), done=lidx(S(1), "viewOn: 'orders'", "'system.views:collection'", 'paid_orders:view'), kv=KV([['视图', '一条存下来的 pipeline'], ['system.views', '保存 viewOn 和 pipeline'], ['readOnly', 'true']], ['视图'])),
    step("视图没有物化:paid_orders.countDocuments 先是 1000;把 orders 里 _id < 6 的 4 个文档(原本不是 paid)改成 paid 之后立即变成 1004,findOne({_id: 3}) 返回的文档已经去掉了 secret 字段(视图的 $project 生效)。", t=tl(S(2)), mark=lidx(S(2), '1004', 'modifiedCount', '_id: 3, user: '), done=lidx(S(2), '1000'), b=bars([['改之前', 1000, '1000'], ['改之后', 1004, '1004']], 1004, mark=[1], done=[0]), kv=KV([['视图', '每次查询都重新执行 pipeline'], ['底层数据一改', '视图立刻反映']], ['视图'])),
    step("视图用底层集合的索引:paid_orders.find({user: \"u3\"}) 的计划是 PROJECTION_SIMPLE > FETCH > IXSCAN(user_1),检查 150 个键 150 个文档,返回 51;直接在 orders 上查同样条件是 FETCH > IXSCAN(user_1),检查数一样。by_user(分组视图)上 $match 条件在分组键 _id 上,被优化器前移到 $group 之前,计划 GROUP > FETCH > IXSCAN(user_1),只检查 150 个文档;条件在聚合结果 total 上无法前移,计划 MATCH > GROUP > COLLSCAN,检查 3000 个文档。", t=tl(S(3)), mark=lidx(S(3), 'MATCH > GROUP > COLLSCAN', 'totalDocsExamined: 3000'), done=lidx(S(3), 'PROJECTION_SIMPLE > FETCH > IXSCAN(user_1)', 'GROUP > FETCH > IXSCAN(user_1)'), b=bars([['视图+条件在 user 上', 150, '150 文档'], ['分组视图+条件在 _id 上', 150, '150 文档'], ['分组视图+条件在 total 上', 3000, '3000 文档']], 3000, mark=[2], done=[0, 1]), kv=KV([['视图自己', '没有索引'], ['条件能前移', '走底层集合的索引'], ['条件在聚合结果上', '只能全表扫描']], ['条件能前移'])),
    step("对视图的限制:insertOne、createIndex、updateOne 都报 Namespace test.paid_orders is a view, not a collection;renameCollection 报 cannot rename view: test.paid_orders;但 find().sort({$natural: 1}) 可以(返回 1004 个)。", t=tl(S(4)), mark=lidx(S(4), 'is a view', 'cannot rename view'), done=lidx(S(4), '1004'), kv=KV([['写入 / 建索引', '报 is a view, not a collection'], ['rename', '不允许'], ['$natural 排序', '可以']], ['写入 / 建索引'])),
    step("视图套视图的层数:连续创建 lv1 基于 lv0、lv2 基于 lv1……成功到 lv20,创建 lv21 时报 View depth limit exceeded; maximum depth is 20。", t=tl(S(5)), mark=lidx(S(5), 'maximum depth is 20'), done=lidx(S(5), 'lv20'), kv=KV([['最大深度', '20 层'], ['超过', 'View depth limit exceeded']], ['最大深度'])),
    step("删掉底层集合 orders 之后视图还在(viewOn 仍是 orders),但查询返回空(0 个);collMod 可以改视图的 pipeline:v2 原先 $match k < 3 返回 3 个,改成 k >= 3 之后返回 7 个。", t=tl(S(6)), mark=lidx(S(6), 'collMod', '7'), done=lidx(S(6), 'length', "orders", '  0', '  3'), kv=KV([['底层集合没了', '视图还在,结果为空'], ['collMod', '直接改 pipeline']], ['collMod'])),
]
A = mkartm('m15', 15, 'MongoDB,视图,view,pipeline,索引,explain,真实验证,动画演示',
    '实测 MongoDB 视图:只是 system.views 里存下来的一条 pipeline,每次查询重新执行,底层数据一改视图立刻变化;视图没有自己的索引,过滤条件能前移到 $group 之前时走底层索引(150 个文档),在聚合结果上则全表扫描(3000 个);视图只读、深度上限 20、底层集合删除后查询为空、collMod 可以改 pipeline。',
    '视图是物化的吗?能走索引吗?这篇建了两个视图,看 listCollections 和 system.views 里存了什么,用 explain 对比条件能不能前移到 $group 之前,再试各种写入和限制。',
    [('150 对 3000', '对分组视图加过滤条件时,底层检查的文档数:条件在分组键上(走索引)对在聚合结果上(全表)'), ('20 层', '视图套视图的最大深度'), ('只是 pipeline', 'system.views 里只存 viewOn 和 pipeline,没有数据')],
    [('视图是什么', '<p>视图在 <code>system.views</code> 里只存 <code>viewOn</code> 和 <code>pipeline</code>,类型是 view,只读,不含任何数据。</p>'),
     ('不物化', '<p>每次查询都重新执行 pipeline,所以底层数据一改,视图立刻跟着变。</p>'),
     ('索引与前移', '<p>视图自己不能建索引,查询用底层集合的索引。优化器会把对视图的过滤条件尽量前移:在分组键上的条件前移到 <code>$group</code> 之前,走底层索引;在聚合结果字段上的条件前移不了,只能全表扫描。</p>'),
     ('限制', '<p>对视图的写入、建索引、更新、rename 都会报错;<code>$natural</code> 排序可以。</p>'),
     ('深度', '<p>视图套视图最多 20 层。</p>'),
     ('底层集合与修改', '<p>底层集合被删除后视图仍在,查询返回空;<code>collMod</code> 可以直接修改视图的 pipeline。</p>')],
    steps,
    [ENV_M + '。计划用 explain("executionStats") 取回,helper 函数把 inputStage 链拼成一行',
     '没有验证:视图上的 collation 与 $lookup / $unionWith 的行为;视图与 $text、$geoNear 的限制;视图查询的权限(基于角色的访问控制);分片集合上的视图;物化视图($merge / $out)的刷新策略;视图 pipeline 里使用 $lookup 时的索引选择'],
    '视图就是存下来的 pipeline')
