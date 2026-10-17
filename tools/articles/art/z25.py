from lib import *
R = J('z25'); ms, ml, mf = R['m_standalone'], R['m_leader'], R['m_follower']
def S(k): return [l for l in out('z25').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("单机节点用 jstack 看线程:NIOServerCxnFactory 的 AcceptThread / SelectorThread / NIOWorkerThread(网络层:接受连接、读写 socket)、RequestThrottler(限流队列)、ProcessThread(PrepRequestProcessor,校验请求并生成事务)、SyncThread(写事务日志并 fsync;mntr 里有对应的 sync、fsync 指标)、SessionTracker、ConnnectionExpirer、ContainerManagerTask。请求链的先后顺序来自处理器的命名和 mntr 指标,我没有逐个请求去追踪。", t=tl(S(1)[:1]), kv=KV([['网络', 'Selector / Worker 线程'], ['处理链', 'Throttler → Prep → Sync → Final']], ['处理链'])),
    step(f"3000 次异步写之后 mntr 里的平均耗时(单机):prep 处理 {ms['avg_prep_process_time']} ms、sync 处理 {ms['avg_sync_process_time']} ms、fsync {ms['avg_fsynctime']} ms、throttle 队列等待 {ms['avg_request_throttle_queue_time_ms']} ms。耗时主要在 fsync(落盘),内存里的处理环节都是微秒到亚毫秒级。", t=tl(S(1)[1:]), b=bars([['prep', float(ms['avg_prep_process_time']), ms['avg_prep_process_time']], ['sync 处理', float(ms['avg_sync_process_time']), ms['avg_sync_process_time']], ['fsync', float(ms['avg_fsynctime']), ms['avg_fsynctime']]], float(ms['avg_fsynctime']) * 1.1, mark=[2], done=[0, 1]), kv=KV([['最大头', 'fsync']], ['最大头'])),
    step("集群里 leader 与 follower 的线程不同:leader 特有 ProcessThread(请求准备)、LearnerHandler(每个 follower 一个,收发同步消息)、SessionTracker、ContainerManagerTask;follower 特有 FollowerRequestProcessor(把写请求转发给 leader);两者都有 CommitProcessor(按顺序提交已被多数派确认的请求)、QuorumPeer、Send/RecvWorker(节点间连接)。", t=tl(S(2)), done=[0, 1], kv=KV([['leader', 'Prep + LearnerHandler'], ['follower', 'FollowerRequestProcessor']], ['leader'])),
    step(f"连在 follower 上的客户端写 3000 次:leader 的 prep {ml['avg_prep_process_time']} ms(只有 leader 做事务准备),follower 的 prep 是 {mf['avg_prep_process_time']};两者都要 fsync({ml['avg_fsynctime']} / {mf['avg_fsynctime']} ms);提案延迟 proposal_latency 在 follower 上是 {mf['avg_proposal_latency']} ms。写请求:follower → leader → 多数派确认 → 各节点提交。", t=tl(S(3)), kv=KV([['事务准备', '只在 leader'], ['落盘', '每个节点各自 fsync']], ['事务准备'])),
    step(f"读请求在 follower 本地完成:连在 follower 的客户端读 3000 次,leader 收到的包数只增加了 {R['read_local']}。读不经过 leader,所以 follower / observer 越多读吞吐可以越高(本文没有量化);代价是读可能读到稍旧的数据,这个滞后我也没有测。", t=tl(S(4)), done=[0], kv=KV([['读', 'follower 本地,不进 leader']], ['读'])),
]
A = dict(
    n=25, series='zookeeper', tags='ZooKeeper,请求处理链,线程模型,真实验证,动画演示',
    desc='请求处理链实测:用 jstack 看单机与集群节点的线程(NIO → RequestThrottler → ProcessThread → SyncThread → …),mntr 的平均耗时显示 fsync 是写路径的大头;leader 特有 ProcessThread / LearnerHandler,follower 特有 FollowerRequestProcessor;读在 follower 本地完成。',
    lead='一个请求进入 ZooKeeper 之后经过哪些环节?与其读源码,不如直接看运行中的线程和 mntr 里每个环节的耗时。这篇用 jstack 和 mntr 把单机、leader、follower 的请求处理链还原出来。',
    facts=[('Throttler → Prep → Sync → Final', '单机写请求依次经过的线程'), ('fsync 是大头', '各环节平均耗时里只有 fsync 达到毫秒级'), (f'{R["read_local"]}', '连在 follower 上读 3000 次,leader 多收到的包数')],
    body=[
        sec('单机的处理链', '', term('', blk('z25', 1)), '<p>线程名里的 <code>N</code> 是我把数字替换掉了,避免不同运行之间不同的编号。线程与处理器的对应关系来自 ZooKeeper 的命名:<code>ProcessThread</code> 运行 PrepRequestProcessor,<code>SyncThread</code> 运行 SyncRequestProcessor。</p>'),
        sec('leader 与 follower 的差别', '', term('', blk('z25', 2) + '\n' + blk('z25', 3))),
        sec('读在哪里完成', '', term('', blk('z25', 4))),
        sec('分步演示', '', demo('请求处理链', [('t', 'term', '输出'), ('b', 'bars', '平均耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。线程名用 jstack 取;耗时来自 mntr(avg_* 指标,单位为毫秒);3 节点伪集群,客户端连在一个 follower 上', '没有验证:每个 RequestProcessor 内部的逻辑(没有读源码,第 99–101 篇再看)、Netty 模式、observer 的处理链、CommitProcessor 的并行度参数、指标单位的官方定义'],
)
