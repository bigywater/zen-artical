import json
from lib import *
R = J('r43')
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("组 g 里 a 读走了 1-0 … 6-0,PEL 里 6 条。流里也是这 6 条。", pel=cells(['1', '2', '3', '4', '5', '6']), stream=cells(['1', '2', '3', '4', '5', '6']), kv=KV([['PEL', '6'], ['XLEN', '6']], ['PEL'])),
    step("XACK s g 1-0 2-0 返回 2:这 2 条从 PEL 里移除。", pel=cells(['—', '—', '3', '4', '5', '6'], done=[0, 1]), stream=cells(['1', '2', '3', '4', '5', '6']), kv=KV([['XACK 返回', '2'], ['PEL', '4']], ['XACK 返回'])),
    step("再 ack 一次 1-0 返回 0;ack 一个不在 PEL 的 99-0 也返回 0——返回值只数「这次真的从 PEL 移除了几条」。XACK 3-0 3-0 4-0 重复的 ID 只算一次,返回 2。", pel=cells(['—', '—', '—', '—', '5', '6'], done=[0, 1, 2, 3]), stream=cells(['1', '2', '3', '4', '5', '6']), kv=KV([['重复 ack', '0'], ['不存在的 ID', '0'], ['3-0 3-0 4-0', '2']], ['3-0 3-0 4-0'])),
    step("XACK 不删除消息:XLEN 还是 6,XRANGE 还能读到 1-0。ack 只是「消费者说处理完了」,消息占的内存留在流里,要靠 XDEL / XTRIM 回收(第 46 篇)。", pel=cells(['—', '—', '—', '—', '5', '6'], done=[0, 1, 2, 3]), stream=cells(['1', '2', '3', '4', '5', '6'], mark=[0, 1, 2, 3]), kv=KV([['XLEN', '6'], ['XRANGE 1-0', '仍能读到']], ['XLEN'])),
    step("PEL 按组维护:组 g2 里 1-0 还在 pending;在 g 里 ack 1-0 返回 0,在 g2 里 ack 才返回 1。XACK 的参数是 key、组、ID,没有消费者名。", pel=cells(['g2:1', 'g2:2'], cur=[0]), stream=cells(['1', '2', '3', '4', '5', '6']), kv=KV([['XACK s g 1-0', '0'], ['XACK s g2 1-0', '1']], ['XACK s g2 1-0'])),
    step("8.x 新增 XACKDEL:ack 并删除消息。三种引用策略——ACKED:只有所有组都 ack 了才删(返回 2 = 已 ack 但没删);KEEPREF:删消息,别的组 PEL 里的引用保留;DELREF:删消息,同时清掉别的组 PEL 里的引用。", pel=cells(['1(ACKED 未删)', '2(KEEPREF)', '3(DELREF)']), stream=cells(['1', '—', '—', '4', '5'], mark=[1, 2]), kv=KV([['ACKED', '返回 2,消息保留'], ['KEEPREF', '返回 1,h 的 PEL 仍有 2-0'], ['DELREF', '返回 1,h 的 PEL 里 3-0 也清了']], ['DELREF'])),
]
A = dict(
    n=43, series='redis', tags='Redis,Stream,XACK,真实验证,动画演示',
    desc='在本机 Redis 上验证 XACK:它只把 ID 从组的 PEL 里移除,返回真实移除的条数(重复 ack、不存在的 ID 都返回 0),不会删除流里的消息(XLEN 不变);PEL 按组维护;并实测 Redis 8.x 新增的 XACKDEL 的 ACKED / KEEPREF / DELREF 三种策略对别的组 PEL 的影响。',
    lead='XACK 是消费者对 Redis 说「这条我处理完了」。它做的事比看上去少:只是把 ID 从组的 PEL 里拿掉,并不删消息。这篇验证它的返回值语义、按组隔离的规则,以及 Redis 8.x 新增的 XACKDEL 如何把「确认」和「删除」合成一步。',
    facts=[('只动 PEL', 'XACK 之后 XLEN 不变、XRANGE 仍能读到消息'), ('返回 0', '重复 ack、ack 不存在的 ID 都返回 0,不报错'), ('3 种', 'XACKDEL 的引用策略:ACKED / KEEPREF / DELREF')],
    body=[
        sec('XACK 的返回值', '', term('', blk('r43', 1)), '<p>返回的是「这次从 PEL 里真的移除了几条」:第一次 ack 1-0、2-0 返回 2;重复 ack 1-0 返回 0;ack 一个从未投递的 99-0 也是 0;<code>3-0 3-0 4-0</code> 里重复的 3-0 只算一次,返回 2。所以返回 0 不代表出错,只代表「没有东西可移除」。</p>'),
        sec('XACK 不删消息', '', term('', blk('r43', 2)), '<p>ack 了 4 条之后,<code>XLEN</code> 仍是 6,<code>XRANGE</code> 还能读到 1-0。确认只影响 PEL;消息本身要用 <code>XDEL</code> / <code>XTRIM</code> 处理(见第 46 篇的内存实测)。</p>'),
        sec('PEL 是按组存的', '', term('', blk('r43', 3)), '<p>1-0 同时在组 g 和 g2 的 PEL 里各有一份记录:在 g 里 ack(g 里其实已 ack 过,返回 0)不影响 g2;在 g2 里 ack 才让 g2 的 PEL 少一条。<code>XACK</code> 的参数只有 key、组和 ID,<b>没有消费者名</b>——组内任何连接只要知道 ID 都能 ack,Redis 不校验是谁读的。</p>'),
        sec('ack 之后还能重读吗', '', term('', blk('r43', 4)), '<p><code>XREADGROUP … 0</code> 只返回还在 PEL 里的消息:已 ack 的 1–4 号不再出现,只剩 5-0、6-0。</p>'),
        sec('Redis 8.x 的 XACKDEL', '一次调用完成 ack + 删除', term('', blk('r43', 5)),
            '<p>两个组 g 和 h 都读了 5 条消息(t 流)。在 g 里对三个 ID 分别用三种策略:</p><ul><li><b>ACKED</b>(1-0):返回 2。结果里 XLEN 从 5 只减了 2 条,说明这条<b>没有被删</b>——因为 h 还没 ack,它只在 g 里被确认。</li><li><b>KEEPREF</b>(2-0):返回 1,消息被删,但 h 的 PEL 里仍留着 2-0。</li><li><b>DELREF</b>(3-0):返回 1,消息被删,同时 h 的 PEL 里的 3-0 也被清除(h 的 PEL 只剩 1-0、2-0、4-0、5-0)。</li></ul><p>返回值中 2 的含义(「已确认但未删除」)是我根据 XLEN 的变化推断的,官方文档的表述我没有逐字核对。</p>'),
        sec('分步演示:PEL 与流内容各自的变化', '', demo('XACK', [('pel', 'cells', 'PEL(—表示已移除)'), ('stream', 'cells', '流里的消息(—表示已删除)'), ('kv', 'kv', '观察')], steps, '本步变化的位置')),
    ],
    refs=[ENV_R, '没有验证:XACKDEL 在 Redis 8.2 之前的版本不存在;返回值 2 的官方定义;XACK 在大 PEL 下的耗时;AOF/复制里 XACK 的传播形式'],
)
