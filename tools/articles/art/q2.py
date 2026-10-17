from lib import *
S = SS('q2')
steps = [
    step("direct:d.a 绑 red,d.b 绑 blue,d.c 绑 red 和 blue 两个 key。发布 5 条(key 分别是 red、blue、green、Red、\"red \"):d.a 收到 red,d.b 收到 blue,d.c 收到 red 和 blue 各一条;green、大小写不同的 Red、末尾带空格的 \"red \" 没有任何绑定匹配,这 3 条被直接丢掉(没开 mandatory,发布方不会知道)。direct 的匹配是逐字节完全相等。", t=tl(S(1)), mark=lidx(S(1), '发布了 5 条'), done=lidx(S(1), 'd.a ', 'd.b ', 'd.c '), kv=KV([['匹配规则', 'routing key == binding key,逐字节相等'], ['大小写', '敏感:Red ≠ red'], ['空格', '末尾空格也算:\"red \" ≠ red'], ['无绑定匹配', '默默丢弃']], ['匹配规则'])),
    step("fanout:3 个队列绑定时给了不同的 key(k1、k2、空串),发布时的 key 是 anything、空串、k1——3 条消息,每个队列都收到全部 3 条。fanout 完全忽略 routing key,不论发布时还是绑定时给的。", t=tl(S(2)), mark=lidx(S(2), '3 条消息 × 3 个队列'), done=lidx(S(2), 'f.a ', 'f.b ', 'f.c '), kv=KV([['匹配规则', '不看 routing key'], ['结果', '每个绑定的队列各一份'], ['3 条 × 3 个队列', '每个队列都收到 3 条']], ['匹配规则'])),
    step("topic:key 用点分成单词,* 匹配恰好一个单词,# 匹配零个或多个。绑定 *.orange.*、*.*.rabbit、lazy.#、# 之后发布 10 个 key。t.all(#)全收,10 条;t.lazy(lazy.#)收到 5 条,包括单独的 lazy(# 可以匹配零个单词);t.orange 3 条,quick.orange.male.rabbit 有四个单词所以不匹配 *.orange.*;t.rabbit 2 条,同理不匹配 *.*.rabbit;单词 orange 只有 t.all 收。", t=tl(S(3)), mark=lidx(S(3), 'quick.orange.male.rabbit', 'orange   ', 'lazy       '), done=lidx(S(3), '各队列收到的条数', 'quick.orange.rabbit', 'lazy.pink.rabbit'), b=bars([['t.all (#)', 10, '10 条'], ['t.lazy (lazy.#)', 5, '5 条'], ['t.orange', 3, '3 条'], ['t.rabbit', 2, '2 条']], 10, mark=[1], done=[0, 2, 3]), kv=KV([['*', '恰好一个单词'], ['#', '零个或多个单词,lazy.# 也匹配 lazy'], ['单词分隔', '只有 . 分隔单词'], ['quick.orange.male.rabbit', '4 个单词,*.orange.* 和 *.*.rabbit 都不匹配']], ['#'])),
    step("headers:忽略 routing key,按消息头路由。h.all 绑定 x-match=all(format=pdf 且 type=report),h.any 绑定 x-match=any(两者其一)。pdf+report 两个队列都收到;pdf+log 和 txt+report 只有 any 收到;pdf+report+extra(多一个无关的头)all 也能匹配——多出来的头不影响;txt only 与无头的消息两个队列都收不到。", t=tl(S(4)), mark=lidx(S(4), 'pdf+log', 'txt+report', 'pdf+report+extra'), done=lidx(S(4), 'pdf+report   ', '无头', 'txt only'), kv=KV([['x-match=all', '绑定的所有头都要匹配'], ['x-match=any', '至少一个头匹配'], ['消息多出的头', '不影响匹配'], ['routing key', '被忽略']], ['x-match=any'])),
    step("同一条消息命中同一个队列的多个绑定,队列里只有一份:u.q 绑了 a.*、# 和 a.b 三个绑定,发布一条 a.b,u.q 里只有 1 条;u.q2 单独绑 a.b,也收到 1 条。所以 exchange 是对“哪些队列”做集合,不是对绑定做累加。", t=tl(S(5)), mark=lidx(S(5), 'u.q 有 3 个绑定'), done=lidx(S(5), 'u.q ', 'u.q2'), kv=KV([['3 个绑定都匹配', '队列里仍是 1 份'], ['不同队列', '各一份'], ['去重单位', '队列']], ['3 个绑定都匹配'])),
    step("路由查找的代价:1 个队列绑 B 个 key,发布 10000 条消息(不开 confirm,3 次中位数)。direct 在 B=10、100、1000 时都是 272~276 ms;topic 277、278、295 ms,几乎不随绑定数变化;headers 266、426、3387 ms——headers 的匹配要逐个比较绑定,B=1000 时慢到约 12 倍。要按头路由又要大量绑定,值得换成 topic 或 direct 的编码方式。", t=tl(S(6)), mark=lidx(S(6), 'headers  '), done=lidx(S(6), 'direct  ', 'topic  '), b=bars([['direct B=1000', 276, '276 ms'], ['topic B=1000', 295, '295 ms'], ['headers B=100', 426, '426 ms'], ['headers B=1000', 3387, '3387 ms']], 3387, mark=[3], done=[0, 1, 2]), kv=KV([['direct', 'B 从 10 到 1000 几乎不变'], ['topic', '同样几乎不变'], ['headers', 'B=1000 时慢 12 倍左右']], ['headers'])),
]
A = mkartq('q2', 2, 'RabbitMQ,exchange,direct,fanout,topic,headers,路由,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测四种 exchange 的路由规则:direct 逐字节相等、fanout 忽略 key、topic 的 * 与 # 匹配(含零个单词)、headers 的 x-match all/any;同队列多个绑定只收一份;1000 个绑定时 direct、topic 约 276~295 ms,headers 3387 ms。',
    'direct、fanout、topic、headers 四种 exchange 到底按什么规则把消息分给队列?topic 的 # 能不能匹配零个单词,headers 多出一个头会怎样,绑定很多时谁会变慢?这篇每种都建好队列、发出一批 key,把每个队列真实收到的东西列成表。',
    [('t.all=10 / t.lazy=5', 'topic 的 # 全收 10 条;lazy.# 收到 5 条,包括单独的 lazy'), ('3 条 × 3 队列', 'fanout 不看 routing key:3 条消息每个队列都收到 3 条'), ('3387 ms', 'headers 绑定数 1000 时发布 10000 条的耗时(direct 276 ms、topic 295 ms)')],
    [('direct', '<p>routing key 与绑定 key 逐字节相等才路由,大小写、空格都算。一个队列可以用多个 key 绑同一个 exchange;没有匹配的消息直接丢弃。</p>'),
     ('fanout', '<p>不看 routing key,所有绑定的队列各收一份。绑定时给的 key 也被忽略。</p>'),
     ('topic', '<p>key 是点分的单词。<code>*</code> 匹配恰好一个单词,<code>#</code> 匹配零个或多个单词(所以 <code>lazy.#</code> 也能匹配 <code>lazy</code> 本身)。表里每个 key 对每个绑定的匹配结果都是真实收到的。</p>'),
     ('headers', '<p>按消息头匹配,忽略 routing key。<code>x-match=all</code> 要求绑定里列的每个头都匹配,<code>any</code> 只要一个;消息多出来的头不影响匹配。</p>'),
     ('去重', '<p>一条消息命中同一个队列的多个绑定,队列里只有一份;命中几个队列就复制几份。</p>'),
     ('代价', '<p>direct 和 topic 的匹配基本不随绑定数增长;headers 要逐个比较绑定,1000 个绑定时 10000 条消息用了 3387 ms,而 direct 只要 276 ms。</p>')],
    steps,
    [ENV_Q + '。每一节先 queue_purge 再发布,发布后等 0.2 秒用 basic_get 取空每个队列;第六节发布时不开 publisher confirm,最后用一次 queue_declare(passive) 往返确保 broker 已处理完,3 次取中位数,每次之间 purge',
     '没有验证:有消费者在线时的行为(这里只用 basic_get);exchange-to-exchange 绑定;alternate-exchange;一致性哈希等插件 exchange;绑定数超过 1000 的 topic 性能;消息体更大时的路由开销;集群里 exchange 的元数据同步'],
    '四种 exchange')
