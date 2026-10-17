from lib import *
S = SS('q32')
steps = [
    step("积压是这样形成的:发布速率 800 条/秒,一个消费者每条处理 2 ms(上限约 500 条/秒),跑 20 秒。每 4 秒看一次:ready 从 1738 涨到 3493、5249、7002、8750,每 4 秒约增加 1750,也就是以约 438 条/秒的速度增长;unacked 稳定在 10(prefetch=10);累计处理了 8878 条,约 444 条/秒。consumer_capacity 只有 0.005 上下——它表示队列能往消费者投递的时间占比,接近 0 说明消费者的 prefetch 窗口一直是满的,消费者就是瓶颈。", t=tl(S(1)), mark=lidx(S(1), '(20, 8750', 'ready 以约'), done=lidx(S(1), '(4, 1738', '(8, 3493'), b=bars([['4 s', 1738, '1738'], ['8 s', 3493, '3493'], ['12 s', 5249, '5249'], ['16 s', 7002, '7002'], ['20 s', 8750, '8750']], 8750, mark=[4], done=[0, 1, 2, 3]), kv=KV([['发布', '800 条/秒'], ['消费', '约 444 条/秒'], ['ready 增长', '约 438 条/秒'], ['consumer_capacity', '≈ 0.005:消费者一直满负荷']], ['consumer_capacity'])),
    step("三种“积压”同样放 5000 条后的样子(等 4 秒):(a) 没有消费者:ready 5000、unacked 0、consumers 0、capacity 0.0;(b) 1 个慢消费者 prefetch=10:ready 4909、unacked 10、consumers 1、capacity 0.044;(b2) 同样的慢消费者 prefetch=1000:ready 3919、unacked 1000、consumers 1、capacity 0.044;(c) 消费者卡住不 ack(prefetch=100):ready 4900、unacked 100、consumers 1、capacity 0.043。一张快照分不出“慢”和“卡住”(capacity 都≈0.04,unacked 都等于 prefetch),要看 ready 随时间是不是还在减少。", t=tl(S(2)), mark=lidx(S(2), '(c)', '(b2)'), done=lidx(S(2), '(a)', '(b) 1 个'), kv=KV([['(a) 无消费者', 'consumers = 0'], ['(b) 慢', 'unacked = prefetch,ready 缓慢下降'], ['(c) 卡住', 'unacked = prefetch,ready 不动']], ['(c) 卡住'])),
    step("恢复:每条处理 5 ms、prefetch=20,加消费者几乎线性提高清积压的速度:1 个消费者 159 条/秒(只放了 4000 条,耗时 25.2 s);2 个 318 条/秒,20000 条花了 62.9 s;4 个 638 条/秒,31.3 s;8 个 1273 条/秒,15.7 s。单个消费者的理论上限是 1 ÷ 5 ms = 200 条/秒,实测约 160。加消费者能线性缩短清空时间,前提是处理本身是瓶颈。", t=tl(S(3)), mark=lidx(S(3), '8       '), done=lidx(S(3), '1       ', '2       ', '4       '), b=bars([['1 个消费者', 159, '159 条/秒'], ['2 个', 318, '318 条/秒'], ['4 个', 638, '638 条/秒'], ['8 个', 1273, '1273 条/秒']], 1273, mark=[3], done=[0, 1, 2]), kv=KV([['1 个消费者', '≈ 160 条/秒'], ['8 个消费者', '≈ 1273 条/秒'], ['规律', '吞吐随消费者数线性增长']], ['规律'])),
    step("最后的手段是 purge:放 50000 条后 queue_purge 返回 message_count=50000,只用了 20 ms,之后 ready=0。purge 丢弃的是 ready 的消息,不会碰 unacked;是个瞬间的、不可逆的操作,只适用于这些消息已经没有价值的情况(比如过期的任务)。", t=tl(S(4)), mark=lidx(S(4), 'purge 50000 条'), done=lidx(S(4), 'purge 50000 条'), kv=KV([['purge', '50000 条 → 20 ms'], ['范围', '只清 ready,不清 unacked'], ['风险', '不可逆']], ['风险'])),
]
A = mkartq('q32', 32, 'RabbitMQ,消息积压,consumer_capacity,prefetch,清积压,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上复现消息积压:发布 800 条/秒、消费约 444 条/秒时 ready 每秒增长约 438 条,consumer_capacity≈0.005 表示消费者是瓶颈;无消费者 / 慢消费者 / 卡住消费者的快照对比;加消费者 1→8 个吞吐 159→1273 条/秒线性增长;purge 50000 条只要 20 ms。',
    '队列里 ready 一直涨,到底是没人消费、消费太慢、还是消费者卡住了?该看哪几个数?怎么最快清掉积压?这篇复现积压,对比三种情况的快照,并实测加消费者与 purge 的效果。',
    [('+438 条/秒', '发布 800 条/秒而消费约 444 条/秒时,ready 的增长速度'), ('159 → 1273', '1 个与 8 个消费者的清积压吞吐(条/秒),线性增长'), ('20 ms', 'purge 50000 条消息所需时间')],
    [('怎么形成', '<p>发布速率超过消费速率,差值就是 ready 的增长速度。队列统计里的 <code>consumer_capacity</code> 接近 0 表示消费者的 prefetch 窗口始终是满的——消费者是瓶颈。</p>'),
     ('排查', '<p>看 <code>consumers</code>(0 说明没人消费)、<code>messages_unacknowledged</code> 是否等于 prefetch、<code>ready</code> 是否还在下降。慢和卡住的快照几乎一样,要看随时间的变化。</p>'),
     ('恢复', '<p>处理本身是瓶颈时,加消费者线性提高清积压速度:1 个 159 条/秒,8 个 1273 条/秒。</p>'),
     ('purge', '<p>消息已无价值时,<code>queue_purge</code> 瞬间清掉所有 ready 的消息(50000 条 20 ms),不可逆。</p>')],
    steps,
    [ENV_Q + '。第一节发布者用线程按固定间隔发,消费者每条 sleep 2 ms 模拟处理;第二节每种情形放 5000 条、等 4 秒再读;第三节每个消费者每条 5 ms、prefetch=20(1 个消费者只放了 4000 条);数字来自 rabbitmqctl list_queues,包括 consumer_capacity',
     '没有验证:消息体更大的积压对内存 / 磁盘的影响;积压到百万级时的恢复;消费者崩溃后重投造成的二次积压;死信 / 限流等减轻积压的策略;quorum 和 stream 队列上同样的指标;publisher 端用 reject-publish 做背压(第 13 篇)'],
    '消息积压')
