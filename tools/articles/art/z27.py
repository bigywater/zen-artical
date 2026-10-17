from lib import *
R = J('z27'); lt = R['lat']; rd = R['read']
def S(k): return [l for l in out('z27').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("3 节点集群的角色:1 个 leader、2 个 follower。mntr 里 zk_synced_followers 和 zk_learners 只有 leader 才有值(= 2,表示 2 个 follower 已同步);follower 上这两项没有。leader 是集群里「唯一决定事务顺序」的节点。", t=tl(S(1)), done=[1], kv=KV([['leader', '决定写入顺序,有 synced_followers 指标'], ['follower', '服务读、转发写、参与投票']], ['leader'])),
    step(f"写请求的路径:连在 leader 上的客户端同步 create 中位 {lt['leader']:.2f} ms,连在 follower 上的 {lt['follower']:.2f} ms——follower 要多转发一跳到 leader,但这一跳的耗时被落盘 fsync 的耗时淹没了,没有观察到明显差别。", t=tl(S(2)), b=bars([['连 leader', lt['leader'], f"{lt['leader']:.2f} ms"], ['连 follower', lt['follower'], f"{lt['follower']:.2f} ms"]], max(lt.values()) * 1.2, done=[0, 1]), kv=KV([['写延迟', '两条路径差别不大(本机)']], ['写延迟'])),
    step(f"读请求的路径:连在 follower 上读 2000 次,leader 只多收到 {rd['via_follower']} 个包;连在 leader 上读 2000 次,leader 多收到 {rd['via_leader']} 个。读在连接的那个节点本地完成,不经过 leader。", t=tl(S(3)), done=[0], kv=KV([['读', '在被连接的节点本地完成']], ['读'])),
    step("通过 follower 写入之后,三个节点的 Zxid 完全一致(0x1000002… 同一个值):所有节点按同一个顺序应用了同一批事务。", t=tl(S(4)), done=[0], kv=KV([['zxid', '三个节点一致']], ['zxid'])),
]
A = dict(
    n=27, series='zookeeper', tags='ZooKeeper,集群角色,请求路径,真实验证,动画演示',
    desc=f'集群角色与请求路径实测(3 节点):leader 才有 zk_synced_followers;写通过 follower 要转发给 leader,但延迟差别被 fsync 淹没({lt["follower"]:.2f} vs {lt["leader"]:.2f} ms);读在连接的节点本地完成(连 follower 读 2000 次,leader 只多收 {rd["via_follower"]} 个包)。',
    lead='ZooKeeper 集群里的 leader 和 follower 各做什么?写和读分别走哪条路?这篇在 3 节点集群上用 mntr 和包计数把请求路径量出来。',
    facts=[('写 → leader', '不管连在哪个节点,写事务都由 leader 排序'), (f'+{rd["via_follower"]} 个包', '连在 follower 读 2000 次,leader 多收到的包数'), ('zxid 一致', '写完之后三个节点的 Zxid 相同')],
    body=[
        sec('三个角色的差别', '', term('', blk('z27', 1))),
        sec('写的路径', '', term('', blk('z27', 2)), '<p>这个测量里连 follower 的结果甚至略快,属于测量噪声(单机五个 JVM 抢同一块磁盘与 CPU),所以结论只能是「没有可见的差别」。</p>'),
        sec('读的路径', '', term('', blk('z27', 3))),
        sec('结果一致', '', term('', blk('z27', 4))),
        sec('分步演示', '', demo('集群角色', [('t', 'term', '输出'), ('b', 'bars', '写延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;延迟是 300 次同步 create 的中位数', '没有验证:follower 读到旧数据的概率(第 44 篇试了一个测法,没有观察到)、跨机房的转发延迟、observer 的路径(第 28、29 篇)、写请求转发的内部协议'],
)
