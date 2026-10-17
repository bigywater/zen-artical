import json, statistics, re
from lib import *
R = J('r75'); T = R['trials']
med = lambda k: statistics.median(t[k] for t in T)
rng = lambda k: (min(t[k] for t in T), max(t[k] for t in T))
pf, fa, pr, rc = med('pfail'), med('fail'), med('promoted'), med('recovered')
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
lost = sum(t['lost'] for t in T); acked = sum(t['acked'] for t in T)
log = T[-1]['replog']
delay = re.search(r'delayed for (\d+) milliseconds \(rank #(\d+), offset (\d+)', ' '.join(log))
steps = [
    step("3 主 3 从集群(cluster-node-timeout = 3000 ms)。两个写线程各自不停地 SET:一个只写将被杀掉的主库 X 负责的槽,另一个写别的主库的槽。1 秒后对 X 执行 kill -9。", n=fl([['主库 X', '被 kill -9'], ['X 的从库', '待升主'], ['其它主库', '继续服务']], mark=[0], cur=[1]), kv=KV([['cluster-node-timeout', '3000 ms']], ['cluster-node-timeout'])),
    step(f"X 的连接立刻断了,但没有人马上宣布它死了:其它节点等它超过 node-timeout 没有应答才标记 PFAIL(可能失败,fail?)。三次实验里 PFAIL 出现在 kill 后 {rng('pfail')[0]*1000:.0f}–{rng('pfail')[1]*1000:.0f} ms(中位 {pf*1000:.0f} ms)。这段时间 X 的槽既不能读也不能写。", n=fl([['主库 X', '已死'], ['其它节点', 'PFAIL(单方面怀疑)']], mark=[0], cur=[1]), b=bars([['PFAIL', pf * 1000, f'{pf*1000:.0f} ms']], 6000, cur=[0]), kv=KV([['PFAIL', f'{pf*1000:.0f} ms 后']], ['PFAIL'])),
    step(f"多数主库都认为 X 不可达之后,PFAIL 升级为 FAIL 并广播(FAIL message):kill 后 {rng('fail')[0]*1000:.0f}–{rng('fail')[1]*1000:.0f} ms(中位 {fa*1000:.0f} ms)。只有 FAIL 才能触发故障转移。", n=fl([['主库 X', 'FAIL'], ['其它节点', 'FAIL 已广播']], mark=[0], cur=[1]), b=bars([['PFAIL', pf * 1000, f'{pf*1000:.0f} ms'], ['FAIL', fa * 1000, f'{fa*1000:.0f} ms']], 6000, cur=[1], done=[0]), kv=KV([['FAIL', f'{fa*1000:.0f} ms 后']], ['FAIL'])),
    step(f"X 的从库看到 FAIL 后发起选举:日志「Start of election delayed for {delay.group(1)} milliseconds (rank #{delay.group(2)}, offset {delay.group(3)})」——先随机延迟,再「Starting a failover election」,拿到多数主库的票后「Failover election won: I'm the new master」。kill 后 {rng('promoted')[0]*1000:.0f}–{rng('promoted')[1]*1000:.0f} ms(中位 {pr*1000:.0f} ms)从库变成主库。", n=fl([['从库', '选举 → 赢'], ['其它主库', '投票']], cur=[0, 1]), b=bars([['PFAIL', pf * 1000, f'{pf*1000:.0f} ms'], ['FAIL', fa * 1000, f'{fa*1000:.0f} ms'], ['从库升主', pr * 1000, f'{pr*1000:.0f} ms']], 6000, done=[0, 1], cur=[2]), kv=KV([['从库升主', f'{pr*1000:.0f} ms 后']], ['从库升主'])),
    step(f"写入恢复:X 的槽上的写线程从第一次出错到成功,总共 {statistics.median(t['errs_x'] for t in T):.0f} 次错误,恢复时间点约 kill 后 {rc*1000:.0f} ms(与升主几乎同时——新主库一升主,客户端刷新槽位表就能写)。整个不可用窗口约 {rc:.1f} 秒,是 cluster-node-timeout 的 {rc/3:.1f} 倍。", n=fl([['X 的槽', f'约 {rc:.1f} s 不可用'], ['其它槽', '几乎不受影响']], mark=[0], done=[1]), b=bars([['X 的槽:不可用', rc * 1000, f'{rc*1000:.0f} ms'], ['cluster-node-timeout', 3000, '3000 ms']], 6000, mark=[0]), kv=KV([['不可用窗口', f'约 {rc:.1f} s'], ['其它槽的写入错误', f"{statistics.median(t['errs_y'] for t in T):.0f} 次(瞬时)"]], ['不可用窗口'])),
    step(f"数据有没有丢:三次实验共确认 {acked} 次写入(每个 key 都回读校验),新主库上丢失 {lost} 个、值落后的 0 个。复制是异步的,理论上最后几条已确认的写入可能没来得及同步就丢——这三次没有发生,但不代表不会发生(见第 93 篇的窗口)。", n=fl([['已确认写入', str(acked)], ['丢失', str(lost)]], done=[0], mark=[1] if lost else []), kv=KV([['丢失', f'{lost} / {acked}']], ['丢失'])),
]
A = dict(
    n=75, series='redis', tags='Redis,Cluster,故障转移,真实验证,动画演示',
    desc=f'kill -9 一个 Redis Cluster 主库(cluster-node-timeout 3000 ms,3 次实验中位):kill 后 {pf*1000:.0f} ms 被标 PFAIL、{fa*1000:.0f} ms 升级 FAIL、{pr*1000:.0f} ms 从库升主;写入该主库槽位的客户端约 {rc:.1f} 秒后恢复,其它槽几乎不受影响;{acked} 次已确认写入回读校验丢失 {lost} 个。',
    lead='主库突然挂了,集群要多久才能恢复写入?这个问题的答案不是「秒级」这种模糊说法,而是一串有先后的事件:怀疑、确认、选举、升主。这篇真的 kill -9 一个主库,让两个写线程一直写着,把每个事件发生的毫秒数量出来,连做三次。',
    facts=[(f'{pf*1000:.0f} → {fa*1000:.0f} → {pr*1000:.0f} ms', 'kill 后 PFAIL → FAIL → 从库升主(中位数)'), (f'约 {rc:.1f} s', '该主库的槽上写入恢复所需时间(cluster-node-timeout 的 %.1f 倍)' % (rc / 3)), (f'{lost} / {acked}', '已确认写入在新主库上丢失的个数(3 次实验)')],
    body=[
        sec('做法', '', '<p>每次实验起一个新的 3 主 3 从集群(<code>cluster-node-timeout 3000</code>)。两个写线程各自用集群客户端不停 <code>SET</code>,每次间隔 3 ms:线程 X 只写将被杀掉的主库负责的槽,线程 Y 写另一个主库的槽。1 秒后对 X 主库 <code>kill -9</code>,同时每 10 ms 读一次三个幸存节点的 <code>CLUSTER NODES</code>,记录被杀节点何时被标 <code>fail?</code>(PFAIL)、何时变 <code>fail</code>、它的从库何时变成 <code>master</code>。结束后把线程 X 确认过的每一个 key 回读,检查是否丢失。重复三次。</p>'),
        sec('三次实验的事件时间线', '时间是 kill 之后的毫秒数;「写入恢复」是线程 X 最后一次报错之后第一次成功的时间', term('', out('r75')),
            f'<p>三次结果比较一致:PFAIL {rng("pfail")[0]*1000:.0f}–{rng("pfail")[1]*1000:.0f} ms,FAIL {rng("fail")[0]*1000:.0f}–{rng("fail")[1]*1000:.0f} ms,升主 {rng("promoted")[0]*1000:.0f}–{rng("promoted")[1]*1000:.0f} ms,写入恢复与升主几乎同时。X 槽上的写线程每次遇到 9–11 次错误;另一个写线程的槽在这一过程中出现过 1 次瞬时错误(我没有追查这一次错误的具体原因,重复三次都是 1 次)。</p>'),
        sec('每个阶段在等什么', '', '', f'<ul><li><b>PFAIL(约 {pf:.1f} s)</b>:其它节点等被杀节点超过 <code>cluster-node-timeout</code>(3 s)没回应,单方面标记「可能失败」。这是整个窗口里最长的一段,也是唯一直接由这个配置决定的一段。</li><li><b>FAIL(约 {fa:.1f} s)</b>:多数主库都同意它不可达,才广播 FAIL。</li><li><b>选举(约 {pr-fa:.1f} s)</b>:从库看到 FAIL 后先延迟一小段(日志里第 3 次是 {delay.group(1)} ms,rank #{delay.group(2)}),再发起选举、获得多数主库的票后升主(投票细节见第 76 篇)。</li><li><b>恢复</b>:新主库升主,客户端刷新槽位表(MOVED)后写入成功。</li></ul><p>所以不可用窗口大约是 <code>cluster-node-timeout</code> 的 {rc/3:.1f} 倍;调小 timeout 能缩短窗口,代价是网络抖动时更容易误判(这个取舍我没有实验)。</p>'),
        sec('已确认的写入丢了吗', '', '', f'<p>三次实验共 {acked} 次已确认的写入(每个 key 最后一次成功的值),回读全部命中,新主库上丢失 {lost} 个、值落后的 0 个。<b>但这不是保证</b>:Redis 复制是异步的,主库回复客户端时不等从库确认,理论上刚写入、还没同步到从库就被 kill 的那几条会丢。我的写线程每 3 ms 写一次、被 kill 的瞬间恰好没有遗留待同步的数据,所以 3 次都没撞上。想量这个窗口需要更高的写入压力,见第 93 篇。</p>'),
        sec('分步演示:一次故障转移的时间线', '', demo('Redis Cluster 故障转移', [('n', 'flow', '角色与状态'), ('b', 'bars', '事件时间(kill 后的毫秒)'), ('kv', 'kv', '要点')], steps, '本步的事件')),
    ],
    refs=[ENV_R + '。每次一个新的 3 主 3 从集群;kill -9 只杀主库进程(操作系统与网络正常),TCP 连接立刻被重置;时间取自我的采样脚本(10 ms 间隔),每个数字有约 10–20 ms 的观测误差', '没有验证:「PFAIL 升级为 FAIL 需要多数主库同意」是官方的设计说明,本文只观察到了 PFAIL→FAIL 的时间间隔,没有单独验证投票数;网络分区(而非进程被杀)下的时间线(第 83 篇)、cluster-node-timeout 取其它值时的关系、多个从库时的选举顺序(rank)、高写入压力下的数据丢失窗口、Linux 上的表现'],
)
