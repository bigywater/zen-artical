import json
from lib import *
R = J('r71'); a, b, c, d, e, rs = R['a'], R['b'], R['c'], R['d'], R['e'], R['reshard']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("三个主库的集群,三种客户端策略,同样的 30000 次 GET。第一种:不知道槽位表,固定连一个节点,遇到 MOVED 就跟过去,但不记住。", b=bars([['无表、不学习', 1, ''], ['无表、每次学一个槽', 1, ''], ['启动拉全表', 1, '']], 1), kv=KV([['变量', '客户端策略']], [])),
    step(f"无表、不学习:{a['moved']} 次 MOVED(占 {a['moved']/a['req']*100:.0f}%,恰好接近 2/3——请求落在另外两个主库上的概率),平均每个请求 {a['rt']:.2f} 次往返,平均耗时 {a['us']:.1f} µs。", b=bars([['MOVED 次数', a['moved'], str(a['moved'])]], a['req'], mark=[0]), kv=KV([['MOVED', f"{a['moved']}/{a['req']}"], ['往返/请求', f"{a['rt']:.2f}"]], ['MOVED'])),
    step(f"无表、每次 MOVED 学一个槽:{b['moved']} 次 MOVED——每个槽只需要被指路一次,30000 个 key 落在很多不同的槽上,所以还是多次;平均耗时 {b['us']:.1f} µs。", b=bars([['无表、不学习', a['moved'], str(a['moved'])], ['无表、每次学一个槽', b['moved'], str(b['moved'])]], a['moved'], mark=[0], done=[1]), kv=KV([['MOVED', f"{b['moved']}/{b['req']}"]], ['MOVED'])),
    step(f"启动时 CLUSTER SLOTS 拉全表:MOVED = {c['moved']},每个请求恰好 1 次往返,平均耗时 {c['us']:.1f} µs——比「不学习」的 {a['us']:.1f} µs 快 {(1-c['us']/a['us'])*100:.0f}%(本机回环,跨机器时每次多的往返更贵)。", b=bars([['无表、不学习', a['us'], f"{a['us']:.1f} µs"], ['无表、学一个槽', b['us'], f"{b['us']:.1f} µs"], ['拉全表', c['us'], f"{c['us']:.1f} µs"]], a['us'], mark=[0], done=[2]), kv=KV([['平均耗时', f"{a['us']:.1f} → {b['us']:.1f} → {c['us']:.1f} µs"]], ['平均耗时'])),
    step(f"在线迁移:redis-cli --cluster reshard 把槽 0–999 从第一个主库搬到第二个主库,耗时 {rs['sec']:.1f} s(每个槽里只有几个 key),迁移后 1000 个槽都归第二个主库。两个客户端手里还是迁移前的槽位表。", b=bars([['reshard 耗时(s)', rs['sec'], f"{rs['sec']:.1f} s"]], 2, done=[0]), kv=KV([['迁移的槽', f"{rs['moved']} 个"]], ['迁移的槽'])),
    step(f"旧表 + 每次 MOVED 只更新那一个槽:读 20000 次落在这些槽里的 key,{d['moved']} 次 MOVED(2000 个 key 覆盖了 {R['distinct']} 个不同的槽,每个槽被纠正一次)。", b=bars([['只更新一个槽', d['moved'], str(d['moved'])], ['整表重新拉取', e['moved'], str(e['moved'])]], d['moved'], mark=[0], done=[1]), kv=KV([['MOVED', f"{d['moved']}"]], ['MOVED'])),
    step(f"旧表 + 第一次 MOVED 就重新拉全表:只有 {e['moved']} 次 MOVED,之后所有槽都对了。这也是大多数成熟客户端的做法:收到 MOVED 就刷新整张槽位表。", b=bars([['只更新一个槽', d['moved'], str(d['moved'])], ['整表重新拉取', max(e['moved'], 0.5), str(e['moved'])]], d['moved'], mark=[0], done=[1]), kv=KV([['MOVED', f"{e['moved']}"]], ['MOVED'])),
]
A = dict(
    n=71, series='redis', tags='Redis,Cluster,客户端,重定向,真实验证,动画演示',
    desc=f'在 3 主集群上对比三种客户端重定向策略(各 30000 次 GET):不缓存槽位表 {a["moved"]} 次 MOVED、平均 {a["us"]:.1f} µs;每次学一个槽 {b["moved"]} 次;启动时拉全表 0 次、{c["us"]:.1f} µs;在线迁移 1000 个槽后,旧表客户端「只更新一个槽」触发 {d["moved"]} 次 MOVED,「整表刷新」只要 {e["moved"]} 次。',
    lead='集群客户端要么自己路由,要么每次都被服务器「指路」。指路要多花一次往返。这篇把三种常见策略在同一个集群上对比:完全不缓存槽位表、只在收到 MOVED 时记一个槽、启动时拉整张槽位表;然后在线迁移 1000 个槽,看手里是旧表的客户端要被指多少次路,才能恢复。',
    facts=[(f'{a["moved"]/a["req"]*100:.0f}%', f'无槽位表的客户端 MOVED 占比(随机 key,3 个主库,期望 2/3)'), (f'{a["us"]:.1f} → {c["us"]:.1f} µs', '平均每个 GET 的耗时:不缓存 → 拉全表(本机回环)'), (f'{d["moved"]} vs {e["moved"]}', '迁移 1000 个槽后:只更新一个槽 vs 整表刷新 的 MOVED 次数')],
    body=[
        sec('三种策略,稳定的集群', '30000 次 GET,key 随机', term('', blk('r71', 1)), f'<p>「无表、不学习」的客户端固定连第一个节点,遇到 <code>MOVED</code> 就换节点重发,但下次仍从原点出发:{a["moved"]} 次 MOVED,约 2/3(3 个主库里只有 1/3 的 key 恰好在这个节点上),每个请求平均 {a["rt"]:.2f} 次往返。「每次 MOVED 学一个槽」把指过的路记下来,MOVED 降到 {b["moved"]} 次,但 30000 个 key 散在很多槽上,仍然要被指很多次。「启动时拉全表」用 <code>CLUSTER SLOTS</code> 一次拿到整张槽位表,之后 MOVED 为 0,每个请求恰好一次往返,平均耗时最低({c["us"]:.1f} µs)。本机回环上,每多一次往返约多 {(a["us"]-c["us"])/(a["rt"]-1):.0f} µs;跨机器网络时代价更大。</p>'),
        sec('在线迁移 1000 个槽', '', term('', blk('r71', 2)), f'<p><code>redis-cli --cluster reshard --cluster-from A --cluster-to B --cluster-slots 1000</code> 用 {rs["sec"]:.1f} s 把槽 0–999 从第一个主库搬到第二个,期间集群一直可用(这里每个槽里的 key 很少)。迁移结束后有两个客户端手里还是迁移之前拉的槽位表。</p>'),
        sec('旧槽位表怎么恢复', '各读 20000 次落在这 1000 个槽里的 key', term('', blk('r71', 3)), f'<p><b>只更新被指路的那一个槽</b>:20000 次读里有 {d["moved"]} 次 MOVED——2000 个 key 覆盖了 {R["distinct"]} 个不同的槽,每个槽被纠正一次,{d["rt"]:.2f} 次往返/请求。<b>收到第一次 MOVED 就重新拉整张表</b>:只有 {e["moved"]} 次 MOVED,之后全部命中。MOVED 说明「地图变了」,而不仅仅是「这一个槽变了」——一次迁移常常一次搬很多槽,整表刷新更划算。(代价是刷新时多一次 <code>CLUSTER SLOTS</code> 调用;槽位变化频繁时要防止「MOVED 风暴」引起的反复刷新,我没有测这个场景。)</p>'),
        sec('分步演示:三种策略与一次迁移', '', demo('Redis Cluster 客户端重定向', [('b', 'bars', 'MOVED / 耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。客户端是我手写的:三种策略各由构造参数控制;3 主 3 从,单连接同步请求,每次 GET 的耗时含一次往返', '没有验证:ASK 期间客户端的行为(第 70 篇覆盖了协议本身)、多线程客户端刷新槽位表的并发问题、真实库(如 redis-py-cluster、Lettuce、Jedis)的具体策略、跨机器网络下的耗时'],
)
