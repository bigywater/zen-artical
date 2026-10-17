from lib import *
R = J('z35'); st = R['stale']; eq = R['equal']
def S(k): return [l for l in out('z35').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"投票比较:先比 epoch、再比 zxid、最后比 sid。场景:3 个节点,leader 是 {S(1)[0].split('=')[1].split('(')[0].strip()},停掉 sid 更大的 follower 再写 50 个 znode,然后杀 leader、重启那个落后的 follower——此时候选的两个节点里,sid 大的落后、sid 小的有最新数据。", t=tl(S(1)[:2]), kv=KV([['规则', 'epoch > zxid > sid']], ['规则'])),
    step(f"结果:新 leader 是 {st['new']}(sid 较小、有最新数据),落后的节点没有当选,尽管它的 sid 更大;两个节点的 zxid 分别是 0x200000000(新 leader,新 epoch 的起点)和 0x100000035(落后者)。有最新数据的节点当选——保证已经提交的事务不会丢。", t=tl(S(1)[2:5]), done=[1, 2], kv=KV([['有最新数据的节点', '当选(即使 sid 小)']], ['有最新数据的节点'])),
    step("落后节点的日志展示了它怎么改投:它先「新一轮选举:我(sid 3)提议 zxid=0x100000002」,收到自己的选票、再收到 sid=1 的选票(zxid=0x100000035 更新)后,把票改投给 sid=1,之后收到的选票也都是选 sid=1。", t=tl(S(1)[5:]), done=[0, 1, 2, 3, 4], kv=KV([['落后者', '看到更新的 zxid 后改投']], ['落后者'])),
    step(f"数据完全相同时,sid 大的占优,但谁先凑够多数派取决于启动时机:5 次独立启动的 3 节点集群,当选的 sid 分布是 {eq}——每次都是 2 号:节点按 1、2、3 的顺序启动,2 号与 1 号先凑齐多数派,3 号还没起来选举已经结束。", t=tl(S(2)), kv=KV([['全新集群', '先凑够多数派的当选,不一定是 sid 最大']], ['全新集群'])),
]
A = dict(
    n=35, series='zookeeper', tags='ZooKeeper,FastLeaderElection,选票,真实验证,动画演示',
    desc=f'FastLeaderElection 的选票比较实测:先比 epoch、再比 zxid、最后比 sid——落后的高 sid 节点落选、有最新数据的节点当选({st["new"]});全新集群 5 次启动都是 2 号当选(谁先凑够多数派取决于启动时机)。',
    lead='选 leader 看什么?sid 大的优先吗?这篇构造一个「sid 更大的节点数据落后」的场景,验证 FastLeaderElection 的选票比较规则;再看全新集群数据都一样时谁当选。',
    facts=[('epoch > zxid > sid', '选票的比较顺序'), ('数据新者当选', 'sid 更大的落后节点落选'), ('{2: 5}', '全新集群 5 次启动的当选 sid 分布(启动顺序 1→2→3)')],
    body=[
        sec('构造一个落后的候选者', '', term('', blk('z35', 1)), '<p>这样的规则保证:任何已经被多数派提交的事务,一定存在于新 leader 的日志里(多数派与多数派必有交集,而新 leader 是日志最新的)。这一段推理是对规则的解释,不是本实验直接测到的。</p>'),
        sec('数据相同时', '', term('', blk('z35', 2))),
        sec('分步演示', '', demo('选票比较', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;落后的节点是 sid 较大的 follower,通过先停它再写 50 个 znode 制造;选票来自 INFO 日志的 Notification', '没有验证:五个节点以上的选举、网络延迟不对称时的选举、选举轮次 round 的完整语义、leader 选择与 observer(observer 不参与,第 28 篇)'],
)
