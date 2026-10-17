from lib import *
R = J('z46')
def S(k): return [l for l in out('z46').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"syncLimit=2、tickTime=500 ms(所以 follower 与 leader 之间的容忍时间是 1000 ms)。暂停一个 follower:leader 的 zk_synced_followers 在暂停后 {R['down_ms']:.0f} ms 从 2 变成 1(判定它已掉线);恢复(SIGCONT)后 {R['back_ms']:.0f} ms 又变回 2。", t=tl(S(1)), b=bars([['暂停 → 判定掉线', R['down_ms'], f"{R['down_ms']:.0f} ms"], ['恢复 → 重新同步', R['back_ms'], f"{R['back_ms']:.0f} ms"]], 1100, mark=[0], done=[1]), kv=KV([['判定掉线', f"约 {R['down_ms']:.0f} ms(≈ syncLimit × tickTime)"]], ['判定掉线'])),
    step("leader 日志里的证据:「Unexpected exception in LearnerHandler」(与该 follower 的会话处理出错)、「Synchronously closing socket to learner 1.」、「******* GOODBYE …」(关闭这个 learner 的连接);之后该节点作为 LOOKING 发出选票,最后重新加入并「Follower sid: 1 : info : …」报到。", t=tl(S(2)), kv=KV([['leader 判定超时', '关闭 learner 连接']], ['leader 判定超时'])),
    step(f"暂停 0.5 秒(短于 syncLimit × tickTime = 1 秒):follower 不会被判定掉线,synced_followers 仍是 {R['short']},Mode 仍是 follower。", t=tl(S(3)), done=[0], kv=KV([['短暂停顿', '在容忍范围内,不被踢出']], ['短暂停顿'])),
]
A = dict(
    n=46, series='zookeeper', tags='ZooKeeper,syncLimit,Follower,真实验证,动画演示',
    desc=f'数据落后 / 无响应节点的处理实测:syncLimit=2 × tickTime=500 ms 时,暂停 follower 后约 {R["down_ms"]:.0f} ms leader 把它判定为掉线(synced_followers 2 → 1),恢复后约 {R["back_ms"]:.0f} ms 重新同步;暂停 0.5 s 则不会被踢出。',
    lead='follower 变慢或卡住时,leader 什么时候放弃它?这篇把 syncLimit 与 tickTime 调小,暂停一个 follower,记录 leader 的 synced_followers 什么时候变、日志里怎么说。',
    facts=[(f'{R["down_ms"]:.0f} ms', '暂停 follower 到 leader 判定它掉线(syncLimit × tickTime = 1000 ms)'), (f'{R["back_ms"]:.0f} ms', '恢复后重新同步完成'), ('0.5 s 不够', '短于 syncLimit × tickTime 的停顿不会被踢出')],
    body=[
        sec('暂停多久会被判定掉线', '', term('', blk('z46', 1)), '<p>syncLimit 以 tickTime 为单位,默认 5 × 2000 ms = 10 秒;这里为了能快速观察调成了 2 × 500 ms。生产环境里 JVM 的长 GC 停顿如果超过这个时间,follower 就会被踢出再重新同步(第 62 篇看 GC)。</p>'),
        sec('日志里的证据', '', term('', blk('z46', 2))),
        sec('短暂停顿', '', term('', blk('z46', 3))),
        sec('分步演示', '', demo('syncLimit', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群,tickTime=500、syncLimit=2、initLimit=4;暂停用 SIGSTOP / SIGCONT;synced_followers 每 50 ms 采样', '没有验证:默认值(syncLimit=5、tickTime=2000)下的行为、慢但没有停顿的 follower(网络延迟高)、leader 被暂停的情形、syncLimit 与会话超时的相互作用'],
)
