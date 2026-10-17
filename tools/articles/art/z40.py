from lib import *
R = J('z40'); c = R['counters']; md = R['modes']
def S(k): return [l for l in out('z40').split('== ')[k].splitlines()[1:] if l.strip()]
leader = next(k for k, v in md.items() if v == 'leader')
steps = [
    step(f"广播的三步:Proposal → Ack → Commit。通过 follower 写 500 个 znode:两个 follower 各收到 500 个 proposal、500 个 commit,leader 自己提交了 500 次(commit_count +500),三个计数器正好对得上。leader 的 avg_quorum_ack_latency 约 5 ms,基本就是等 follower 落盘 ack 的时间。", t=tl(S(1)), done=[0, 1, 2], kv=KV([['每个写', '1 个 proposal + 1 个 commit 发给每个 follower']], ['每个写'])),
    step(f"提交需要多数派确认:暂停两个 follower 后,leader 上的异步 create 1.5 秒都没有完成(ready = {R['pending']['ready']}),另一个客户端读 /pending 得到 None(数据没有对外可见),leader 的 zk_outstanding_requests = {R['pending']['outstanding']}——提案还在等 ack。", t=tl(S(2)[:1]), mark=[0], kv=KV([['没有多数派 ack', '提案卡住,数据不可见']], ['没有多数派 ack'])),
    step(f"follower 恢复后 4 ms 内:create 完成(结果 {R['after_resume']['ok']}),/pending 变得可见({R['after_resume']['exists']})。写请求在被多数派确认并提交之前,对读者是不存在的。", t=tl(S(2)[1:]), done=[0], kv=KV([['多数派 ack 之后', 'commit → 对外可见']], ['多数派 ack 之后'])),
]
A = dict(
    n=40, series='zookeeper', tags='ZooKeeper,ZAB,Proposal,Commit,真实验证,动画演示',
    desc=f'Proposal、事务日志与 Commit 实测:写 500 个 znode,每个 follower 收到 500 个 proposal 和 500 个 commit,leader 提交 500 次;暂停两个 follower 后提案 ack 不齐,数据对读者不可见,恢复后几毫秒内提交可见。',
    lead='ZAB 的广播阶段是怎么让一个写入「在整个集群里生效」的?这篇用 mntr 的计数器验证 Proposal → Ack → Commit 的对应关系,再暂停 follower 看没有多数派确认时写入处于什么状态。',
    facts=[('500 / 500 / 500', '每个 follower 收到的 proposal、commit 数,与 leader 提交数'), ('ack 不齐就不可见', '两个 follower 暂停时,leader 上的写卡住且读不到'), ('恢复后 4 ms', '多数派 ack 之后很快提交并对外可见')],
    body=[
        sec('计数器对得上', '', term('', blk('z40', 1)), '<p>字段名对应:<code>zk_learner_proposal_received_count</code>、<code>zk_learner_commit_received_count</code> 是 follower 收到的数量,<code>zk_commit_count</code> 是本节点提交到内存树的数量。</p>'),
        sec('没有多数派确认', '', term('', blk('z40', 2)), '<p>leader 自己也要把提案写进事务日志并 ack,所以 3 个节点里 leader 加任意一个 follower 的 ack 就够多数派。这里两个 follower 都被暂停,leader 自己的 ack 不够,提案就卡住。</p>'),
        sec('分步演示', '', demo('Proposal 与 Commit', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群,写入通过一个 follower 的客户端;暂停用 SIGSTOP;计数器取自 mntr', '没有验证:提案在 follower 上被写入事务日志的确切时刻(没有逐条追踪)、proposal 的批量化、慢 follower 对提交的影响、follower 在 ack 之后崩溃的情形'],
)
