from lib import *
R = J('z82'); nv, lk, bn = R['naive'], R['locking'], R['bench']
def S(k): return [l for l in out('z82').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("kazoo 的 Queue 在服务端就是 /q 下的顺序节点,名字 entry-<优先级 3 位>-<10 位序号>;出队 = 取最小的一个并删除。先入 5 条优先级 100,再入 1 条优先级 10:取出顺序是 urgent、job-0…job-4,即优先级数字小的先出、同级先进先出;空队列 get() 返回 None(不阻塞)。", t=tl(S(1)), done=[0], kv=KV([['节点名', 'entry-<优先级>-<序号>'], ['空队列 get', '返回 None']], ['节点名'])),
    step(f"普通 Queue 是「取出即删除」:3 个消费者处理 200 条,处理中途 kill -9 其中一个:200 条都被取出,只有 {nv['done']} 条处理完成,丢了 {nv['lost'][0]}(被杀的消费者手里的那条)。取出之后、处理完成之前崩溃的消息永远消失。", t=tl(S(2)), mark=[0], kv=KV([['取出', f"{nv['take']}"], ['处理完成', f"{nv['done']}"], ['丢失', nv['lost'][0]]], ['丢失'])),
    step(f"LockingQueue:取出时在消息上加一个临时锁节点,处理完调用 consume() 才删消息。kill -9 一个消费者后,它手里的 {lk['dup'][0]} 在会话过期后(+3.8 s)被另一个消费者重新取出并确认;30 条全部确认({lk['ack']} / 30),没有丢,但 {lk['dup'][0]} 被取出了 2 次 —— 至少一次投递,处理要幂等。", t=tl(S(3)), done=[0, 1], kv=KV([['确认', f"{lk['ack']} / 30"], ['重复取出', lk['dup'][0]]], ['重复取出'])),
    step(f"代价:单生产者单消费者各 300 条,Queue 入队 {bn['q_put']:.0f} 条/s、出队 {bn['q_get']:.0f} 条/s;LockingQueue 入队 {bn['lq_put']:.0f} 条/s、出队并确认 {bn['lq_get']:.0f} 条/s(出队约慢一半)。每条消息都是一次顺序节点写、一次提交到多数派 —— 这是协调用的队列,不是消息中间件。", b=bars([['Queue 出队', bn['q_get'], f"{bn['q_get']:.0f}/s"], ['LockingQueue 出队+确认', bn['lq_get'], f"{bn['lq_get']:.0f}/s"]], 350, done=[0], mark=[1]), t=tl(S(4)), kv=KV([['Queue 出队', f"{bn['q_get']:.0f} 条/s"], ['LockingQueue 出队', f"{bn['lq_get']:.0f} 条/s"]], ['LockingQueue 出队'])),
]
A = dict(
    n=82, series='zookeeper', tags='ZooKeeper,分布式队列,kazoo,真实验证,动画演示',
    desc=f'kazoo 的 Queue / LockingQueue 实测:节点名 entry-优先级-序号;普通 Queue 消费者崩溃丢 1 条({nv["done"]}/200 完成);LockingQueue 崩溃后消息在会话过期后被重取,30 条全确认但有 1 条被取 2 次;吞吐 {bn["q_get"]:.0f} vs {bn["lq_get"]:.0f} 条/s。',
    lead='用 ZooKeeper 做队列很容易:顺序节点就是天然的排队号。但消费者崩溃时消息去哪了?这篇用 kazoo 的两种队列做对比实验:普通 Queue 丢了一条,LockingQueue 没丢但会重复,以及这个队列到底能跑多快。',
    facts=[(f'{nv["done"]} / 200', '普通 Queue 在消费者 kill -9 后完成的条数(丢 1 条)'), (f'{lk["ack"]} / 30', 'LockingQueue 在消费者 kill -9 后确认的条数(0 丢失,1 条重复)'), (f'{bn["q_get"]:.0f} 条/s', '单消费者出队速度(Queue)')],
    body=[
        sec('队列在服务端的样子', '', term('', blk('z82', 1)), '<p>和<a href="zookeeper-sequential-node.html">顺序节点</a>那篇的结论一致:序号由服务端分配,所以多个生产者同时入队也不会冲突。</p>'),
        sec('普通 Queue:取出即删除', '', term('', blk('z82', 2)), '<p>出队是「读最小节点 + 删除」一步完成,消息一旦出队就只存在于消费者内存里。消费者在处理中崩溃,没有任何地方还留着它。能接受丢失(比如统计、缓存刷新通知)才用这种。</p>'),
        sec('LockingQueue:至少一次', '', term('', blk('z82', 3)), '<p>消息先被「锁」住(一个临时节点,属于消费者的会话),处理完调用 <code>consume()</code> 才真正删除。消费者崩溃后<a href="zookeeper-session-expire.html">会话过期</a>,锁节点消失,消息重新可见。结果是不丢但可能重复:如果消费者处理完了、还没来得及 consume 就崩溃,这条会被处理第二次。</p>'),
        sec('吞吐', '', term('', blk('z82', 4)), '<p>队列里未消费的每条消息都是内存里的 znode、也在快照里(见<a href="zookeeper-datree.html">DataTree</a>),积压成千上万条会拖慢 <code>get_children</code>。堆积量大、吞吐高的场景请用 Kafka / RabbitMQ 之类,ZooKeeper 队列适合少量、低频、需要强一致排序的协调任务。</p>'),
        sec('分步演示', '', demo('分布式队列', [('t', 'term', '输出'), ('b', 'bars', '吞吐'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0 的 Queue 与 LockingQueue;消费者是独立子进程;会话超时 3 s;吞吐是单进程单连接的同步调用,不是集群上限', '没有验证:PriorityQueue 之外的 kazoo 队列(LockingQueue 的优先级)、几万条积压时 get_children 的耗时、多消费者并发取同一条的竞争细节、与 Kafka / RabbitMQ 的对比'],
)
