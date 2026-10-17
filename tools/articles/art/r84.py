import json
from lib import *
R = J('r84'); a, b, c, d = R['a'], R['b'], R['c'], R['d']; af = R['a_first']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step(f"最坏的情形:同时 kill 掉一个主库和它的唯一从库(该分片的数据副本全没了)。默认 cluster-require-full-coverage yes:幸存节点在 {af['fail']:.1f} s 后 cluster_state 变成 fail——16384 个槽有 5461 个没人负责。", n=fl([['分片 X', '主 + 从都死了'], ['其它两个分片', '幸存,但集群 fail']], mark=[0], cur=[1]), b=bars([['cluster_state → fail', af['fail'] * 1000, f"{af['fail']:.1f} s"]], 6000, mark=[0]), kv=KV([['cluster_state', f"ok → fail({af['fail']:.1f} s)"]], ['cluster_state'])),
    step("此时连幸存分片的读写也被拒:向幸存主库写它自己负责的槽里的 key、读 key,都报 CLUSTERDOWN The cluster is down。一个分片没了,整个集群不可用——这是默认配置的取舍(宁可全停,不要部分可用)。", n=fl([['幸存分片', 'CLUSTERDOWN(读写都拒)'], ['丢失分片', 'CLUSTERDOWN']], mark=[0, 1]), kv=KV([['读 / 写幸存分片', 'CLUSTERDOWN'], ['原因', '有槽没人负责']], ['读 / 写幸存分片'])),
    step(f"恢复办法一:数据在磁盘上时,只重启被杀的主库(nodes.conf、AOF 都在)。{a['ok']:.1f} s 后整个集群 cluster_state 回到 ok,30000 个 key 校验 {a['miss']} 个丢失(AOF 用 appendfsync always)。之后再起从库,它从主库同步。", n=fl([['主库(AOF 恢复)', '加载 AOF → 恢复槽位'], ['集群', 'cluster_state ok']], done=[0, 1]), b=bars([['重启到 ok', a['ok'] * 1000, f"{a['ok']:.1f} s"]], 6000, done=[0]), kv=KV([['丢失的 key', f"{a['miss']} / 30000"], ['恢复用时', f"{a['ok']:.1f} s"]], ['丢失的 key'])),
    step(f"同样的事故,但没有任何持久化:重启主库后 {b['ok']:.1f} s cluster_state 就回到 ok(nodes.conf 还在,槽位归属恢复)——集群看起来「恢复正常」,但读 30000 个 key,{b['miss']} 个读不到({b['miss']/300:.1f}%,恰好是那一片)。空的主库带着旧槽位重新上线,没有任何告警。", n=fl([['主库(无持久化)', '空数据 + 旧槽位'], ['集群', 'cluster_state ok']], mark=[0], done=[1]), b=bars([['读不到的 key', b['miss'], f"{b['miss']}(33.3%)"]], 30000, mark=[0]), kv=KV([['读不到', f"{b['miss']} / 30000"], ['cluster_state', 'ok(有欺骗性)']], ['读不到'])),
    step(f"恢复办法二(不想全停):cluster-require-full-coverage no。同样丢一个分片,幸存节点 cluster_state 仍是 {c['state']},cluster_slots_ok / fail = {c['ok']} / {c['fail']};写幸存分片的 key 成功;请求丢失分片里的 key,幸存节点回 MOVED 指向死掉的主库(客户端连不上,超时)。", n=fl([['幸存分片', '继续读写'], ['丢失分片', '不可用(MOVED 到死节点)']], done=[0], mark=[1]), kv=KV([['cluster_state', c['state']], ['slots_ok / fail', f"{c['ok']} / {c['fail']}"]], ['slots_ok / fail'])),
    step(f"恢复办法三(放弃这片数据):redis-cli --cluster fix 提示这些槽位没人负责,在你确认后「Covering slot … with 127.0.0.1:7582」把它们随机分给存活的主库。cluster_state 变回 {d['state']},16384 个槽都有人负责——但这些槽里的数据没有了(前 6000 个 key 里 {d['miss']} 个读不到)。", n=fl([['fix', '把 5461 个槽分给存活的主库'], ['数据', '永久丢失']], done=[0], mark=[1]), b=bars([['前 6000 个 key 读不到', d['miss'], str(d['miss'])]], 6000, mark=[0]), kv=KV([['槽位', '全部有主'], ['数据', '丢失']], ['数据'])),
]
A = dict(
    n=84, series='redis', tags='Redis,Cluster,故障恢复,真实验证,动画演示',
    desc=f'同时杀掉一个分片的主库和从库:默认配置下 {af["fail"]:.1f} s 后 cluster_state = fail,连幸存分片也拒绝读写;有 AOF 时重启主库 {a["ok"]:.1f} s 恢复、{a["miss"]}/30000 个 key 丢失;没有持久化时集群同样 {b["ok"]:.1f} s「恢复」,却有 {b["miss"]} 个 key(33.3%)读不到;require-full-coverage no 时幸存分片继续服务;--cluster fix 可以把槽分给存活节点,代价是数据永久丢失。',
    lead='一个分片的主库和从库同时挂了怎么办?这比「主库挂了从库接手」严重得多:那一片数据在集群里已经没有副本了。这篇复现这个最坏情形,看三种结局:数据在磁盘上→重启找回;没有持久化→集群「恢复正常」却悄悄丢了三分之一的数据;放弃数据→用 fix 强行让集群可用。',
    facts=[(f'{af["fail"]:.1f} s', '同时杀掉一个分片的主从后,cluster_state 变 fail(默认 require-full-coverage yes,连幸存分片也拒绝读写)'), (f'{a["miss"]} vs {b["miss"]}', '重启主库后 30000 个 key 里读不到的个数:有 AOF vs 没有持久化'), ('cluster_state 会说谎', '没有持久化时重启主库,集群 2 秒就变 ok,但那一片数据已经没了')],
    body=[
        sec('事故一:主从一起挂,默认配置', '', term('', blk('r84', 1)), f'<p>杀掉分片 X 的主库和从库后,幸存节点在 {af["fail"]:.1f} s 后把 <code>cluster_state</code> 置为 <code>fail</code>。之后无论读写,哪怕是完全属于幸存分片的 key,都会得到 <code>CLUSTERDOWN The cluster is down</code>:默认 <code>cluster-require-full-coverage yes</code> 要求 16384 个槽都有主库,少一个就全体拒绝服务。</p><p>恢复:只重启被杀的主库(<code>nodes.conf</code> 在,AOF 在):{a["ok"]:.1f} s 后整个集群回到 ok,30000 个 key 校验丢失 {a["miss"]} 个(这里 AOF 用了 <code>appendfsync always</code>;默认 <code>everysec</code> 下崩溃时可能丢最近约 1 秒——这一点本文没有实测)。</p>'),
        sec('事故二:同样的事故,没有持久化', '', term('', blk('r84', 2)), f'<p>没有 AOF、没有 RDB 时,重启的主库带着旧的 <code>nodes.conf</code>(槽位归属)上线,但数据是空的。集群 {b["ok"]:.1f} s 就回到 ok,看起来完全正常——但读 30000 个 key,{b["miss"]} 个读不到(33.3%,恰好是那个分片)。<b>没有任何告警:cluster_state 是 ok,只是那一片数据没有了。</b>这也是集群里「主库必须有持久化,或者至少有从库」的原因:从库是第二份副本,持久化是第三份。</p>'),
        sec('如果不想全体停摆', '', term('', blk('r84', 3)), f'<p><code>cluster-require-full-coverage no</code> 让集群在有槽没人负责时仍然工作:幸存节点 <code>cluster_state = {c["state"]}</code>,<code>cluster_slots_ok / cluster_slots_fail</code> = {c["ok"]} / {c["fail"]},写幸存分片的 key 成功。请求丢失分片的 key,幸存节点回 <code>MOVED</code> 指向那个已经死掉的主库——客户端会连不上、超时。这是「部分可用」与「全体可用」的取舍。</p>'),
        sec('放弃这片数据:redis-cli --cluster fix', '', term('', blk('r84', 4)), f'<p>如果那个分片确实回不来了,又想让集群恢复完整,<code>redis-cli --cluster fix</code> 可以把没人负责的槽分给存活的主库。它对「有不可达主库」的情形要求额外的 <code>--cluster-fix-with-unreachable-masters</code> 选项,并且提示这可能导致数据丢失;确认后逐个槽位 <code>Covering slot … with 127.0.0.1:7582</code>。结果:<code>cluster_state</code> 回到 {d["state"]},<code>cluster_slots_ok = 16384</code>,但那片数据永久丢了(前 6000 个 key 里 {d["miss"]} 个读不到)。</p>'),
        sec('分步演示:三种结局', '', demo('Redis Cluster 故障恢复', [('n', 'flow', '节点与状态'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 主 3 从;每个分片只有 1 个从库;kill -9 同时杀主从;30000 个 key 每个 key 校验一次(fix 之后只校验前 6000 个,因为丢失分片的请求会很慢)', '没有验证:AOF everysec 下崩溃的实际丢失量、断电场景、只有从库存活时的手工 CLUSTER FAILOVER TAKEOVER、CLUSTER SETSLOT … NODE / ADDSLOTS 手工重新分配、Redis 8 之前版本 fix 的行为'],
)
