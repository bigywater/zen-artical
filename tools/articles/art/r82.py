import json
from lib import *
R = J('r82'); rows = R['rows']; mg = R['migrate']; sl = R['sleep']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
big = max(rows, key=lambda r: r['mem']); small = min(rows, key=lambda r: r['mem'])
steps = [
    step(f"3 主集群,30 万个普通 key(每个 20 字节值)均匀分布,再往其中一个主库({big['port']})写入一个 200 MB 的大 key。三个主库的槽位数是 5461 / 5462 / 5461,DBSIZE 都约 10 万——看起来完全均衡。", n=fl([[f"主 {r['port']}", f"槽 {r['slots']},key {r['dbsize']}"] for r in rows], done=[0, 1, 2]), kv=KV([['槽位数', '5461 / 5462 / 5461'], ['DBSIZE', ' / '.join(str(r['dbsize']) for r in rows)]], ['槽位数'])),
    step(f"但内存不均衡:{big['port']} 用了 {big['mem']/1e6:.0f} MB,另外两个各 {small['mem']/1e6:.1f} MB,相差 {big['mem']/small['mem']:.0f} 倍。一个 key 就能让一个分片「变胖」,而槽位与 key 数量都看不出来。", b=bars([[f"主 {r['port']}", r['mem'] / 1e6, f"{r['mem']/1e6:.1f} MB"] for r in rows], big['mem'] / 1e6, mark=[[r['port'] for r in rows].index(big['port'])], done=[i for i, r in enumerate(rows) if r['port'] != big['port']]), kv=KV([['内存差', f"{big['mem']/small['mem']:.0f} 倍"]], ['内存差'])),
    step(f"redis-cli --cluster rebalance 看的是槽位数:输出「No rebalancing needed! All nodes are within the 2.00% threshold」——工具认为已经均衡,不会做任何事。它不知道内存不均衡。", n=fl([['rebalance', 'No rebalancing needed']], done=[0]), kv=KV([['rebalance', '不需要调整']], ['rebalance'])),
    step(f"想靠迁移槽位来疏散大 key?迁移含大 key 的槽(19 个 key,其中一个 200 MB):MIGRATE 用了 {mg['ms']:.0f} ms,期间源节点 {big['port']} 上另一个连接的 PING 最大停顿 {mg['stall']:.0f} ms(平时约 0.03 ms)——这个节点上其它所有槽的请求都被卡住这么久。", b=bars([['MIGRATE 耗时', mg['ms'], f"{mg['ms']:.0f} ms"], ['源节点 PING 最大停顿', mg['stall'], f"{mg['stall']:.0f} ms"], ['平常的 PING', 0.05, '≈0.03 ms']], mg['ms'], mark=[1]), kv=KV([['源节点停顿', f"{mg['stall']:.0f} ms"]], ['源节点停顿'])),
    step(f"更危险的:如果一次阻塞超过 cluster-node-timeout(3000 ms),集群会认为这个主库死了。我用 DEBUG SLEEP 5 模拟一次 5 秒的阻塞(真实的超大 key 删除/迁移会造成类似的停顿):其它节点 {sl['pfail']*1000:.0f} ms 标 PFAIL、{sl['fail']*1000:.0f} ms 标 FAIL,它的从库 {sl['promoted']*1000:.0f} ms 升主。阻塞结束后,原主库自己变成了从库。", n=fl([['被阻塞的主库', '5 s 无响应 → 被判 FAIL'], ['它的从库', f"{sl['promoted']*1000:.0f} ms 升主"], ['阻塞结束后', '原主库变从库']], mark=[0], cur=[1], done=[2]), b=bars([['PFAIL', sl['pfail'] * 1000, f"{sl['pfail']*1000:.0f} ms"], ['FAIL', sl['fail'] * 1000, f"{sl['fail']*1000:.0f} ms"], ['从库升主', sl['promoted'] * 1000, f"{sl['promoted']*1000:.0f} ms"], ['cluster-node-timeout', 3000, '3000 ms']], 5000, mark=[0, 1, 2]), kv=KV([['阻塞 5 s', '触发故障转移']], ['阻塞 5 s'])),
]
A = dict(
    n=82, series='redis', tags='Redis,Cluster,大Key,真实验证,动画演示',
    desc=f'集群里一个 200 MB 的大 key:三个主库槽位数 5461/5462/5461、DBSIZE 都约 10 万,内存却是 {big["mem"]/1e6:.0f} MB 对 {small["mem"]/1e6:.1f} MB;redis-cli rebalance 认为「No rebalancing needed」;迁移含大 key 的槽让源节点 PING 停顿 {mg["stall"]:.0f} ms;主库阻塞 5 秒(DEBUG SLEEP 模拟)超过 cluster-node-timeout 后被判 FAIL、从库 {sl["promoted"]*1000:.0f} ms 升主。',
    lead='单机上大 key 的问题是慢命令、内存;集群里它还多出三个问题:数据看起来均衡其实不均衡、迁移时会卡住整个节点、更糟的是节点被卡住太久会被整个集群判死。这篇用一个 200 MB 的 key 把三个问题都复现一遍。(每一步的数字来自本机;最后一步的「阻塞」是我用 DEBUG SLEEP 模拟的。)',
    facts=[(f'{big["mem"]/1e6:.0f} vs {small["mem"]/1e6:.1f} MB', '槽位数、DBSIZE 都均衡时,含大 key 的主库与另外两个主库的内存'), (f'{mg["stall"]:.0f} ms', '迁移含 200 MB 大 key 的槽时,源节点上 PING 的最大停顿'), (f'{sl["promoted"]*1000:.0f} ms', '主库被阻塞 5 秒(超过 node-timeout)后,从库升主所用的时间')],
    body=[
        sec('均衡的假象', '', term('', blk('r82', 1)), f'<p>槽位数、key 数量是集群「均衡」的通常指标,三个主库都是 5461/5462/5461、约 10 万个 key。但 {big["port"]} 上有一个 200 MB 的 key,内存 {big["mem"]/1e6:.0f} MB,另外两个只有 {small["mem"]/1e6:.1f} MB。这个 key 只占 1 个槽、1 个 key,在槽位数与 DBSIZE 上完全不可见。内存告警、RDB 大小之类的问题理论上也会先在这个分片上出现(这一点本文没有实测)。</p>'),
        sec('rebalance 帮不上忙', '', term('', blk('r82', 2)), '<p><code>redis-cli --cluster rebalance</code> 按槽位数(可以加权重)均衡,它给出的结论是 <code>No rebalancing needed! All nodes are within the 2.00% threshold</code>。要疏散大 key,我能想到的办法是人工找到含它的槽再迁走,或者拆分这个 key(有没有别的工具,本文没有验证)。</p>'),
        sec('迁移含大 key 的槽:卡住整个源节点', '', term('', blk('r82', 3)), f'<p>手工迁移这个槽(第 80 篇的四步):槽里 19 个 key,其中含 200 MB 的大 key,<code>MIGRATE</code> 用了 {mg["ms"]:.0f} ms,期间源节点上另一个连接的 <code>PING</code> 最大停顿 {mg["stall"]:.0f} ms——几乎等于整个 MIGRATE。第 81 篇量过:MIGRATE 在源上同步执行,所以这个节点的<b>其它所有槽</b>在这段时间里都不响应。</p>'),
        sec('阻塞超过 cluster-node-timeout:被判死', '', term('', blk('r82', 4)), f'<p>如果这样的停顿(或者一次超大 key 的 <code>DEL</code>)超过 <code>cluster-node-timeout</code>(这里 3000 ms),其它节点收不到它的心跳,会把它标成 PFAIL、再确认 FAIL,从库发起选举升主(第 75、76 篇)。我用 <code>DEBUG SLEEP 5</code> 模拟 5 秒的阻塞:其它节点 {sl["pfail"]*1000:.0f} ms 标 PFAIL、{sl["fail"]*1000:.0f} ms 标 FAIL,从库 {sl["promoted"]*1000:.0f} ms 升主。阻塞结束后原主库醒来,自己变成了从库(第 77 篇)。<b>这是「模拟」的阻塞,不是真的大 key 操作</b>;要说的是:任何持续超过 node-timeout 的主线程阻塞,不管原因,都会触发故障转移。</p>'),
        sec('分步演示:大 key 在集群里的三个坑', '', demo('Redis Cluster 中的大 Key', [('n', 'flow', '节点'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 主 3 从,enable-debug-command yes(只为 DEBUG SLEEP 模拟阻塞);大 key 是一个 200 MB 的字符串', '没有验证:真实的大 key 删除(DEL / UNLINK)对集群的影响、大 hash/list 的迁移(MIGRATE 会分块吗)、cluster-node-timeout 设得更大时的取舍、从库上大 key 对复制缓冲区的影响'],
)
