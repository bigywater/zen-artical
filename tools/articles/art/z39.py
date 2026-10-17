from lib import *
R = J('z39'); pm = R['phase_ms']
def S(k): return [l for l in out('z39').split('== ')[k].splitlines()[1:] if l.strip()]
t1 = S(1)
steps = [
    step("ZAB 一任 leader 的三个阶段:发现(discovery)→ 同步(synchronization)→ 广播(broadcast)。杀掉 leader 后新 leader 的日志:+11 ms looking → +217 ms leading → +231 ms discovery(确定 epoch)→ +340 ms synchronizing with learner、Sending DIFF → +344 ms Have quorum of supporters(多数派已同步)→ +351 ms 进入 broadcast。", t=tl(t1[:10]), done=[2, 3, 4, 5, 6, 7, 8], kv=KV([['发现', '约 110 ms(含等待 follower 报到)'], ['同步', '约 10 ms'], ['广播', '正常服务']], ['发现'])),
    step("follower 一侧对应的日志:following → discovery → synchronization(diff)→ Learner received NEWLEADER message → Set the current epoch to 2 → Sent NEWLEADER ack(此时才把新 epoch 落盘并向 leader 确认)→ Learner received UPTODATE message → broadcast。NEWLEADER / UPTODATE 是 leader 在同步阶段发给 follower 的两条关键消息。", t=tl(t1[10:]), done=list(range(0, 12)), kv=KV([['NEWLEADER', '同步完成,请确认新 epoch'], ['UPTODATE', '你已追上,可以开始服务']], ['NEWLEADER'])),
    step(f"各阶段用时(leader 视角):选出 leader 后进入 discovery,{pm['discovery']:.0f} ms 后进入 synchronization,{pm['sync']:.0f} ms 后进入 broadcast。发现阶段占了大部分——leader 要等 follower 报到;同步阶段只用约 10 ms,因为这次 follower 只落后一点点(DIFF)。", t=tl(S(2)), b=bars([['discovery', pm['discovery'], f"{pm['discovery']:.0f} ms"], ['synchronization', pm['sync'], f"{pm['sync']:.0f} ms"]], pm['discovery'] * 1.2, done=[0, 1]), kv=KV([['阶段耗时', f"discovery {pm['discovery']:.0f} ms / sync {pm['sync']:.0f} ms"]], ['阶段耗时'])),
    step("INFO 日志里能搜到的协议消息只有 DIFF、NEWLEADER、UPTODATE;文档里提到的发现阶段消息(FOLLOWERINFO、LEADERINFO、ACKEPOCH)在 INFO 日志里没有打印——我只能验证它们的「结果」(discovery 状态、epoch 更新),没有直接看到这些消息本身。", t=tl(S(3)), mark=[0], kv=KV([['能验证', 'DIFF / NEWLEADER / UPTODATE'], ['没有直接看到', 'FOLLOWERINFO / LEADERINFO / ACKEPOCH']], ['没有直接看到'])),
]
A = dict(
    n=39, series='zookeeper', tags='ZooKeeper,ZAB,一致性协议,真实验证,动画演示',
    desc=f'ZAB 一致性协议的三个阶段实测:用杀 leader 后新 leader 与 follower 的日志还原发现 → 同步 → 广播,discovery 约 {pm["discovery"]:.0f} ms、synchronization 约 {pm["sync"]:.0f} ms;NEWLEADER / UPTODATE 消息可见,发现阶段的消息在 INFO 日志里看不到。',
    lead='ZAB 是 ZooKeeper 的一致性协议。教科书讲它有发现、同步、广播三个阶段,运行起来分别是什么样?这篇用杀 leader 之后新一任的日志,把三个阶段按毫秒还原出来。',
    facts=[('3 个阶段', '发现 → 同步 → 广播'), (f'{pm["discovery"]:.0f} + {pm["sync"]:.0f} ms', 'discovery 与 synchronization 的用时(本次)'), ('NEWLEADER / UPTODATE', '同步阶段 leader 发给 follower 的两条关键消息')],
    body=[
        sec('leader 一侧的时间线', '', term('', blk('z39', 1))),
        sec('各阶段花了多久', '', term('', blk('z39', 2))),
        sec('哪些消息没能直接验证', '', term('', blk('z39', 3))),
        sec('分步演示', '', demo('ZAB 三阶段', [('t', 'term', '日志'), ('b', 'bars', '阶段耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群,INFO 日志;时间相对杀 leader 的时刻,每次运行有波动', '没有验证:发现阶段的消息细节、同步阶段 SNAP / TRUNC 的触发(第 42 篇)、follower 数量更多时各阶段的耗时、DEBUG 级别日志(试了一次,没有增加协议消息的行)'],
)
