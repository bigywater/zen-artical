import re
from lib import *
R = J('z95'); T = R['stdout']; st = R['stale']
def S(k): return [x for x in out('z95').split('== ')[k].splitlines()[1:] if x.strip()]
ld = int(re.search(r'加载完成:(\d+) ms', T).group(1)); m = re.search(r'缓存 ([\d.]+) µs,直接读 ZooKeeper (\d+) µs\(约 (\d+) 倍', T); cm, zm, mult = m.group(1), m.group(2), m.group(3)
ev = re.findall(r'(建|改|删) → (\w+),延迟 ([\d.]+) ms', T); ch = re.search(r'收到 NODE_CHANGED (\d+) 次', T).group(1)
steps = [
    step(f"CuratorCache 初始加载:/tree 下 1000 个 1 KiB 节点,{ld} ms 内加载完成(收到 initialized);之后读一个节点,缓存 {cm} µs,直接读 ZooKeeper {zm} µs,约 {mult} 倍。缓存读是本地内存里的 map 查找,不走网络。", t=tl(S(1)), done=[0], b=bars([['缓存读', float(cm), f'{cm} µs'], ['直读 ZooKeeper', float(zm), f'{zm} µs']], float(zm), mark=[1], done=[0]), kv=KV([['初始加载 1000 节点', f'{ld} ms'], ['缓存读 vs 直读', f'{cm} µs vs {zm} µs']], ['缓存读 vs 直读'])),
    step(f"事件:{' / '.join(f'{o}→{t}({d} ms)' for o, t, d in ev)};连续同步 setData 200 次,监听器只收到 {ch} 次 NODE_CHANGED,缓存最终值是最后一次的 v199 —— 和原生 watch 一样,事件会合并,但最终状态一致。", t=tl(S(2)), done=[0], kv=KV([['快速更新 200 次', f'{ch} 次事件'], ['最终值', '一致 v199']], ['快速更新 200 次'])),
    step(f"缓存客户端与服务端之间的连接被切断 {st['unblock']:.0f} s,期间服务端 /cfg 在 +{st['changed']:.1f} s 被改成 v2:SUSPENDED(+0.1 s)→ LOST(+3.1 s,会话超时 3 s)→ RECONNECTED(+{st['unblock']+0.1:.1f} s)。整个断开期间缓存一直返回旧值 v1(没有任何「数据可能过期」的标记),恢复后 0.1 s 就追上 v2。", t=tl(S(3)), mark=[0], kv=KV([['断开期间读缓存', '返回旧值 v1'], ['恢复后追上', '0.1 s']], ['断开期间读缓存'])),
]
A = dict(
    n=95, series='zookeeper', tags='ZooKeeper,Curator,CuratorCache,本地缓存,真实验证,动画演示',
    desc=f'Curator 5.7.1 的 CuratorCache 实测:1000 个节点 {ld} ms 加载完成;读缓存 {cm} µs vs 直读 ZooKeeper {zm} µs(约 {mult} 倍);事件类型与延迟;200 次快速更新合并成 {ch} 次事件;断网 {st["unblock"]:.0f} s 期间缓存一直返回旧值、恢复后 0.1 s 追上。',
    lead='CuratorCache 把 ZooKeeper 的一棵子树镜像到本地内存,并在变化时回调。它让读变成本地查表,但也带来「缓存可能过期」的问题。这篇量加载速度、读的收益、事件的延迟与合并,以及断网期间缓存返回什么。',
    facts=[(f'{mult} 倍', f'读缓存({cm} µs)相对直读 ZooKeeper({zm} µs)'), (f'{ch} / 200', '快速连续更新 200 次时监听器收到的 NODE_CHANGED 数'), ('旧值', '断网期间缓存一直返回旧值,没有过期标记')],
    body=[
        sec('加载与读取', '', term('', blk('z95', 1)), '<p>缓存要镜像整棵子树,节点更多时要关心 <a href="zookeeper-connection-watcher-memory.html">watch 的内存</a>。</p>'),
        sec('事件', '', term('', blk('z95', 2)), '<p>合并行为的原因见<a href="zookeeper-watcher-once.html">watch 的一次性</a>。如果每次变更都要处理,请把变更写成顺序节点(队列)而不是改同一个节点。</p>'),
        sec('断网时的缓存', '', term('', blk('z95', 3)), '<p>缓存本身没有「过期时间」。需要时请在 ConnectionStateListener 里把应用标记为「配置可能过期」。这里「断网」用 TCP 代理拒绝连接实现。</p>'),
        sec('分步演示', '', demo('CuratorCache', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Curator 5.7.1 + OpenJDK 17;读耗时是 100000 次缓存读 / 2000 次直读的平均,同机本地回环;连接中断用 TCP 代理拒绝连接,会话超时 3 s', '没有验证:缓存的堆内存占用、选项 SINGLE_NODE_CACHE / DO_NOT_CLEAR_ON_CLOSE 的行为、缓存与旧的 PathChildrenCache / TreeCache 的差别、数十万节点的加载'],
)
