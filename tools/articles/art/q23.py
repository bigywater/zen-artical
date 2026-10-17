from lib import *
S = SS('q23')
steps = [
    step("pika 的 BlockingConnection 没有自动重连:用 rabbitmqctl close_connection <pid> \"closed by operator\" 强制关掉消费者所在的连接,消费者的 process_data_events 立刻抛 ConnectionClosedByBroker: (320, 'CONNECTION_FORCED - closed by operator'),is_open 变成 False;随后另一个连接再发一条消息 after,队列里是 (ready, unacked) = (1, 0)——没有消费者了,消息就停在队列里。连接、channel、消费者全靠应用自己重建。", t=tl(S(1)), mark=lidx(S(1), 'ConnectionClosedByBroker', '(1, 0)'), done=lidx(S(1), '消费者在线时收到', 'close_connection'), kv=KV([['pika Blocking', '没有自动重连'], ['被关后', '抛 ConnectionClosedByBroker(320)'], ['应用要做的', '重连 + 重新声明 + 重新订阅']], ['pika Blocking'])),
    step("aio-pika 的 connect_robust(reconnect_interval=1 s)会自动重连并恢复拓扑:每 10 ms 发一条带序号的持久化消息(带 confirm),期间正常关闭 broker(1.5 s)再启动(4.9 s 后可用)。broker 一可用,消费者在 0.03 s 后就又收到了消息;消费端共 728 条,重复 0 条,redelivered=True 0 条,已确认发送但没收到的 0 条。消费端相邻两条的最大间隔是 6.05 s,正是停机加启动的时间。注意发布端:停机期间有 510 次发布失败(ChannelInvalidStateError)——robust 连接不会替你缓冲或重发,发布失败要自己重试。", t=tl(S(2)), mark=lidx(S(2), '发布端:确认成功', '最大间隔'), done=lidx(S(2), 'broker 关闭用了', '已确认发送但没收到'), b=bars([['确认成功并收到', 728, '728 条'], ['发布失败(停机期间)', 510, '510 次'], ['重复', 0, '0'], ['丢失', 0, '0']], 728, mark=[1], done=[0, 2, 3]), kv=KV([['消费端', '自动恢复,无重复无丢失'], ['发布端', '停机期间 510 次失败,需自己重试'], ['中断', '6.05 s = 停机 + 启动']], ['发布端'])),
    step("队列被别人删除(或者 quorum / 单副本队列所在节点出了问题)时,broker 主动取消消费者,发 Basic.Cancel(consumer_cancel_notify 能力):pika 的 add_on_cancel_callback 收到 Cancel,channel 仍然开着(is_open=True),连接也没断。这种情况不会触发“连接断了就重连”的逻辑——客户端必须自己监听取消通知,重新声明队列、重新订阅。", t=tl(S(3)), mark=lidx(S(3), "['Cancel']"), done=lidx(S(3), '这种取消不会'), kv=KV([['队列被删', 'broker 发 Basic.Cancel'], ['连接 / channel', '都还开着'], ['应用要做', '监听 cancel 并重新订阅']], ['应用要做'])),
    step("拓扑恢复的边界:排他队列在 broker 重启后本身会消失,但 robust 客户端按原名重新声明出来了(按原名 passive 声明能找到;aio-pika 的空队列名是客户端自己生成的 amq_<uuid>,不是服务器命名),它里面的消息当然是空的;durable 的队列 keepme 本来就在磁盘上,重启后还在。所以“恢复”恢复的是定义和订阅,不是数据:非持久队列里的消息、没确认的发布,都要靠应用层处理。", t=tl(S(4)), mark=lidx(S(4), '排他队列'), done=lidx(S(4), 'durable 的 keepme'), kv=KV([['恢复的', 'exchange / 队列 / 绑定 / 消费者的定义'], ['不恢复的', '非持久队列里的消息、未确认的发布'], ['durable 队列', '在磁盘上,重启后还在']], ['不恢复的'])),
]
A = mkartq('q23', 23, 'RabbitMQ,自动重连,拓扑恢复,aio-pika,connect_robust,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上对比客户端的断线行为:pika 的 BlockingConnection 被强制关闭后抛 ConnectionClosedByBroker 且不恢复;aio-pika 的 connect_robust 在 broker 重启(6 秒中断)后自动重连并恢复消费者,728 条无重复无丢失,但停机期间发布端有 510 次失败要自己重试;队列被删时只收到 Basic.Cancel。',
    '连接断了以后谁来恢复:连接、channel、exchange、队列、绑定、消费者,还有没发完的消息?不同客户端库差别很大。这篇用 pika 和 aio-pika 在同一个 broker 上做断线实验,看哪些被自动恢复,哪些要应用自己做。',
    [('6.05 s', 'broker 重启期间消费端的最大间隔(停机 1.5 s + 启动 4.9 s),之后自动恢复'), ('0 / 0', 'robust 消费者收到 728 条,重复 0 条、丢失 0 条'), ('510 次', '停机期间发布端的失败次数(ChannelInvalidStateError),需要应用自己重试')],
    [('没有自动恢复', '<p>pika 的 <code>BlockingConnection</code> 不会重连,连接被关后异常抛给调用者,所有对象都要应用重建。</p>'),
     ('robust 连接', '<p>aio-pika 的 <code>connect_robust</code> 会按 <code>reconnect_interval</code> 重连,并把声明过的 exchange、队列、绑定和消费者重新声明。消费端无重复无丢失,持久消息一条不少;但发布端不一样——连接断开期间的 publish 直接失败(停机期间 510 次),robust 连接不会替你缓冲,应用要自己重试并考虑幂等。</p>'),
     ('队列被删除', '<p>broker 发 <code>Basic.Cancel</code>,连接和 channel 不受影响,客户端要自己监听并重新订阅。</p>'),
     ('恢复的是什么', '<p>恢复的是拓扑定义和订阅,不是数据:非持久队列在重启后是空的,未确认的发布结果不确定。</p>')],
    steps,
    [ENV_Q + '。第一节用 rabbitmqctl close_connection <pid> 关掉消费者连接;第二节 aio-pika(connect_robust,reconnect_interval=1)的发布者带 publisher confirm,每 10 ms 一条;关闭 broker 用 rabbitmqctl shutdown,再启动;序号核对收发的重复与丢失',
     '没有验证:kill -9 突然死亡时的恢复(这里是正常关闭);指数退避的重连策略与重连风暴;集群里故障转移到其他节点(客户端地址列表);发布端自己实现重试后产生的重复;Java / Go 等客户端库的恢复行为;消费者在重连窗口里已处理未确认的消息会重复投递(这次没有出现 redelivered)'],
    '自动重连')
