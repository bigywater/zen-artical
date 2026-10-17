from lib import *
R = J('z18'); cn, wt = R['conn'], R['watch']
def S(k): return [l for l in out('z18').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("基线:20000 个空 znode(用来被 watch),没有额外连接:JVM 已用堆 12.3 MiB(每次测量前先触发一次 GC),RSS 125 MiB。", t=tl([out('z18').splitlines()[0][3:]]), kv=KV([['基线', '堆 12.3 MiB / RSS 125 MiB']], ['基线'])),
    step(f"连接的内存代价:新增 400 个空闲连接(没有 watch),zk_num_alive_connections = {cn['conns']},JVM 已用堆增加 {cn['heap']:.1f} MiB、RSS 增加 {cn['rss']:.0f} MiB——每个空闲连接约 {cn['heap'] * 1024 / 400:.1f} KiB 堆。", t=tl(S(1)), done=[0], kv=KV([['400 个空闲连接', f"堆 +{cn['heap']:.1f} MiB"]], ['400 个空闲连接'])),
    step(f"watch 的内存代价:这 400 个客户端各对 50 个不同的 znode 注册 watch,共 {wt['count']} 个 watch;JVM 堆再增加 {wt['heap']:.1f} MiB——约每个 watch {wt['heap'] * 1048576 / int(wt['count']):.0f} 字节;wchs 显示「400 connections watching 20000 paths Total watches:20000」。", t=tl(S(2)), b=bars([['400 个连接', cn['heap'], f"+{cn['heap']:.1f} MiB"], ['20000 个 watch', wt['heap'], f"+{wt['heap']:.1f} MiB"]], max(cn['heap'], wt['heap']) * 1.2, done=[0, 1]), kv=KV([['每个 watch', f"约 {wt['heap'] * 1048576 / int(wt['count']):.0f} 字节"]], ['每个 watch'])),
    step(f"同一个连接对同一个路径重复注册 100 次 watch:zk_watch_count 从 {R['dup'][0]} 到 {R['dup'][1]},没有增加——服务端对「同一连接 + 同一路径」的 watch 去重,所以客户端在循环里反复 get(path, watch=…) 不会让服务端内存无限增长(但每次回调都会触发,第 17 篇)。", t=tl(S(3)), kv=KV([['重复注册', '同连接同路径只算 1 个']], ['重复注册'])),
]
A = dict(
    n=18, series='zookeeper', tags='ZooKeeper,内存,连接,Watcher,真实验证,动画演示',
    desc=f'连接数、Watcher 数量和内存的关系实测:400 个空闲连接堆增加 {cn["heap"]:.1f} MiB(约每个 {cn["heap"] * 1024 / 400:.1f} KiB);20000 个 watch 再增加 {wt["heap"]:.1f} MiB(约每个 {wt["heap"] * 1048576 / int(wt["count"]):.0f} 字节);同一连接对同一路径重复注册只算 1 个。',
    lead='ZooKeeper 服务端要为每个连接、每个 watch 付出多少内存?这篇在 20000 个 znode 的树上,先加 400 个空闲连接,再加 20000 个 watch,每一步都先 GC 再读 JVM 堆,得到每个连接、每个 watch 的大致内存代价。',
    facts=[(f'约 {cn["heap"] * 1024 / 400:.1f} KiB', '每个空闲连接占用的 JVM 堆'), (f'约 {wt["heap"] * 1048576 / int(wt["count"]):.0f} 字节', '每个 watch 占用的 JVM 堆'), ('去重', '同一连接对同一路径的重复注册只算 1 个')],
    body=[
        sec('连接的代价', '', term('', blk('z18', 1))),
        sec('watch 的代价', '', term('', blk('z18', 2)), '<p>这些数字是在 JVM 堆 256 MiB、小路径的条件下得到的粗略值,只用来估数量级。容量规划见第 60 篇。</p>'),
        sec('重复注册', '', term('', blk('z18', 3))),
        sec('分步演示', '', demo('连接与 watch 的内存', [('t', 'term', '输出'), ('b', 'bars', '堆增量'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,maxClientCnxns=2000;连接是 kazoo 客户端;堆用 jcmd GC.run + GC.heap_info 读取;路径形如 /w/n00000', '没有验证:Netty 连接(NIO 之外)的内存、路径很长时 watch 的开销、集群里每个节点的 watch 内存、持久 watch 的内存(第 16 篇)、连接的堆外内存'],
)
