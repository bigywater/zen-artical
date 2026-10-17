from lib import *
R = J('z90'); rc = R['race']; cr = R['crash']; cn = R['cron']
def S(k): return [x for x in out('z90').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step(f"没有 master:300 个任务放在 /tasks,5 个 worker 进程各自随机顺序尝试 create /claims/<任务>(临时节点),只有一个能成功。结果:{rc['done']} / 300 完成,用时 {rc['s']:.1f} s,没有任何任务被执行两次;各 worker 抢到 {min(rc['per'].values())}–{max(rc['per'].values())} 个,基本均匀。", t=tl(S(1)), done=[0], kv=KV([['抢占方式', 'create 临时节点'], ['重复执行', '0']], ['抢占方式'])),
    step(f"worker 在执行任务中途被 kill -9:耗时 3 s 的 slow00 刚开始就杀掉执行它的 W1;它的 claim 临时节点要等会话过期,{cr['takeover']:.1f} s 后 W3 才接手(会话超时 3 s),{cr['end']:.1f} s 时完成。slow00 一共开始 {cr['starts']} 次、完成 {cr['ends']} 次:至少一次执行 —— 被杀的那次做了一半,任务必须幂等。", t=tl(S(2)), mark=[0], b=bars([['接手', cr['takeover'], f"{cr['takeover']:.1f} s"], ['完成', cr['end'], f"{cr['end']:.1f} s"]], 7, done=[0, 1]), kv=KV([['崩溃后接手', f"{cr['takeover']:.1f} s"], ['执行次数', f"START {cr['starts']} / END {cr['ends']}"]], ['崩溃后接手'])),
    step(f"定时任务只让一个实例跑:3 个实例都想每秒执行一次,抢 /cron/tick-<k>(持久节点,谁 create 成功谁执行)。25 个 tick:{cn['ran']} 个被执行,漏 {len(cn['missing'])} 个,重复 {len(cn['dup'])} 个。第 10 秒 kill -9 {cn['victim']} 后其余实例照常执行,没有空窗;执行时刻相对整点的偏差中位 {cn['med']:.0f} ms、最大 {cn['mx']:.0f} ms。", t=tl(S(3)), done=[0, 1], kv=KV([['25 个 tick', f"执行 {cn['ran']},漏 {len(cn['missing'])},重复 {len(cn['dup'])}"]], ['25 个 tick'])),
]
A = dict(
    n=90, series='zookeeper', tags='ZooKeeper,任务调度,定时任务,真实验证,动画演示',
    desc=f'用 ZooKeeper 做任务调度:5 个无 master 的 worker 抢 300 个任务零重复;执行中被 kill -9 的任务 {cr["takeover"]:.1f} s 后被接手(至少一次执行);3 个实例抢 25 个定时 tick,无漏无重复,kill 一个实例无空窗。',
    lead='调度不一定要有 master:让所有 worker 去抢一个「只能有一个成功」的节点就行。这篇用 create 的原子性做两件事 —— 无 master 的任务抢占,以及多实例部署时的定时任务单实例执行 —— 并在执行中途杀进程,看任务怎么被接走。',
    facts=[(f'{rc["done"]} / 300', '5 个 worker 抢任务:全部完成、0 个重复'), (f'{cr["takeover"]:.1f} s', '执行中被 kill -9 的任务被别的 worker 接手'), (f'{cn["ran"]} / 25', '3 个实例抢定时 tick:全部执行,0 个重复,0 个遗漏')],
    body=[
        sec('抢占:create 就是互斥', '', term('', blk('z90', 1)), '<p>这是<a href="zookeeper-distributed-lock.html">分布式锁</a>最简单的形态:每个任务一个节点名,只有一个 <code>create</code> 能成功。和<a href="zookeeper-master-election.html">有 master 的方案</a>相比没有单点,但每个 worker 都要扫描 /tasks,任务多时目录大(见<a href="zookeeper-many-znodes.html">大目录</a>)。</p>'),
        sec('崩溃与接手', '', term('', blk('z90', 2)), '<p>claim 是临时节点,所以崩溃的 worker 持有的任务在<a href="zookeeper-session-expire.html">会话过期</a>后自动释放。因为无法区分「还没开始」和「做了一半」,只能提供至少一次的语义。完成标记 /done 是在任务做完之后才写的。</p>'),
        sec('定时任务只跑一次', '', term('', blk('z90', 3)), '<p>每个 tick 用一个持久节点占位,谁先 create 成功谁执行。要注意:如果抢到的实例在 create 之后、执行完之前崩溃,这个 tick 就丢了(节点已存在,别人不会再做)—— 我没有测这种情况。需要「一定执行」就要像上面的 claim 一样用临时节点加完成标记。所有实例在同一台机器上,时钟没有偏差;跨机器要考虑时钟差。</p>'),
        sec('分步演示', '', demo('任务调度', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。worker 与定时实例都是独立的 Python 子进程(kazoo);会话超时 3 s;5 个 worker 在同一台机器', '没有验证:抢到 tick 后崩溃导致该 tick 丢失(见正文)、跨机器时钟偏差、延迟任务(到点才可抢)、任务数上万时的扫描成本、与 Quartz / xxl-job 等调度框架的对比'],
)
