import re
from lib import *
R = J('z93'); T = R['stdout']
def S(k): return [x for x in out('z93').split('== ')[k].splitlines()[1:] if x.strip()]
tm = re.search(r'用时 ([\d.]+) s', T).group(1)
steps = [
    step(f"InterProcessMutex:10 个线程各用独立客户端,各做 20 次「读 → 加 1 → 写回」:最终 200 / 200,用时 {tm} s(和 kazoo 的 Lock 一样,无锁时会丢更新)。锁节点名是 _c_<uuid>-lock-<序号>。", t=tl(S(1)), done=[0], kv=KV([['互斥', '200 / 200'], ['用时', f'{tm} s']], ['互斥'])),
    step("可重入:同一线程两次 acquire 都成功,但 /re 下只有 1 个锁节点(重入计数在本地内存里),release 一次后节点还在,release 第二次才删除;多 release 一次抛 IllegalMonitorStateException。InterProcessSemaphoreMutex 不可重入:同线程第二次 acquire(1 s) 等满 1.0 s 返回 false —— 自己把自己锁住了。", t=tl(S(2)), done=[0], kv=KV([['InterProcessMutex', '可重入(本地计数)'], ['SemaphoreMutex', '不可重入']], ['InterProcessMutex'])),
    step("获取超时:A 持有锁,B 在另一个客户端 acquire(1, SECONDS):1.02 s 后返回 false,/to 下只剩 A 的节点 —— B 超时后自己清理了排队节点,不会留下垃圾。", t=tl(S(3)), done=[0], kv=KV([['acquire(timeout)', '返回 false,排队节点已清理']], ['acquire(timeout)'])),
    step("读写锁:5 个读者同时持有读锁(同时在内的最大数 5);写者等到 1.5 s 读者全部释放后才拿到写锁;写者排队之后才到达的新读者没有插队,等了 1.5 s,在写者释放后(2.1 s)才拿到读锁 —— 按排队顺序,写者不会被读者饿死。", t=tl(S(4)), done=[0, 1], kv=KV([['读者并发', '最大 5'], ['写者之后的读者', '排在写者后面']], ['写者之后的读者'])),
    step("持有者所在的 JVM 被冻结超过会话超时:3.2 s 后另一个进程拿到了同一把锁;持有者解冻后收到 LOST → RECONNECTED,但 isOwnedByCurrentThread() 与 isAcquiredInThisProcess() 仍是 true —— Curator 的锁和 kazoo 一样,不会自己发现锁已被别人拿走(见<a href='zookeeper-distributed-lock.html'>第 79 篇</a>)。需要靠 fencing token 或在状态监听器里主动中止业务。", t=tl(S(5)), mark=[3], kv=KV([['别人拿到锁', '3.2 s 后'], ['解冻后的持有者', '仍以为持有']], ['解冻后的持有者'])),
]
A = dict(
    n=93, series='zookeeper', tags='ZooKeeper,Curator,分布式锁,真实验证,动画演示',
    desc=f'Curator 5.7.1 的 InterProcessMutex 实测:10 线程累加 200/200;可重入靠本地计数、SemaphoreMutex 不可重入;acquire 超时后排队节点被清理;读写锁按排队顺序、写者不被饿死;JVM 冻结超过会话超时后别人拿到锁、解冻的持有者仍以为持有。',
    lead='Curator 的 InterProcessMutex 是 Java 世界里最常用的分布式锁。这篇用真实的 Curator 5.7.1 做五件事:互斥是否成立、可重入怎么实现、获取超时是否留垃圾、读写锁的排队规则,以及持有者 JVM 被冻结(长 GC)后会发生什么。',
    facts=[('200 / 200', '10 线程累加的最终值'), ('1 个节点', '同线程重入两次时 ZooKeeper 里的锁节点数'), ('3.2 s', '持有者被冻结后另一个进程拿到锁的时间(会话超时 3 s)')],
    body=[
        sec('互斥', '', term('', blk('z93', 1)), '<p>底层配方和<a href="zookeeper-distributed-lock.html">kazoo 的锁</a>一样:临时顺序节点,每个排队者只监听前一个。</p>'),
        sec('可重入', '', term('', blk('z93', 2))),
        sec('获取超时', '', term('', blk('z93', 3))),
        sec('读写锁', '', term('', blk('z93', 4)), '<p>读写锁在同一个路径下用两种前缀的顺序节点来排队,所以先后顺序由序号决定。</p>'),
        sec('JVM 冻结', '', term('', blk('z93', 5)), '<p>只有持有者的 JVM 被冻结,ZooKeeper 服务端正常运行,所以会话超时后别人合法地拿到了锁。冻结的 JVM 恢复后先发现 LOST,再 RECONNECTED,但业务线程不会被打断。</p>'),
        sec('分步演示', '', demo('Curator 分布式锁', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Curator 5.7.1 + OpenJDK 17;客户端与服务端同一台机器;会话超时 3 s;冻结用 kill -STOP', '没有验证:InterProcessMultiLock、InterProcessSemaphoreV2(信号量)、revoke(撤销锁)、锁在服务端重启期间的行为、Curator 与 kazoo 的锁互操作(两者节点命名不同:kazoo 是 uuid__lock__序号,Curator 是 _c_uuid-lock-序号;是否互相排斥没有测)'],
)
