import json
from lib import *
R = J('r68'); per = R['per']; st = R['slotstat']; sl = R['slots']
ports = sorted(per)
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
rng = [(s, e, m) for s, e, m, r in sl]
steps = [
    step("6 个空节点(cluster-enabled yes),用 redis-cli --cluster create --cluster-replicas 1 组成 3 主 3 从。16384 个槽被均分给 3 个主库:槽 0–5460、5461–10922、10923–16383。", n=fl([[f'主 {m}', f'槽 {s}–{e}({e-s+1} 个)'] for s, e, m in rng], cur=[0, 1, 2]), kv=KV([['分配', '5461 / 5462 / 5461']], ['分配'])),
    step("CLUSTER NODES:每个主库的 epoch 各不相同(1、2、3),从库带着自己主库的 ID(replicates)。此时槽位表在每个节点上一致(check 输出 All nodes agree about slots configuration)。", n=fl([['主 A epoch 1', '槽 0–5460'], ['主 B epoch 2', '槽 5461–10922'], ['主 C epoch 3', '槽 10923–16383'], ['从 ×3', 'replicates 各自的主']], cur=[0, 1, 2], done=[3]), kv=KV([['check', 'All 16384 slots covered']], ['check'])),
    step(f"写入 10 万个 key:客户端用 CRC16 自己算槽位、直接发给对应主库,总共 0 次 MOVED。三个主库的 DBSIZE 是 {per[str(ports[0])]} / {per[str(ports[1])]} / {per[str(ports[2])]},几乎均分。", b=bars([[f'主库 {p}', per[str(p)], f'{per[str(p)]} 个 key'] for p in ports], max(per.values()), done=[0, 1, 2]), kv=KV([['MOVED 次数', '0'], ['合计', '100000']], ['MOVED 次数'])),
    step("刚建好、还没有数据流过时,从库的健康状态是 loading,CLUSTER SLOTS 里看不到它们;有数据流过后变成 online,CLUSTER SLOTS 与 CLUSTER SHARDS 才都列出「主 + 从」。", n=fl([['CLUSTER SLOTS', '每段槽 → 主 + 从(online 后)'], ['CLUSTER SHARDS', '每个分片 → 各节点 role / health']], cur=[0, 1]), kv=KV([['从库 health', 'loading → online']], ['从库 health'])),
    step(f"每个槽里平均 {st['mean']:.2f} 个 key,最小 {st['mn']},最大 {st['mx']},标准差 {st['sd']:.2f}(纯随机的泊松分布约 2.47)。key 在槽里的分布略比纯随机更散。CLUSTER COUNTKEYSINSLOT 抽查 5 个槽,与自己用 CRC16 算的完全一致。", b=bars([['平均', st['mean'], f"{st['mean']:.2f}"], ['最小', max(st['mn'], 0.05), str(st['mn'])], ['最大', st['mx'], str(st['mx'])]], st['mx'], mark=[2], done=[0]), kv=KV([['槽内 key 数', f"平均 {st['mean']:.2f},标准差 {st['sd']:.2f}"]], ['槽内 key 数'])),
]
A = dict(
    n=68, series='redis', tags='Redis,Cluster,槽位,真实验证,动画演示',
    desc=f'用 6 个本机节点建 3 主 3 从的 Redis Cluster:16384 个槽被均分为 5461 / 5462 / 5461;10 万个 key 落在三个主库上是 {per[str(ports[0])]} / {per[str(ports[1])]} / {per[str(ports[2])]};每个槽平均 {st["mean"]:.2f} 个 key(标准差 {st["sd"]:.2f});CLUSTER SLOTS 在从库健康状态为 loading 时不列出从库,online 后才列出。',
    lead='Redis Cluster 不按节点分数据,而是先把整个键空间切成 16384 个槽,再把槽分给主库。所有关于「数据在哪」的问题,都是在问「这个槽在哪个节点上」。这篇从零搭一个 3 主 3 从的集群,看槽位怎么分配、怎么查询,并把 10 万个 key 写进去,量它们在槽和节点上的实际分布。',
    facts=[('5461 / 5462 / 5461', '16384 个槽在 3 个主库上的分配(create 命令自动均分)'), (f'{per[str(ports[0])]} / {per[str(ports[1])]} / {per[str(ports[2])]}', '10 万个 key 在三个主库上的 DBSIZE'), (f'{st["mean"]:.2f}(σ={st["sd"]:.2f})', '每个槽里 key 数的平均值(标准差)')],
    body=[
        sec('建集群:槽位如何分配', '', term('', blk('r68', 1)), '<p><code>redis-cli --cluster create</code> 把 16384 个槽按顺序平均切成三段:0–5460、5461–10922、10923–16383(5461 + 5462 + 5461)。三个从库随机挂到三个主库下。(为了让从库快点同步,实验中的每个节点都设了 <code>repl-diskless-sync-delay 0</code>,默认是 5 秒。)</p>'),
        sec('CLUSTER NODES', '', term('', blk('r68', 2)), '<p>每个主库有各自的 epoch(1、2、3),槽位区间写在每个主库那一行;从库那一行的第四列是它主库的 ID。同一个集群里所有节点看到的这张表是一致的,<code>--cluster check</code> 的 <code>All nodes agree about slots configuration</code> 检查的就是这一点。</p>'),
        sec('写入 10 万个 key', '', term('', blk('r68', 3)), f'<p>我的客户端用自己实现的 CRC16 先算出每个 key 的槽位,再发给对应的主库,10 万次写入 <b>MOVED 为 0</b>。三个主库的 <code>DBSIZE</code> 是 {per[str(ports[0])]}、{per[str(ports[1])]}、{per[str(ports[2])]},合计 100000,几乎均分。这里的 key 是 <code>user:0</code> 到 <code>user:99999</code>,没有使用 hash tag(第 72 篇)。</p>'),
        sec('CLUSTER SLOTS 与 CLUSTER SHARDS', '', term('', blk('r68', 4)), '<p>我第一次查询时(集群刚建好、没有数据流过),<code>CLUSTER SLOTS</code> 只返回主库、没有从库;<code>CLUSTER SHARDS</code> 显示从库的 <code>health</code> 是 <code>loading</code>。写入数据之后,两者都变成「主 + 从(online)」。所以<b>刚建好的集群里,从库可能暂时不出现在槽位表里</b>——依赖 <code>CLUSTER SLOTS</code> 做读写分离的客户端要注意(我没有深究 loading 的判定规则,只观察到了这个现象)。</p>'),
        sec('槽里的 key 分布', '', term('', blk('r68', 5)), f'<p>10 万个 key 分布在 16384 个槽里,平均每槽 {st["mean"]:.2f} 个,最少 {st["mn"]}、最多 {st["mx"]},标准差 {st["sd"]:.2f}。如果 key 是完全随机地落到槽里,标准差应约 {st["mean"]**.5:.2f};实际略大,说明这批规则的 key 名(<code>user:数字</code>)在槽里的分布比纯随机稍散——但整体仍然很均匀(最大 {st["mx"]} vs 平均 {st["mean"]:.1f})。抽查的 5 个槽,<code>CLUSTER COUNTKEYSINSLOT</code> 返回的数与我自己用 CRC16 算出来的完全一致。</p>'),
        sec('check 的输出', '', term('', blk('r68', 6)), '<p><code>--cluster check</code> 汇总:每个主库的 key 数、槽数、从库数;「All 16384 slots covered」表示所有槽都有主库负责。</p>'),
        sec('分步演示:16384 个槽与三个主库', '', demo('Redis Cluster Slot 分布', [('n', 'flow', '节点与槽位'), ('b', 'bars', '数据'), ('kv', 'kv', '观察')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 主 3 从,cluster-node-timeout 3000,repl-diskless-sync-delay 0(只为加快从库同步)', '没有验证:更大集群(几十个主库)的槽位分配与再平衡、槽位在多个 key 类型(hash tag、集合等)下的分布、从库 health 为 loading 的判定条件'],
)
