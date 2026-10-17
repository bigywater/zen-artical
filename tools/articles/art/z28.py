from lib import *
R = J('z28'); lt = R['lat']; lm = R['leader_m']
def S(k): return [l for l in out('z28').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"3 个投票节点加 2 个 observer:srvr 的 Mode 是 follower / leader / follower / observer / observer。observer 在配置里的写法:自己的 zoo.cfg 里加 peerType=observer,所有节点的 server 列表里它那一行末尾加 :observer(server.4=127.0.0.1:7403:7503:observer)。leader 的 mntr 里 zk_synced_followers = {lm['zk_synced_followers']}、zk_synced_observers = {lm['zk_synced_observers']}。", t=tl(S(1)), done=[0, 1, 2, 3, 4], kv=KV([['observer', '不投票,只同步数据、服务读'], ['配置', 'peerType=observer + server 行加 :observer']], ['observer'])),
    step("observer 不参与多数派:3 个投票节点停掉 2 个(只剩 1 个投票节点 + 2 个 observer,共 3 个活着),所有存活节点都变成「不服务」,通过 observer 写入失败——名单里有 5 个节点,但「多数派」只按 3 个投票节点计算(需要 2 个)。", t=tl(S(2)), mark=[0, 1], kv=KV([['多数派', '只按投票节点算,observer 不算']], ['多数派'])),
    step("恢复 1 个投票节点(2/3 投票节点 + 2 个 observer):恢复服务;通过 observer 写入成功——observer 把写请求转给 leader,读回 v。observer 也能接受客户端的写,只是自己不投票。", t=tl(S(3)), done=[0, 1], kv=KV([['observer 收到写', '转发给 leader']], ['observer 收到写'])),
    step(f"对写延迟的影响:3 个投票节点的同步写中位 {lt['plain']:.2f} ms,加 2 个 observer 后 {lt['with_obs']:.2f} ms(3 轮交替测量:{', '.join(f'{x:.2f}' for x in lt['rounds_a'])} vs {', '.join(f'{x:.2f}' for x in lt['rounds_b'])})——多了约 {lt['with_obs'] - lt['plain']:.1f} ms。observer 不用确认写入,但 leader 要多向 2 个节点发送提案和提交,这个测法下(5 个 JVM 在同一台机器上)能看到一点额外开销。", t=tl(S(4)), b=bars([['3 投票', lt['plain'], f"{lt['plain']:.2f} ms"], ['3 投票 + 2 observer', lt['with_obs'], f"{lt['with_obs']:.2f} ms"]], lt['with_obs'] * 1.15, mark=[1], done=[0]), kv=KV([['写延迟', f"+{lt['with_obs'] - lt['plain']:.1f} ms(同一台机器)"]], ['写延迟'])),
]
A = dict(
    n=28, series='zookeeper', tags='ZooKeeper,Observer,Learner,真实验证,动画演示',
    desc=f'Learner、Follower、Observer 的区别实测:observer 不投票、不算多数派(3 投票节点停 2 个即使还有 2 个 observer 也不能写);observer 接受写并转发给 leader;对写延迟有少量额外开销({lt["plain"]:.2f} → {lt["with_obs"]:.2f} ms)。',
    lead='ZooKeeper 的节点分 leader、follower、observer,前两个投票,observer 不投票。Learner 又是什么?这篇用 3 个投票节点加 2 个 observer 的集群验证:谁算多数派、observer 怎么写、对延迟有什么影响。',
    facts=[('observer 不算多数派', '3 投票节点停 2 个,即使 2 个 observer 都在也不能写'), ('Learner', 'follower 与 observer 都向 leader 学习状态,统称 learner'), (f'{lt["plain"]:.2f} → {lt["with_obs"]:.2f} ms', '加 2 个 observer 前后的同步写延迟(同一台机器上的 5 个 JVM)')],
    body=[
        sec('三种角色', '', term('', blk('z28', 1)), '<p>「learner」是 follower 与 observer 的统称(日志里的 LearnerHandler 就是 leader 为每个 learner 开的处理线程)。</p>'),
        sec('observer 与多数派', '', term('', blk('z28', 2))),
        sec('observer 的写', '', term('', blk('z28', 3))),
        sec('对写延迟的影响', '', term('', blk('z28', 4)), '<p>这个差别在不同环境里可能不同(跨机房时 observer 的作用主要是不让远端节点参与投票),本文只测了单机。</p>'),
        sec('分步演示', '', demo('Observer', [('t', 'term', '输出'), ('b', 'bars', '写延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 个投票节点 + 2 个 observer 的伪集群;延迟是 3 轮交替的中位数(5 个 JVM 在同一台机器)', '没有验证:跨机房场景、observer 的读扩展吞吐(第 29 篇)、observer 选举与重连、observer masters(observerMasterPort)'],
)
