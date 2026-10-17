from lib import *
S = SS('m67')
steps = [
    step("哈希分片键在 shardCollection 时就预先建好 chunk:2 个分片得到 2 个 chunk——sh0 拥有 [MinKey, 0),sh1 拥有 [0, MaxKey)(哈希值的符号分界),每个分片 1 个。", t=tl(S(1)), mark=lidx(S(1), "[{'k': 0}, {'k': MaxKey()})"), done=lidx(S(1), "[{'k': MinKey()}, {'k': 0})", 'chunk 分布'), kv=KV([['默认', '每个分片 1 个 chunk'], ['范围', '哈希空间按 0 对半分'], ['存储位置', 'sh0 / sh1']], ['默认'])),
    step("numInitialChunks=8(想把哈希空间预先切成 8 份):在这个 9.0.2 上实测 chunk 仍然只有 2 个(sh0 一个 [MinKey, 0)、sh1 一个 [0, MaxKey)),参数没有生效(原因没有查明)。", t=tl(S(2)), mark=lidx(S(2), "chunk 分布 {'sh0': 1, 'sh1': 1}"), done=lidx(S(2), "[{'k': 0}, {'k': MaxKey()})"), kv=KV([['numInitialChunks=8', '实测仍然 2 个 chunk'], ['结论', '不要假定预拆分一定生效,用 config.chunks 核对']], ['结论'])),
    step("写入 60,000 个连续整数键 0..59999(balancer 关着):hashed 集合两个分片拥有 30,451 和 29,549 个文档,几乎对半;ranged 集合 60,000 个全在 sh0(1 个 chunk)。连续的键被哈希打散,没打散的全挤在同一个 chunk。", t=tl(S(3)), mark=lidx(S(3), "ranged:各分片拥有的文档数 {'sh0': 60000}"), done=lidx(S(3), 'hashed:各分片拥有的文档数'), b=bars([['hashed sh0', 30451, '30,451'], ['hashed sh1', 29549, '29,549'], ['ranged sh0', 60000, '60,000'], ['ranged sh1', 0, '0']], 60000, mark=[2, 3], done=[0, 1]), kv=KV([['hashed', '30,451 对 29,549'], ['ranged 连续键', '60,000 对 0']], ['ranged 连续键'])),
    step("随机整数键写进 ranged 集合:balancer 关着时 60,000 个文档仍然全在 sh0(1 个 chunk);打开 balancer 10 秒后 chunk 被拆成 sh0 一个、sh1 三个,拥有的文档 sh0 37,044、sh1 22,956——随机键的 ranged 集合在 balancer 的帮助下可以分开。", t=tl(S(4)), mark=lidx(S(4), 'balancer 开了 10 秒后'), done=lidx(S(4), '写完后'), kv=KV([['balancer 关着', '全在 sh0'], ['balancer 开 10 秒后', '37,044 对 22,956'], ['随机键', 'ranged 也能慢慢分开']], ['随机键'])),
    step("热点键:70% 的文档 k = 42,其余随机,哈希分片键:两个分片拥有 50,984(sh0)和 9,016(sh1)个文档;最大的一个 chunk 有 50,984 个文档(85%)——哈希把 k = 42 的所有文档映射到同一个哈希值,只能落在同一个 chunk 里,哈希救不了单个热点键。", t=tl(S(5)), mark=lidx(S(5), '85%'), done=lidx(S(5), '各分片拥有的文档数'), b=bars([['sh0(含 k=42)', 50984, '50,984'], ['sh1', 9016, '9,016']], 50984, mark=[0], done=[1]), kv=KV([['k = 42 占 70%', '同一个哈希值,同一个 chunk'], ['结果', '85% 的文档在一个分片'], ['要避免', '热点键本身要打散(加后缀等)']], ['要避免'])),
    step("explain 看路由:hot 集合(哈希键)k = 42 只涉及 sh0,k = 43 只涉及 sh1(等值查询 targeted);k ∈ [40, 50) 的范围查询涉及 sh0 和 sh1,k $in [1, 2, 3, 4] 也涉及两个分片(scatter-gather)。", t=tl(S(6)), mark=lidx(S(6), "k ∈ [40, 50) → ['sh0', 'sh1']"), done=lidx(S(6), "k = 42 → ['sh0']"), kv=KV([['等值', 'targeted,1 个分片'], ['范围 / $in 多值', '哈希后散在各处,多个分片']], ['等值'])),
]
A = mkartm('m67', 67, 'MongoDB,分片,hashed,ranged,chunk分布,热点键,真实验证,动画演示',
    '实测哈希与 ranged 分片键的 chunk 分布:哈希键建集合时每个分片一个 chunk、连续键对半分(30,451 对 29,549),ranged 连续键 100% 在一个分片;随机键的 ranged 集合靠 balancer 分开;70% 文档同一个键值时哈希也救不了(85% 在一个 chunk);哈希键的等值查询 targeted,范围与 $in 多值 scatter-gather。',
    '哈希分片键和 ranged 分片键,chunk 是怎么分布的?哈希一定均匀吗?这篇用连续键、随机键、热点键三种数据在两个分片上逐个看。',
    [('30,451 对 29,549', '60,000 个连续键在哈希分片集合上两个分片拥有的文档数'), ('60,000 对 0', '同样的连续键在 ranged 分片集合上两个分片拥有的文档数'), ('85%', '70% 文档同一个键值时,最大 chunk 占的文档比例')],
    [('哈希的初始 chunk', '<p>哈希分片集合在建立时就按哈希空间(以 0 为界)给每个分片一个 chunk。</p>'),
     ('numInitialChunks', '<p><code>numInitialChunks=8</code> 在这个版本上实测没有生效,chunk 仍是 2 个,要用 <code>config.chunks</code> 核对。</p>'),
     ('连续键', '<p>哈希把连续键均匀打散(30,451 对 29,549);ranged 的连续键全挤在一个 chunk 里(60,000 对 0)。</p>'),
     ('随机键', '<p>ranged 集合上随机键开始也都在一个 chunk,但 balancer 拆分并迁移后能分开(37,044 对 22,956)。</p>'),
     ('热点键', '<p>哈希只能打散不同的键值,同一个键值始终映射到同一个哈希值、同一个 chunk:70% 文档同一个 k,85% 的文档就在一个分片上。</p>'),
     ('路由', '<p>哈希键的等值查询 targeted 到一个分片,范围与 <code>$in</code> 多值要问多个分片。</p>')],
    steps,
    [ENV_M + '。2 个分片,chunk 1 MB,balancer 在大部分对比里关着',
     '没有验证:numInitialChunks 为什么没有生效(可能与版本或集合状态有关,没有查明);presplitHashedZones;数据倾斜在 zone sharding 下的表现;复合哈希键;热点键加随机后缀的办法;chunk 数很多时 mongos 路由缓存的开销'],
    '哈希与 ranged 的 chunk 分布')
