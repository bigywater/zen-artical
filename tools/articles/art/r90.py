import json, statistics
from lib import *
c75 = J('r75')['trials']; s89 = J('r89'); c79 = J('r79'); s91 = J('r91')['a']; c73 = None
cf = statistics.median(t['recovered'] for t in c75); sf = s89['outage']['recovered']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("Sentinel 与 Cluster 都能做故障转移,但解决的是不同的问题:Sentinel = 一个主库(一份完整数据)+ 自动切换;Cluster = 数据分片 + 每个分片自己切换。", n=fl([['Sentinel', '1 个主 + N 个从,不分片'], ['Cluster', '16384 槽分片,每片主 + 从']], cur=[0, 1]), kv=KV([['本质差别', '是否分片']], ['本质差别'])),
    step(f"故障转移时长(本机同样的 down/node-timeout = 3000 ms):Cluster kill -9 主库,写入恢复中位约 {cf:.1f} s(第 75 篇,3 次);Sentinel 约 {sf:.1f} s(第 89 篇)。两者都主要取决于超时设置,量级相同。", b=bars([['Cluster 写入恢复', cf * 1000, f'{cf:.1f} s'], ['Sentinel 写入恢复', sf * 1000, f'{sf:.1f} s']], 6000, done=[0, 1]), kv=KV([['恢复', f'Cluster {cf:.1f} s / Sentinel {sf:.1f} s']], ['恢复'])),
    step(f"容量:Sentinel 只有一个主库,写入与内存受限于单机。Cluster 在线加一个主库并 rebalance:{c79['tot']} 个槽 {c79['sec']:.1f} s 搬完,搬迁期间吞吐 {c79['ph']['before']['rate']:.0f} → {c79['ph']['during']['rate']:.0f} ops/s(第 79 篇)。", b=bars([['Cluster 扩容:搬槽耗时', c79['sec'] * 1000, f"{c79['sec']:.1f} s"]], 4000, done=[0]), kv=KV([['扩容', 'Sentinel 不能横向扩,Cluster 可以']], ['扩容'])),
    step("多 key 命令:Sentinel 下是一个普通的 Redis,MSET / 事务 / Lua 跨任意 key 都可以;Cluster 里要求同槽,否则 CROSSSLOT(第 73 篇,同节点不同槽也不行),需要 hash tag,并带来热点风险(第 72 篇)。", n=fl([['Sentinel', '任意 key 组合'], ['Cluster', '必须同槽(CROSSSLOT)']], done=[0], mark=[1]), kv=KV([['多 key', 'Sentinel 自由,Cluster 受限']], ['多 key'])),
    step(f"客户端:Sentinel 客户端向 sentinel 问主库地址(第 92 篇);Cluster 客户端要维护槽位表、处理 MOVED/ASK(第 70、71 篇)。数据丢失方面,两者都是异步复制:Sentinel 分区实验里被确认的写入丢了 {s91['lost']}/{s91['okA']}(第 91 篇),Cluster 里一个被隔离的旧主库在 node-timeout 内仍接受写入(第 83 篇)。", n=fl([['Sentinel', '客户端问 sentinel;分区时可能脑裂'], ['Cluster', '客户端维护槽位表;少数派一侧超时后停写']], cur=[0, 1]), kv=KV([['复杂度', 'Cluster 更高']], ['复杂度'])),
]
A = dict(
    n=90, series='redis', tags='Redis,Sentinel,Cluster,对比,动画演示',
    desc=f'把本系列里 Sentinel 与 Redis Cluster 的实测数字放在一起:kill -9 主库后写入恢复 Cluster 约 {cf:.1f} s、Sentinel 约 {sf:.1f} s(同为 3000 ms 超时);Cluster 能在线扩容({c79["tot"]} 个槽 {c79["sec"]:.1f} s),Sentinel 不能;多 key 命令在 Cluster 里受 CROSSSLOT 限制;两者都是异步复制,都有写入丢失的窗口。',
    lead='选 Sentinel 还是 Cluster,很多文章给的是「数据小用 Sentinel,数据大用 Cluster」这类经验话。这篇不新增实验,把前面各篇已经实测的数字并排放在一起,看两者在故障转移、扩容、多 key 命令和数据安全上到底差在哪里。数字来自第 70–95 篇。',
    facts=[(f'{cf:.1f} vs {sf:.1f} s', '故障转移写入恢复时间:Cluster vs Sentinel(3000 ms 超时)'), ('分片', 'Cluster 的槽位分片能在线扩容;Sentinel 只有一个主库'), ('CROSSSLOT', 'Cluster 的多 key 命令必须同槽;Sentinel 下没有这个限制')],
    body=[
        sec('这是一篇对照,不是新实验', '', '<p>下面所有数字都引用自本系列前面的实验(条件:本机、回环网络、3000 ms 超时),两个系统的对比条件并不完全一致:Cluster 用的是 3 主 3 从、kill -9 一个主库,Sentinel 用的是 1 主 2 从 + 3 个 sentinel、kill -9 主库。</p>'),
        sec('故障转移', '', f'<p>Cluster(第 75 篇):PFAIL → FAIL → 从库升主,写入恢复中位约 {cf:.1f} s。Sentinel(第 89 篇):s_down → o_down → 选领导者 → 提升,写入恢复约 {sf:.1f} s。量级相同,都由检测超时主导。差别在语义:Cluster 每个分片独立切换,一个分片的故障只影响它负责的槽;Sentinel 的主库故障影响全部数据。</p>'),
        sec('容量与扩展', '', f'<p>Sentinel 只有一个主库,数据和写入都受单机限制。Cluster 加一个空主库后 rebalance,{c79["tot"]} 个槽搬迁用时 {c79["sec"]:.1f} s,期间吞吐几乎不变(第 79 篇)。</p>'),
        sec('使用限制', '', '<p>Sentinel 下的 Redis 是普通的单机 Redis:任意多 key 命令、事务、Lua 都可以。Cluster 要求同一命令里的 key 在同一个槽(第 73 篇,连「同节点不同槽」都不行),需要 hash tag(第 72 篇),而 tag 会造成热点。</p>'),
        sec('数据安全', '', f'<p>两者都是异步复制。Sentinel 分区实验里被确认的写入丢了 {s91["lost"]}/{s91["okA"]}(第 91 篇);Cluster 里被隔离的旧主库在 node-timeout 之内仍接受写入,之后拒绝(第 83 篇)。min-replicas-to-write 对两者都适用(第 94、95 篇)。</p>'),
        sec('分步演示:五个维度', '', demo('Sentinel 与 Redis Cluster', [('n', 'flow', '对比'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=['数字引用自第 75、79、89、91 篇;' + ENV_R, '没有验证:两者在相同硬件相同压力下的吞吐对比、运维复杂度的量化(只是描述)、Sentinel 与 Cluster 在云托管环境下的差异'],
)
