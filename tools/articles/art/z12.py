from lib import *
R = J('z12')
def S(k): return [l for l in out('z12').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("会话 id 的最高字节是创建它的服务端的 myid:分别通过 1、2、3 号节点建立会话,得到 0x01000b…、0x02000b…、0x03000b… 三个 id。所以从会话 id 就能看出它最初是在哪个节点上建立的。", t=tl(S(1)), done=[0, 1, 2], kv=KV([['会话 id', '[myid][时间戳][计数]']], ['会话 id'])),
    step(f"空闲时靠 ping 保活:请求超时 6 s,客户端空闲 12 s,服务端统计的该连接 sent(回给客户端的包)增加了 {R['ping']['delta']} 个,正好对应每 2 秒(超时的 1/3)一个 ping 的响应。只要还在 ping,会话就不会过期。", t=tl(S(2)), kv=KV([['ping 间隔', '会话超时的 1/3'], ['12 s 空闲', f"{R['ping']['delta']} 个 ping"]], ['ping 间隔'])),
    step("dump 命令:leader 返回 SessionTracker 的会话分桶(「Session Sets」,按过期时间分组,每桶里列出会话 id)和持有临时节点的会话;follower 返回「Global Sessions」及每个会话的超时。两者都含有这个会话和它的临时节点。", t=tl(S(3)), kv=KV([['leader dump', '按过期时间分桶'], ['follower dump', 'Global Sessions + 超时']], ['leader dump'])),
    step(f"会话是集群级的:连在 follower 上的会话,leader 的 zk_global_sessions = {R['gs']},follower 的也是 2;zk_local_sessions = 0(默认没有启用本地会话)。", t=tl(S(4)), done=[0], kv=KV([['global_sessions', '集群里全局可见'], ['local_sessions', '0(默认不启用)']], ['global_sessions'])),
]
A = dict(
    n=12, series='zookeeper', tags='ZooKeeper,会话,Session,真实验证,动画演示',
    desc=f'会话机制实测:会话 id 最高字节是创建它的服务端 myid;空闲时每 timeout/3 一个 ping(6 s 超时空闲 12 s 共 {R["ping"]["delta"]} 个);leader 的 dump 按过期时间分桶;连在 follower 上的会话在 leader 的 zk_global_sessions 里可见。',
    lead='会话(Session)是 ZooKeeper 里最核心的概念:临时节点、watch、重连都围绕它。这篇用 3 节点集群看会话 id 怎么构成、空闲时怎么保活、服务端怎么跟踪它。',
    facts=[('最高字节 = myid', '会话 id 的构成:服务端 id + 时间戳 + 计数'), ('timeout / 3', 'ping 的间隔:6 s 超时 → 每 2 秒一个'), ('global_sessions', '会话是集群级的,不管连在哪个节点')],
    body=[
        sec('会话 id', '', term('', blk('z12', 1))),
        sec('保活:ping', '', term('', blk('z12', 2)), '<p>如果客户端持续有请求,请求本身就能保活;只有空闲时才需要 ping。</p>'),
        sec('服务端怎么跟踪', '', term('', blk('z12', 3))),
        sec('集群级会话', '', term('', blk('z12', 4)), '<p>「本地会话」(local session)是 ZooKeeper 的可选特性,本文没有启用也没有验证。</p>'),
        sec('分步演示', '', demo('会话', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;ping 次数取自 cons 里该连接的 sent 差值', '没有验证:会话过期的细节(第 13 篇)、本地会话(localSessionsEnabled)、会话升级、dump 输出里每一项的完整含义、大量会话的跟踪开销(第 14 篇)'],
)
