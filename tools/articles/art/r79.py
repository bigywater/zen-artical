import json
from lib import *
R = J('r79'); ph = R['ph']; dbs = R['dbs']
b, d, a = ph['before'], ph['during'], ph['after']
mv = R['moves']; mvtxt = '、'.join(f"{m[1].split(':')[1]} → {m[2].split(':')[1]} 搬 {m[0]} 个槽" for m in mv); mvsum = ' + '.join(m[0] for m in mv)
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("起点:3 主 3 从,共写入 30 万个 key,每个主库约 10 万个,各管 5461/5462 个槽。", n=fl([['主 A', '≈10 万 key,5461 槽'], ['主 B', '≈10 万 key,5462 槽'], ['主 C', '≈10 万 key,5461 槽']], done=[0, 1, 2]), kv=KV([['DBSIZE', '99963 / 100060 / 99977']], ['DBSIZE'])),
    step("扩容:新增一个空主库 D(redis-cli --cluster add-node)。它加入集群,但槽位数是 0,不承担任何数据。", n=fl([['A', '5461'], ['B', '5462'], ['C', '5461'], ['D(新)', '0 槽']], mark=[3]), kv=KV([['新节点槽位', '0']], ['新节点槽位'])),
    step(f"开始 redis-cli --cluster rebalance --cluster-use-empty-masters,同时后台流量不停(一个客户端 GET/SET 随机 key)。输出:{mvtxt},共 {R['tot']} 个槽,全部搬给新节点,让 4 个主库各 4096 个槽。", n=fl([['A', '→ D 1365'], ['B', '→ D 1366'], ['C', '→ D 1365'], ['D', '+4096']], cur=[0, 1, 2], done=[3]), kv=KV([['搬走的槽位', f"{R['tot']}"]], ['搬走的槽位'])),
    step(f"耗时 {R['sec']:.1f} s,搬完后各主库槽位数 4096 / 4096 / 4096 / 4096。", n=fl([['A', '4096'], ['B', '4096'], ['C', '4096'], ['D', '4096']], done=[0, 1, 2, 3]), b=bars([['耗时(s)', R['sec'], f"{R['sec']:.1f} s"]], 5, done=[0]), kv=KV([['槽位分布', '4 × 4096'], ['耗时', f"{R['sec']:.1f} s"]], ['耗时'])),
    step(f"搬迁期间流量:搬迁前 {b['rate']:.0f} ops/s、p99 {b['p99']:.0f} µs;搬迁中 {d['rate']:.0f} ops/s、p99 {d['p99']:.0f} µs、最大 {d['mx']/1000:.1f} ms;搬迁后 {a['rate']:.0f} ops/s、p99 {a['p99']:.0f} µs。吞吐几乎不变,只有最大延迟出现毫秒级的尖峰。", b=bars([['搬迁前 ops/s', b['rate'], f"{b['rate']:.0f}"], ['搬迁中 ops/s', d['rate'], f"{d['rate']:.0f}"], ['搬迁后 ops/s', a['rate'], f"{a['rate']:.0f}"]], max(b['rate'], d['rate'], a['rate']), mark=[1], done=[0, 2]), kv=KV([['吞吐', f"{b['rate']:.0f} → {d['rate']:.0f} → {a['rate']:.0f} ops/s"]], ['吞吐'])),
    step(f"客户端遇到 {R['moved']} 次 MOVED(每个搬走的槽被指路一次,与 4096 接近)、{R['ask']} 次 ASK,{R['errs']} 次错误,{R['bad']} 次读到错误的值。搬完后我把 30 万个 key 全部回读校验:{R['verify_bad']} 个错误。新分布:每个主库约 7.5 万个 key。", b=bars([['MOVED', R['moved'], str(R['moved'])], ['ASK', max(R['ask'], 0.5), str(R['ask'])], ['错误', 0.5, str(R['errs'])]], 4200, mark=[0]), kv=KV([['校验', f"30 万 key 中错误 {R['verify_bad']} 个"], ['DBSIZE', ' / '.join(str(v) for k, v in sorted(dbs.items()))]], ['校验'])),
]
A = dict(
    n=79, series='redis', tags='Redis,Cluster,扩容,Resharding,真实验证,动画演示',
    desc=f'在有 30 万个 key 和持续流量的 3 主集群上加一个空主库并 rebalance:搬 {R["tot"]} 个槽用时 {R["sec"]:.1f} s,搬迁期间吞吐 {b["rate"]:.0f} → {d["rate"]:.0f} ops/s(几乎不变)、p99 {d["p99"]:.0f} µs、最大延迟 {d["mx"]/1000:.1f} ms;客户端 {R["moved"]} 次 MOVED、0 次错误;搬完后 30 万个 key 校验 {R["verify_bad"]} 个错误。',
    lead='给集群扩容,最让人担心的是「搬数据的时候业务会不会抖、会不会丢」。这篇在真实集群上做:先写 30 万个 key,后台一直有读写流量,然后加一个空主库,让 redis-cli 自动把槽位均分给 4 个主库,同时测吞吐、延迟、错误,最后逐个校验数据。',
    facts=[(f'{R["tot"]} 个槽 / {R["sec"]:.1f} s', '把 4 个主库的槽位均分(每个 4096)所搬的槽数与耗时'), (f'{b["rate"]:.0f} → {d["rate"]:.0f} ops/s', f'搬迁前 → 搬迁中的吞吐(p99 {b["p99"]:.0f} → {d["p99"]:.0f} µs)'), (f'{R["errs"]} 错误 / {R["verify_bad"]} 坏值', '搬迁期间的客户端错误数;搬完后 30 万个 key 的校验错误')],
    body=[
        sec('准备:数据与新节点', '', term('', blk('r79', 1)), '', term('', blk('r79', 2)), '<p>先用管道把 30 万个 key 写进 3 个主库(约各 10 万)。再启动一个空的集群节点(7496),用 <code>redis-cli --cluster add-node</code> 加入:它成为集群成员,但是槽位数是 0,不承担任何数据——只是「加入」并不会自动搬走任何数据。</p>'),
        sec('rebalance:把槽位均分给 4 个主库', '后台客户端一直在随机 GET/SET', term('', blk('r79', 3)),
            f'<p><code>redis-cli --cluster rebalance --cluster-use-empty-masters</code> 计算出每个主库应有 4096 个槽,于是从三个老主库各搬一部分({mvsum})到新主库,共 {R["tot"]} 个槽,耗时 {R["sec"]:.1f} s。每个槽的搬迁走的是第 80 篇的 <code>IMPORTING / MIGRATING / MIGRATE</code> 流程。这里每个槽只有几十个 key(总共 30 万个 key ÷ 16384 个槽 ≈ 18),搬一个槽很快;<b>key 更大、更多时耗时会大得多</b>。</p><p>搬迁期间的客户端吞吐是 {b["rate"]:.0f} → {d["rate"]:.0f} → {a["rate"]:.0f} ops/s(前 / 中 / 后),p50 都是约 {b["p50"]:.0f} µs,p99 {b["p99"]:.0f} → {d["p99"]:.0f} µs,搬迁中的最大延迟是 {d["mx"]/1000:.1f} ms(搬迁前 {b["mx"]/1000:.1f} ms)。客户端遇到 {R["moved"]} 次 <code>MOVED</code>——每个被搬走的槽被指路一次——和搬走的 {R["tot"]} 个槽接近,而 <code>ASK</code> 是 {R["ask"]} 次:每个槽从「开始迁移」到「迁移完成」只有很短的一瞬间,随机访问几乎撞不上它(第 80 篇会用确定性的方式复现 ASK)。</p>'),
        sec('搬完之后的校验', '', term('', blk('r79', 4)), f'<p>把 30 万个 key 全部按新槽位表回读:{R["verify_bad"]} 个错误。搬迁期间客户端 {R["errs"]} 次错误、{R["bad"]} 次读到错误值。新的 DBSIZE 分布是每个主库约 7.5 万个 key(和槽位数成比例,因为 key 在槽里几乎均匀)。</p>'),
        sec('这个实验的边界', '', '<p>数据量小(每个 key 很小,总共 30 万个)、流量是单个同步客户端、没有大 key、也没有开持久化。真实业务里搬迁的耗时主要取决于槽里的数据量,最大延迟主要取决于单个 key 的大小(大 key 的 <code>MIGRATE</code> 会阻塞源节点,见第 81、82 篇)。</p>'),
        sec('分步演示:一次在线扩容', '', demo('Redis Cluster Resharding', [('n', 'flow', '主库与槽位'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 主 3 从加一个无从库的新主库;流量线程是单个同步客户端;rebalance 使用 redis-cli 默认的 pipeline 与超时参数', '没有验证:更大数据量、大 key、多客户端并发下的搬迁表现;新增主库同时新增从库的流程;缩容(把槽位搬出再 del-node);rebalance 的 weight 参数;搬迁失败后的恢复(第 80 篇讨论手工步骤)'],
)
