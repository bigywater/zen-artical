from lib import *
S = SS('m41')
steps = [
    step("20 万个订单、2 万个客户。$lookup {localField: \"cust\", foreignField: \"_id\"}(customers 有默认的 _id 索引)的 explain 里 strategy 是 IndexedLoopJoin,foreignIndex 是 _id_;换成 {localField: \"ccid\", foreignField: \"cid\"}(cid 没有索引)strategy 是 NestedLoopJoin,foreignIndex 是 null。", t=tl(S(1)), mark=lidx(S(1), "strategy: 'NestedLoopJoin'", 'foreignIndex: null'), done=lidx(S(1), "strategy: 'IndexedLoopJoin'", "foreignIndex: '_id_'"), kv=KV([['外键有索引', 'IndexedLoopJoin'], ['外键没有索引', 'NestedLoopJoin'], ['explain', 'EQ_LOOKUP 阶段的 strategy']], ['外键有索引'])),
    step("同样的 $lookup 耗时:100 条订单,有索引 0.7 ms,没有索引 247 ms;1,000 条订单,有索引 3.9 ms,没有索引 2,367 ms(约 600 倍)。没有索引时每条订单都要扫一遍 2 万个客户。", t=tl(S(2)), mark=lidx(S(2), '1000 条订单', '   1000'), done=lidx(S(2), '100 条订单'), b=bars([['100 条 有索引', 0.7, '0.7 ms'], ['100 条 无索引', 247, '247 ms'], ['1000 条 有索引', 3.9, '3.9 ms'], ['1000 条 无索引', 2367, '2,367 ms']], 2367, mark=[3], done=[0, 1, 2]), kv=KV([['有索引', '3.9 ms / 1000 条'], ['没有索引', '2,367 ms,约 600 倍'], ['原因', '每条订单扫一遍 2 万个客户']], ['原因'])),
    step("给 customers.cid 建索引后,同一个 $lookup 的 strategy 变成 IndexedLoopJoin,foreignIndex 是 cid_1;100 条订单 0.6 ms,1,000 条 4.3 ms,接近 _id 的 0.7 / 3.9 ms。", t=tl(S(3)), mark=lidx(S(3), "foreignIndex: 'cid_1'"), done=lidx(S(3), "strategy: 'IndexedLoopJoin'", '100 条订单', '1000 条订单'), kv=KV([['建 cid 索引', 'NestedLoopJoin → IndexedLoopJoin'], ['耗时', '2,367 ms → 4.3 ms']], ['建 cid 索引'])),
    step("输入订单数增加:有索引的耗时随输入线性增长——100 / 1,000 / 10,000 条是 0.6 / 4.0 / 35 ms;没有索引的是 247 / 2,389 / 24,016 ms(10,000 条要 24 秒),也线性增长,但斜率大得多。", t=tl(S(4)), mark=lidx(S(4), '10,000'), done=lidx(S(4), '       100', '     1,000'), b=bars([['10,000 条 有索引', 35, '35 ms'], ['10,000 条 无索引', 24016, '24,016 ms']], 24016, mark=[1], done=[0]), kv=KV([['有索引', '约 3.5 μs / 条'], ['无索引', '约 2.4 ms / 条'], ['比例', '约 690 倍']], ['比例'])),
    step("$lookup 的 let / pipeline 形式({$match: {$expr: {$eq: [\"$_id\", \"$$c\"]}}}):explain 里没有 EQ_LOOKUP 的 strategy 字段(strategy 为 null);1,000 条订单耗时 22 ms,普通 localField / foreignField 形式是 4.2 ms——子管道形式更灵活,但慢约 5 倍。", t=tl(S(5)), mark=lidx(S(5), 'strategy: null', '22 ms'), done=lidx(S(5), 'let / pipeline'), kv=KV([['let / pipeline', '22 ms / 1000 条,无 strategy'], ['localField / foreignField', '4.2 ms'], ['选择', '能用等值连接就用后者']], ['选择'])),
    step("$lookup 把匹配到的所有文档放进一个数组字段:匹配 20 个 1 MiB 的文档,结果文档有 20,972,239 字节(n: 20),超过 16 MiB 也能返回给客户端;同样的结果 $out 写进集合则失败:Serializing Document failed :: caused by :: Size 20972239 exceeds maximum 16793600;先 $unwind 再 $project 去掉大字段就没问题(n: 20)。", t=tl(S(6)), mark=lidx(S(6), 'exceeds maximum 16793600'), done=lidx(S(6), 'bytes: 20972239', 'n: 20'), kv=KV([['返回客户端', '结果文档可以 > 16 MiB'], ['$out 写集合', '超过 16793600 字节失败'], ['办法', '$unwind + $project 去掉大字段']], ['办法'])),
]
A = mkartm('m41', 41, 'MongoDB,$lookup,索引,连接,IndexedLoopJoin,NestedLoopJoin,真实验证,动画演示',
    '实测 $lookup 有无索引的差别:外键有索引是 IndexedLoopJoin,1,000 条订单 3.9 ms;没有索引是 NestedLoopJoin,2,367 ms(约 600 倍),10,000 条要 24 秒;建索引后立刻恢复;let / pipeline 形式慢约 5 倍;$lookup 结果超过 16 MiB 可以返回但不能 $out。',
    '$lookup 的性能完全取决于外键有没有索引?这篇用 20 万订单关联 2 万客户,看 explain 的 strategy,对比耗时随输入量的增长,再看 let / pipeline 形式和结果大小限制。',
    [('3.9 对 2,367 ms', '1,000 条订单 $lookup:外键有索引与没有索引'), ('24,016 ms', '没有索引时 10,000 条订单 $lookup 的耗时(有索引 35 ms)'), ('IndexedLoopJoin', '外键有索引时 EQ_LOOKUP 的执行策略(没有索引是 NestedLoopJoin)')],
    [('strategy', '<p>explain 里的 <code>EQ_LOOKUP</code> 阶段带 <code>strategy</code>:外键有索引时是 <code>IndexedLoopJoin</code>,没有索引是 <code>NestedLoopJoin</code>。</p>'),
     ('差别有多大', '<p>1,000 条订单关联 2 万个客户:有索引 3.9 ms,没有索引 2,367 ms,慢约 600 倍,因为每条订单都要扫一遍客户。</p>'),
     ('建索引', '<p>给外键 <code>cid</code> 建索引,同样的 <code>$lookup</code> 立刻变成 <code>IndexedLoopJoin</code>,耗时回到 4.3 ms。</p>'),
     ('线性增长', '<p>两种情形都随输入线性增长,斜率相差约 690 倍:10,000 条订单,有索引 35 ms,没有索引 24 秒。</p>'),
     ('let / pipeline', '<p>子管道形式可以写任意条件,但 explain 里没有等值连接的 strategy,1,000 条订单 22 ms,慢约 5 倍。</p>'),
     ('结果大小', '<p><code>$lookup</code> 的匹配结果是一个数组字段,整条结果文档可超过 16 MiB 返回客户端,但写进集合(<code>$out</code>)会失败。</p>')],
    steps,
    [ENV_M + '。20 万个订单、2 万个客户;耗时为 pymongo 的 3~5 次中位数(没有索引的 10,000 条只跑 1 次)',
     '没有验证:HashJoin 策略出现的条件(foreign 集合很小且没有索引时,这里 2 万个客户仍是 NestedLoopJoin);$lookup 后接 $unwind 的合并优化;分片集群上的 $lookup 限制;$graphLookup;经典引擎(非 SBE)下的 $lookup 执行方式;一对多关联的结果规模对耗时的影响'],
    '$lookup 与索引')
