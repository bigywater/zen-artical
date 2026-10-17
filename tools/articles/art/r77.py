import json, statistics
from lib import *
R = J('r77'); T = R['trials']; col = R['collision']; ini = R['init']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
t1 = T[0]; X = str(t1['X']); rep = str(t1['rep'])
e0 = list(ini.values())[0][0]
lost = sum(1 for t in T if t['write_after_cont'] == 'OK' and t['final_new'] == 'after-failover')
conv = [t['conv'] * 1000 for t in T]
steps = [
    step(f"两种 epoch:current_epoch 是集群级的「逻辑时钟」,所有节点尽量对齐;my_epoch(configEpoch)是每个主库自己「槽位归属的版本号」,从库的 my_epoch 等于它主库的。新建的 3 主 3 从集群里:三个主库 configEpoch 是 1、2、3,current_epoch 是 {e0},三个从库的 my_epoch 分别是 1、2、3(与各自主库相同)。", n=fl([['主 A', 'configEpoch 1'], ['主 B', 'configEpoch 2'], ['主 C', 'configEpoch 3'], ['从 ×3', 'my_epoch = 各自主库']], done=[0, 1, 2]), kv=KV([['current_epoch', '6(所有节点相同)']], ['current_epoch'])),
    step("configEpoch 冲突:我手工把两个新节点都设成 configEpoch 5(CLUSTER SET-CONFIG-EPOCH),再让它们握手。约 116 ms 内服务器自己解决:其中一个的 configEpoch 被推进成 6,另一个保持 5,current_epoch 也变成 6——不需要人工干预。第三个节点(0)也对齐了 current_epoch,但它的 configEpoch 仍是 0。", n=fl([['节点 1', '5 → 6(被推进)'], ['节点 2', '5(保留)'], ['节点 3', '0(configEpoch 不变)']], cur=[0], done=[1]), kv=KV([['冲突', '两个 configEpoch = 5'], ['结果', '一个变 6,current_epoch = 6']], ['结果'])),
    step(f"主库 X({X})被 SIGSTOP 冻结(进程还在,只是不响应)。约 {statistics.median(t['prom'] for t in T):.1f} s 后它的从库({rep})升主,升主时向集群申请新的 epoch:current_epoch 6 → 7,新主库的 configEpoch 也变成 7(比旧主库的 2 大)。", n=fl([[f'旧主 {X}', '冻结,configEpoch 2'], [f'从 {rep}', '升主,configEpoch 7']], mark=[0], cur=[1]), kv=KV([['新主库的 configEpoch', '2 → 7'], ['current_epoch', '6 → 7']], ['新主库的 configEpoch'])),
    step(f"SIGCONT 解冻旧主库:它还以为自己是主库。解冻后 {t1['write_ms']:.1f} ms 我经旧连接对它发了一次 SET,返回 {t1['write_after_cont']}——旧主库接受了一次写入!三次实验的结果一样({[t['write_after_cont'] for t in T]}):解冻后旧主库还没收到新 epoch 的消息,不知道槽已经换了主人。", n=fl([[f'旧主 {X}', '刚解冻,以为自己还是主'], ['客户端(旧连接)', 'SET → OK']], mark=[0, 1]), kv=KV([['解冻后首次写', 'OK(被接受)']], ['解冻后首次写'])),
    step(f"很快收到新主库的消息:旧主库看到更高的 configEpoch(7)声称拥有同样的槽 → 认输,把自己重新配置成新主库的从库(我没有抓取这一步的日志,只观察到了角色变化)。三次分别用了 {conv[0]:.0f}、{conv[1]:.0f}、{conv[2]:.0f} ms,它的 epoch 变成 (7, 7)。", n=fl([[f'旧主 {X}', '→ 从库(epoch 7)'], [f'新主 {rep}', 'configEpoch 7']], done=[0, 1]), b=bars([[f'第 {i+1} 次:变成从库', c, f'{c:.0f} ms'] for i, c in enumerate(conv)], 20, done=[0, 1, 2]), kv=KV([['旧主变从库', f'{min(conv):.0f}–{max(conv):.0f} ms']], ['旧主变从库'])),
    step(f"代价:那次被接受的 SET(stale-write)去哪了?最终新主库上这个 key 的值是「after-failover」——新主库那边我在故障转移之后写的值;旧主库变成从库后从新主库全量/部分同步,它自己那次写入被覆盖丢弃。{lost}/{len(T)} 次实验里,被回复 OK 的写入最终丢失了。", n=fl([['客户端看到', 'SET stale-write → OK'], ['新主库最终值', 'after-failover'], ['stale-write', '丢失']], mark=[2]), kv=KV([['被 OK 的写入丢失', f'{lost} / {len(T)}']], ['被 OK 的写入丢失'])),
]
A = dict(
    n=77, series='redis', tags='Redis,Cluster,Epoch,真实验证,动画演示',
    desc=f'验证 Redis Cluster 的两种 epoch:新建 3 主 3 从集群 configEpoch 是 1/2/3、current_epoch 6;手工制造两个 configEpoch = 5 的冲突,握手后约 116 ms 内自动分开(一个变 6);冻结旧主库再解冻,新主库的 configEpoch 升到 7,旧主库解冻后仍接受了一次写入(3/3 次),随后 {min(conv):.0f}–{max(conv):.0f} ms 变成从库,该次被 OK 的写入丢失。',
    lead='Redis Cluster 里 epoch 到处都是:CLUSTER INFO 里有 cluster_current_epoch 和 cluster_my_epoch,nodes.conf 里每一行有 epoch,日志里选举叫「for epoch 7」。它们各是什么、谁比谁大意味着什么?这篇通过三个可复现的实验来看:新建集群、人为制造冲突、以及冻结/解冻一个旧主库时 epoch 如何决定「谁的槽位声明有效」——顺便发现一个能丢数据的窗口。',
    facts=[('两种 epoch', 'current_epoch(集群逻辑时钟)与 configEpoch(每个主库槽位归属的版本号)'), ('约 116 ms', '两个 configEpoch = 5 的节点握手后,服务器自动分开所用的时间'), (f'{lost} / {len(T)}', '旧主库解冻后仍回复 OK、随后却丢失的写入次数')],
    body=[
        sec('新建的集群里的 epoch', '', term('', blk('r77', 1)), '<p>每个节点的 <code>CLUSTER INFO</code> 有两个 epoch:<code>cluster_current_epoch</code>(整个集群的逻辑时钟,所有节点尽量保持一致,这里都是 6)和 <code>cluster_my_epoch</code>(本节点的 configEpoch)。三个主库的 configEpoch 依次是 1、2、3,是 <code>--cluster create</code> 时分配的;每个从库的 my_epoch 等于它主库的。</p>'),
        sec('configEpoch 冲突会自动解决', '', term('', blk('r77', 2)), f'<p>configEpoch 用来在两个节点都声称拥有同一个槽时分出胜负,所以每个主库必须有<b>不同</b>的值。我用 <code>CLUSTER SET-CONFIG-EPOCH</code> 手工把两个新节点都设成 5,让它们握手:约 116 ms 内其中一个的 configEpoch 被推进到 6(同时 current_epoch 成为 6),另一个保持 5——冲突消失了。第三个节点没有设置,它的 configEpoch 保持 0,但 current_epoch 与集群对齐。哪一个被推进由什么规则决定(我推测与节点 ID 有关,官方文档也是这么说),我没有做对照验证。</p>'),
        sec('冻结旧主库:更大的 epoch 赢', '用 SIGSTOP 冻结,SIGCONT 恢复;重复三次', term('', blk('r77', 3)), f'<p>冻结旧主库直到从库升主(约 {statistics.median(t["prom"] for t in T):.1f} s)。升主的从库申请了新的 epoch:<code>current_epoch</code> 6 → 7,新主库的 configEpoch 也是 7,比旧主库的 2 大。解冻旧主库之后,它收到新主库对同一批槽位的声明——configEpoch 更大者胜出,于是旧主库把自己重新配置为新主库的从库,epoch 变成 (7, 7),用时 {min(conv):.0f}–{max(conv):.0f} ms。</p>'),
        sec('那 10 ms 里发生了什么:一次被接受的写入', '', '', f'<p>关键在解冻的那一瞬间:旧主库进程恢复运行,但它还没收到新 epoch 的消息,仍然以为自己是这些槽位的主库。我提前打开了一条到旧主库的连接,解冻后立刻(约 {t1["write_ms"]:.1f} ms 内)发一次 <code>SET</code>:三次实验里它都返回了 <b>OK</b>。随后旧主库降为从库、与新主库同步,<b>这次被 OK 的写入被丢弃</b>:最终该 key 在新主库上的值是故障转移之后写入的 <code>after-failover</code>。这是「已确认的写入在故障转移中丢失」的一个具体窗口,长度在毫秒量级,并且需要「客户端还连着旧主库」这个条件才会撞上。这类窗口的更多形态见第 93 篇。</p><p>注意这里用的是冻结/解冻(进程暂停后恢复),它对应的是「主库因 GC/虚拟机暂停等原因暂时假死」这类场景;和第 75 篇 kill -9(进程彻底消失)不同,后者不会有「旧主库醒来」的这一幕。</p>'),
        sec('分步演示:epoch 如何决定谁是主', '', demo('Redis Cluster Epoch', [('n', 'flow', '节点与 epoch'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。冲突实验用三个新节点;冻结实验每次一个新的 3 主 3 从集群,冻结用 SIGSTOP、恢复用 SIGCONT,「解冻后的写入」通过冻结前已经建立好的连接发送', '没有验证:冲突时到底由哪个节点让步的规则(只观察到一次)、更长的冻结时间、多个从库的选举 epoch、写入通过新建连接(而不是旧连接)时是否同样被接受、cluster-replica-no-failover 等选项的影响'],
)
