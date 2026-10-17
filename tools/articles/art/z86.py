from lib import *
R = J('z86'); rm = R['rmw']; rb = R['rollback']; tn = R['torn']
def S(k): return [x for x in out('z86').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step("每个节点有 version(每次 set 加 1)。A、B 都读到 version=0;A 带 version=0 写成功后 version 变成 1;B 再带 version=0 写,得到 BadVersionError —— 被拒绝而不是悄悄覆盖 A。这是配置的乐观锁(CAS)。", t=tl(S(1)), done=[0], kv=KV([['带 version 写', '版本不符 → BadVersionError']], ['带 version 写'])),
    step(f"10 个客户端各「读 → 加 1 → 写回」20 次:不带 version 最终 {rm['nocas']} / 200(丢 {200 - rm['nocas']} 次);带 version 并在 BadVersionError 后重读重试,最终 {rm['cas']} / 200,为此重试了 {rm['retries']} 次。不丢更新,代价是冲突时的重试。", t=tl(S(2)), mark=[0], b=bars([['不带 version', rm['nocas'], str(rm['nocas'])], ['带 version 重试', rm['cas'], str(rm['cas'])]], 200, mark=[0], done=[1]), kv=KV([['无 CAS', f"{rm['nocas']} / 200"], ['CAS 重试', f"{rm['cas']} / 200({rm['retries']} 次重试)"]], ['无 CAS'])),
    step(f"ZooKeeper 只保存当前值;stat.version 只是个计数器,没有历史内容。想回滚就要自己存:这里每次发布前往 /hist/app/ver-<序号> 里追加一份。把 ver-0000000001 的内容写回 /app:写入 {rb['write']:.0f} ms,{rb['ok']} / {rb['n']} 个实例最晚 {rb['last']:.0f} ms 收到旧值。", t=tl(S(3)), done=[0], kv=KV([['历史', '自己存(顺序节点)'], ['回滚到全部实例', f"{rb['last']:.0f} ms"]], ['历史'])),
    step(f"一次要改两个相关配置项:写入端用 multi 原子提交 a 和 b,但读者分两次 get:{tn['reads']} 次读取里 {tn['torn']} 次读到 a≠b(读者读 a 之后、读 b 之前,写入端又提交了一次)。放在同一个 JSON 节点里:{tn['jreads']} 次读取 0 次不一致。multi 保证写入原子,不保证「分两次读」得到一致快照。", t=tl(S(4)), mark=[0], b=bars([['两个节点,分两次读', tn['torn'], f"{tn['torn']} 次不一致"], ['单个 JSON 节点', tn['jtorn'], f"{tn['jtorn']} 次不一致"]], 500, mark=[0], done=[1]), kv=KV([['分两次读', f"{tn['torn']} / {tn['reads']} 不一致"], ['单节点 JSON', f"{tn['jtorn']} / {tn['jreads']}"]], ['分两次读'])),
]
A = dict(
    n=86, series='zookeeper', tags='ZooKeeper,热更新,乐观锁,配置版本,真实验证,动画演示',
    desc=f'配置热更新的版本控制实测:带 version 的写被 BadVersionError 拒绝;10 客户端累加不带 version 丢更新({rm["nocas"]}/200)、带 version 重试 200/200;ZooKeeper 无历史,回滚要自己存;multi 原子写但分两次读会读到半新半旧({tn["torn"]}/{tn["reads"]})。',
    lead='配置能热更新之后,下一批问题是:两个人同时改怎么办、改错了怎么回滚、一次改多项如何不让应用看到中间状态。这篇用 ZooKeeper 的 version 做乐观锁,自己存历史做回滚,并量一量把相关配置拆成两个节点会读到什么。',
    facts=[(f'{rm["nocas"]} → {rm["cas"]}', '10 客户端累加 200 次:不带 version vs 带 version 重试'), (f'{rb["last"]:.0f} ms', '回滚到旧版本、50 个实例全部收到的时间'), (f'{tn["torn"]} / {tn["reads"]}', '两个节点分两次读时读到 a≠b 的次数')],
    body=[
        sec('version 与乐观锁', '', term('', blk('z86', 1)), '<p>配置发布工具应该永远带上自己读到的 version 去写,这样两个管理员同时改同一份配置时,后写的人会被拒绝并被迫重新看一遍。</p>'),
        sec('冲突与重试', '', term('', blk('z86', 2)), '<p>重试次数很多是因为 10 个客户端在满速互相冲突(热点)。真实的配置发布冲突很少,这里是故意放大的极端情况。</p>'),
        sec('历史与回滚', '', term('', blk('z86', 3)), '<p>回滚就是「把旧内容当作一次新的发布」,所以所有实例收到的是一次普通更新(见<a href="zookeeper-config-center.html">上一篇</a>的推送延迟)。历史节点会占内存,要定期清理旧版本。</p>'),
        sec('一次改多项', '', term('', blk('z86', 4)), '<p>相关的配置项(比如主机与端口)要么放进同一个节点,要么让读者先读一个「版本指针」节点再按版本读。<code>multi</code> 只解决写入的原子性。</p>'),
        sec('分步演示', '', demo('配置版本控制', [('t', 'term', '输出'), ('b', 'bars', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0;第 4 项的写入端满速连续提交,读者满速连续读,不一致次数取决于这个压力,不是真实业务下的概率', '没有验证:版本指针方案(读者先读指针再读版本节点)、历史节点的自动清理、发布前的 schema 校验、权限分离(只有发布工具可写,见第 71 篇)'],
)
