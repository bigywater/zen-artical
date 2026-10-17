import json
from lib import *
R = J('r104'); rows = {r[0]: r for r in R['rows']}; sz = R['size']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def L(k): return [f'RESP2  {rows[k][1]}', f'RESP3  {rows[k][2]}']
steps = [
    step("默认连接是 RESP2。发送 HELLO 3 让这条连接切到 RESP3:服务器回复一个 map(%7 开头:server、version、proto、id、mode、role、modules 共 7 项),proto 是 3。同一个连接里发 HELLO 2 可以切回去。", t=tm(['> HELLO 3', '%7 ⏎ $6 ⏎ server ⏎ $5 ⏎ redis ⏎ … $5 ⏎ proto ⏎ :3 ⏎ …'], cur=[1]), kv=KV([['切换', 'HELLO 2 / HELLO 3(连接级)']], ['切换'])),
    step("HGETALL h:RESP2 返回一个平铺的数组(*4:f1 v1 f2 v2),RESP3 返回一个 map(%2,键值成对);字节内容里元素的编码完全一样,只有头部前缀不同。", t=tm(L('HGETALL h'), mark=[1]), kv=KV([['HGETALL', '*4 → %2']], ['HGETALL'])),
    step("SMEMBERS s:RESP2 用数组(*2),RESP3 用集合类型(~2)——客户端能知道这是集合而不是列表。", t=tm(L('SMEMBERS s'), mark=[1]), kv=KV([['SMEMBERS', '*2 → ~2']], ['SMEMBERS'])),
    step("ZSCORE z m:RESP2 把分数当作字符串(批量字符串 $3 ⏎ 1.5);RESP3 有专门的浮点类型(,1.5)。GET 一个不存在的 key:RESP2 是 $-1(空批量字符串),RESP3 是 _(null 类型)。", t=tm(L('ZSCORE z m') + L('GET nosuch'), mark=[1, 3]), kv=KV([['double / null', ', 与 _']], ['double / null'])),
    step("ZRANGE … WITHSCORES:RESP2 平铺成 [m, \"1.5\"],RESP3 变成「数组的数组」[[m, 1.5]] 且分数是 double(*1 ⏎ *2 ⏎ $1 ⏎ m ⏎ ,1.5)。客户端得到更结构化的数据,不必再自己两两配对。", t=tm(L('ZRANGE z 0 -1 WITHSCORES'), mark=[1]), kv=KV([['WITHSCORES', '平铺 → 嵌套']], ['WITHSCORES'])),
    step(f"字节数没变:100 个字段的 HGETALL,RESP2 {sz[0]} 字节,RESP3 {sz[1]} 字节——头部 *200 与 %100 一样长。RESP3 改的是类型信息,不是大小。INFO 在 RESP3 下用 verbatim string(= 前缀,内容以 txt: 标记格式)。", t=tm([f'RESP2 HGETALL(100 字段): {sz[0]} 字节', f'RESP3 HGETALL(100 字段): {sz[1]} 字节', 'INFO(RESP3):' + R['info3']]), kv=KV([['大小', f'{sz[0]} vs {sz[1]} 字节']], ['大小'])),
    step("RESP3 还有服务器主动推送(Push,> 前缀)。开启 CLIENT TRACKING 后,这个连接读过的 key 被别人改动,不等任何命令就直接收到 >2 ⏎ $10 ⏎ invalidate ⏎ *1 ⏎ $3 ⏎ str——失效通知和普通回复走同一条连接,客户端要能区分。", t=tm(['> CLIENT TRACKING on', '> GET str', '(另一连接 SET str changed)', '>2 ⏎ $10 ⏎ invalidate ⏎ *1 ⏎ $3 ⏎ str'], mark=[3]), kv=KV([['Push', '> 前缀:invalidate']], ['Push'])),
]
A = dict(
    n=104, series='redis', tags='Redis,RESP3,协议,真实验证,动画演示',
    desc=f'用原始 socket 对比 RESP2 与 RESP3:HGETALL 从 *4 数组变成 %2 map、SMEMBERS 变成 ~ 集合、ZSCORE 变成 , 浮点、空回复从 $-1 变成 _;WITHSCORES 变成嵌套数组;100 字段 HGETALL 都是 {sz[0]} 字节(类型信息变、大小不变);CLIENT TRACKING 时服务器主动推送 > 前缀的 invalidate 消息;HELLO 2/3 可在同一连接上切换。',
    lead='RESP3 不是「更快的协议」,而是「有类型的协议」:客户端能直接知道一个回复是 map、集合还是浮点数,而不必靠命令名去猜。这篇用原始 socket 把同一条命令在 RESP2 与 RESP3 下的字节逐个摆出来,并看它新增的服务器推送。',
    facts=[('HELLO 3', '同一条连接上切到 RESP3;HELLO 2 可以切回'), (f'{sz[0]} = {sz[1]} 字节', '100 个字段的 HGETALL 在两种协议下的大小——RESP3 改的是类型,不是体积'), ('> 推送', 'CLIENT TRACKING 下,服务器主动发出的 invalidate 消息')],
    body=[
        sec('同样的命令,不同的字节', '', term('', blk('r104', 1)), '<p><code>HELLO 3</code> 之后,map(<code>%</code>)、set(<code>~</code>)、double(<code>,</code>)、null(<code>_</code>)这些类型直接出现在回复里。RESP2 里没有这些类型,一律用数组或批量字符串表示,客户端只能按命令名再去解释(比如「HGETALL 的数组是键值成对」)。</p>'),
        sec('类型前缀与 INFO', '', term('', blk('r104', 2)), '<p>RESP3 的 <code>INFO</code> 用 verbatim string(<code>=</code>),后面带 <code>txt:</code> 格式标记。</p>'),
        sec('体积没有变', '', term('', blk('r104', 3)), f'<p>100 个字段的 HGETALL:RESP2 {sz[0]} 字节、RESP3 {sz[1]} 字节。头部 <code>*200</code> 与 <code>%100</code> 一样长,元素本身的编码相同。所以换 RESP3 不会省带宽,收益在客户端更容易解析、不再需要「命令 → 类型」的映射表。</p>'),
        sec('Push:服务器主动推送', '', term('', blk('r104', 4)), '<p>RESP3 的 Push 类型(<code>&gt;</code>)让服务器在没有对应请求时也能发消息。最常见的用途是客户端缓存(CLIENT TRACKING):读过的 key 被改动时,服务器通过同一条连接推送 <code>invalidate</code>。RESP2 下要做到这一点需要额外开一条连接订阅。</p>'),
        sec('切回 RESP2', '', term('', blk('r104', 5)), '<p>同一个连接里 <code>HELLO 2</code> 切回 RESP2,之后 HGETALL 又是平铺数组。</p>'),
        sec('分步演示:RESP2 与 RESP3', '', demo('RESP2 与 RESP3', [('t', 'term', '原始字节'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。原始 socket 收发;「⏎」表示 \\r\\n', '没有验证:客户端库对 RESP3 的实际支持与性能差异、RESP3 下其它新类型(boolean #、big number ( 、attribute |)的出现场景、CLIENT TRACKING 的广播模式与 NOLOOP 选项'],
)
