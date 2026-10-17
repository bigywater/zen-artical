import json
from lib import *
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
own = lambda a: cells(a)
steps = [
    step("流里有 8 条消息。工作进程 A(独立进程)读 5 条,ack 前 2 条,正在处理第 3 条。此时 PEL:3-0、4-0、5-0 属于 A。", own=cells(['1 A✓', '2 A✓', '3 A', '4 A', '5 A', '6', '7', '8'], cur=[2, 3, 4], done=[0, 1]), kv=KV([['A 的 pending', '3']], ['A 的 pending'])),
    step("kill -9 掉 A。CLIENT LIST 里 worker-A 的连接从 1 个变成 0 个——Redis 知道连接断了。", own=cells(['1 A✓', '2 A✓', '3 A ✗', '4 A ✗', '5 A ✗', '6', '7', '8'], mark=[2, 3, 4], done=[0, 1]), kv=KV([['CLIENT LIST worker-A', '1 → 0 个连接']], ['CLIENT LIST worker-A'])),
    step("但消费者 A 还在、它的 PEL 也还在:XINFO CONSUMERS 里 A pending = 3、idle = 306 ms(距 A 最后一次活动);再过约 1 秒,XPENDING 里这 3 条各自的 idle 是 1309 ms(距投递时间)。Redis 不会因为连接断开就把消息还回去。", own=cells(['1', '2', '3 A', '4 A', '5 A', '6', '7', '8'], mark=[2, 3, 4], dim=[0, 1]), kv=KV([['A pending', '3'], ['XINFO 消费者 idle', '306 ms'], ['XPENDING 消息 idle', '1309 ms']], ['XPENDING 消息 idle'])),
    step("消费者 B 用 > 读,拿到的是 6-0、7-0、8-0——游标之后的新消息。A 没处理完的 3、4、5 不会自动转给 B。", own=cells(['1', '2', '3 A', '4 A', '5 A', '6 B', '7 B', '8 B'], cur=[5, 6, 7], mark=[2, 3, 4], dim=[0, 1]), kv=KV([['B 用 > 读到', '6-0 7-0 8-0']], ['B 用 > 读到'])),
    step("B 主动 XCLAIM 3-0 4-0 5-0(min-idle 1000 ms):A 空闲 1309 ms ≥ 1000,认领成功。这三条现在属于 B,投递次数变成 2。", own=cells(['1', '2', '3 B', '4 B', '5 B', '6 B', '7 B', '8 B'], cur=[2, 3, 4], dim=[0, 1]), kv=KV([['XCLAIM 后 3-0', 'owner=B, deliveries=2, idle=0']], ['XCLAIM 后 3-0'])),
    step("C 马上再 XCLAIM 3-0(min-idle 1000 ms):3-0 刚被 B 认领,idle 才 0 ms,返回空。min-idle 防止两个人同时认领同一条消息。", own=cells(['1', '2', '3 B', '4 B', '5 B', '6 B', '7 B', '8 B'], mark=[2], dim=[0, 1]), kv=KV([['XCLAIM C 1000 3-0', '(empty array)']], ['XCLAIM C 1000 3-0'])),
    step("危险:XGROUP DELCONSUMER s g B 返回 6,直接丢弃 B 名下的 6 条 PEL 记录。消息还在流里(XRANGE 能读到 3-0),但没有任何组记得它没处理完——这些消息不会再被重投。", own=cells(['1', '2', '3 ?', '4 ?', '5 ?', '6 ?', '7 ?', '8 ?'], mark=[2, 3, 4, 5, 6, 7], dim=[0, 1]), kv=KV([['DELCONSUMER 返回', '6'], ['XPENDING s g', '0']], ['DELCONSUMER 返回'])),
]
A = dict(
    n=44, series='redis', tags='Redis,Stream,故障恢复,真实验证,动画演示',
    desc='用独立进程真实 kill -9 一个 Stream 消费者:连接断开后它的 PEL 仍留在组里、idle 持续增长、消息不会自动转给别的消费者;另一个消费者要用 XCLAIM 主动认领(投递次数 +1,min-idle 防重复认领);XGROUP DELCONSUMER 会直接丢弃 PEL,是个危险操作。',
    lead='消费者崩溃是消息队列最该讲清楚的场景。Stream 的答案是:消息不会丢,也不会自动换人——它们留在崩溃消费者名下的 PEL 里,等别人来认领。这篇真的起一个工作进程、用 kill -9 杀掉它,一步步看 Redis 里留下什么。',
    facts=[('3 条', '被 kill -9 的消费者 A 名下遗留的未确认消息'), ('不自动转移', 'B 用 > 读,只拿到新消息,拿不到 A 遗留的'), ('DELCONSUMER', '返回被丢弃的 PEL 条数,消息本身在流里但不再被追踪')],
    body=[
        sec('做的事:让一个真实进程崩溃', '', term('', blk('r44', 1)), '<p>A 是用 <code>subprocess</code> 启动的独立 Python 进程:读 5 条,ack 前 2 条,然后开始「处理」第 3 条。我从外面直接 <code>kill -9</code>。用 <code>CLIENT LIST</code> 数 <code>name=worker-A</code> 的连接:kill 前 1 个,kill 后 0 个。</p>'),
        sec('连接没了,PEL 还在', '', term('', blk('r44', 2)), '<p>消费者 A 依然存在(<code>XINFO CONSUMERS</code>),pending 是 3(3-0、4-0、5-0,前两条已 ack),idle 306 ms。约 1 秒后 XPENDING 明细里这三条消息的 idle 是 1309 ms。注意两个 idle 不是同一个计数:<code>XINFO CONSUMERS</code> 的是「消费者距最后一次活动」,<code>XPENDING</code> 的是「这条消息距上次投递」。这里的关键事实:<b>连接断开不会触发任何重新分配</b>。</p>'),
        sec('新消费者拿不到这些消息', '', term('', blk('r44', 3)), '<p>B 用 <code>XREADGROUP … &gt;</code> 读,只拿到游标之后的 6-0、7-0、8-0。这是 <code>&gt;</code> 的定义:只要「从没投递给任何人」的新消息。</p>'),
        sec('XCLAIM:主动认领', '', term('', blk('r44', 4)), '<p>B 认领 A 空闲超过 1000 ms 的三条:成功,消息内容一并返回。认领后 XPENDING 显示它们的消费者变成 B、idle 归零、<b>投递次数变成 2</b>(6、7、8 号是 B 自己刚读的,所以次数是 1)。</p>', term('', blk('r44', 5)), '<p>C 立刻再来认领 3-0:返回空——3-0 刚被 B 认领,idle 只有几毫秒,不满足 1000 ms 的 <code>min-idle-time</code>。这个参数是防止两个恢复进程同时抢同一条消息的保护。</p>'),
        sec('危险:XGROUP DELCONSUMER', '', term('', blk('r44', 6)), '<p>删除消费者 B 时返回 6,表示丢弃了 B 名下 6 条 PEL 记录;之后 <code>XPENDING s g</code> 是 0。消息本身还在流里(XRANGE 读得到 3-0),但组里已经没有任何记录说它「还没处理完」。<b>下线消费者之前,应先把它的 PEL 认领走再删。</b></p>'),
        sec('分步演示:崩溃后消息的去向', '', demo('消费者崩溃', [('own', 'cells', '8 条消息当前归谁(✓ = 已 ack)'), ('kv', 'kv', '关键事实')], steps, '本步变化的消息')),
    ],
    refs=[ENV_R + '。A 是独立 Python 进程,被 SIGKILL;其余操作在同一个测试脚本里串行完成', '没有验证:客户端库自带的自动重试与重连行为、连接断开时 Redis 是否有 CLIENT 相关的超时清理(只观察了 5 秒内)、消费者数量很多时 XINFO CONSUMERS 的开销'],
)
