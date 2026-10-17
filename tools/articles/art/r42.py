import json
from lib import *
R = J('r42'); p = R['pel']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
ids = [f'{i}-0' for i in range(1, 11)]
def pel(rows, cur=(), mark=()): return {'lines': rows, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("流里有 10 条消息,组 g 从 0 开始。PEL(Pending Entries List)此刻是空的:什么都没投递。", pel=pel(['(空)']), kv=KV([['组 g pending', '0']], ['组 g pending'])),
    step("消费者 a 用 XREADGROUP > 读了 5 条,b 读了 3 条,都没有 XACK。每条消息一投递就进 PEL,记录 [ID, 消费者, 上次投递时间, 投递次数]。", pel=pel(['1-0  a  idle=…  deliveries=1', '2-0  a  …', '3-0  a  …', '4-0  a  …', '5-0  a  …', '6-0  b  …', '7-0  b  …', '8-0  b  …'], cur=range(8)), kv=KV([['XPENDING s g', '8 条:a 5、b 3'], ['最小/最大 ID', '1-0 / 8-0']], ['XPENDING s g'])),
    step("等 1.2 秒再看 XPENDING 明细:idle 变成 1202 ms。idle 只涨、不会自己触发重投——需要有人来处理(见第 44、45 篇)。", pel=pel(['1-0  a  idle=1202  deliveries=1', '… 共 8 行,idle 都在 1202 ms 左右'], cur=[0]), kv=KV([['idle', '1202 ms']], ['idle'])),
    step("用 XREADGROUP … 0 重读自己的历史(b 重读 6-0、7-0、8-0):这些消息又被投递了一次,idle 归零,投递次数从 1 变成 2。重读也算一次投递。", pel=pel(['6-0  b  idle=1  deliveries=2', '7-0  b  idle=1  deliveries=2', '8-0  b  idle=1  deliveries=2'], mark=[0, 1, 2]), kv=KV([['b 的 3 条', 'deliveries 1 → 2']], ['b 的 3 条'])),
    step("NOACK 读取(g2 组读了 4 条):不进 PEL,XPENDING g2 的条数是 0。适合「丢了也无所谓」的消息。", pel=pel(['g2: 读到 4 条 → PEL 0 条']), kv=KV([['g2 pending', '0']], ['g2 pending'])),
    step("PEL 只记 ID、不存消息内容:XDEL 掉 1-0 之后,PEL 里仍有 1-0;XREADGROUP … 0 返回 1-0 时内容是 (nil)。", pel=pel(['XDEL s 1-0', 'PEL: 1-0 仍在', 'XREADGROUP … 0 → 1-0 (nil)'], mark=[1, 2]), kv=KV([['1-0', 'PEL 有,流里没有']], ['1-0'])),
    step(f"代价:10 万条消息读了不 ack,MEMORY USAGE 从 {p['m0']} B 涨到 {p['m1']} B,PEL 增加 {p['m1']-p['m0']} B,平均 {(p['m1']-p['m0'])/p['pel']:.1f} B/条。不 ack,内存就一直涨。", pel=pel([f'{p["pel"]} 条 PEL', f'+{(p["m1"]-p["m0"])/p["pel"]:.1f} B/条']), kv=KV([['读之前', f"{p['m0']} B"], ['读完(PEL 10 万)', f"{p['m1']} B"]], ['读完(PEL 10 万)'])),
]
A = dict(
    n=42, series='redis', tags='Redis,Stream,PEL,真实验证,动画演示',
    desc=f'在本机 Redis 上验证 Stream 的 Pending Entries List:消息投递就进 PEL(记录消费者、idle、投递次数),XPENDING 汇总与明细的格式,重读历史会让投递次数 +1,NOACK 不进 PEL,PEL 只存 ID 不存内容(XDEL 后仍在),10 万条不 ack 会让内存增加约 {(p["m1"]-p["m0"])/p["pel"]:.0f} 字节/条。',
    lead='消费组读走一条消息,并不意味着它已经处理完了。Redis 会把这条消息记进组里的 Pending Entries List(PEL),等消费者显式 XACK 才移除。PEL 是 Stream 「至少投递一次」语义的核心。这篇量一量它里面到底存了什么、怎么看、什么会让它变大。',
    facts=[('4 项', 'PEL 每条记录:ID、消费者、上次投递后的 idle 毫秒、投递次数'), ('1 → 2', '用 XREADGROUP … 0 重读自己的历史一次,投递次数 +1'), (f'{(p["m1"]-p["m0"])/p["pel"]:.1f} B/条', '10 万条不 ack 时 PEL 增加的内存')],
    body=[
        sec('读了不 ack:消息进 PEL', '', term('', blk('r42', 1)), '<p><code>XPENDING s g</code> 不带范围时返回汇总:PEL 总条数、最小和最大 ID、每个消费者各有几条(a 5 条、b 3 条)。</p>'),
        sec('XPENDING 明细', '', term('', blk('r42', 2)), '<p>带范围参数时,每条返回 <code>[ID, 消费者, idle 毫秒, 投递次数]</code>。等了 1.2 秒之后,idle 都在 1202 毫秒上下。idle 一直涨,但 Redis 不会自动重新投递——这是留给消费者(或监控)处理的信号。</p>'),
        sec('重读历史:XREADGROUP … 0', '', term('', blk('r42', 3)), '<p>用 ID <code>0</code>(而不是 <code>&gt;</code>)读,返回的是「分配给这个消费者、还没 ack 的历史消息」。观察 b 的三条:重读之后 idle 变成 1 ms、<b>投递次数从 1 变成 2</b>。所以「投递次数」不只是被别人认领时增加,自己重读也会加。</p>', term('', blk('r42', 4)), '<p><code>XPENDING</code> 可以加 <code>IDLE</code> 过滤,只看空闲超过某个毫秒数的条目,用来找「卡住」的消息。</p>'),
        sec('NOACK:不进 PEL', '', term('', blk('r42', 5)), '<p>g2 组读了 4 条,<code>NOACK</code> 让它们不进 PEL,XPENDING 显示 0。没有 PEL 就没有重投机制:消费者崩溃就丢了这几条。</p>'),
        sec('PEL 只存 ID', '', term('', blk('r42', 6)), '<p>把 1-0 XDEL 之后,PEL 里的 1-0 还在(idle 继续涨);用 <code>XREADGROUP … 0</code> 重读时,1-0 的内容是 <code>(nil)</code>——ID 还在 PEL,消息已经不在流里。消费者得处理这种「有 ID 没内容」的情形。</p>'),
        sec('代价:PEL 的内存', '10 万条消息,读了不 ack', term('', blk('r42', 7)), f'<p>10 万条消息读走不 ack:MEMORY USAGE 从 {p["m0"]} B 涨到 {p["m1"]} B,PEL 增加约 {(p["m1"]-p["m0"])/p["pel"]:.1f} 字节/条。第 43 篇会看到 ack 之后这部分内存会还回去。</p>'),
        sec('分步演示:一条消息在 PEL 里的一生', '', demo('Pending Entries List', [('pel', 'term', 'PEL 里的记录 [ID 消费者 idle 投递次数]'), ('kv', 'kv', '观察')], steps, '本步变化的记录')),
    ],
    refs=[ENV_R, '没有验证:PEL 在复制与 RDB/AOF 持久化中的形态、消费者数量很多时 XPENDING 的耗时、不同 value 大小对 PEL 每条内存的影响(这里的值只有十几个字节)'],
)
