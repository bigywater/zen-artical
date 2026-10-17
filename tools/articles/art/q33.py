from lib import *
S = SS('q33')
steps = [
    step("消息 TTL 到点就从 ready 里消失:10 条消息 expiration=1000 ms,按每 0.25 s 间隔读队列条数(每次读本身要几百毫秒),采样点 0.0 s 是 10、0.62 s 仍是 10、1.26 s 就是 0、1.91 s 是 0——大约 1 秒时整批过期被清走。过期消息没被投给消费者,走死信(如果配了)或者直接丢弃。", t=tl(S(1)), mark=lidx(S(1), '(秒, ready)'), done=lidx(S(1), '(秒, ready)'), b=bars([['0.0 s', 10, '10 条'], ['0.62 s', 10, '10 条'], ['1.26 s', 0, '0 条']], 10, mark=[2], done=[0, 1]), kv=KV([['expiration=1000', '约 1 秒时整批过期'], ['过期后', '死信或丢弃'], ['消费者', '不会收到']], ['expiration=1000'])),
    step("队头阻塞造成“僵尸消息”:1 条没有 expiration 的消息排在队头,后面 10 条 expiration=500 ms。3 秒后 ready 仍是 11——后面已经过期的 10 条没有被清掉,因为只在队头检查。消费者 basic_get 取空时实际只拿到 head-no-ttl 一条:那 10 条是到达队头时才被丢掉,消费者看不到。僵尸消息会一直占着队列空间,直到前面的消息被消费。", t=tl(S(2)), mark=lidx(S(2), '3 秒后 ready = 11'), done=lidx(S(2), 'basic_get 取空'), b=bars([['3 秒后 ready', 11, '11 条'], ['消费者实际拿到', 1, '1 条']], 11, mark=[0], done=[1]), kv=KV([['过期检查', '只看队头'], ['队头没过期', '后面过期的也留着(11 条)'], ['消费者', '只拿到未过期的 1 条']], ['过期检查'])),
    step("队列 TTL 和消息 TTL 同时设取较小的:x-message-ttl=2000 的队列里,expiration=500 的消息在 0.9 s 的采样点已经不见;expiration=5000 的消息在 0.9 s 时还在、1.8 s 时已经没了——2000 ms 的队列 TTL 生效了。", t=tl(S(3)), mark=lidx(S(3), 'exp5000'), done=lidx(S(3), 'exp500('), kv=KV([['队列 TTL', '2000 ms'], ['消息 expiration=500', '500 ms 过期'], ['消息 expiration=5000', '按队列的 2000 ms 过期']], ['队列 TTL'])),
    step("expiration=0 的特殊含义:只有消息能立刻投给消费者才保留。没有消费者时发布,队列里 ready=0——立即被丢;有一个空闲消费者时发布,消费者收到了 ['with-consumer']。0 不是“永不过期”,而是“立即投递或丢弃”。", t=tl(S(4)), mark=lidx(S(4), '无消费者', '有一个空闲消费者'), done=lidx(S(4), '无消费者'), kv=KV([['expiration=0, 无消费者', '立即丢弃'], ['expiration=0, 有空闲消费者', '收到'], ['含义', '立即投递,否则丢']], ['含义'])),
    step("队列 TTL(x-expires)是“没人用”之后多久自动删除队列。x-expires=3000 ms 的队列声明后什么都不做,用 rabbitmqctl list_queues(只读元数据,不算使用)看:0.0、0.9、1.9 s 都在,2.8 s 起消失——约 3 秒。每秒做一次 passive 声明时,6 秒内队列一直在——passive 声明也重置计时;有消费者连着时 5 秒后仍在;消费者断开后同样是 2.8 s 起消失。", t=tl(S(5)), mark=lidx(S(5), '(2.8, False)', '消费者断开后'), done=lidx(S(5), '声明后什么都不做', 'passive 声明', '有一个消费者连着'), b=bars([['无人使用:消失', 2.8, '约 2.8~3 s'], ['每秒 passive 声明', 6, '6 s 仍在'], ['有消费者', 5, '5 s 仍在']], 6, mark=[0], done=[1, 2]), kv=KV([['x-expires=3000', '无人使用约 3 s 后删除'], ['重置计时的“使用”', '消费者 / basic_get / 声明(含 passive)'], ['不算使用', 'rabbitmqctl list_queues']], ['重置计时的“使用”'])),
    step("TTL 与重启:持久化消息 expiration=8000 ms,发布后 2 秒关闭 broker,停 8 秒再启动(总共超过 TTL):重启后队列 t6 的 ready=0——过期时间按发布时刻算,停机期间也在“走”,重启后消息已经过期被丢掉了。", t=tl(S(6)), mark=lidx(S(6), '重启后队列 t6'), done=lidx(S(6), '重启后队列 t6'), kv=KV([['TTL 计时', '从发布时刻起,不受停机影响'], ['重启后', '已过期的消息不再出现'], ['ready', '0']], ['TTL 计时'])),
]
A = mkartq('q33', 33, 'RabbitMQ,TTL,消息过期,x-expires,队头阻塞,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上实测 TTL:1000 ms 的消息约 1 秒整批过期;队头没过期时后面过期的 10 条变成“僵尸”(ready 仍是 11);队列 TTL 与消息 TTL 取较小;expiration=0 表示立即投递否则丢弃;x-expires 的队列无人使用约 3 秒后删除,passive 声明也算使用;TTL 按发布时刻计,重启后已过期的消息不再出现。',
    'TTL 看起来简单——到时间就删。但过期是在什么时刻真正发生的?队列 TTL 和消息 TTL 谁说了算?expiration=0 是什么意思?队列自己的 TTL 又怎么算?这篇一项项在 RabbitMQ 4.3.6 上量。',
    [('11 条', '队头没过期时,后面 10 条已过期的消息仍留在队列里的总数'), ('≈ 3 s', 'x-expires=3000 的队列在无人使用后被删除的时间,passive 声明也会重置计时'), ('0 条', '停机 8 秒、TTL 8000 ms 的持久化消息在重启后剩下的条数')],
    [('消息过期', '<p>消息 TTL 到点后从队列里移除(走死信或丢弃),消费者不会收到;实测 1000 ms 约 1 秒时整批过期。</p>'),
     ('只看队头', '<p>过期检查只在队头进行:队头没过期时,后面过期的消息继续占用队列,到达队头时才被丢弃,消费者看不到它们。</p>'),
     ('两种 TTL', '<p>队列的 <code>x-message-ttl</code> 与消息的 <code>expiration</code> 同时存在时取较小的。</p>'),
     ('expiration=0', '<p><code>expiration=0</code> 表示只在能立即投递给消费者时保留,否则立刻丢弃。</p>'),
     ('队列 TTL', '<p><code>x-expires</code> 是队列无人使用多久后被删除。消费者连着、basic_get、重新声明(包括 passive)都算使用。</p>'),
     ('重启', '<p>过期时间从发布时刻起算,broker 停机期间也在走,重启后已过期的消息不再出现。</p>')],
    steps,
    [ENV_Q + '。读队列条数用 rabbitmqctl list_queues(每次读本身要几百毫秒,时间戳是读之前的);x-expires 的存在检查用 list_queues name(只读元数据,不碰队列进程);第六节关闭 broker 用 rabbitmqctl shutdown',
     '没有验证:quorum 队列和 stream 队列上同样的 TTL 行为(第 11 篇看过 quorum 的队头阻塞);大量 TTL 消息的 CPU 开销;集群里队列 TTL 的清理;TTL 与死信的组合(见第 10、11 篇);expiration 字符串不合法时的错误'],
    'TTL')
