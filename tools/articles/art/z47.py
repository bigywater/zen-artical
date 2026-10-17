from lib import *
R = J('z47'); tlm = R['timeline']; w = R['write']
ns = [t for t, nm, m in tlm if m == '不服务' and t > 0]; ld_t = next((t for t, nm, m in tlm if m == 'leader' and t > min(ns)), None); heal_t = 8010
t_ns1, t_ns3 = min(ns), max(ns[:3])
def S(k): return [l for l in out('z47').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"把 leader 单独隔离(用 TCP 代理让它与另两个节点之间的节点间通信悄悄丢包,连接不断,客户端端口不受影响):约 +{t_ns1} ms 三个节点都变成「不服务」(follower 判定 leader 丢失、旧 leader 判定失去多数派,≈ syncLimit × tickTime = 1000 ms);多数派一侧在 +{ld_t} ms 才选出新 leader——这一次选举花了约 {(ld_t - t_ns1) / 1000:.1f} 秒,比正常选举(第 34 篇约 0.3 秒)慢得多,因为选举消息被丢弃、要等连接超时。我先后跑到过 +3.4 s 和 +{ld_t / 1000:.1f} s,差别很大。", t=tl(S(1)[:8]), mark=[3, 4, 5], done=[6, 7], kv=KV([['发现分区', f'≈ +{t_ns1} ms'], ['多数派恢复', f'+{ld_t} ms(各次差别大)']], ['发现分区'])),
    step(f"网络恢复(+{heal_t} ms)时,我的代理会断开所有连接,多数派一侧又经历一次重新选举,旧 leader 最终以 follower 身份回来(见下面的状态变化)。这次重选是我的实验方式造成的,真实网络恢复时不一定发生。", t=tl(S(1)[8:]), done=[0, 1, 2, 3, 4], kv=KV([['旧 leader 回来', '以 follower 加入']], ['旧 leader 回来'])),
    step(f"分区期间两侧的写入:多数派一侧的客户端(带重试)create /from-majority 成功,从分区开始到完成 {w['majority_ms']:.0f} ms(含故障检测与重新选举);连在旧 leader 上的客户端在分区前发出的 create /from-isolated,3 秒后仍 ready = True(收到了结果:失败),网络恢复后得到的是 {R['isolated_result']}。", t=tl(S(2)[:4]), done=[1], mark=[2, 3], kv=KV([['多数派一侧', f"写入成功({w['majority_ms']:.0f} ms)"], ['被隔离一侧', 'ConnectionLoss']], ['被隔离一侧'])),
    step(f"恢复后:/from-majority 存在({R['final']['maj']}),/from-isolated 不存在({R['final']['iso']});三个节点 Mode 为一个 leader + 两个 follower,Zxid 相同。被隔离侧的那次写没有被保留,集群没有分歧。", t=tl(S(2)[4:]), done=[0, 1, 2], kv=KV([['恢复后', '只保留多数派一侧的写入']], ['恢复后'])),
]
A = dict(
    n=47, series='zookeeper', tags='ZooKeeper,网络分区,集群恢复,真实验证,动画演示',
    desc=f'网络分区与集群恢复实测(TCP 代理悄悄丢包):隔离 leader 后约 1 s 内所有节点发现并「不服务」,多数派一侧在几秒内选出新 leader(各次差别大);被隔离侧的写得到 ConnectionLoss 且不会保留;恢复后一个 leader + 两个 follower,数据一致。',
    lead='真实的网络分区不是「立刻断开」而是「悄悄丢包」。这篇用一个会丢弃节点间流量的 TCP 代理把 leader 隔离出去,按毫秒记录各节点的角色变化,以及分区两侧的写入各是什么结果。',
    facts=[('≈ 1 s', '悄悄丢包下,follower 发现 leader 丢失的时间(syncLimit × tickTime)'), (f'{w["majority_ms"]:.0f} ms', '分区开始到多数派一侧的写入成功'), ('被隔离侧的写不保留', '恢复后读不到 /from-isolated')],
    body=[
        sec('各节点的角色时间线', '', term('', blk('z47', 1)), '<p>代理有两种断网方式:立刻关闭连接(检测很快),或悄悄丢包(要等超时)。我最先用了前者,发现节点几乎立刻就发现了故障,这与真实分区不同,所以改成了丢包。</p>'),
        sec('两侧的写入', '', term('', blk('z47', 2))),
        sec('分步演示', '', demo('网络分区', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群,tickTime=500、syncLimit=2;分区用 zkl.NetEnsemble(每对节点之间的 quorum / 选举连接各经过一个 TCP 代理,分区时代理丢弃全部数据但不断开连接,恢复时断开所有连接);客户端端口不经过代理', '没有验证:真实网络(iptables / 交换机)下的分区、非对称分区(A 能连 B,B 不能连 A)、分区时间很长、客户端也被分区(分区两侧的客户端行为取决于客户端库)'],
)
