from lib import *
R = J('z21'); sp = R['speed']
def S(k): return [l for l in out('z21').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"100 次 create:逐个同步提交 {sp['single']:.0f} ms(约 {sp['single'] / 100:.2f} ms/个,每次都要等一次事务日志 fsync);一个 multi 含 100 个 create 只用 {sp['multi']:.1f} ms({sp['multi'] / 100:.2f} ms/个)——快约 {sp['single'] / sp['multi']:.0f} 倍(各重复 5 次取中位数,单机)。multi 把多个操作合并成一个事务,只提交一次。", t=tl(S(1)), b=bars([['逐个 create', sp['single'], f"{sp['single']:.0f} ms"], ['一个 multi', sp['multi'], f"{sp['multi']:.1f} ms"]], sp['single'] * 1.05, mark=[0], done=[1]), kv=KV([['multi', '一个事务,一次落盘']], ['multi'])),
    step("原子性:multi 里 create /at/a、/at/b、再 create /at/a(重复)、/at/c:commit 抛出 RolledBackError,返回的各操作结果是 [RolledBackError, RolledBackError, NodeExistsError, RuntimeInconsistency]——失败的是第 3 个(NodeExists),前两个被回滚、第 4 个没有执行;之后 /at 下一个子节点都没有。要么全部成功,要么全部不生效。", t=tl(S(2)), mark=[0], done=[1], kv=KV([['multi', '全部成功或全部不生效']], ['multi'])),
    step("一个 multi 里的所有操作共用同一个 zxid:5 个 create 的 czxid 都是同一个值(0x209)。它们在事务日志里是一条记录,在整个集群里是不可分割的。", t=tl(S(3)), done=[0], kv=KV([['zxid', '一个 multi = 一个 zxid']], ['zxid'])),
    step("check 操作:multi 里放 check(path, version) 再做写入,用来实现「依赖的数据没变才写」:版本一致时 commit 成功,/cfg 被改过之后同样的 multi 得到 [BadVersionError, RuntimeInconsistency],/derived2 没有被创建。", t=tl(S(4)), mark=[1], done=[0], kv=KV([['check', '版本没变才继续']], ['check'])),
    step("multi 的整个请求仍受约 1 MiB 的请求大小限制:30 个各 50000 字节的 create(合计约 1.5 MiB)一次提交 → ConnectionLoss。要把大批量拆成多个 multi。", t=tl(S(5)), mark=[0], kv=KV([['请求大小', 'multi 也不能超过约 1 MiB']], ['请求大小'])),
]
A = dict(
    n=21, series='zookeeper', tags='ZooKeeper,multi,事务,批量写入,真实验证,动画演示',
    desc=f'批量写入与单次写入对比:100 次 create 逐个提交 {sp["single"]:.0f} ms,一个 multi {sp["multi"]:.1f} ms(快 {sp["single"] / sp["multi"]:.0f} 倍);multi 原子(失败全部回滚)、共用一个 zxid、可用 check 做版本条件;整个请求受 ~1 MiB 限制。',
    lead='ZooKeeper 的 multi(事务)不只是为了原子性,它还是批量写入最有效的办法。这篇量一下 100 次 create 逐个提交和一次 multi 提交的差别,再验证它的原子性、zxid 和 check 条件。',
    facts=[(f'{sp["single"] / sp["multi"]:.0f} 倍', '100 次 create:逐个同步 vs 一个 multi(单机)'), ('1 个 zxid', 'multi 里的所有操作共用同一个事务号'), ('约 1 MiB', 'multi 整个请求的大小上限')],
    body=[
        sec('速度', '', term('', blk('z21', 1)), '<p>差别主要来自每次写都要等事务日志 fsync(第 55 篇)。如果用异步 API 流水线提交,也能接近这个速度(第 1 篇量到异步写 1 万次/秒),区别是 multi 还保证原子性。</p>'),
        sec('原子性', '', term('', blk('z21', 2))),
        sec('zxid 与 check', '', term('', blk('z21', 3) + '\n' + blk('z21', 4))),
        sec('大小限制', '', term('', blk('z21', 5))),
        sec('分步演示', '', demo('multi 事务', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;kazoo 的 transaction();耗时是 5 次重复的中位数', '没有验证:集群里 multi 的耗时、multi 里操作数量的上限、setData / delete 在 multi 里的行为、multi 失败时的 watch 触发、Java 客户端的 Op 与 multi API 差别'],
)
