from lib import *
R = J('z36'); md = R['med']; runs = R['runs']
def S(k): return [l for l in out('z36').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"杀 leader 时的客户端体验:一个写线程和一个读线程每 10 ms 一次,看杀 leader 前后最长的「两次成功之间的间隔」。5 次的写不可用时间 {', '.join(str(round(x['w'])) for x in runs)} ms,读不可用 {', '.join(str(round(x['r'])) for x in runs)} ms。中位:写 {md['w']:.0f} ms、读 {md['r']:.0f} ms。", t=tl(S(1)), b=bars([[f'第 {i + 1} 次写', x['w'], f"{x['w']:.0f} ms"] for i, x in enumerate(runs)], max(x['w'] for x in runs) * 1.1, done=list(range(len(runs)))), kv=KV([['写不可用', f"中位 {md['w']:.0f} ms"], ['读不可用', f"中位 {md['r']:.0f} ms"]], ['写不可用'])),
    step("读和写的不可用时间几乎相同:选举期间所有存活节点都处于 LOOKING(不服务),不仅是写,读也一起停。ZooKeeper 在没有 leader 时拒绝所有请求,而不是只拒绝写。", t=tl(S(1)[-1:]), mark=[0], kv=KV([['选举期间', '读写一起不可用']], ['选举期间'])),
    step("kazoo 的同步调用在断线时会阻塞等待重连,所以这里「失败写次数」几乎为 0(最多 1 次)——客户端侧不会看到异常,只看到某一次调用特别慢。用的是没有额外超时设置的普通客户端;应用层的超时和重试策略会改变这个体验。", t=tl(S(1)[1:6]), kv=KV([['客户端体验', '一次调用变慢,而不是报错(kazoo 默认)']], ['客户端体验'])),
]
A = dict(
    n=36, series='zookeeper', tags='ZooKeeper,Leader选举,可用性,真实验证,动画演示',
    desc=f'Leader 重新选举实测:杀 leader 5 次,持续写 / 读的客户端遇到的最长中断:写中位 {md["w"]:.0f} ms(最小 {md["mn"]:.0f} / 最大 {md["mx"]:.0f})、读中位 {md["r"]:.0f} ms;选举期间读写一起不可用。',
    lead='leader 重新选举期间,应用会感觉到什么?这篇让一个写线程和一个读线程不停地发请求,杀 leader 5 次,记录它们遇到的最长中断。',
    facts=[(f'{md["w"]:.0f} ms', '杀 leader 后写入的最长中断(中位)'), (f'{md["r"]:.0f} ms', '读也同样中断(没有 leader 时全部节点不服务)'), ('不报错、只变慢', 'kazoo 同步调用在断线重连期间阻塞,而不是抛异常')],
    body=[
        sec('不可用的时间窗', '', term('', blk('z36', 1)), '<p>这是「最长两次成功请求之间的间隔」,包含客户端发现断线、重新连接到别的节点的时间,所以略大于第 34 篇里服务端侧的选举耗时。</p>'),
        sec('分步演示', '', demo('重新选举', [('t', 'term', '输出'), ('b', 'bars', '写中断'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;每 10 ms 一次的同步写(创建节点)与读(exists);重复 5 次,每次把被杀的节点启动回来', '没有验证:Java 客户端 / Curator 的重试表现(第 92、97 篇)、客户端请求超时设置较小时的失败率、更大的集群、tickTime 调整后的中断时间'],
)
