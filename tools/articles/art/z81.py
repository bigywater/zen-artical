from lib import *
R = J('z81'); wc, mc, per = R['w_crash'], R['m_crash'], R['per']
def S(k): return [l for l in out('z81').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("2 个 master 候选(M1 当选,M2 待命,/master-election 下 2 个节点)、3 个 worker(各建一个临时节点 /workers/Wx),一次放入 300 个任务 /tasks/…。master 把任务原子地(multi:删 /tasks/t、建 /assign/Wx/t)分给 worker;worker 完成后创建 /done/t(创建失败说明有人已做过)。1.2 秒后已完成 72 个。", t=tl(S(1)), done=[0], kv=KV([['/workers', 'W1 W2 W3(临时节点)'], ['分配', 'multi 原子移动']], ['/workers'])),
    step(f"kill -9 一个 worker(W2):master 在 {wc['lost'][0]:.1f} s 后看到 /workers 少了它,把它名下 76 个未完成任务放回 /tasks 重新分配。最终 {wc['done']} / 300 完成,重复执行 {wc['dup']} 次,总用时 {wc['total_s']:.1f} s。W2 死前完成了 {per['W2']} 个,W1 {per['W1']},W3 {per['W3']}。", b=bars([[k, v, str(v)] for k, v in sorted(per.items())], 150, mark=[1], done=[0, 2]), t=tl(S(2)), kv=KV([['发现 worker 死亡', f"{wc['lost'][0]:.1f} s"], ['重复执行', f"{wc['dup']} 次"]], ['发现 worker 死亡'])),
    step(f"再放 200 个任务,同时 kill -9 当前 master(M1):M2 在 {mc['starts'][-1][0]:.1f} s 后接管。master 没有私有状态:任务、分配、worker 列表全在 ZooKeeper,新 master 读出来继续。最终 {mc['done']} / 500 完成,重复 {mc['dup']} 次。", t=tl(S(3)), mark=[0], kv=KV([['master 接管', f"{mc['starts'][-1][0]:.1f} s"], ['最终完成', f"{mc['done']} / 500"]], ['master 接管'])),
]
A = dict(
    n=81, series='zookeeper', tags='ZooKeeper,Master选举,任务分配,kazoo,真实验证,动画演示',
    desc=f'用 ZooKeeper 做 Master/Worker:临时节点登记 worker、multi 原子分配任务;kill -9 一个 worker {wc["lost"][0]:.1f} s 后任务被重新分配,500 个任务无重复执行、全部完成;kill -9 master 后备用 master {mc["starts"][-1][0]:.1f} s 接管并读回状态继续。',
    lead='Master 选举不只是「选出一个」,还要让 master 能管理 worker:发现 worker 加入和死亡、重新分配任务、自己挂了之后备用 master 能无缝接手。这篇用 kazoo 搭一个最小的 master/worker,杀 worker、杀 master,数任务有没有丢、有没有重复。',
    facts=[(f'{wc["done"]} / 300', 'kill -9 一个 worker 后全部完成的任务'), (f'{wc["dup"]} 次', '重复执行次数(完成时用 create 判重)'), (f'{mc["starts"][-1][0]:.1f} s', 'kill -9 master 后备用 master 接管的时间')],
    body=[
        sec('结构与正常运行', '', term('', blk('z81', 1)), '<p>所有状态都在 ZooKeeper 里:<code>/workers</code>(worker 的临时节点)、<code>/tasks</code>(待分配)、<code>/assign/&lt;worker&gt;</code>(已分配未完成)、<code>/done</code>(已完成)。选举复用<a href="zookeeper-leader-election.html">上一篇</a>的 Election。把任务从 /tasks 移到 /assign 用 <a href="zookeeper-multi-vs-single.html">multi</a>,保证任务不会同时在两处或两处都没有。</p>'),
        sec('worker 挂了', '', term('', blk('z81', 2)), '<p>worker 的临时节点随<a href="zookeeper-session-expire.html">会话过期</a>消失,master 比较前后两次的 worker 列表发现它死了。重复执行是靠 worker 完成时 <code>create /done/t</code> 判重(已存在则放弃)来避免的;但「任务做了一半副作用已发生」这种情况 ZooKeeper 管不了,要靠任务本身幂等。</p>'),
        sec('master 挂了', '', term('', blk('z81', 3)), '<p>新 master 启动时从 ZooKeeper 读出状态继续分配。需要诚实说明我这个最小实现的一个漏洞:新 master 的 <code>known</code>(已知 worker 集合)从空开始,所以<em>在 master 空窗期内死掉的 worker</em>,它的 /assign 目录不会被回收。我没有去测这种情况(因此没有验证);真实实现应该在接管时扫描 /assign 下所有没有对应 /workers 节点的目录。</p>'),
        sec('分步演示', '', demo('Master / Worker', [('t', 'term', '输出'), ('b', 'bars', '各 worker 完成数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0;master、worker 都是独立子进程;任务分配按任务名哈希到当前 worker;会话超时 3 s', '没有验证:master 空窗期内 worker 死亡的任务回收(见正文的漏洞说明)、任务执行到一半崩溃的副作用、worker 数量动态大幅变化、任务数远大于 300 时 /tasks 的 get_children 成本(见第 23 篇)'],
)
