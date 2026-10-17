import json, re
from lib import *
R = J('r76'); A_, B_, C_ = R['A'], R['B'], R['C']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
ap = list(A_['promoted'].values())[0]
rep_a = [p for p in A_['diff'] if A_['diff'][p]['auth-req_sent'] > 0][0]
d_rep = A_['diff'][rep_a]
voters = sorted(p for p, d in A_['diff'].items() if d['auth-ack_sent'] > 0)
delay = re.search(r'delayed for (\d+) milliseconds \(rank #(\d+)', ' '.join(l for L in A_['replogs'].values() for l in L))
cp = sorted(C_['promoted'].values())
vc = sorted(p for p, d in C_['diff'].items() if d['auth-ack_sent'] > 0)
steps = [
    step(f"3 主 3 从,kill 掉 1 个主库 {A_['killed'][0]}。它的从库 {rep_a} 看到 FAIL 之后发起选举:日志「Start of election delayed for {delay.group(1)} milliseconds (rank #{delay.group(2)})」——先等一个随机加排名的延迟,再「Starting a failover election for epoch 7」。", n=fl([[f"主 {A_['killed'][0]}", '已死'], [f'从 {rep_a}', '发起选举 epoch 7'], ['其它两个主库', '投票'], ['其它两个从库', '不投票']], mark=[0], cur=[1]), kv=KV([['选举 epoch', '7'], ['延迟', f"{delay.group(1)} ms(rank #{delay.group(2)})"]], ['选举 epoch'])),
    step(f"从库向所有节点发 FAILOVER_AUTH_REQUEST:{rep_a} 的 CLUSTER INFO 里 auth-req_sent = {d_rep['auth-req_sent']}。两个幸存主库({', '.join(map(str, voters))})各回一票:auth-ack_sent = 1,日志「Failover auth granted to … for epoch 7」。两个幸存的从库也收到了请求(auth-req_received = 1),但 auth-ack_sent = 0——从库不投票。", n=fl([[f'从 {rep_a}', f"auth-req_sent {d_rep['auth-req_sent']},auth-ack_received {d_rep['auth-ack_received']}"], ['主库 ×2', 'auth-ack_sent 1'], ['从库 ×2', '收到请求,不回票']], cur=[0, 1]), kv=KV([['投票者', '只有主库'], ['得票', f"{d_rep['auth-ack_received']}"]], ['投票者'])),
    step(f"拿到 {d_rep['auth-ack_received']} 票(3 个主库里的多数是 2 票)→「Failover election won: I'm the new master」,kill 后约 {ap*1000:.0f} ms 升主,cluster_state = {A_['state']}。", n=fl([[f'{rep_a}', '新主库'], ['其它', '继续服务']], done=[0]), b=bars([['升主耗时', ap * 1000, f'{ap*1000:.0f} ms']], 6500, done=[0]), kv=KV([['结果', f'{rep_a} 升主,state = {A_["state"]}']], ['结果'])),
    step(f"同时 kill 掉 2 个主库({B_['killed'][0]}、{B_['killed'][1]}):只剩 1 个主库。15 秒里没有任何从库升主,cluster_state = {B_['state']}。更意外的是:所有幸存节点的 auth-req 计数都是 0——连选举都没发起。", n=fl([['主库 ×2', '已死'], ['唯一幸存的主库', '无法确认它们已 FAIL'], ['从库 ×3', '一直是从库']], mark=[0, 1]), kv=KV([['15 秒内升主', '无'], ['auth-req', '全是 0']], ['15 秒内升主'])),
    step("为什么没有选举?看角色:两个被杀的主库在幸存节点眼里始终是 master,fail?(PFAIL),没有升级成 fail。FAIL 要多数主库都认为它不可达才能确定,而 3 个主库只剩 1 个,凑不齐多数——从库只在看到 FAIL 之后才发起选举,所以卡在了投票之前的一步。", n=fl([['7410', 'master,fail?(PFAIL)'], ['7411', 'master,fail?(PFAIL)'], ['7412', 'master']], mark=[0, 1]), kv=KV([['卡住的位置', 'PFAIL → FAIL 之间'], ['角色', "master,fail?"]], ['卡住的位置'])),
    step(f"对照:5 主 5 从,同时 kill 2 个主库,还剩 3 个主库(5 个的多数)。两个从库都成功升主({cp[0]*1000:.0f} ms 和 {cp[1]*1000:.0f} ms),cluster_state = {C_['state']};3 个幸存主库各投出 2 票(auth-ack_sent = 2)。", n=fl([['5 主 5 从', 'kill 2 主'], ['3 个幸存主库', '各投 2 票'], ['2 个从库', '都升主']], done=[1, 2]), b=bars([['第一个升主', cp[0] * 1000, f'{cp[0]*1000:.0f} ms'], ['第二个升主', cp[1] * 1000, f'{cp[1]*1000:.0f} ms']], 6500, done=[0, 1]), kv=KV([['结果', f'两个从库都升主,state = {C_["state"]}']], ['结果'])),
]
A = dict(
    n=76, series='redis', tags='Redis,Cluster,选举,投票,真实验证,动画演示',
    desc=f'三组真实故障转移看投票:3 主 3 从杀 1 个主库,从库发 {d_rep["auth-req_sent"]} 条 auth-req,两个幸存主库各投 1 票(从库不投票)后升主;杀 2 个主库时只剩 1 个主库,被杀主库停在 PFAIL、没有任何从库发起选举,cluster_state 一直 fail;5 主 5 从杀 2 个仍有 3 个主库,两个从库都成功升主。',
    lead='故障转移的关键是「多数主库同意」。但这个「多数」在哪一步起作用、谁有投票权、什么时候即使没有选举也不可能成功?这篇用 CLUSTER INFO 里的投票消息计数、节点日志和角色表,把三种情形的每一票都数出来。',
    facts=[('只有主库投票', '从库收到 auth-req 但 auth-ack_sent 始终是 0'), ('PFAIL 卡住', '杀掉 3 个主库中的 2 个:被杀主库停在 master,fail?,没有选举发生'), ('5 主杀 2', f'还剩 3 个主库(多数),两个从库分别在 {cp[0]*1000:.0f} / {cp[1]*1000:.0f} ms 升主')],
    body=[
        sec('情形一:3 主 3 从,杀 1 个主库', '', term('', blk('r76', 1)), f'<p>从库看到 FAIL 之后先延迟 {delay.group(1)} ms(延迟 = 固定 500 ms + 随机 + 排名相关,这里是 rank #{delay.group(2)}——这个公式来自文档,我只看到了日志里的这个数),然后发起选举,<code>Starting a failover election for epoch 7</code>。它向所有节点发出 auth 请求({d_rep["auth-req_sent"]} 条),收到 {d_rep["auth-ack_received"]} 票:两个幸存主库各给一票(日志 <code>Failover auth granted to … for epoch 7</code>)。两个从库虽然也收到了请求,但<b>没有投票</b>。3 个主库的多数是 2,拿到 2 票就赢,<code>Failover election won</code>。</p>'),
        sec('情形二:杀 2 个主库,选举根本不会开始', '', term('', blk('r76', 2)), f'<p>这是最容易被误解的一种:3 主 3 从里同时杀掉 2 个主库,你可能以为「从库发起选举、但拿不到票」。实际上<b>一条 auth 请求都没有发出</b>——所有幸存节点的 <code>auth-req</code> 计数全是 0。看幸存节点眼中被杀主库的角色:<code>master,fail?</code>,一直是 PFAIL,没有变成 <code>fail</code>。我推断原因是:把 PFAIL 确认成 FAIL 需要多数主库同意,3 个主库只剩 1 个凑不齐,从库只在看到 FAIL 后才发起选举。这个「需要多数主库」的机制是官方设计说明,本次实验的证据是「没有 FAIL、没有选举」这个现象,我没有再去区分其它可能的原因。结果:{B_["state"]},15 秒里没有任何从库升主。</p>'),
        sec('情形三:5 主 5 从,杀 2 个主库', '', term('', blk('r76', 3)), f'<p>杀 2 个主库后还剩 3 个主库——5 个的多数。两个失去主库的从库都成功升主(kill 后 {cp[0]*1000:.0f} ms 和 {cp[1]*1000:.0f} ms),<code>cluster_state = {C_["state"]}</code>。三个幸存主库每个都投出了 2 票(auth-ack_sent = 2,分别投给两个候选);先升主的从库随后也对另一个候选投了票(它的 <code>auth-ack_sent = 1</code>),推测是因为它此时已经是主库,有了投票权。</p>'),
        sec('结论:「多数」指的是主库,不是所有节点', '', '<p>三个观察合起来:投票权只属于主库(从库不投票);多数是相对<b>所有主库</b>的多数(3 主要 2、5 主要 3);而一旦幸存主库不足多数,连「确认主库已死」这一步都过不去,选举都不会开始。所以规划集群时,主库数量决定了能同时容忍几个主库宕机(3 主 → 1 个,5 主 → 2 个),从库数量只决定每个分片有没有可升的候选。</p>'),
        sec('分步演示:三种情形的投票', '', demo('Redis Cluster 故障转移投票', [('n', 'flow', '节点与状态'), ('b', 'bars', '升主耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。三组各起一个新集群;票数来自各节点 CLUSTER INFO 中 cluster_stats_messages_auth-req/auth-ack 计数在 kill 前后的差值;kill -9 只杀进程', '没有验证:选举延迟的公式(文档说法)、从库数量大于 1 时不同 rank 的行为、网络分区下的投票(第 83 篇)、「杀 2 个主库」情形里恢复其中一个主库后集群的恢复过程(第 84 篇)'],
)
