from lib import *
R = J('z84'); h = R['happy']; d = R['die']
def S(k): return [l for l in out('z84').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"协议(我自己写的最小两阶段,不是 ZooKeeper 自带):协调者建 /tx/<id>/prepare 列出参与者;参与者 watch 到后在 /tx/<id>/votes/<自己> 写 yes 或 no;协调者收齐票写 /tx/<id>/decision(commit 或 abort);参与者 watch decision 后应用。20 个事务全部 yes:从 prepare 发出到最后一个参与者应用 commit,中位 {h['med']:.0f} ms(最小 {h['mn']:.0f}、最大 {h['mx']:.0f})。", t=tl(S(1)), done=[0], kv=KV([['全部 yes', f"{h['med']:.0f} ms(中位)"], ['事务节点', 'prepare / votes / decision']], ['全部 yes'])),
    step("P2 投 no:协调者看到第一个 no 就停止等待,写 abort;P1、P2、P3 都应用了 abort(包括投 yes 的 P1、P3)。", t=tl(S(2)), mark=[5], kv=KV([['任何一个 no', '全体 abort']], ['任何一个 no'])),
    step(f"P3 收到 prepare 后、投票前被 kill -9:协调者等不到它的票,{d['wait']:.1f} s(投票超时 3 s)后写 abort;P1、P2 应用 abort。参与者的投票和协调者的决定全在 ZooKeeper 里,是持久节点,不会因为某个进程崩溃而丢。", t=tl(S(3)), mark=[0], b=bars([['投票超时', 3.0, '3 s'], ['协调者实际等待', d['wait'], f"{d['wait']:.1f} s"]], 4, done=[0, 1]), kv=KV([['缺票', '超时 → abort'], ['协调者等待', f"{d['wait']:.1f} s"]], ['缺票'])),
    step("协调者收齐了全部 yes、写 decision 之前被 kill -9:这是经典的 2PC 阻塞 —— 两个参与者都投了 yes,处于「不知道该提交还是回滚」的状态,5 秒内没有一个应用(decision 不存在)。我手动启动了一个恢复进程:读到所有票都是 yes、写 commit,两个参与者在 0.10 s 内应用。这里恢复是我手动触发的,实际要自己实现「谁来恢复、什么时候恢复」(通常再选一个 leader 去做)。", t=tl(S(4)), mark=[0], done=[3], kv=KV([['协调者崩溃', '参与者阻塞(5 s 无应用)'], ['恢复', '读票 → 写 commit(手动触发)']], ['协调者崩溃'])),
]
A = dict(
    n=84, series='zookeeper', tags='ZooKeeper,两阶段提交,协调者,真实验证,动画演示',
    desc=f'用 ZooKeeper 节点实现最小两阶段提交:全 yes 的 20 个事务中位 {h["med"]:.0f} ms 完成;一个 no 全体 abort;参与者崩溃 {d["wait"]:.1f} s 后超时 abort;协调者在写决定前崩溃时参与者阻塞,读回投票的恢复进程 0.1 s 内写 commit。',
    lead='把「多个参与者要么都做、要么都不做」交给 ZooKeeper 来协调:投票、决定都存在节点里,崩溃后别的进程能接着做。这篇我自己写一个最小的两阶段提交,分别验证全票通过、有人反对、参与者崩溃、协调者崩溃四种情形。',
    facts=[(f'{h["med"]:.0f} ms', '20 个全 yes 事务从 prepare 到全部应用的中位耗时'), ('3 s', '参与者崩溃时协调者的投票超时,之后写 abort'), ('阻塞', '协调者在写 decision 前崩溃,参与者无法自行决定,需要恢复进程')],
    body=[
        sec('正常提交', '', term('', blk('z84', 1)), '<p>ZooKeeper 在这里的作用是一个<em>可靠、有序、可 watch 的共享记录板</em>。它自己不是事务协调器,协议是我写的最小实现(没有处理参与者重复投票、网络分区下的 watch 丢失等)。每个事务三个节点:prepare、votes(每个参与者一个子节点)、decision。</p>'),
        sec('有人反对', '', term('', blk('z84', 2)), '<p>协调者看到 no 就不再等其余的票(日志里 VOTES 只记录了 P2 和 P3 的票,P1 的票虽然也写了但协调者没来得及读)。</p>'),
        sec('参与者崩溃', '', term('', blk('z84', 3)), '<p>没有票就不能提交,所以超时视为 no。超时设短了会误杀慢参与者,设长了让事务久悬(这期间参与者持有的资源锁不能释放)。</p>'),
        sec('协调者崩溃:2PC 的老问题', '', term('', blk('z84', 4)), '<p>阻塞问题是 2PC 本身固有的,ZooKeeper 缓解了其中一部分:投票持久地保存在节点里,所以<em>任何</em>进程都能读到完整的票并替协调者做决定(如果所有票都在,就能确定结果)。两个写 decision 的人都用 <code>create</code>,按设计后写的会得到 NodeExists、从而决定只有一个(这个并发竞争我没有测)。但<em>如果有参与者的票没来得及写</em>,恢复进程只能选 abort。</p>'),
        sec('分步演示', '', demo('两阶段提交', [('t', 'term', '输出'), ('b', 'bars', '超时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。协议是我写的最小实现;协调者与参与者都是独立子进程,会话超时 3 s;事务 20 个全 yes,另各 1 个 no / 参与者崩溃 / 协调者崩溃', '没有验证:参与者在投 yes 之后崩溃再恢复的行为(应从 votes 与 decision 重建状态)、「恢复进程写 NodeExists 保证单一决定」的并发竞争(原协调者与恢复进程同时写 decision)、跨数据库的真实事务资源、与 XA / Seata 之类框架的比较'],
)
