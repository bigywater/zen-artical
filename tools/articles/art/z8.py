from lib import *
R = J('z8')
def S(k): return [l for l in out('z8').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("持久节点的 ephemeralOwner = 0x0;临时节点的 ephemeralOwner 就是创建它的会话 id(本例创建者的会话 id 与 ephemeralOwner 相等)。临时节点不能有子节点:create /eph/child → NoChildrenForEphemeralsError。", t=tl(S(1) + S(2)), done=[0, 1, 2], kv=KV([['ephemeralOwner', '会话 id'], ['临时节点', '不能有子节点']], ['ephemeralOwner'])),
    step(f"会话正常 close():另一个客户端轮询,节点在约 {R['close_ms']:.0f} ms 内消失。客户端进程被 kill -9(没有 close):杀掉后立即查询,节点还在;{R['kill_ms'] / 1000:.1f} 秒后才消失——等于协商后的会话超时 6 秒(请求 6000 ms,tickTime=1000,在 2000–20000 范围内)再加一点检测延迟。", t=tl(S(3) + S(4)), b=bars([['close()', R['close_ms'], f"{R['close_ms']:.0f} ms"], ['kill -9', R['kill_ms'], f"{R['kill_ms']:.0f} ms"]], R['kill_ms'] * 1.1, done=[0], mark=[1]), kv=KV([['正常关闭', '几毫秒内删除'], ['进程被杀', '要等会话超时']], ['进程被杀'])),
    step("服务端重启:会话信息保存在快照和事务日志里。客户端请求的会话超时 30 秒(在 tickTime=1000 下被限制为 20 秒),服务端重启后客户端自动重连,同一个会话 id、临时节点 /eph-restart 还在——重启服务端不等于临时节点消失。", t=tl(S(5)), done=[0], kv=KV([['服务端重启', '会话与临时节点都保留']], ['服务端重启'])),
    step(f"TTL 节点与容器节点(3.6+,需要 -Dzookeeper.extendedTypesEnabled=true):create -t 2000 /ttl1 存在了 {R['ttl_ms']:.0f} ms 后被删除(我把容器检查间隔调成 300 ms);容器节点 /cont 在最后一个子节点被删除后 {R['container_ms']:.0f} ms 内被自动删除;没有打开该开关的节点上 create -t 会得到「KeeperErrorCode = Unimplemented」。", t=tl(S(6)), b=bars([['TTL=2000 ms 的存活', R['ttl_ms'], f"{R['ttl_ms']:.0f} ms"], ['容器节点删除延迟', R['container_ms'], f"{R['container_ms']:.0f} ms"]], 2200, done=[0, 1]), kv=KV([['TTL / 容器节点', '需要 extendedTypesEnabled'], ['清理', '由 ContainerManager 定期检查']], ['TTL / 容器节点'])),
]
A = dict(
    n=8, series='zookeeper', tags='ZooKeeper,临时节点,会话,TTL,真实验证,动画演示',
    desc=f'临时节点与持久节点实测:ephemeralOwner 等于会话 id;close() 后几毫秒内消失,进程被 kill -9 要等 {R["kill_ms"] / 1000:.1f} 秒的会话超时;服务端重启后同一会话的临时节点仍在;TTL 节点与容器节点需要 extendedTypesEnabled。',
    lead='临时节点什么时候消失?客户端被杀、服务端重启、会话正常关闭,三种情形差别很大,也是做服务发现、分布式锁时最需要弄清的行为。这篇逐一量出来,最后看 TTL 节点与容器节点两种较新的节点类型。',
    facts=[(f'{R["close_ms"]:.0f} ms vs {R["kill_ms"] / 1000:.1f} s', '临时节点消失的时间:正常 close() vs 进程被 kill -9(会话超时 6 s)'), ('ephemeralOwner = 会话 id', '持久节点是 0x0;临时节点没有子节点'), ('服务端重启不删', '会话保存在快照 / 日志里,客户端在超时内重连,临时节点还在')],
    body=[
        sec('stat 里的区别', '', term('', blk('z8', 1) + '\n' + blk('z8', 2))),
        sec('什么时候被删除', '', term('', blk('z8', 3) + '\n' + blk('z8', 4)), '<p>这就是服务发现里「实例挂了多久会被摘除」的答案:取决于会话超时(第 13 篇),不是 TCP 断开的时间。</p>'),
        sec('服务端重启', '', term('', blk('z8', 5))),
        sec('TTL 节点与容器节点', '', term('', blk('z8', 6)), '<p>这两种节点由服务端的 ContainerManager 定期清理,清理间隔默认 60 秒(本实验把它调成 300 ms 才能观察),所以实际的消失时间会比 TTL 长一个检查周期。</p>'),
        sec('分步演示', '', demo('临时节点的生命周期', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。tickTime=1000;客户端 kazoo(请求的会话超时 6 s);TTL / 容器节点用官方 CLI 创建,JVM 加 -Dzookeeper.extendedTypesEnabled=true、-Dznode.container.checkIntervalMs=300', '没有验证:多服务端节点集群里重启 leader 对临时节点的影响(第 36 篇)、会话迁移、容器检查间隔的默认值 60 s 下的实际延迟(只看到日志里写着 checkIntervalMs=60000)、kazoo 的会话重连策略'],
)
