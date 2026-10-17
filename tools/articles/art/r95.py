import json
from lib import *
R = J('r95'); g = R['guard']; lag = R['lag']; base = J('r91')['a']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("min-replicas-max-lag 的「lag」是主库 INFO replication 里每个从库的 lag 字段:距上次收到该从库 REPLCONF ACK 的秒数。冻结 slave0:冻结后 1、2、3……7 秒,它的 lag 依次是 " + '、'.join(x[1][0] for x in lag) + ";正常的 slave1 始终是 " + lag[-1][1][1] + "。", b=bars([[f'冻结后 {s} s', int(v[0]), f'lag = {v[0]}'] for s, v in lag], 8, mark=[len(lag) - 1]), kv=KV([['slave0 lag', ' → '.join(x[1][0] for x in lag)], ['slave1 lag', lag[-1][1][1]]], ['slave0 lag'])),
    step("回到第 91 篇的分区实验:sentinel 把主库切走,而不知情的客户端 A 仍在写旧主库。不加保护时,A 收到 OK 的写入里丢了 " + f"{base['lost']} / {base['okA']}。", b=bars([['被回复 OK', base['okA'], str(base['okA'])], ['丢失', base['lost'], str(base['lost'])]], base['okA'], mark=[1]), kv=KV([['不加保护', f"丢失 {base['lost']} / {base['okA']}"]], ['不加保护'])),
    step(f"给旧主库加 min-replicas-to-write 1、min-replicas-max-lag 3。故障转移后从库都离开了旧主库,它的「好从库」变成 0,约 3 s 后开始对客户端 A 回 NOREPLICAS——一共拒绝了 {dict(g['errs'])['NOREPLICAS Not enough good replicas to w']} 次写入。", n=fl([['旧主库', 'good replicas = 0 → 拒绝写入'], ['客户端 A', 'NOREPLICAS']], mark=[0, 1]), kv=KV([['NOREPLICAS 次数', str(dict(g['errs'])['NOREPLICAS Not enough good replicas to w'])]], ['NOREPLICAS 次数'])),
    step(f"结果:客户端 A 共 {g['okA']} 次写入被回复 OK(而不是 {base['okA']} 次),最终保留 {g['kept']} 条,丢失 {g['lost']} 条——丢失从 {base['lost']} 条降到 {g['lost']} 条。剩下的丢失来自 max-lag 这 3 秒窗口内还被接受的写入。", b=bars([['无保护:丢失', base['lost'], str(base['lost'])], ['有保护:丢失', g['lost'], str(g['lost'])]], base['lost'], mark=[0], done=[1]), kv=KV([['丢失', f"{base['lost']} → {g['lost']}"]], ['丢失'])),
]
A = dict(
    n=95, series='redis', tags='Redis,复制,min-replicas,脑裂,真实验证,动画演示',
    desc=f'min-replicas-max-lag 的 lag 就是 INFO 里从库距上次 ACK 的秒数;在第 91 篇的分区实验里给旧主库加 min-replicas-to-write 1 / max-lag 3:客户端收到 OK 的写入从 {base["okA"]} 条降到 {g["okA"]} 条,丢失从 {base["lost"]} 条降到 {g["lost"]} 条,拒绝写入 {dict(g["errs"])["NOREPLICAS Not enough good replicas to w"]} 次(NOREPLICAS)。',
    lead='上一篇看到 min-replicas-to-write 会在联系不上从库时拒绝写入。这一篇看它的另一半:max-lag 的「lag」究竟是什么,以及把这个设置放进脑裂场景里,它能挽回多少数据。',
    facts=[('lag = 距上次 ACK 的秒数', '冻结一个从库,它在主库 INFO 里的 lag 每秒 +1'), (f'{base["lost"]} → {g["lost"]}', '同一个脑裂实验里,加 min-replicas 前后丢失的已确认写入'), (f'{dict(g["errs"])["NOREPLICAS Not enough good replicas to w"]} 次', '旧主库拒绝的写入(NOREPLICAS)')],
    body=[
        sec('lag 是什么', '', term('', blk('r95', 1)), '<p>主库 INFO replication 的 <code>slaveN</code> 行里有 <code>lag=</code>:从库每秒发一次 <code>REPLCONF ACK</code>,主库记录最近一次收到的时间,lag 就是「现在减去那个时间」的秒数。冻结一个从库后,它的 lag 每秒加 1;另一个正常的从库保持在 1 以内。<code>min-replicas-max-lag 3</code> 意思是 lag ≤ 3 的从库才算「好」。</p>'),
        sec('放进脑裂实验', '', term('', blk('r95', 2)), f'<p>同样是第 91 篇的分区(sentinel 切换主库,客户端 A 继续写旧主库),只是旧主库多了 <code>min-replicas-to-write 1</code> 和 <code>min-replicas-max-lag 3</code>。故障转移后从库都离开了旧主库,它的好从库数变成 0,约 3 秒后开始拒绝 A 的写入(<code>NOREPLICAS</code>,{dict(g["errs"])["NOREPLICAS Not enough good replicas to w"]} 次)。A 收到 OK 的写入只有 {g["okA"]} 条(无保护时 {base["okA"]} 条),最终丢失 {g["lost"]} 条(无保护时 {base["lost"]} 条)。<b>剩下的 {g["lost"]} 条丢失,来自 max-lag 那 3 秒窗口里仍被接受的写入</b>——min-replicas 缩小了窗口,没有消除它。</p>'),
        sec('代价', '', '<p>同样的设置在没有故障、只是从库重启或网络抖动时也会让主库停写(第 94 篇)。所以这是一个「宁可不可用也不丢数据」的取舍,并且窗口大小由 max-lag 决定:设得越小,窗口越小,误停写的概率越高。</p>'),
        sec('分步演示:min-replicas 对脑裂的作用', '', demo('min-replicas-max-lag', [('n', 'flow', '节点'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。实验条件同第 91 篇(代理切断 sentinel 与主库的通路;客户端 A 直连旧主库,每 10 ms 一次同步 SET),仅多了 min-replicas 两项配置;每种配置只跑一次', '没有验证:多次重复的方差、max-lag 取 1 或 10 时丢失量的变化、客户端 A 同时读写时的行为、真实网络分区'],
)
