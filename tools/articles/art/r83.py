import json, statistics
from lib import *
R = J('r83'); T = R['trials']
P = J('r75')['trials']; p_lo = min(t['promoted'] for t in P); p_hi = max(t['promoted'] for t in P)
fail_t = [t['states']['fail'] for t in T]; rej_t = [t['first_reject'] for t in T]; ok_n = [t['ok_frozen'] for t in T]; rej_n = [t['rej'] for t in T]; heal = [t['heal_ok'] for t in T]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
mn = lambda v: min(v) * 1000; mx = lambda v: max(v) * 1000
steps = [
    step("模拟「少数派被隔离」:3 主 3 从集群(cluster-node-timeout 3000 ms),主库 X 仍在运行并被客户端每 5 ms 写一次;把其余 5 个节点全部 SIGSTOP——从 X 的角度看,它和所有节点断开了。(这是模拟:其余节点是暂停的,不是活着但不可达,所以看不到「多数派那一侧」在做什么——那一侧的行为见第 75 篇。)", n=fl([['主库 X', '运行,收到写入'], ['其余 5 个节点', '被 SIGSTOP(X 看来是断开)']], cur=[0], mark=[1]), kv=KV([['X', '孤立(少数派)']], ['X'])),
    step(f"X 不会立刻停止服务:它要等其它节点超过 node-timeout 没有心跳,才会认为自己联系不上多数主库。三次实验里,X 眼中 cluster_state 变成 fail 用了 {mn(fail_t):.0f}–{mx(fail_t):.0f} ms;这之前 X 一直是 ok。", n=fl([['X', '仍 ok,继续接受写入']], cur=[0]), b=bars([[f'第 {i+1} 次:X 变 fail', t * 1000, f'{t*1000:.0f} ms'] for i, t in enumerate(fail_t)] + [['cluster-node-timeout', 3000, '3000 ms']], 5000, mark=[0, 1, 2]), kv=KV([['X 转 fail', f'{mn(fail_t):.0f}–{mx(fail_t):.0f} ms']], ['X 转 fail'])),
    step(f"这段窗口里 X 照常接受写入:12 秒观察期里被接受的写入 {min(ok_n)}–{max(ok_n)} 条(每 5 ms 一条 ≈ 头 3–4 秒的写入)。第一条被拒的写入出现在 {mn(rej_t):.0f}–{mx(rej_t):.0f} ms。如果这段时间里多数派那一侧已经把它的从库升了主,这些写入就是可能丢失的(在真实分区里会发生冲突;我这里另一侧是暂停的,没有验证这一点)。", n=fl([['X', f'接受 {min(ok_n)}–{max(ok_n)} 条,然后开始拒绝']], mark=[0]), b=bars([[f'第 {i+1} 次:被接受的写入', n_, str(n_)] for i, n_ in enumerate(ok_n)], max(ok_n) * 1.2, done=[0, 1, 2]), kv=KV([['窗口内被接受的写入', f'{min(ok_n)}–{max(ok_n)} 条']], ['窗口内被接受的写入'])),
    step(f"之后 X 拒绝所有写入(和读):错误是 CLUSTERDOWN The cluster is down;12 秒观察期里被拒 {min(rej_n)}–{max(rej_n)} 条。少数派一侧「宁可不可用,也不接受写入」。", n=fl([['X', 'CLUSTERDOWN']], mark=[0]), b=bars([[f'第 {i+1} 次:被拒的写入', n_, str(n_)] for i, n_ in enumerate(rej_n)], max(rej_n) * 1.2, mark=[0, 1, 2]), kv=KV([['被拒写入', f'{min(rej_n)}–{max(rej_n)} 条'], ['错误', 'CLUSTERDOWN']], ['错误'])),
    step(f"恢复:SIGCONT 让其余节点回来,X 眼中的 cluster_state 约 {mn(heal):.0f}–{mx(heal):.0f} ms 后回到 ok,角色仍是原来的 3 主 3 从(暂停 12 秒没有触发故障转移;我的解释是它们同时暂停、同时恢复,没有哪个节点先判定别人死了,这个解释没有验证)。", n=fl([['X', 'cluster_state: fail → ok'], ['其余节点', '恢复']], done=[0, 1]), b=bars([[f'第 {i+1} 次:恢复到 ok', h * 1000, f'{h*1000:.0f} ms'] for i, h in enumerate(heal)], 4000, done=[0, 1, 2]), kv=KV([['恢复', f'{mn(heal):.0f}–{mx(heal):.0f} ms']], ['恢复'])),
]
A = dict(
    n=83, series='redis', tags='Redis,Cluster,网络分区,真实验证,动画演示',
    desc=f'模拟少数派被隔离(3 主集群里只让主库 X 留下运行,其余节点暂停 12 秒):X 在 {mn(rej_t):.0f}–{mx(rej_t):.0f} ms(cluster-node-timeout 3000 ms)之内仍接受写入(窗口内 {min(ok_n)}–{max(ok_n)} 条),之后 cluster_state 变 fail、拒绝所有读写(CLUSTERDOWN);其余节点恢复后约 {mn(heal):.0f}–{mx(heal):.0f} ms 回到 ok。',
    lead='网络分区是分布式系统最难的问题。Redis Cluster 的策略是:少数派一侧不能继续写。这篇不谈理论,量一个具体问题:一个被隔离的主库,在自己意识到「联系不上多数」之前,还会接受多久的写入?意识到之后它的表现如何?(我没有办法在这台 macOS 上制造真正的网络分区,用的是「暂停其余节点」的等价模拟,局限写在文中。)',
    facts=[(f'{mn(rej_t):.0f}–{mx(rej_t):.0f} ms', '被隔离的主库上第一条被拒写入出现的时间(cluster-node-timeout 3000 ms)'), (f'{min(ok_n)}–{max(ok_n)} 条', '这段窗口里(约头几秒)被接受的写入'), ('CLUSTERDOWN', '之后所有读写的错误')],
    body=[
        sec('怎么模拟', '', '<p>真正的分区需要在网络层丢包(iptables、pfctl 之类),这台 macOS 上我没有权限做。等价的办法:让被观察的主库 X 保持运行,把<b>其余所有节点</b>用 <code>SIGSTOP</code> 暂停——对 X 而言,「其余所有节点都不再回应」和「被分区到少数派」是同样的。X 被一个客户端每 5 ms 写一次。局限:另一侧的节点是被暂停的,而不是活着的多数派,所以我<b>看不到「多数派一侧同时升主、产生两个主库」的冲突</b>,只能看到少数派一侧自己的行为。</p>'),
        sec('少数派一侧:先照常写,然后拒绝', '重复三次', term('', blk('r83', 1)),
            f'<p>三次结果稳定:X 在 {mn(fail_t):.0f}–{mx(fail_t):.0f} ms 时判定自己联系不到多数主库,<code>cluster_state</code> 变成 <code>fail</code>——比 <code>cluster-node-timeout</code>(3000 ms)长一点,因为要先经过 PFAIL 判断。<b>在这之前,X 一直照常接受写入</b>(观察期里被接受 {min(ok_n)}–{max(ok_n)} 条,就是头 3–4 秒每 5 ms 写的那些);之后 X 拒绝所有读写,错误是 <code>CLUSTERDOWN The cluster is down</code>({min(rej_n)}–{max(rej_n)} 条被拒)。</p>'),
        sec('这个窗口意味着什么', '', f'<p>如果这是一次真正的分区,多数派一侧的从库会在 kill 后约 5 秒升主(第 75 篇:从 kill 起 {p_lo:.1f}–{p_hi:.1f} s),而这里被隔离主库停止写入的时间是 {mn(rej_t)/1000:.1f}–{mx(rej_t)/1000:.1f} s——<b>在本机这组参数下,少数派主库先停,多数派再升主,两者没有重叠</b>。这个推断来自两个不同实验的时间对比(第 75 篇的时间是 kill -9 而不是分区,两边的时钟精度也不同),不是同一次实验里同时观察到的;但它解释了为什么默认参数下「被隔离的旧主库」通常不会和新主库同时接受写入。而窗口本身(头几秒里被接受的写入)如果分区发生的时间点恰好让多数派更早判定,仍然有丢失的可能(第 77、93 篇)。</p>'),
        sec('恢复', '', '<p>其余节点恢复后,X 眼中的 <code>cluster_state</code> 约 3 秒回到 ok,角色仍是原来的 3 主 3 从,没有发生故障转移(我的解释是所有节点同时冻结、同时恢复,没有哪个先判定对方死了,没有验证)。真实的分区里,多数派一侧会在分区期间完成故障转移,愈合后旧主库变成从库(第 77 篇的场景)。</p>'),
        sec('分步演示:少数派一侧的行为', '', demo('Redis Cluster 网络分区', [('n', 'flow', '节点'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。用 SIGSTOP/SIGCONT 暂停其余 5 个节点模拟「X 被隔离」;cluster-node-timeout 3000;X 由单个客户端每 5 ms 直连写入', '没有验证:真正的网络分区(丢包、单向不可达、部分节点可达)、多数派一侧同时故障转移时的冲突与数据丢失(第 77、93 篇覆盖了相关的窗口)、cluster-require-full-coverage、cluster-allow-reads-when-down、cluster-replica-validity-factor 与 cluster-slave-no-failover 的影响'],
)
