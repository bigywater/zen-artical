import json
from lib import *
R = J('r74'); meet = R['meet']; hs = R['hs']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
import re
t = {i: round(x[0] * 1000) for i, x in enumerate(meet)}
sec3 = blk('r74', 3)
def first(port, known):
    m = re.search(r'\+\s*(\d+) ms\s+%d 认识的节点端口: \[%s\]' % (port, known), sec3)
    return int(m.group(1))
g_a = first(7382, '7381'); g_b = first(7382, '7380, 7381'); g_c = first(7380, '7381, 7382'); g_d = first(7381, '7380, 7382')
eps = []
for l in blk('r74', 7).splitlines():
    p_ = l.split()
    if len(p_) > 8 and 'master' in p_[2] + p_[3]: eps.append((p_[1].split('@')[0].split(':')[1], int(p_[6])))
eps = sorted(eps); ep_txt = '、'.join(str(e) for _, e in eps)
steps = [
    step("三个刚启动的集群节点(cluster-enabled yes)互相不认识:各自 known_nodes = 1(自己)、cluster_state = fail、current_epoch = 0。", n=fl([['7380', '只认识自己'], ['7381', '只认识自己'], ['7382', '只认识自己']]), kv=KV([['cluster_state', 'fail'], ['known_nodes', '1']], ['cluster_state'])),
    step(f"在 7380 上执行 CLUSTER MEET 127.0.0.1 7381:立刻在 7380 的节点表里出现一条 handshake/disconnected 的记录(此时还不知道对方的节点 ID)。", n=fl([['7380', 'handshake → 7381'], ['7381', '还不知道 7380']], cur=[0]), t=tm([f'+{t[0]} ms  7380 眼中:7381 = handshake/disconnected', f'+{t[1]} ms  7381 眼中:(空)'], cur=[0]), kv=KV([['状态', 'handshake / disconnected']], ['状态'])),
    step(f"约 {t[2]} ms 后 7380 连上了 7381(handshake/connected);同时 7381 也开始出现 7380 的 handshake 记录(+{t[3]} ms)。", n=fl([['7380', 'connected'], ['7381', 'handshake ← 7380']], cur=[0, 1]), t=tm([f'+{t[2]} ms  7380 眼中:7381 = handshake/connected', f'+{t[3]} ms  7381 眼中:7380 = handshake/disconnected'], cur=[0, 1]), kv=KV([['握手', '双向进行']], ['握手'])),
    step(f"握手完成:+{t[4]} ms 7380 眼中的 7381 变成 master/connected(拿到了对方的真实 ID 与角色),+{t[5]} ms 7381 眼中的 7380 也是 master/connected。两个节点直接互相认识只用了约 {t[5]} ms。", n=fl([['7380', 'master/connected'], ['7381', 'master/connected']], done=[0, 1]), t=tm([f'+{t[4]} ms  7380: 7381 = master/connected', f'+{t[5]} ms  7381: 7380 = master/connected'], mark=[0, 1]), kv=KV([['耗时', f'约 {t[5]} ms']], ['耗时'])),
    step(f"7381 再去 MEET 7382——7380 和 7382 不直接见面。7381 在 +{g_d} ms 就认识了 7382,7382 在 +{g_a} ms 认识 7381;之后靠 gossip:7382 在 +{g_b} ms 知道了 7380,7380 在 +{g_c} ms 才知道 7382。", n=fl([['7380', f'+{g_c} ms 才知道 7382'], ['7381', '中间人'], ['7382', f'+{g_b} ms 知道 7380']], cur=[1], done=[0, 2]), kv=KV([['三个节点互相认识', f"{R['full_ms']:.0f} ms"]], ['三个节点互相认识'])),
    step(f"握手完成之后每个节点 known_nodes = 3,但 cluster_state 仍是 fail——槽位还没分配。给三个节点各分一段槽位后,约 {R['ok_ms']/1000:.1f} s 才都变成 ok。current_epoch 是 2(握手期间已经产生了 epoch)。", n=fl([['known_nodes', '3'], ['cluster_state', 'fail → ok'], ['current_epoch', '2']], done=[0, 2], cur=[1]), kv=KV([['ADDSLOTS → ok', f"{R['ok_ms']/1000:.1f} s"]], ['ADDSLOTS → ok'])),
    step(f"握手对象不存在时:CLUSTER MEET 127.0.0.1 9(没人监听)。7380 的节点表里出现 handshake 节点,{hs[1]/1000:.1f} 秒后消失、known_nodes 仍是 3——握手有超时,不会永远挂着(本实验 cluster-node-timeout 是 3000 ms)。", n=fl([['127.0.0.1:9', f'handshake → {hs[1]/1000:.1f} s 后被丢弃']], mark=[0]), kv=KV([['handshake 存活', f'{hs[1]/1000:.2f} s']], ['handshake 存活'])),
    step(f"节点的关系被写进 nodes.conf:每行一个节点(ID、地址@总线端口、角色、epoch、链路状态、槽位),最后一行 vars currentEpoch 2 lastVoteEpoch 0。按端口 7380 / 7381 / 7382 排序,三个主库的 configEpoch 分别是 {ep_txt}——三个 configEpoch 互不相同(它们是怎么分开的,见第 77 篇)。", n=fl([['nodes.conf', '每行一个节点 + vars 行']], cur=[0]), kv=KV([['vars', 'currentEpoch 2 lastVoteEpoch 0']], ['vars'])),
]
A = dict(
    n=74, series='redis', tags='Redis,Cluster,握手,Gossip,真实验证,动画演示',
    desc=f'从零观察 Redis Cluster 节点握手:CLUSTER MEET 后约 {t[5]} ms 双方互相认识(handshake/disconnected → handshake/connected → master/connected);第三个节点只 MEET 中间人,靠 gossip 在 {R["full_ms"]:.0f} ms 内互相发现;分配槽位后 cluster_state 约 {R["ok_ms"]/1000:.1f} s 才变 ok;MEET 一个不存在的地址,handshake 记录 {hs[1]/1000:.1f} s 后被丢弃。',
    lead='新节点是怎么加入集群的?你只对一个节点说了一句 CLUSTER MEET,其它节点怎么知道它?这篇把三个空节点从「互不认识」到「集群 ok」的全过程,按毫秒采样打印出来:握手的几个状态、gossip 的传播延迟、cluster_state 什么时候变 ok,以及握手一个不存在的节点会发生什么。',
    facts=[(f'约 {t[5]} ms', 'CLUSTER MEET 后两个节点互相认识(master/connected)'), (f'{R["full_ms"]:.0f} ms', '第三个节点只 MEET 中间人,靠 gossip 三方互相认识'), (f'{hs[1]/1000:.1f} s', 'MEET 一个不存在地址时 handshake 记录的存活时间')],
    body=[
        sec('起点:三个互不认识的节点', '', term('', blk('r74', 1)), '<p>启动后各自只认识自己:<code>known_nodes = 1</code>,没有槽位所以 <code>cluster_state = fail</code>,<code>current_epoch = 0</code>。</p>'),
        sec('CLUSTER MEET:直接握手', '每 10 ms 采样两端的 CLUSTER NODES,只打印变化', term('', blk('r74', 2)), f'<p>{t[0]} ms 时 7380 的节点表里出现 <code>handshake/disconnected</code>——还不知道对方的 ID,用一个临时的随机 ID 占位;连上之后是 <code>handshake/connected</code>({t[2]} ms);对方回应后拿到真实 ID 与角色,变成 <code>master/connected</code>({t[4]} ms)。另一端(7381)比 7380 晚一点才认出 7380({t[5]} ms)。整个过程约 {t[5]} ms。</p>'),
        sec('gossip:不需要两两 MEET', '', term('', blk('r74', 3)), f'<p>只让 7381 去 MEET 7382:7381 立刻认识了两个邻居,7382 认识了 7381(+{g_a} ms);而 7380 与 7382 互相不知道对方。它们通过 gossip(节点之间的心跳消息里附带的「我认识的其它节点」)传播:7382 在 +{g_b} ms 学到了 7380,7380 在 +{g_c} ms 才学到 7382——比直接握手慢一个数量级(约每秒一轮心跳)。所以<b>新节点只要 MEET 集群里任何一个节点,不需要逐个 MEET;但完全互相认识需要 1–2 秒</b>。这个延迟是这台实验机上的一次测量,不同规模的集群会不同。</p>'),
        sec('握手之后与分配槽位', '', term('', blk('r74', 4)), '', term('', blk('r74', 5)), f'<p>三个节点都知道另外两个之后 <code>known_nodes = 3</code>,但 <code>cluster_state</code> 仍是 <code>fail</code>——因为 16384 个槽都没有主库负责。分配槽位后大约 {R["ok_ms"]/1000:.1f} 秒三个节点才都变成 <code>ok</code>(状态更新不是立即的,我没有拆开这 {R["ok_ms"]/1000:.1f} 秒各是什么等待)。</p>'),
        sec('握手一个不存在的节点', '', term('', blk('r74', 6)), f'<p><code>CLUSTER MEET 127.0.0.1 9 10009</code> 之后,节点表里立刻出现一个 <code>handshake</code> 节点,{hs[1]/1000:.1f} 秒后被丢弃,<code>known_nodes</code> 仍是 3。握手不会永远挂着;这里的时长与 <code>cluster-node-timeout</code>(3000 ms)吻合,我没有改这个配置验证它们的关系。</p>'),
        sec('持久化:nodes.conf', '', term('', blk('r74', 7)), f'<p>节点关系写在 <code>nodes.conf</code>:每行 <code>ID 地址@总线端口 角色 主ID ping 时间 pong 时间 configEpoch 链路状态 槽位</code>,最后一行 <code>vars currentEpoch … lastVoteEpoch …</code>。按端口排序三个主库的 configEpoch 是 {ep_txt}——互不相同(第 77 篇讨论它们怎么分开)。</p>'),
        sec('分步演示:从互不认识到 cluster ok', '', demo('Redis Cluster 节点握手', [('n', 'flow', '节点与状态'), ('t', 'term', '时间线'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。三个新启动的集群节点,cluster-node-timeout 3000;每 10 ms 采样 CLUSTER NODES 的变化', '没有验证:更多节点时 gossip 的收敛时间、跨机器网络下的握手耗时、MEET 时指定不同总线端口以外的参数(如 cluster-announce-*)、cluster_state 从 fail 变 ok 的 3 秒里的具体等待项'],
)
