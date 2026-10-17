from lib import *
S = SS('m68')
steps = [
    step("3 个分片,分片键 uid(ranged),手工 split 在 1000、2000 并 moveChunk:sh0 拥有 [MinKey, 1000)、sh1 拥有 [1000, 2000)、sh2 拥有 [2000, MaxKey),每段 1000 个文档。", t=tl(S(1)), mark=lidx(S(1), 'sh1  [1000, 2000)'), done=lidx(S(1), 'sh0  [MinKey()', 'sh2  [2000'), kv=KV([['sh0', 'uid < 1000'], ['sh1', '[1000, 2000)'], ['sh2', '>= 2000']], ['sh1'])),
    step("explain 里 winningPlan.stage 与涉及的分片:uid = 1500 → SINGLE_SHARD、['sh1'];uid ∈ [500, 800) → SINGLE_SHARD、['sh0'];uid ∈ [900, 1100) 跨两段 → SHARD_MERGE、['sh0', 'sh1'];uid $in [10, 1100, 2100] → SHARD_MERGE、三个分片;city = 7(不含分片键)→ SHARD_MERGE、三个分片;空条件 → 三个分片;city = 7 加 sort uid → SHARD_MERGE_SORT、三个分片。", t=tl(S(2)), mark=lidx(S(2), 'city = 7(不含分片键)', '空条件', 'SHARD_MERGE_SORT'), done=lidx(S(2), 'uid = 1500', 'uid ∈ [500, 800)'), kv=KV([['SINGLE_SHARD', 'targeted,只问 1 个分片'], ['SHARD_MERGE', '问多个分片再合并'], ['SHARD_MERGE_SORT', '多个分片各自排序,mongos 归并']], ['SINGLE_SHARD'])),
    step("实际执行各 100 次查询,各分片 opcounters.query 的增量:uid = 单值 → sh0 0、sh1 100、sh2 0(只有一个分片被问);uid 范围 [0, 100) → sh0 100,其它 0;city = 7(无分片键)→ 三个分片各 100(每次查询的负载乘以 3);空条件 limit 1 → 三个分片各 100。", t=tl(S(3)), mark=lidx(S(3), 'city = 7(无分片键)', '空条件'), done=lidx(S(3), 'uid = 1500(targeted)', 'uid 范围 [0, 100)'), b=bars([['uid 等值', 1, '1 个分片 × 100'], ['uid 范围 [0,100)', 1, '1 个分片 × 100'], ['无分片键 city', 3, '3 个分片 × 100'], ['空条件', 3, '3 个分片 × 100']], 3, mark=[2, 3], done=[0, 1]), kv=KV([['targeted', '每次 1 个分片'], ['scatter-gather', '每次所有分片,集群总负载乘分片数']], ['scatter-gather'])),
    step("sort + limit:city = 7 按 uid 降序取前 5 个:stage 是 SHARD_MERGE_SORT,三个分片(sh1、sh2、sh0)各返回 5 个,mongos 归并后最终只取 5 个。", t=tl(S(4)), mark=lidx(S(4), 'SHARD_MERGE_SORT'), done=lidx(S(4), '最终 nReturned 5'), kv=KV([['每个分片', '各自排序取 limit 个'], ['mongos', '归并后再取 limit 个']], ['mongos'])),
    step("不带分片键的写:update_one 带 uid 成功(matched 1);update_one 用 city(非分片键)成功(matched 1);update_many 不带分片键成功(matched 60);delete_one 不带分片键成功——9.0.2 上不再要求单文档写必须带分片键(服务端会自己找到文档所在的分片)。", t=tl(S(5)), mark=lidx(S(5), 'update_one 只带', 'delete_one 不带分片键'), done=lidx(S(5), 'update_one 带分片键 uid', 'update_many'), kv=KV([['单文档写不带分片键', '成功'], ['update_many', '成功,matched 60']], ['单文档写不带分片键'])),
    step("executionStats:uid = 1500 涉及 1 个分片,sh1 检查 1 个键 1 个文档,返回 1,合计检查 1 个键;city = 7 涉及 3 个分片,每个分片检查 20 个键 20 个文档、返回 20,合计检查 60 个键。", t=tl(S(6)), mark=lidx(S(6), 'city = 7'), done=lidx(S(6), 'uid = 1500'), b=bars([['uid = 1500', 1, '检查 1 个键'], ['city = 7', 60, '检查 60 个键(3 个分片)']], 60, mark=[1], done=[0]), kv=KV([['targeted', '1 个分片,1 个键'], ['scatter-gather', '3 个分片,各 20 个键']], ['targeted'])),
]
A = mkartm('m68', 68, 'MongoDB,mongos,路由,targeted,scatter-gather,分片查询,真实验证,动画演示',
    '实测 mongos 路由:3 个分片上带分片键的等值/范围查询是 SINGLE_SHARD,跨段范围或 $in 多值或不含分片键是 SHARD_MERGE(问所有分片,各分片计数器各 +100);sort + limit 是 SHARD_MERGE_SORT,每个分片各返回 5 个再归并;9.0.2 上不带分片键的 update_one / delete_one 也能成功。',
    '一条查询是怎么被 mongos 路由到分片的?带不带分片键差多少负载?这篇用 3 个分片逐种查询看 explain 的 stage、涉及的分片,再统计 100 次查询带给每个分片的负载。',
    [('1 对 3', '带分片键的等值查询与不带分片键的查询涉及的分片数'), ('SHARD_MERGE_SORT', 'sort + limit 的查询在 mongos 上的阶段:各分片排序后归并'), ('60 对 1', 'city = 7 与 uid = 1500 两种查询合计检查的索引键数')],
    [('targeted', '<p>条件里有分片键的等值或落在单个 chunk 范围内的范围查询,mongos 只问一个分片(<code>SINGLE_SHARD</code>)。</p>'),
     ('scatter-gather', '<p>跨 chunk 的范围、<code>$in</code> 多值、不含分片键的查询要问所有相关分片(<code>SHARD_MERGE</code>),集群总负载约乘以分片数。</p>'),
     ('负载', '<p>各 100 次查询时,targeted 查询只给一个分片带来 100 次 query,无分片键的查询给三个分片各带来 100 次。</p>'),
     ('排序', '<p>sort + limit:每个分片各自排序取 limit 个,mongos 归并后再取前 limit 个。</p>'),
     ('写入', '<p>9.0.2 上不带分片键的 <code>update_one</code>、<code>delete_one</code> 也能成功,服务端会自己找到文档所在的分片。</p>'),
     ('检查量', '<p>targeted 查询只检查 1 个键,scatter-gather 在每个分片上各检查一遍(这里共 60 个键)。</p>')],
    steps,
    [ENV_M + '。3 个分片(各为单节点副本集)+ 1 个 config server + 1 个 mongos;分片范围手工 split 与 moveChunk 得到',
     '没有验证:多个 mongos 之间路由表缓存不一致(StaleConfig 重试)的开销;sort 的内存合并上限;不带分片键的单文档写的实现方式与代价(可能用到内部事务);aggregate 的路由(见后面一篇);读偏好、maxTimeMS 在 scatter-gather 中的作用;mongos 连接池'],
    'mongos 路由')
