from lib import *
S = SS('m66')
steps = [
    step("单调递增的分片键(ranged,键是递增的时间戳):关掉 balancer(排除迁移带来的 insert),4 个线程持续写入 30 秒共 287,500 个文档,每 5 秒窗口 sh0 收到约 47,400~48,500 次 insert,sh1 一次都没有——sh0 占 100%;键最大的那个 chunk 始终在 sh0。", t=tl(S(1)), mark=lidx(S(1), 'sh0 占 100%', '287,500'), done=lidx(S(1), '第  5 s 窗口', '第 30 s 窗口'), b=bars([['sh0', 287500, '287,500 次 insert'], ['sh1', 0, '0 次']], 287500, mark=[0], done=[1]), kv=KV([['新写入的键', '总是最大,总落进最后一个 chunk'], ['sh0', '承担 100% 的写入'], ['sh1', '0']], ['sh0'])),
    step("哈希分片键(同样的负载,balancer 仍关着):shardCollection 时两个分片上各建好一个 chunk,写入被哈希打散:合计 sh0 137,761、sh1 137,439,各占约 50%,每个窗口都是约 22,600~23,200 对 22,700~23,000。", t=tl(S(2)), mark=lidx(S(2), 'sh0 占 50%'), done=lidx(S(2), '第  5 s 窗口', '第 30 s 窗口'), b=bars([['sh0', 137761, '137,761'], ['sh1', 137439, '137,439']], 137761, mark=[1], done=[0]), kv=KV([['哈希键', '写入均匀分到两个分片'], ['建好 chunk', 'shardCollection 时每个分片一个']], ['哈希键'])),
    step("复合键 {bucket, ts}(bucket 是 8 个桶):手工 split 在 bucket=4、moveChunk 把 bucket >= 4 的 chunk 搬到 sh1(balancer 仍关着),chunk 分布 {sh0: 1, sh1: 1}。写入分散到两个分片:合计 sh0 138,300、sh1 138,348,各占约 50%;每个桶内部键仍是递增的。", t=tl(S(3)), mark=lidx(S(3), 'sh0 占 50%'), done=lidx(S(3), '手工 split + moveChunk'), kv=KV([['前缀字段', 'bucket 把写入分散到多个 chunk'], ['桶内', 'ts 仍然递增'], ['代价', '要用 bucket 才能 targeted 查询']], ['前缀字段'])),
    step("单调键再打开 balancer:55 秒后数据分布是 sh1 拥有 119,535 个文档、sh0 拥有 167,965 个——旧数据被搬走了一部分;但再写 20,000 个更大的键,直连 sh0 里 ts 大于等于起点的有 20,000 个,sh1 里 0 个,键最大的 chunk 仍在 sh0:balancer 只能搬走旧数据,新写入仍然追着最大的 chunk。", t=tl(S(4)), mark=lidx(S(4), '有 20,000 个,sh1 里有 0 个'), done=lidx(S(4), 'balancer 搬了 55 秒后'), b=bars([['balancer 之后 sh1 拥有', 119535, '119,535 个'], ['balancer 之后 sh0 拥有', 167965, '167,965 个'], ['新写入落在 sh0', 20000, '20,000 / 20,000']], 167965, mark=[2], done=[0, 1]), kv=KV([['balancer', '搬走旧数据,平衡存储'], ['新写入', '仍然 100% 落在最大 chunk 所在的 sh0'], ['结论', '单调键的写入热点靠 balancer 解决不了']], ['结论'])),
    step("代价:范围查询 ts ∈ [t+1000, t+1100):ranged 集合只涉及 ['sh1'](targeted),hashed 涉及 ['sh0', 'sh1'](scatter-gather),复合键不带 bucket 同样 ['sh0', 'sh1'];等值查询 ts = t+1000 都只涉及一个分片;带 bucket 的复合键查询只涉及一个分片(bucket = 3 在 sh0,bucket = 6 在 sh1)。", t=tl(S(5)), mark=lidx(S(5), "hashed 涉及的分片 ['sh0', 'sh1']"), done=lidx(S(5), "ranged 涉及的分片 ['sh1']", '带 bucket'), kv=KV([['ranged', '范围查询 targeted'], ['hashed', '范围查询 scatter-gather'], ['复合键', '带 bucket 才能 targeted']], ['hashed'])),
    step("汇总(balancer 关着时 30 秒写入):ranged {ts} 单调键 287,500 个、sh0 占 100%;hashed {ts} 275,200 个、sh0 占 50%;复合 {bucket, ts}(手工分两半)276,800 个、sh0 占 50%。", t=tl(S(6)), mark=lidx(S(6), '100%'), done=lidx(S(6), '50%'), b=bars([['ranged {ts}', 100, 'sh0 占 100%'], ['hashed {ts}', 50, 'sh0 占 50%'], ['复合 {bucket, ts}', 50, 'sh0 占 50%']], 100, mark=[0], done=[1, 2]), kv=KV([['单调键', '热点在一个分片'], ['哈希 / 前缀打散', '各占一半'], ['取舍', '范围查询的 targeted 能力']], ['取舍'])),
]
A = mkartm('m66', 66, 'MongoDB,分片键,单调递增,写入热点,hashed,balancer,真实验证,动画演示',
    '实测单调递增分片键的写入热点:关掉 balancer 后 30 秒 287,500 次写入全部打在 sh0(100%),哈希键与手工打散的复合键各占 50%;开 balancer 后旧数据被搬走一部分(119,535 对 167,965),但新写入的 20,000 个更大键仍然全部落在 sh0;范围查询 ranged 只问 1 个分片,hashed 要问全部。',
    '用时间戳或 ObjectId 这类单调递增的字段做分片键会怎样?balancer 能不能解决写入热点?哈希和复合键各自的代价是什么?这篇在 2 个分片上用同样的写入负载对比三种分片键。',
    [('100% 对 50%', '30 秒写入中 sh0 的占比:单调 ranged 键与哈希键'), ('0 个', '开 balancer 搬完旧数据后,再写 20,000 个更大的键,落在 sh1 的个数'), ('scatter-gather', '哈希键下按时间范围查询要问所有分片')],
    [('热点', '<p>单调递增的 ranged 分片键,新文档的键总是最大,总是落进键空间末端的那个 chunk,所以 100% 的写入都打在同一个分片上。</p>'),
     ('哈希', '<p>哈希键在 <code>shardCollection</code> 时就在各个分片上建好 chunk,写入被均匀分开(各约 50%)。</p>'),
     ('复合键', '<p>在单调字段前面加一个有限基数的前缀(这里是 8 个桶),写入分散到前缀对应的多个 chunk,每个桶内键仍然递增。</p>'),
     ('balancer 解决不了', '<p>balancer 能把旧数据搬到别的分片(119,535 对 167,965),但新写入仍然追着最大 chunk 所在的分片。</p>'),
     ('查询代价', '<p>ranged 键的范围查询只问一个分片;哈希键的范围查询要问所有分片;复合键带前缀字段才能 targeted。</p>'),
     ('怎么选', '<p>写入热点和范围查询的 targeted 能力要取舍:大量按时间范围查询又大量写入时,常用复合键(低基数前缀 + 时间)折中。</p>')],
    steps,
    [ENV_M + '。2 个分片(各为单节点副本集),chunk 大小 1 MB;为排除迁移带来的 insert,写入对比时关掉了 balancer;insert 次数取自各分片 serverStatus().opcounters',
     '没有验证:真实多核多机下热点分片的 CPU / 磁盘饱和程度(本机两个分片共享一块硬盘与 CPU,吞吐数字没有比较意义);复合键桶数的选取;时间序列场景下 MongoDB 对时序集合的分片键建议;ObjectId 作为 ranged 分片键的同样现象;zone sharding 与预拆分对热点的作用'],
    '单调递增的分片键')
