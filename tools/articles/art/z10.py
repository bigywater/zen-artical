from lib import *
R = J('z10'); g = R['grow']; rs = R['restart']
import re
LOADED = (re.search(r'loaded in (\d+) ms', out('z10')) or [None, '?'])[1]
def S(k): return [l for l in out('z10').split('== ')[k].splitlines()[1:] if l.strip()]
base, last = g[0], g[-1]
per = (last[2] - base[2]) * 1048576 / (last[0] - base[0])
steps = [
    step(f"DataTree 是整棵树的内存表示。每个 znode 数据 200 字节,znode 数从 {base[0]} 增长到 {last[0]}:mntr 的近似数据大小 {last[1] / 1048576:.1f} MiB,但 JVM 已用堆(每次先触发 GC)从 {base[2]:.1f} MiB 涨到 {last[2]:.1f} MiB,进程 RSS 从 {base[3]} MiB 涨到 {last[3]} MiB。", t=tl(S(1)), b=bars([[f'{x[0]} 个', x[2], f'{x[2]:.1f} MiB'] for x in g], last[2] * 1.1, done=list(range(len(g)))), kv=KV([['mntr 近似数据大小', '只算数据本身'], ['JVM 已用堆', f'约每个 znode {per / 1024:.2f} KiB(含 200 B 数据)']], ['JVM 已用堆'])),
    step(f"读取不走磁盘:先用 srst 清零统计,再随机读 20000 次,srvr 的 Latency min/avg/max 是 {R['lat']} ms——平均约 0.02 ms。读直接命中内存里的树。", t=tl(S(2)), done=[0], kv=KV([['读延迟', '约 0.02 ms(内存)']], ['读延迟'])),
    step(f"重启要把整棵树重新读回内存:{last[0]} 个 znode,停机时快照文件总大小 {rs['snap_mib']:.1f} MiB;日志里「Snapshot loaded in … ms」是 {LOADED} ms;重启到能响应 {rs['ms']:.0f} ms,重启后 znode 数 {rs['count']},一个不少。", t=tl(S(3)), done=[0, 1, 2, 3, 4], b=bars([['重启到能响应', rs['ms'], f"{rs['ms']:.0f} ms"]], rs['ms'] * 1.2, done=[0]), kv=KV([['重启', '读快照 + 回放日志重建整棵树']], ['重启'])),
]
A = dict(
    n=10, series='zookeeper', tags='ZooKeeper,DataTree,内存,快照,真实验证,动画演示',
    desc=f'内存里的 DataTree 实测:每个 znode 数据 200 字节,{last[0]} 个 znode 时 JVM 已用堆 {last[2]:.1f} MiB(约每个 {per / 1024:.2f} KiB),读延迟约 0.02 ms;重启从快照重建整棵树 {rs["ms"]:.0f} ms。',
    lead='ZooKeeper 把整棵树放在内存里,这是它读得快、也是它不适合存大量数据的原因。这篇创建到 20 万个 znode,量 JVM 堆和进程内存是怎么随 znode 数增长的、读延迟是多少、重启把树读回内存要多久。',
    facts=[(f'{per / 1024:.2f} KiB', f'每个 znode(含 200 字节数据)占用的 JVM 堆,由 {last[0]} 个 znode 的增量算出'), ('约 0.02 ms', '服务端统计的读延迟(清零统计后随机读 20000 次)'), (f'{rs["ms"]:.0f} ms', f'{last[0]} 个 znode 的节点重启到能响应')],
    body=[
        sec('内存随 znode 数增长', '', term('', blk('z10', 1)), f'<p>mntr 的 <code>zk_approximate_data_size</code> 只估算了路径和数据的大小(约 {last[1] / 1048576:.0f} MiB),真正的 JVM 堆占用大得多,因为每个 znode 还有对象头、stat 结构、父子关系等开销。容量规划(第 60 篇)要用实测的堆占用,不是数据大小。(这里的「已用堆」每次都先手动触发了一次 GC;JVM 堆上限我设成 256 MiB。)</p>'),
        sec('读不走磁盘', '', term('', blk('z10', 2))),
        sec('重启重建整棵树', '', term('', blk('z10', 3)), '<p>数据越多,重启越慢,选举后 follower 同步(第 42 篇)也越慢。快照加载日志里的耗时就是把树读回内存的时间。</p>'),
        sec('分步演示', '', demo('内存里的树', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。JVM 堆上限调成 256 MiB;znode 路径形如 /d/k000001,数据 200 字节,用 kazoo 异步创建;snapCount=200000;已用堆用 jcmd GC.run + GC.heap_info 取得', '没有验证:更深的路径层级、更小或更大的数据对每个 znode 开销的影响、G1 / ZGC 等不同垃圾回收器、堆接近上限时的行为(第 62 篇看 GC 停顿)、集群里 follower 的内存'],
)
