from lib import *
R = J('z43'); runs = R['runs']
def S(k): return [l for l in out('z43').split('== ')[k].splitlines()[1:] if l.strip()]
tot_a = sum(x['acked'] for x in runs); tot_u = sum(x['unknown'] for x in runs); tot_p = sum(x['present'] for x in runs)
steps = [
    step(f"leader 崩溃时有写请求在进行:一个线程不停创建节点,记录每个请求的结果(成功 = 已确认,ConnectionLoss = 未确认),杀 leader 后核对。5 次共确认 {tot_a} 个写入,确认之后丢失的 {sum(x['lost'] for x in runs)} 个;每次各有 1 个请求得到 ConnectionLoss(崩溃那一刻正在进行的),共 {tot_u} 个,其中实际已经写入的有 {tot_p} 个。", t=tl(S(1)), b=bars([[f'第 {i + 1} 次', x['acked'], f"{x['acked']} 确认"] for i, x in enumerate(runs)], max(x['acked'] for x in runs) * 1.1, done=list(range(len(runs)))), kv=KV([['已确认的写入', '一个都不丢'], ['ConnectionLoss 的写', f'{tot_p} / {tot_u} 其实写入了']], ['已确认的写入'])),
    step("所以 ConnectionLoss 的含义是「结果未知」:同一个崩溃场景里有的请求没写成,有的其实已经被多数派接受、被新 leader 保留(与第 20 篇的「响应丢失」一致)。要得到确定的结果,必须在重连后查询,或者设计成可重试的幂等写。", t=tl(S(1)[-1:]), mark=[0], kv=KV([['ConnectionLoss', '结果未知,不是失败']], ['ConnectionLoss'])),
    step(f"崩溃恢复完成后,三个节点的 Zxid 一致({', '.join(set(R['counts'].keys()))} 的 zxid 相同:{R['zxid_same']}),各节点上 /r0..r4 下的 znode 总数也一致({list(R['counts'].values())[0]} 个)——恢复后集群里没有分歧。", t=tl(S(2)), done=[0, 1], kv=KV([['恢复后', 'zxid 与数据全部一致']], ['恢复后'])),
]
A = dict(
    n=43, series='zookeeper', tags='ZooKeeper,ZAB,崩溃恢复,持久性,真实验证,动画演示',
    desc=f'ZAB 崩溃恢复实测:持续写入时杀 leader 5 次,共 {tot_a} 个已确认的写入全部保留(丢失 0 个);每次崩溃时正在进行的请求得到 ConnectionLoss,{tot_u} 个里有 {tot_p} 个其实已经写入;恢复后三个节点 zxid 与数据一致。',
    lead='leader 崩溃的瞬间,有些写已经确认、有些还在路上。ZooKeeper 保证什么?这篇让一个线程持续写入、杀掉 leader 并核对每一个请求的结果,验证「已确认的写不丢」,并看看「没确认的」到底发生了什么。',
    facts=[('0 个丢失', f'5 次崩溃共 {tot_a} 个已确认写入,全部保留'), (f'{tot_p} / {tot_u}', 'ConnectionLoss 的请求里,实际已经写入的数量'), ('恢复后一致', '三个节点 zxid 与 znode 总数相同')],
    body=[
        sec('已确认的写入不丢', '', term('', blk('z43', 1)), '<p>已确认 = 客户端的 create 调用返回成功。这个保证来自「只有多数派确认的提案才会被提交」加上选举规则(第 35 篇):新 leader 一定拥有所有已提交的事务。</p>'),
        sec('恢复后的一致性', '', term('', blk('z43', 2))),
        sec('分步演示', '', demo('崩溃恢复', [('t', 'term', '输出'), ('b', 'bars', '确认的写入'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;写入线程是单个 kazoo 客户端的同步 create;每次杀当时的 leader 后等 6 秒再核对;共 5 次', '没有验证:多个客户端并发写、杀掉的是 follower 的情形、磁盘 fsync 关闭(forceSync=no)时的持久性、整个集群同时断电'],
)
