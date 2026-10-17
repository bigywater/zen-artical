from lib import *
S = SS('m65')
steps = [
    step("两个分片 sh0、sh1(各是单节点副本集)加一个 config server、一个 mongos;为了在小数据上观察,把 chunk 大小设成 1 MB(config.settings 里 { _id: 'chunksize', value: 1 },默认 128 MB)。listShards 给出 sh0/127.0.0.1:9902 与 sh1/127.0.0.1:9903。", t=tl(S(1)), mark=lidx(S(1), "_id: 'chunksize', value: 1"), done=lidx(S(1), "('sh0'"), kv=KV([['分片', 'sh0、sh1'], ['chunk 大小', '1 MB(默认 128 MB)'], ['组件', 'mongos + config server + 2 个分片']], ['chunk 大小'])),
    step("刚分片的空集合只有一个覆盖 [MinKey, MaxKey) 的 chunk,放在 primary 分片 sh0 上:config.chunks 里 { min: { k: MinKey() }, max: { k: MaxKey() }, shard: 'sh0' }。", t=tl(S(2)), mark=lidx(S(2), "shard: 'sh0'"), done=lidx(S(2), 'config.chunks'), kv=KV([['空集合', '1 个 chunk'], ['范围', 'MinKey → MaxKey'], ['位置', 'primary 分片']], ['空集合'])),
    step("balancer 开着时写入 60,000 个文档(约 60 MB,k 随机):写入期间 chunk 分布从 {sh0: 1} 变成 6 s 时 {sh0: 1, sh1: 1}、8 s 时 {sh0: 1, sh1: 3}、10 s 时 {sh0: 1, sh1: 4},写完(12 s)时 {sh0: 1, sh1: 6}——写入触发 chunk 分裂,balancer 同时把拆出来的 chunk 迁到 sh1。", t=tl(S(3)), mark=lidx(S(3), "'sh1': 6", "6s:"), done=lidx(S(3), '写入期间 chunk 分布'), kv=KV([['chunk 分裂', '由写入流量触发(没有写入就不再拆)'], ['迁移', 'balancer 同时进行']], ['chunk 分裂'])),
    step("写入停止后 balancer 继续迁移,chunk 分布 {sh0: 1, sh1: 6} → 10 s {sh0: 1, sh1: 14} → 20 s {1, 21} → 30 s {1, 26} → 40 s 起稳定在 {sh0: 1, sh1: 26}。chunk 个数差很多(1 对 26),但 $shardedDataDistribution 显示数据量接近:sh1 拥有 28,525 个文档 / 28.2 MB,sh0 拥有 31,475 个 / 31.1 MB——sh0 上剩下的那 1 个大 chunk 没有再被拆分(拆分由写入触发),balancer 按数据量判断已经平衡。sh0 还有 26,312 个孤儿文档(26.0 MB):迁走的数据在源分片上暂时没删,直连 sh0 看到 57,787 个,经 mongos 总数 60,000;orphanCleanupDelaySecs 是 3600 秒。", t=tl(S(4)), mark=lidx(S(4), '孤儿文档 26,312', 'orphanCleanupDelaySecs', '3600'), done=lidx(S(4), '拥有 28,525', '拥有 31,475', "'sh1': 26"), b=bars([['sh0 拥有', 31.1, '31.1 MB / 1 个 chunk'], ['sh1 拥有', 28.2, '28.2 MB / 26 个 chunk'], ['sh0 孤儿文档', 26, '26.0 MB(待清理)']], 31.1, mark=[2], done=[0, 1]), kv=KV([['chunk 个数', '1 对 26'], ['拥有的数据量', '31.1 MB 对 28.2 MB'], ['孤儿文档', '源分片上延迟 3600 秒才删']], ['孤儿文档'])),
    step("config.changelog 里每次迁移是一条 moveChunk.from,共 26 条;其中一条从 sh0 到 sh1,范围 k 259913947 到 276259863,各步骤耗时(毫秒)step 1~6:0、0、13、110、21、91——全程不到 0.25 秒;其它字段有 from、max、min、note、to。", t=tl(S(5)), mark=lidx(S(5), 'step 1 of 6'), done=lidx(S(5), 'moveChunk.from 事件共 26 条'), kv=KV([['moveChunk.from', '每次迁移一条'], ['step 4 of 6', '110 ms(最长的一步之一)'], ['整次迁移', '约 0.25 秒(1 MB 的 chunk)']], ['moveChunk.from'])),
    step("jumbo chunk:test.j 里 4,000 个文档(约 4 MB)全部 k = 7——chunk 比 1 MB 大却没有可用的分割点,只有一个 chunk([MinKey, MaxKey)),且带 jumbo 标记(1 个)。选分片键时基数要够高。", t=tl(S(6)), mark=lidx(S(6), 'jumbo 标记的 1'), done=lidx(S(6), 'test.j'), kv=KV([['全部 k = 7', '没法拆分'], ['jumbo', '1 个 chunk 带标记'], ['教训', '分片键基数要高']], ['教训'])),
]
A = mkartm('m65', 65, 'MongoDB,分片,chunk,balancer,moveChunk,jumbo,孤儿文档,真实验证,动画演示',
    '实测分片集群上 chunk 的拆分与迁移:空集合一个 chunk;写入触发分裂,balancer 同时把拆出的 chunk 迁到另一个分片;最终 chunk 个数 1 对 26 但数据量 31.1 MB 对 28.2 MB(按数据量平衡);迁走的数据以孤儿文档形式在源分片留 3600 秒;changelog 记录每次迁移的 6 个步骤;分片键全相同产生 jumbo chunk。',
    'chunk 是怎么拆分、怎么被 balancer 搬走的?chunk 个数不平衡算不算失衡?迁走的数据什么时候删?这篇在 2 个分片的集群上把 chunk 大小设为 1 MB,写入 60 MB 数据,观察分布变化、迁移步骤和 jumbo chunk。',
    [('1 对 26', '最终两个分片的 chunk 个数,但拥有的数据量是 31.1 MB 对 28.2 MB'), ('3600 秒', 'orphanCleanupDelaySecs:迁走的数据在源分片上延迟这么久才删(之前是孤儿文档)'), ('6 个步骤', 'config.changelog 中 moveChunk.from 记录的迁移步骤,一次 1 MB 的 chunk 迁移约 0.25 秒')],
    [('起点', '<p>刚分片的空集合只有一个 [MinKey, MaxKey) 的 chunk,在 primary 分片上;chunk 大小设成 1 MB 便于在小数据上观察。</p>'),
     ('分裂与迁移', '<p>写入触发 chunk 分裂,balancer 同时把新 chunk 迁到另一个分片。分裂由写入流量触发:写入停止后,剩下的一个大 chunk 不会再被拆。</p>'),
     ('按数据量平衡', '<p>最终 chunk 个数是 1 对 26,但两个分片拥有的数据量是 31.1 MB 对 28.2 MB,balancer 认为已经平衡。</p>'),
     ('孤儿文档', '<p>迁走的数据在源分片上不会立刻删除,直连源分片看到的文档数比 mongos 看到的多;<code>orphanCleanupDelaySecs</code> 默认 3600 秒。</p>'),
     ('迁移的步骤', '<p>每次迁移在 <code>config.changelog</code> 里记录 6 个步骤的耗时;1 MB 的 chunk 迁移总共不到 0.25 秒。</p>'),
     ('jumbo chunk', '<p>分片键全相同的数据没法拆分,chunk 超过大小上限却不能拆,被标记为 jumbo,无法被 balancer 迁移。</p>')],
    steps,
    [ENV_M + '。2 个分片(各为单节点副本集)+ 1 个 config server + 1 个 mongos;chunk 大小设成 1 MB(默认 128 MB)',
     '没有验证:默认 128 MB chunk 下的行为;三个及以上分片的平衡;orphanCleanupDelaySecs 到期后孤儿文档的清理;jumbo chunk 的手工处理(清除标记、增加分片键后缀);autoMerger 与 defragmentation;balancer 的窗口与限流参数(balancerMigrationsThrottlingMs)'],
    'chunk 拆分与迁移')
