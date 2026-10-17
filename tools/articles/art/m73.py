from lib import *
S = SS('m73')
steps = [
    step("全新的 mongod:db.getProfilingStatus() 返回 {was: 0, slowms: 100, slowinprogms: 5000, sampleRate: 1}——profile 级别 0(不往 system.profile 写任何东西),慢操作阈值 100 ms;system.profile 里确实是 0 个文档。", t=tl(S(1)), mark=lidx(S(1), 'was: 0', 'slowms: 100', 'sampleRate: 1'), done=lidx(S(1), 'countDocuments'), kv=KV([['profile 级别', '0'], ['slowms', '100'], ['sampleRate', '1'], ['system.profile 文档数', '0']], ['slowms'])),
    step("t 有 5 万个文档、没有索引。跑 20 次 find + sort + toArray(全表扫描):阈值 100 ms 下日志里新增的 \"Slow query\" = 0。把 slowms 调到 5(db.setProfilingLevel(0, {slowms: 5})),同样的 20 次之后新增 28 条:20 条 find(durationMillis = 15,docsExamined = 50000,planSummary = COLLSCAN,keysExamined = 0,nreturned = 101)+ 8 条 getMore——日志按每个操作记一条,不是按每次循环。", t=tl(S(2)), mark=lidx(S(2), '阈值 100 ms', '阈值 5 ms', '其中 durationMillis'), done=lidx(S(2), 'db.setProfilingLevel(0, {slowms: 5})'), b=bars([['阈值 100 ms', 0, '0 条'], ['阈值 5 ms', 28, '28 条']], 28, mark=[1], done=[0]), kv=KV([['阈值 100 ms', '0 条 Slow query'], ['阈值 5 ms', '28 条:find 20 + getMore 8'], ['日志字段', 'durationMillis、docsExamined、planSummary、…']], ['阈值 5 ms'])),
    step("profile 级别 1(setProfilingLevel(1, {slowms: 5}))把慢操作写进 system.profile:5 次循环得到 5 条 op: 'query'(最慢 18 ms)和 5 条 op: 'getmore'(最慢 8 ms),计划都是 COLLSCAN;快的 findOne 在 test.small 上 0 条。级别 2 则记录所有操作:一条 findOne 的记录里有 command、keysExamined: 1、docsExamined: 1、planSummary: 'EXPRESS_IXSCAN { _id: 1 }'、millis: 0、micros 等字段。", t=tl(S(3)), mark=lidx(S(3), "op: 'getmore'", "op: 'query'", "ns: 'test.small'", 'EXPRESS_IXSCAN'), done=lidx(S(3), 'setProfilingLevel(1'), kv=KV([['级别 1', '只记录超过 slowms 的操作'], ['级别 2', '记录所有操作'], ['findOne(级别 1)', '0 条记录'], ['findOne(级别 2)', '1 条,micros 级耗时']], ['级别 2'])),
    step("system.profile 是 capped 集合:stats() 里 capped = true,maxSize = 1048576(1 MB)。想放大要先把 profile 关掉、drop 掉、再 createCollection('system.profile', {capped: true, size: 4 * 1024 * 1024}),之后 maxSize = 4194304。", t=tl(S(4)), mark=lidx(S(4), 'true 1048576', '4194304'), done=lidx(S(4), 'stats().capped'), kv=KV([['默认大小', '1 MB(capped)'], ['放大方法', '关 profile → drop → 重建 capped'], ['重建后 maxSize', '4,194,304']], ['重建后 maxSize'])),
    step("级别对吞吐的影响:3,000 次 findOne 的耗时(5 次中位数)级别 0 是 293 ms,级别 1(阈值 100 ms,基本不记录)295 ms,级别 2 是 337 ms,是级别 0 的 1.15 倍。级别 2 下一共执行了 18,000 次 findOne,但 4 MB 的 system.profile 里只剩 4,280 条——旧记录已被覆盖。", t=tl(S(5)), mark=lidx(S(5), '级别 0:', '4280'), done=lidx(S(5), '18,000'), b=bars([['级别 0', 293, '293 ms'], ['级别 1', 295, '295 ms'], ['级别 2', 337, '337 ms']], 337, mark=[2], done=[0, 1]), kv=KV([['级别 0 / 1 / 2', '293 / 295 / 337 ms'], ['级别 2 / 级别 0', '1.15 倍'], ['执行 / 保留的记录', '18,000 / 4,280']], ['级别 2 / 级别 0'])),
    step("sampleRate:slowms = 0 让每一个操作都算“慢”,再设 sampleRate = 0.1;1,000 次 findOne 之后日志里新增 104 条 \"Slow query\"——大约 10%,而不是 1,000 条。", t=tl(S(6)), mark=lidx(S(6), 'sampleRate: 0.1', '新增'), done=lidx(S(6), 'slowms: 0'), b=bars([['findOne 次数', 1000, '1,000'], ['日志里的 Slow query', 104, '104']], 1000, mark=[1], done=[0]), kv=KV([['slowms', '0'], ['sampleRate', '0.1'], ['1,000 次 findOne 后', '104 条日志']], ['1,000 次 findOne 后'])),
]
A = mkartm('m73', 73, 'MongoDB,profiler,slowms,system.profile,sampleRate,慢查询,真实验证,动画演示',
    '实测 profiler:默认级别 0、slowms = 100;阈值 100 ms 时 20 次全表扫描一条 Slow query 日志都没有,5 ms 时是 28 条(20 个 find + 8 个 getMore);级别 1/2 往 system.profile 写;system.profile 默认 1 MB capped,级别 2 的开销是 1.15 倍且 18,000 条操作只剩 4,280 条;sampleRate = 0.1 只记约 10%。',
    '慢查询日志和 system.profile 是两回事吗?slowms 到底影响什么?把 profiler 开到级别 2 会拖慢多少?这篇逐个验证。',
    [('28', 'slowms = 5 时 20 次全表扫描产生的 Slow query 日志条数(20 find + 8 getMore)'), ('1.15×', 'profile 级别 2 相对级别 0 的耗时'), ('4,280', '级别 2 跑 18,000 次操作后 4 MB system.profile 里剩下的条数')],
    [('默认值', '<p>profile 级别 0,<code>slowms = 100</code>,<code>sampleRate = 1</code>;<code>system.profile</code> 是空的。</p>'),
     ('slowms 与日志', '<p>超过 <code>slowms</code> 的操作写进 mongod 日志(<code>Slow query</code>),profile 级别为 0 时也会写;日志按操作记,find 和 getMore 各一条,字段包括 <code>durationMillis</code>、<code>docsExamined</code>、<code>planSummary</code>。</p>'),
     ('级别 1 与 2', '<p>级别 1 把超过 slowms 的操作写进 <code>system.profile</code>,级别 2 写所有操作;每条记录有命令、keysExamined、docsExamined、planSummary、耗时等。</p>'),
     ('capped', '<p><code>system.profile</code> 是 1 MB 的 capped 集合;想放大要关 profile、drop、再按大小重建。</p>'),
     ('开销', '<p>级别 2 让 3,000 次 findOne 从 293 ms 变成 337 ms(1.15 倍),并且旧记录会被覆盖:18,000 次操作后只剩 4,280 条。</p>'),
     ('sampleRate', '<p><code>slowms = 0</code> 加 <code>sampleRate = 0.1</code>,1,000 次操作只记录了 104 条日志。</p>')],
    steps,
    [ENV_M + '。单机 mongod,5 万个文档的集合;mongosh 做交互,pymongo 做计时',
     '没有验证:sampleRate 对 system.profile(而不是日志)的影响;slowinprogms(进行中的慢操作日志)的行为;按集合/操作类型过滤的 profile 过滤器(filter 选项);副本集上 secondary 的 profile;日志的 JSON 结构在其它版本的差异;并发压力下 profile 级别 2 的锁争用'],
    'profiler 与 slowms')
