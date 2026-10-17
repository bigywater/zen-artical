import json
from lib import *
R = J('r91'); r = R['a']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("搭建:1 主 2 从 + 3 个 sentinel。sentinel 通过一个我写的可切断 TCP 代理访问主库(monitor 的是代理地址);客户端 A 不知情,一直直连旧主库写;客户端 B 每次先问 sentinel 再写。", n=fl([['旧主库', 'sentinel 经代理访问;客户端 A 直连'], ['sentinel ×3', '经代理看主库'], ['从库 ×2', '直连主库复制']], cur=[0]), kv=KV([['分区方式', '切断 sentinel ↔ 主库的代理']], ['分区方式'])),
    step(f"切断代理:sentinel 联系不上主库,{r['switch']:.1f} s 后完成故障转移,把一个从库提升为新主库。但旧主库进程完好,客户端 A 还连着它——现在有两个主库同时在接受写入(脑裂)。", n=fl([['旧主库', '仍接受客户端 A 的写入'], ['新主库(原从库)', '接受客户端 B 的写入']], mark=[0, 1]), b=bars([['切换完成', r['switch'] * 1000, f"{r['switch']:.1f} s"]], 12000, mark=[0]), kv=KV([['脑裂开始', f"约 {r['switch']:.1f} s"]], ['脑裂开始'])),
    step(f"分区持续 {r['heal_at']:.1f} s,期间客户端 A 在旧主库上又有 {r['okA_split']} 次写入被回复 OK。这些写入既没有到达新主库,也不会再被复制。", n=fl([['旧主库', f"分区期间 {r['okA_split']} 次 OK 写入"], ['新主库', '看不到这些写入']], mark=[0]), kv=KV([['分区期间 OK 的写入', str(r['okA_split'])]], ['分区期间 OK 的写入'])),
    step(f"恢复代理后,sentinel 重新连上旧主库,发现它已不是主库,把它改成新主库的从库——用了 {r['demote']:.1f} s。这 {r['demote']:.0f} 秒里旧主库仍在接受客户端 A 的写入。降级后它从新主库全量同步,自己的写入被丢弃。", n=fl([['旧主库', f"{r['demote']:.1f} s 后降为从库,数据被新主库覆盖"]], done=[0]), b=bars([['分区', r['heal_at'] * 1000, f"{r['heal_at']:.1f} s"], ['恢复后到降级', r['demote'] * 1000, f"{r['demote']:.1f} s"]], 11000, mark=[0, 1]), kv=KV([['降级耗时', f"{r['demote']:.1f} s"]], ['降级耗时'])),
    step(f"结果:客户端 A 共 {r['okA']} 次写入被回复 OK,最终在新主库上还在的只有 {r['kept']} 条(都是在故障转移之前复制过去的),丢失 {r['lost']} 条——被回复了 OK 的数据丢了 {r['lost']/r['okA']*100:.0f}%。客户端 B 在新主库上写入的数据不受影响。", b=bars([['被回复 OK', r['okA'], str(r['okA'])], ['最终保留', r['kept'], str(r['kept'])], ['丢失', r['lost'], str(r['lost'])]], r['okA'], done=[1], mark=[2]), kv=KV([['丢失', f"{r['lost']} / {r['okA']}"]], ['丢失'])),
]
A = dict(
    n=91, series='redis', tags='Redis,Sentinel,脑裂,真实验证,动画演示',
    desc=f'用可切断的代理制造 Sentinel 与主库之间的分区:{r["switch"]:.1f} s 后 sentinel 完成故障转移,而不知情的客户端仍在向旧主库写入——两个主库同时接受写入;旧主库在恢复后 {r["demote"]:.1f} s 才被降级为从库;客户端收到 OK 的 {r["okA"]} 次写入里最终只保留了 {r["kept"]} 条,丢失 {r["lost"]} 条。',
    lead='脑裂是说:同一时刻有两个节点都以为自己是主库、都接受写入。Sentinel 架构里,「sentinel 联系不上主库」并不等于「客户端联系不上主库」。这一篇做出这种情形:切断 sentinel 与主库之间的通路,让一个不知情的客户端继续写旧主库,看故障转移之后有多少已确认的写入消失。',
    facts=[(f'{r["switch"]:.1f} s', '切断后 sentinel 完成故障转移(此后出现两个主库)'), (f'{r["demote"]:.1f} s', '分区恢复后旧主库被降级为从库所用时间(期间仍在接受写入)'), (f'{r["lost"]} / {r["okA"]}', '客户端 A 被回复 OK 的写入中,最终丢失的条数')],
    body=[
        sec('做法', '', '<p>三个 sentinel 监控的主库地址是我写的一个 TCP 代理(<code>127.0.0.1:7900</code> → 主库 7910)。<code>cut()</code> 关闭代理并断开它上面的所有连接,等价于「sentinel 与主库之间网络断了」;而客户端 A 是直连主库的、不受影响。从库直连主库做复制。另一个客户端 B 每次写之前先向 sentinel 询问当前主库地址。</p>'),
        sec('结果', '', term('', blk('r91', 1)), f'<p>切断后 {r["switch"]:.1f} s,sentinel 提升了一个从库,B 开始写新主库。而 A 仍在写旧主库,分区期间又有 {r["okA_split"]} 次写入被回复 <code>OK</code>。恢复代理之后,sentinel 花了 {r["demote"]:.1f} s 才把旧主库降级成从库(第 89 篇里也观察到旧主库回归耗时约 10 s),这期间 A 继续写。降级后旧主库从新主库同步,自己的写入被覆盖。最终:A 共 {r["okA"]} 次写入被回复 OK,还在的只有 {r["kept"]} 条——故障转移之前复制过去的那些;<b>其余 {r["lost"]} 条(约 {r["lost"]/r["okA"]*100:.0f}%)已经被回复 OK 的写入丢失了</b>。(A 的失败 {r["errA"]} 次主要是降级之后连接被断开。)</p>'),
        sec('这说明什么', '', '<p>Sentinel 本身不能阻止旧主库继续接受写入——它只能在恢复联系后把旧主库降级。缓解办法是让旧主库自己在联系不上从库时拒绝写入(<code>min-replicas-to-write</code>,第 94、95 篇),以及让客户端通过 sentinel 发现主库、并在连接断开或收到只读错误后重新发现(第 92 篇)。</p><p>这次实验是「sentinel 与主库分区、客户端与主库连通」这一种拓扑;真实的分区形态很多(包括客户端也被分区),这里没有覆盖。</p>'),
        sec('分步演示:脑裂与写入丢失', '', demo('Sentinel 脑裂', [('n', 'flow', '节点'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。1 主 2 从 + 3 sentinel,sentinel monitor 的是代理地址;分区 = 切断代理;客户端 A 直连旧主库(每 10 ms 一次同步 SET)', '没有验证:真实网络分区、多个从库之间的偏移量差异对丢失量的影响、不同 down-after / failover-timeout 设置、旧主库降级延迟 10 s 的来源(第 89 篇也观察到)'],
)
