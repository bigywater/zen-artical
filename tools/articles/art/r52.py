import json
from lib import *
R = J('r52')
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
s2 = R['s2']
steps = [
    step("A 是主库,B、C 是从库。三个节点的 master_replid 一样(6a40066f…)、master_repl_offset 一样(31803)——它们共享同一段复制历史。A 上 sync_full = 2(B、C 各一次全量同步)。", n=cells(['A master 6a40066f @31803', 'B replica 6a40066f @31803', 'C replica 6a40066f @31803']), kv=KV([['复制 ID', '相同'], ['offset', '相同']], ['复制 ID'])),
    step(f"B 执行 REPLICAOF NO ONE 被提升:生成新的 replid(551b2c4d…),把旧的 6a40066f… 保存到 master_replid2,并记下 second_repl_offset = {s2['second']}(提升时的 offset {s2['off']} + 1)。意思是:「到这个 offset 为止,旧历史和我的历史是同一条」。", n=cells(['A master 6a40066f', 'B master 551b2c4d + replid2 6a40066f, second=%d' % s2['second'], 'C replica 6a40066f'], cur=[1]), kv=KV([['B.replid2 == A 的旧 replid', str(s2['same'])], ['second_repl_offset', str(s2['second'])]], ['second_repl_offset'])),
    step(f"C 改跟随 B:C 拿旧 replid 6a40066f… 和 offset 来请求 PSYNC,B 发现它等于自己的 replid2、且 offset ≤ second_repl_offset,接受部分重同步:B 的 sync_full +{R['s3'][0]}、sync_partial_ok +{R['s3'][1]},日志「accepted. Sending 0 bytes of backlog」。", n=cells(['A master 6a40066f', 'B master 551b2c4d', 'C replica 551b2c4d(部分重同步,0 字节)'], cur=[2]), kv=KV([['B sync_full 变化', f'+{R["s3"][0]}'], ['B sync_partial_ok 变化', f'+{R["s3"][1]}']], ['B sync_partial_ok 变化'])),
    step(f"B 上写 500 个 key 后,旧主 A 也以从库身份加入 B:同样是部分重同步(full +{R['s4'][0]}、partial_ok +{R['s4'][1]}),A、B、C 的 dbsize 都是 1500,replid 全部变成 551b2c4d…。", n=cells(['A replica 551b2c4d', 'B master 551b2c4d', 'C replica 551b2c4d'], done=[0, 1, 2]), kv=KV([['dbsize A/B/C', '1500 / 1500 / 1500']], ['dbsize A/B/C'])),
    step(f"对照:一个毫无关系的新节点 D(它有自己的 replid)挂到 B:replid 对不上,只能全量同步(B 的 sync_full +{R['s5'][0]}、partial_ok +{R['s5'][1]})。", n=cells(['B master 551b2c4d', 'D 自己的历史', 'D → B:FULLRESYNC'], mark=[2]), kv=KV([['D 挂到 B', f'sync_full +{R["s5"][0]}']], ['D 挂到 B'])),
]
A = dict(
    n=52, series='redis', tags='Redis,复制,PSYNC2,真实验证,动画演示',
    desc=f'用 3 个本机 Redis 节点验证 PSYNC2:提升从库后它保留旧主的 replid 作为 replid2(second_repl_offset = 提升时 offset + 1);另一个从库改跟随新主、旧主降为从库重新加入,都是部分重同步(新主 sync_full 变化 {R["s3"][0]} / {R["s4"][0]},partial_ok +{R["s3"][1]} / +{R["s4"][1]});毫无关系的新节点则只能全量同步。',
    lead='早期的 Redis 复制里,只要主从关系一变——比如故障转移——所有从库都要做一次全量同步。PSYNC2 让节点记住「我上一任主库的复制 ID 和 offset」,换主之后可以接着同步。这篇用三个真实节点、一次真实的提升,看这些 ID 和 offset 怎么变,并对照哪些场景仍然要全量同步。',
    facts=[('2 个 ID', '被提升的从库同时持有 master_replid(新)与 master_replid2(旧)'), (f'+1', f'second_repl_offset 比提升时的 offset 大 1({s2["off"]} → {s2["second"]})'), (f'full +{R["s3"][0]}', 'C 改跟随新主 B 时,B 的 sync_full 增量(partial_ok +%d)' % R['s3'][1])],
    body=[
        sec('同一段复制历史:replid 与 offset', '', term('', blk('r52', 1)), '<p><code>master_replid</code> 是一段复制历史的标识,<code>master_repl_offset</code> 是这段历史里已复制的字节位置。主库和它的从库共享同一个 replid,offset 也一致;A 上的 <code>sync_full=2</code> 是 B、C 最初各做了一次全量同步。</p>'),
        sec('提升 B:新 ID + 保留旧 ID', '', term('', blk('r52', 2)), f'<p>B 执行 <code>REPLICAOF NO ONE</code> 之后:<code>master_replid</code> 换成新的(551b2c4d…),旧的存入 <code>master_replid2</code>,<code>second_repl_offset</code> = {s2["second"]},正好是提升时 offset({s2["off"]})加 1。两个字段合起来的含义是:用旧 replid 来请求、并且请求的起始位置不超过 second_repl_offset 的从库,可以接受(下一步日志里 C 请求的起始位置就是 {s2["second"]},正好等于 second_repl_offset)。</p>'),
        sec('C 改跟随 B:部分重同步', '', term('', blk('r52', 3)), f'<p>C 带着旧 replid 和自己的 offset 向 B 发 PSYNC,B 的日志是 <code>Partial resynchronization request from 127.0.0.1:7154 accepted. Sending 0 bytes of backlog starting from offset {s2["second"]}</code>:接受,需要补的数据是 0 字节。B 的 <code>sync_full</code> 增量 {R["s3"][0]}、<code>sync_partial_ok</code> 增量 {R["s3"][1]}。日志里还有一行 <code>Partial resynchronization not possible (no cached master)</code>,那是 B 自己(刚被提升、没有缓存的主库)的一条记录,不是对 C 的拒绝。</p>'),
        sec('旧主降级为从库重新加入', '', term('', blk('r52', 4)), f'<p>B 上又写了 500 个 key;旧主 A 用 <code>REPLICAOF</code> 挂到 B:仍然是部分重同步(full +{R["s4"][0]}、partial_ok +{R["s4"][1]}),三个节点 dbsize 都是 1500,replid 全部收敛为新主的 551b2c4d…。</p>'),
        sec('对照:毫无关系的节点只能全量', '', term('', blk('r52', 5)), f'<p>新节点 D 有自己的复制历史,replid 与 B 的 replid、replid2 都对不上,B 只能全量同步(sync_full +{R["s5"][0]})。所以「换主可以部分重同步」有前提:两边的历史在某个 offset 之前是同一条。</p>'),
        sec('分步演示:replid 与 replid2 的变化', '', demo('PSYNC2', [('n', 'cells', '节点(角色 复制ID)'), ('kv', 'kv', '观察')], steps, '本步变化的节点')),
    ],
    refs=[ENV_R + '。A、B、C、D 四个独立实例;「提升」用 REPLICAOF NO ONE 手动完成,没有经过 Sentinel 或 Cluster', '没有验证:backlog 不够大时同样的场景是否退回全量(见第 53 篇的 backlog 实验)、级联复制(从库的从库)下的 replid 传播、Redis 早于 4.0 的行为'],
)
