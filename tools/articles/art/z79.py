from lib import *
R = J('z79'); mx = R['mutex']; hd = R['herd']
def S(k): return [l for l in out('z79').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"没有锁:10 个客户端各自「读计数器 → 加 1 → 写回」20 次,期望 200,实际 {mx['nolock']},丢了 {200 - mx['nolock']} 次更新。有锁(kazoo Lock):{mx['lock']} / 200,但用时从 {mx['t_no']:.1f} s 变成 {mx['t_lock']:.1f} s —— 互斥的代价是串行。", t=tl(S(1)), mark=[0], kv=KV([['无锁', f"{mx['nolock']} / 200"], ['有锁', f"{mx['lock']} / 200"]], ['无锁'])),
    step("锁在 ZooKeeper 里就是 /lock 下的临时顺序节点:名字 <客户端 uuid>__lock__<10 位序号>,序号最小的持有锁。服务端显示 5 个连接各 watch 了 1 个路径:排队者只监听它前面的那一个节点。", t=tl(S(2)), done=[0], kv=KV([['节点', '临时 + 顺序'], ['watch', '各监听前一个']], ['节点'])),
    step(f"30 个排队者时每次释放:kazoo 的做法让服务端多收到约 {hd['kazoo']:.0f} 个请求包,朴素做法(所有人 watch 父节点、变化后全部重新读子节点)约 {hd['naive']:.0f} 个。差别随排队人数线性放大。", b=bars([['kazoo(各监听前一个)', hd['kazoo'], f"{hd['kazoo']:.0f}"], ['朴素(都 watch 父节点)', hd['naive'], f"{hd['naive']:.0f}"]], 32, mark=[1], done=[0]), t=tl(S(3)), kv=KV([['kazoo', f"{hd['kazoo']:.0f} 包/次释放"], ['朴素', f"{hd['naive']:.0f} 包/次释放"]], ['朴素'])),
    step(f"持有者被 kill -9:会话超时 3 s,排队者 {R['crash']:.1f} s 后拿到锁(临时节点随会话过期被删)。崩溃释放的延迟 ≈ 会话超时,不是 0。", t=tl(S(4)), mark=[0], kv=KV([['崩溃后拿锁', f"{R['crash']:.1f} s"], ['会话超时', '3 s']], ['崩溃后拿锁'])),
    step("持有者被冻结超过会话超时(模拟 GC 长停顿,SIGSTOP):B 拿到了锁;A 醒来,日志依次是 SUSPENDED → LOST → CONNECTED,但 is_acquired 仍是 True —— kazoo 的 Lock 对象没有自己「失去了锁」。这是任何基于会话的锁共有的问题:靠 fencing token 让被保护的资源拒绝旧持有者。", t=tl(S(5)), mark=[4], kv=KV([['冻结后醒来', '仍以为自己持有锁'], ['补救', 'fencing token(czxid 单调递增)']], ['冻结后醒来'])),
]
A = dict(
    n=79, series='zookeeper', tags='ZooKeeper,分布式锁,kazoo,真实验证,动画演示',
    desc=f'用 kazoo 在真实 ZooKeeper 上量分布式锁:无锁 {mx["nolock"]}/200、有锁 200/200;锁就是临时顺序节点、各监听前一个,30 人排队每次释放 {hd["kazoo"]:.0f} 包 vs 朴素 {hd["naive"]:.0f} 包;持有者崩溃 {R["crash"]:.1f} s 后锁转移;冻结的持有者醒来仍以为自己持有锁。',
    lead='ZooKeeper 做分布式锁是最常见的用法。这篇用 kazoo 的 Lock 在真实集群上做五个实验:互斥是否成立、锁在服务端长什么样、为什么不惊群、持有者崩溃要多久释放,以及最容易被忽略的 —— 持有者没死、只是停顿了一下,会发生什么。',
    facts=[(f'{mx["nolock"]} → 200', '10 个客户端累加 200 次,无锁 vs 有锁的最终值'), (f'{hd["kazoo"]:.0f} vs {hd["naive"]:.0f}', '30 人排队时每次释放服务端多收到的包'), (f'{R["crash"]:.1f} s', 'kill -9 持有者后下一个拿到锁的时间(会话超时 3 s)')],
    body=[
        sec('互斥', '', term('', blk('z79', 1)), '<p>计数器放在 ZooKeeper 的一个 znode 里,「读 → 加 1 → 写回」不是原子的,所以无锁时更新互相覆盖。加锁后结果正确,但 200 次累加用时被串行化。</p>'),
        sec('锁在服务端的样子', '', term('', blk('z79', 2)), '<p>节点是<a href="zookeeper-ephemeral-persistent.html">临时节点</a>(持有者会话没了就消失)加<a href="zookeeper-sequential-node.html">顺序节点</a>(序号决定先后)。持有锁的是序号最小的;其余的每个只 watch 比自己小的上一个。</p>'),
        sec('为什么不会惊群', '', term('', blk('z79', 3)), '<p>惊群的原因见 <a href="zookeeper-watcher-storm.html">watch 风暴</a>。「包」是 <code>mntr</code> 里 <code>zk_packets_received</code> 在一次释放前后的差值(5 次释放取平均),包含 ping 等所有包,不是严格的请求数。</p>'),
        sec('持有者崩溃', '', term('', blk('z79', 4)), '<p>锁靠会话保活,所以崩溃释放的延迟取决于<a href="zookeeper-session-expire.html">会话超时</a>。超时设得越小,释放越快,但网络抖动或 GC 时越容易误判。</p>'),
        sec('持有者没死、只是冻结', '', term('', blk('z79', 5)), '<p>这是锁真正的陷阱:ZooKeeper 保证的是「同一时刻锁节点只属于一个有效会话」,不保证持有者的<em>代码</em>知道自己已不再持有。我这里没有实现 fencing token(只确认了 czxid 单调递增这个前提),正确做法是让被保护的资源(数据库、文件服务)校验令牌、拒绝较小的令牌。</p>'),
        sec('分步演示', '', demo('分布式锁', [('t', 'term', '输出'), ('b', 'bars', '包数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0 的 Lock;「冻结」用 SIGSTOP/SIGCONT,持有者在子进程里;会话超时 3 s', '没有验证:fencing token 的完整实现、读写锁(ReadWriteLock)、跨机房网络延迟下的锁行为、Curator 的 InterProcessMutex(见第 93 篇)'],
)
