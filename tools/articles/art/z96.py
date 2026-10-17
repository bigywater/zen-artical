import re
from lib import *
R = J('z96'); T = R['stdout']
def S(k): return [x for x in out('z96').split('== ')[k].splitlines()[1:] if x.strip()]
a1 = re.search(r'一.*?\n.*?true (\d+) 次,false (\d+) 次;最终值 (\d+);用时 ([\d.]+) s', T, re.S).groups()
a2 = re.search(r'二.*?\n.*?true (\d+) 次,false (\d+) 次;最终值 (\d+)', T, re.S).groups()
a3 = re.search(r'三.*?\n.*?true (\d+) 次,false (\d+) 次;最终值 (\d+);用时 ([\d.]+) s', T, re.S).groups()
th = [(int(x), int(y)) for x, y in re.findall(r'\s*(\d+) 线程:(\d+) 次/s', T)]
sq = re.search(r'不同的 (\d+) 个;用时 ([\d.]+) s\((\d+) 个/s', T).groups()
steps = [
    step(f"DistributedAtomicLong 默认乐观方式:读值、算新值、带 version 写回,冲突就按重试策略重试。10 线程各 increment() 100 次:{a1[0]} 次 succeeded()=true、{a1[1]} 次 false,最终值 {a1[2]},用时 {a1[3]} s。", t=tl(S(1)), done=[0], kv=KV([['最终值', f'{a1[2]} / 1000'], ['失败', a1[1]]], ['最终值'])),
    step(f"重试策略只允许重试 1 次:同样的 1000 次 increment,{a2[0]} 次成功、{a2[1]} 次 succeeded()=false,最终值 {a2[2]}(正好等于成功次数)—— 失败的不抛异常、也不计数,你必须检查 succeeded()。忘了检查就会悄悄少计数。", t=tl(S(2)), mark=[0], b=bars([['成功', int(a2[0]), a2[0]], ['succeeded()=false', int(a2[1]), a2[1]]], 1000, mark=[1], done=[0]), kv=KV([['重试 1 次', f'成功 {a2[0]} / 失败 {a2[1]}'], ['失败时', '不抛异常']], ['重试 1 次'])),
    step(f"PromotedToLock:乐观写失败后升级成用分布式锁串行执行。同样只允许重试 1 次的策略,{a3[0]} 次成功、{a3[1]} 次失败,最终值 {a3[2]},用时 {a3[3]} s —— 保证成功,代价是退化为串行(此处和乐观方式耗时相近)。", t=tl(S(3)), done=[0, 1], kv=KV([['PromotedToLock', f'{a3[0]} / 1000 成功']], ['PromotedToLock'])),
    step("吞吐随线程数:" + ';'.join(f'{t} 线程 {v} 次/s' for t, v in th) + "。线程越多冲突越多,总吞吐反而下降 —— 这是一个热点节点上的 CAS,不能靠加线程扩展。", t=tl(S(4)), b=bars([[f'{t} 线程', v, f'{v}/s'] for t, v in th], max(v for t, v in th), mark=[3], done=[0, 1, 2]), kv=KV([['1 → 10 线程', f'{th[0][1]} → {th[-1][1]} 次/s']], ['1 → 10 线程'])),
    step(f"另一种发号方式:创建 PERSISTENT_SEQUENTIAL 节点并立刻删除,用序号当 ID:10 线程 1000 个序号全部不同({sq[0]} 个),{sq[2]} 个/s(含删除),没有冲突重试。唯一但不「连续有意义」—— 序号是父节点里的计数,不是业务计数。", t=tl(S(5)), done=[0, 1], kv=KV([['顺序节点发号', f'{sq[0]} 个全不同,{sq[2]} 个/s']], ['顺序节点发号'])),
]
A = dict(
    n=96, series='zookeeper', tags='ZooKeeper,Curator,DistributedAtomicLong,计数器,真实验证,动画演示',
    desc=f'Curator DistributedAtomicLong 实测:10 线程 1000 次 increment 最终值 {a1[2]};重试只允许 1 次时 {a2[1]} 次 succeeded()=false 且不抛异常(最终值 {a2[2]});PromotedToLock 保证 1000/1000;吞吐随线程数从 {th[0][1]} 降到 {th[-1][1]} 次/s;顺序节点发号 {sq[2]} 个/s。',
    lead='用 ZooKeeper 做全局计数器 / 发号器是常见需求。Curator 的 DistributedAtomicLong 用乐观重试实现,但「失败了不抛异常」这个设计很容易踩坑。这篇量正确性、重试耗尽时的行为、PromotedToLock、吞吐随线程数的变化,并与顺序节点发号比较。',
    facts=[(f'{a2[1]} / 1000', '重试只允许 1 次时 succeeded()=false 的次数(不抛异常)'), (f'{th[0][1]} → {th[-1][1]}', '1 线程到 10 线程的吞吐(次/s),冲突让总吞吐下降'), (f'{sq[2]} 个/s', '顺序节点发号的吞吐(1000 个序号全部唯一)')],
    body=[
        sec('乐观方式', '', term('', blk('z96', 1)), '<p>原理就是<a href="zookeeper-hot-config.html">乐观锁(带 version 的写)</a>:读到 version,写回时版本不符就重试。</p>'),
        sec('重试耗尽', '', term('', blk('z96', 2))),
        sec('PromotedToLock', '', term('', blk('z96', 3)), '<p>锁的机制见<a href="zookeeper-curator-lock.html">上一篇</a>。</p>'),
        sec('吞吐', '', term('', blk('z96', 4)), '<p>每次 increment 至少一次读和一次写(都要经过 leader 写提交),所以它是一个低频计数器。需要每秒数万次的计数,应当在应用内批量累加后定期写入,或者用别的存储。</p>'),
        sec('顺序节点发号', '', term('', blk('z96', 5)), '<p>顺序号的行为见<a href="zookeeper-sequential-node.html">顺序节点</a>:由服务端串行分配,不会冲突。</p>'),
        sec('分步演示', '', demo('原子计数器', [('t', 'term', '输出'), ('b', 'bars', '次数 / 吞吐'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Curator 5.7.1 + OpenJDK 17;10 线程各用独立客户端;同机本地回环;吞吐受 fsync 影响(见第 55 篇)', '没有验证:SharedCount / DistributedIdQueue 等其它计数配方、PromotedToLock 的 lockPath 与重试策略的组合、跨机房的冲突率、与 Redis INCR 的对比'],
)
