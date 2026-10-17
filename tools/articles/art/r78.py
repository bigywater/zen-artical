import json
from lib import *
R = J('r78'); a = R['a']; tl = R['b']['tl']; c = R['c']; d = R['d']
prop = tl[-1][0]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step(f"从库进程被 kill -9:{a['t_fail']*1000:.0f} ms 后在其它节点眼中变成 slave,fail;但 cluster_state 仍是 ok——从库离线不影响集群可用性。", n=fl([['主库', '继续服务'], ['从库', 'fail(被标记)']], mark=[1], done=[0]), b=bars([['被标 fail', a['t_fail'] * 1000, f"{a['t_fail']*1000:.0f} ms"]], 5000, mark=[0]), kv=KV([['cluster_state', 'ok']], ['cluster_state'])),
    step(f"重启这个从库(nodes.conf 还在):{a['t_back']*1000:.0f} ms 后 link up,节点 ID 不变,其它节点眼中重新变成 slave,DBSIZE 与主库一致(期间主库又写入了 5000 个 key)。", n=fl([['主库', ''], ['从库', 'ID 不变,重新加入']], done=[0, 1]), b=bars([['重新加入', a['t_back'] * 1000, f"{a['t_back']*1000:.0f} ms"]], 5000, done=[0]), kv=KV([['重新加入耗时', f"{a['t_back']*1000:.0f} ms"]], ['重新加入耗时'])),
    step("看日志:重启的从库先尝试部分重同步(Trying a partial resynchronization request …:1),主库拒绝(Replication ID mismatch),改走全量同步(Full resync requested,走 RDB channel),RDB 之后又出现一次「Partial resynchronization request … accepted. Sending 300704 bytes of backlog」——那是 RDB 之后补增量。所以 INFO 里的计数是 full +0、partial_ok +1,和「实际发生了一次全量同步」对不上——判断同步类型要看日志,不能只看这两个计数。", n=fl([['PSYNC', '被拒:Replication ID mismatch'], ['全量', 'RDB channel'], ['补增量', 'partial accepted 300704 B']], mark=[0], cur=[1], done=[2]), kv=KV([['INFO stats 变化', f"full +{a['full']},partial_ok +{a['part']}"], ['日志说的', '全量 + 补增量']], ['日志说的'])),
    step("另一种「离开」:节点被清空(丢了 nodes.conf 和数据)后重启。它是一个全新的节点:新 ID,只认识自己(已知节点 1 个);而集群里其它节点仍然保留着旧 ID 的记录,成了「幽灵」。", n=fl([['新节点', '新 ID,已知 1 个'], ['其它节点', '仍记着旧 ID(6 个节点)']], mark=[1], cur=[0]), kv=KV([['幽灵', '旧 ID 仍在节点表里']], ['幽灵'])),
    step(f"在一个节点上 CLUSTER FORGET <旧 ID>:该节点立刻少一个;其它节点在 {prop:.0f} ms 内也都不见了——FORGET 在这个版本里会通过集群总线传播,不需要逐个节点执行(这一点我用一个不做任何 FORGET 的对照确认了:幽灵会一直保留)。", n=fl([['执行 FORGET 的节点', '立刻 5 个'], ['其它 4 个节点', f'{prop:.0f} ms 内陆续 5 个']], done=[0, 1]), b=bars([[f'+{t:.0f} ms', sum(1 for x in v.values() if x == 5), f"{sum(1 for x in v.values() if x == 5)}/5 个节点已删除"] for t, v in tl], 5, done=[len(tl) - 1]), kv=KV([['传播完成', f'{prop:.0f} ms']], ['传播完成'])),
    step(f"让新节点重新加入:CLUSTER MEET 之后 {c['meet']*1000:.0f} ms 认识全部 6 个节点;再 CLUSTER REPLICATE <主库 ID>,{c['link']*1000:.0f} ms 后 link up,DBSIZE = 8334(与主库同步完成)。", n=fl([['MEET', f"{c['meet']*1000:.0f} ms"], ['REPLICATE', f"{c['link']*1000:.0f} ms"]], done=[0, 1]), kv=KV([['重新成为从库', '完成']], ['重新成为从库'])),
    step(f"旧主库的回归:主库被杀,从库 {d['prom']*1000:.0f} ms 后升主;旧主库重启(nodes.conf 还在)后 {d['rejoin']*1000:.0f} ms 内自动变成新主库的从库,ID 不变,不需要人工干预。", n=fl([['旧主库', '重启 → 从库'], ['新主库(原从库)', '主']], done=[0, 1]), b=bars([['升主', d['prom'] * 1000, f"{d['prom']*1000:.0f} ms"], ['旧主库回归为从库', d['rejoin'] * 1000, f"{d['rejoin']*1000:.0f} ms"]], 5500, done=[1], mark=[0]), kv=KV([['旧主库回归', f"{d['rejoin']*1000:.0f} ms"]], ['旧主库回归'])),
]
A = dict(
    n=78, series='redis', tags='Redis,Cluster,节点管理,真实验证,动画演示',
    desc=f'验证 Redis Cluster 节点离开与重新加入:从库被 kill -9 {a["t_fail"]*1000:.0f} ms 后被标 fail 但集群仍 ok,重启 {a["t_back"]*1000:.0f} ms 内回归(日志显示 PSYNC 因 ID 不符被拒、走 RDB channel 全量同步,INFO 计数却是 full +0);清空的节点是新 ID,旧 ID 成幽灵,CLUSTER FORGET 在一个节点执行后 {prop:.0f} ms 内传播到所有节点;旧主库重启 {d["rejoin"]*1000:.0f} ms 内自动成为从库。',
    lead='节点离开集群有两种:短暂离线(进程崩溃再重启)和永久离开(机器换掉、数据丢了)。它们在集群眼里差别很大:前者节点 ID 还在、自动回来;后者留下一个永远连不上的「幽灵」,需要 CLUSTER FORGET 清理。这篇把四种情形分别真做一遍,并纠正我一个预期:FORGET 在这个版本里居然会自己传播。',
    facts=[(f'{a["t_back"]*1000:.0f} ms', '从库进程重启(nodes.conf 还在)到 link up'), (f'{prop:.0f} ms', '在一个节点执行 CLUSTER FORGET 后,所有节点都删除幽灵所用的时间'), (f'{d["rejoin"]*1000:.0f} ms', '被杀的旧主库重启后自动变成新主库的从库所用的时间')],
    body=[
        sec('从库崩溃再重启', '', term('', blk('r78', 1)), f'<p>kill -9 一个从库:约 {a["t_fail"]:.1f} s(cluster-node-timeout 3 s 之后)其它节点把它标成 <code>slave,fail</code>,但因为槽位都还有主库,<code>cluster_state</code> 仍是 ok。期间主库继续被写入 5000 个 key。重启后(<code>nodes.conf</code> 还在,节点 ID 不变){a["t_back"]*1000:.0f} ms 就 link up 并追上了数据。<b>日志的细节值得看</b>:从库先尝试部分重同步,被主库以 <code>Replication ID mismatch</code> 拒绝,于是走 <code>rdb-channel</code> 的全量同步;之后又有一次 <code>Partial resynchronization request … accepted. Sending 300704 bytes of backlog</code>,用来补 RDB 之后的增量。所以主库 <code>INFO stats</code> 的变化是 <code>sync_full +{a["full"]}</code>、<code>sync_partial_ok +{a["part"]}</code>——和「发生过一次全量同步」的事实不一致。<b>在这个版本上判断同步类型,要看日志,别只看这两个计数。</b>(这次的 <code>rdb-channel</code> 全量同步与第 53 篇里我用计数判断类型的场景不同;那里我又对照日志复核过,结论没有变。)</p>'),
        sec('节点被清空:新 ID 与幽灵', '', term('', blk('r78', 2)), f'<p>把一个从库的 <code>nodes.conf</code> 和数据文件删掉再启动,它就是一个<b>全新的节点</b>:新的 ID,只认识自己。而其它节点还记着旧 ID(已知节点数仍是 6)。我另外用一个不做任何操作的对照观察了 22 秒(该次探针没有打印进上面的输出):这个幽灵一直是 <code>slave/disconnected</code>,不会自己消失。在一个节点上 <code>CLUSTER FORGET 旧ID</code> 后,该节点立刻少一个;<b>其它节点在 {prop:.0f} ms 内也都删除了它</b>——我原本以为要在每个节点上都执行,实测这个版本里 FORGET 会通过集群总线传播,我没有去查是从哪个版本开始的。</p>'),
        sec('让新节点重新加入', '', term('', blk('r78', 3)), f'<p><code>CLUSTER MEET</code> 一个已有节点,{c["meet"]*1000:.0f} ms 后认识全部 6 个节点(第 74 篇);再 <code>CLUSTER REPLICATE 主库ID</code>,{c["link"]*1000:.0f} ms 后从库 link up、数据同步完成。</p>'),
        sec('旧主库回来:自动变成从库', '', term('', blk('r78', 4)), f'<p>主库被杀,从库 {d["prom"]*1000:.0f} ms 后升主;旧主库用原来的 <code>nodes.conf</code> 重启后 {d["rejoin"]*1000:.0f} ms 内自动变成新主库的从库,节点 ID 不变。不需要 <code>CLUSTER REPLICATE</code>——节点重启后从 gossip 里看到更高的 epoch,自己就明白了(第 77 篇)。</p>'),
        sec('分步演示:离开与回来的四种情形', '', demo('节点离开与重新加入', [('n', 'flow', '节点状态'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 主 3 从,每个场景在同一个集群里顺序进行;「清空」指删除该节点目录下的 nodes.conf 与数据文件', '没有验证:CLUSTER FORGET 传播是从哪个版本开始的(只在本机 8.10.2 上观察)、FORGET 的 60 秒黑名单时间、CLUSTER RESET 各模式、redis-cli --cluster del-node / add-node 的完整流程、节点换 IP 后的行为(cluster-announce-ip)'],
)
