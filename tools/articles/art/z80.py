from lib import *
R = J('z80'); runs = R['runs']
def S(k): return [l for l in out('z80').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("5 个候选进程各自一个会话,用 kazoo 的 Election 配方参选:每个创建 /election 下一个临时顺序节点,序号最小的当选。启动后当选的是 A,/election 下有 5 个子节点,同一时刻只有一个进程在发心跳(leader 才干活)。", t=tl(S(1)), done=[0], kv=KV([['当选', 'A'], ['候选节点', '5 个临时顺序节点']], ['当选'])),
    step(f"依次 kill -9 当前 leader 四次:从它最后一次心跳到新 leader 开始工作的空窗是 {', '.join(f'{r['gap']:.2f}' for r in runs)} s,中位 {R['gap_med']:.2f} s ≈ 会话超时 3 s + 选举。四次都没有出现两个 leader 同时在工作。", b=bars([[f"{r['killed']}→{r['new']}", r['gap'], f"{r['gap']:.2f} s"] for r in runs], 4, done=[0, 1, 2, 3]), t=tl(S(2)), kv=KV([['空窗中位', f"{R['gap_med']:.2f} s"], ['脑裂', '4 次都没有']], ['空窗中位'])),
    step(f"leader 正常让位(resign,进程退出时关闭会话):临时节点立刻消失,新 leader 在 {R['resign_gap']:.2f} s 内接上,几乎没有空窗。所以进程退出前要主动关闭会话,别等超时。", t=tl(S(3)), b=bars([['kill -9', R['gap_med'], f"{R['gap_med']:.2f} s"], ['正常退出', R['resign_gap'], f"{R['resign_gap']:.2f} s"]], 4, mark=[0], done=[1]), kv=KV([['kill -9', f"{R['gap_med']:.2f} s"], ['正常退出', f"{R['resign_gap']:.2f} s"]], ['正常退出'])),
]
A = dict(
    n=80, series='zookeeper', tags='ZooKeeper,Leader选举,kazoo,真实验证,动画演示',
    desc=f'5 个 kazoo Election 候选进程的 Leader 选举实测:同一时刻只有一个 leader;kill -9 leader 4 次,空窗期 {", ".join(f"{r["gap"]:.2f}" for r in runs)} s(中位 {R["gap_med"]:.2f} s ≈ 会话超时),全程无两个 leader;正常让位只有 {R["resign_gap"]:.2f} s。',
    lead='用 ZooKeeper 给自己的应用(而不是 ZooKeeper 集群本身)选 leader:主备切换、单实例定时任务都靠它。这篇起 5 个候选进程,量选举结果、kill -9 之后的空窗期、有没有两个 leader 重叠,以及主动让位和崩溃的差别。',
    facts=[('1 个', '同一时刻发心跳的 leader 数(5 个候选)'), (f'{R["gap_med"]:.2f} s', 'kill -9 leader 后新 leader 出现的空窗(中位,会话超时 3 s)'), (f'{R["resign_gap"]:.2f} s', 'leader 正常关闭会话时的切换空窗')],
    body=[
        sec('选出一个', '', term('', blk('z80', 1)), '<p>配方和<a href="zookeeper-distributed-lock.html">分布式锁</a>几乎一样:临时顺序节点,序号最小的当选,别人只监听前一个。区别是「锁」被持有一小会儿,「leader」被持有到进程结束。</p>'),
        sec('杀掉 leader', '', term('', blk('z80', 2)), '<p>空窗由<a href="zookeeper-session-expire.html">会话超时</a>决定:leader 被 kill -9 后,服务端要等会话过期才删除它的临时节点,下一个候选才被通知。中间这几秒没有 leader,业务必须能容忍;调小会话超时能缩短,但会增加误切换。</p>'),
        sec('主动让位', '', term('', blk('z80', 3)), '<p>进程收到退出信号时先关闭会话(或调用 resign),临时节点立刻删除。发布升级、滚动重启都应该走这条路径。</p>'),
        sec('分步演示', '', demo('Leader 选举', [('t', 'term', '输出'), ('b', 'bars', '空窗 s'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0 的 Election;5 个候选各为独立子进程;「同时有两个 leader」用各进程写的心跳日志的时间区间是否重叠来判断;会话超时 3 s', '没有验证:leader 被冻结(不是死亡)后的重叠窗口(与第 79 篇的冻结锁同理,Election 配方没有防护)、网络分区下的 leader、候选数更大时的选举耗时'],
)
