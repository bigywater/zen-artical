import json
from lib import *
R = J('r118'); cost = {c[0]: c for c in R['cost']}; kj = R['keys']; dy = R['dyn']; mt = R['match']; sq = R['seq']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("SCAN cursor [MATCH pattern] [COUNT n]:每次调用只取一小批,返回 [下一个游标, 这批 key],游标回到 0 表示一轮遍历结束。游标不是递增的序号:COUNT 10 时前几次的游标依次是 0、" + '、'.join(s[0] for s in sq[1:6]) + "……(按哈希表「二进制位倒序」的顺序推进,这一点是文档说法,我只验证了游标确实不是 10、20、30)。", t=tm([f'SCAN {s[0]} COUNT 10  → {s[1]} 个 key' for s in sq[:6]], cur=range(6)), kv=KV([['游标', '非递增,回到 0 表示结束']], ['游标'])),
    step(f"每次调用只做一点点工作:100 万个 key 的库,COUNT 10 单次 {cost[10][1]:.3f} ms、COUNT 100 {cost[100][1]:.3f} ms、COUNT 1000 {cost[1000][1]:.2f} ms、COUNT 10000 {cost[10000][1]:.1f} ms;遍历完整个库分别要 {cost[10][2]}、{cost[100][2]}、{cost[1000][2]}、{cost[10000][2]} 次调用。", b=bars([[f'COUNT {k}', cost[k][1], f'{cost[k][1]:.3f} ms'] for k in (10, 100, 1000, 10000)], cost[10000][1], done=[0, 1, 2], mark=[3]), kv=KV([['单次耗时', '随 COUNT 线性增长']], ['单次耗时'])),
    step(f"对比 KEYS *:同一个库,命令本身耗时约 {kj[0]:.0f} ms(含把 100 万个 key 传给客户端),另一个连接的 PING 被卡了 {kj[1]:.0f} ms。而 SCAN COUNT 1000 遍历期间 PING 的最大停顿只有 {cost[1000][3]:.1f} ms,COUNT 10000 时 {cost[10000][3]:.1f} ms。SCAN 把一次长阻塞拆成很多次短阻塞,让别的命令能插进来。", b=bars([['KEYS * 时 PING 停顿', kj[1], f'{kj[1]:.0f} ms'], ['SCAN COUNT 10000', cost[10000][3], f'{cost[10000][3]:.1f} ms'], ['SCAN COUNT 1000', cost[1000][3], f'{cost[1000][3]:.1f} ms']], kj[1], mark=[0], done=[1, 2]), kv=KV([['KEYS vs SCAN', f'{kj[1]:.0f} ms vs {cost[1000][3]:.1f} ms 停顿']], ['KEYS vs SCAN'])),
    step(f"遍历时库在变:开始前的 20 万个 key 边遍历边增加了 {dy['added']} 个新 key(触发字典扩容),结果:开始前的 {dy['a_seen']}/200000 个 key 全部被遍历到——这是 SCAN 的保证;新增的 key 只遍历到 {dy['b_seen']}/{dy['added']};返回的 {dy['total']} 个 key 里重复 {dy['dup']} 个(文档说 SCAN 可能返回重复,这次没有发生,不代表不会发生)。", b=bars([['开始前的 key 被遍历到', dy['a_seen'] / 1000, f"{dy['a_seen']}/200000"], ['遍历中新增的 key 被遍历到', dy['b_seen'] / 1000, f"{dy['b_seen']}/{dy['added']}"]], 400, done=[0], mark=[1]), kv=KV([['保证', '开始前就在、且未被删的 key 一定出现']], ['保证'])),
    step(f"MATCH 是在「取出一批之后」再过滤的,不是先过滤再取:50 万个 key 中只有 2 个匹配 special:*,COUNT 1000 时遍历完要 {mt['calls']} 次调用,其中 {mt['empties']} 次返回空数组,最终找到 {mt['found']} 个。所以「返回空数组」不等于遍历结束,只有游标回到 0 才是结束。", b=bars([['调用次数', mt['calls'], str(mt['calls'])], ['返回空数组的次数', mt['empties'], str(mt['empties'])], ['找到的 key', 2, '2']], mt['calls'], mark=[1]), kv=KV([['空数组', '不代表结束,看游标']], ['空数组'])),
]
A = dict(
    n=118, series='redis', tags='Redis,SCAN,真实验证,动画演示',
    desc=f'验证 SCAN 的行为:游标不是递增序号;100 万个 key 时 COUNT 10/100/1000/10000 单次 {cost[10][1]:.3f}/{cost[100][1]:.3f}/{cost[1000][1]:.2f}/{cost[10000][1]:.1f} ms,遍历期间 PING 最大停顿 {cost[1000][3]:.1f}/{cost[10000][3]:.1f} ms,而 KEYS * 让 PING 停顿 {kj[1]:.0f} ms;遍历中新增 40 万个 key,开始前的 20 万个 key 全部被遍历到;MATCH 在取出一批之后过滤,{mt["calls"]} 次调用里 {mt["empties"]} 次返回空数组。',
    lead='SCAN 为什么不会一次阻塞很久?它到底保证什么、不保证什么?这篇在 100 万个 key 的库上把它的耗时、遍历时库在变化的行为、以及 MATCH 的过滤时机都量出来。',
    facts=[(f'{cost[1000][3]:.1f} vs {kj[1]:.0f} ms', 'SCAN COUNT 1000 遍历期间 vs KEYS * 期间,另一个连接 PING 的最大停顿(100 万个 key)'), (f'{dy["a_seen"]}/200000', '遍历中大量新增 key 时,开始前就在的 key 被遍历到的个数(保证全部出现)'), (f'{mt["empties"]}/{mt["calls"]}', 'MATCH 只匹配 2 个 key 时,返回空数组的调用次数')],
    body=[
        sec('游标', '', term('', blk('r118', 1)), '<p>每次返回的游标不是「偏移量」,前几次依次是 0、720896、425984、671744……;返回的 key 数也不严格等于 COUNT(11、10、12、10……,COUNT 只是提示)。调用方唯一要做的是:把返回的游标原样传给下一次调用,直到游标是 0。</p>'),
        sec('代价:每次调用很短', '', term('', blk('r118', 2)), f'<p>单次耗时随 COUNT 线性增长;COUNT 1000 时 {cost[1000][1]:.2f} ms,期间另一个连接的 PING 最大停顿 {cost[1000][3]:.1f} ms。KEYS * 一次性遍历整个库:{kj[0]:.0f} ms(含传输),PING 被卡 {kj[1]:.0f} ms(第 119 篇专门量 KEYS 的风险)。COUNT 不宜太大:COUNT 10000 时单次 {cost[10000][1]:.1f} ms,PING 停顿已经到 {cost[10000][3]:.1f} ms。</p>'),
        sec('遍历时库在变化', '', term('', blk('r118', 3)), f'<p>SCAN 的保证是:从开始到结束一直存在的 key 一定会被返回至少一次。实测边遍历边新增 40 万个 key(库从 20 万涨到 60 万,字典会扩容),开始前的 20 万个 key 一个不少,新增的 key 只有 {dy["b_seen"]} 个被遍历到——新增的不保证出现。文档还说 SCAN 可能返回重复的 key,这次实验里重复是 {dy["dup"]} 个;所以调用方仍然要做好去重的准备。</p>'),
        sec('MATCH 的过滤时机', '', term('', blk('r118', 4)), f'<p><code>MATCH</code> 不会加速遍历:服务器先按游标取出一批,再对这一批过滤。匹配很少时,大部分调用返回空数组({mt["calls"]} 次里 {mt["empties"]} 次)。<b>判断遍历是否结束只能看游标是否为 0,不能看返回数组是否为空。</b></p>'),
        sec('分步演示:SCAN 的三件事', '', demo('SCAN 为什么不会一次阻塞', [('t', 'term', '游标'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。单实例 100 万个 key(值 v);PING 探测每 0.5 ms 一次;遍历中新增的 key 用管道写入', '没有验证:重复 key 在字典缩容/rehash 时出现的条件、SCAN 的 TYPE 参数、集群下的 SCAN(每个节点各自遍历)、SSCAN/HSCAN/ZSCAN 对小集合的一次性返回'],
)
