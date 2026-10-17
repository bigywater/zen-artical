from lib import *
R = J('z60'); pts = R['pts']; pr = R['pred']; cf = R['coef']; cn = R['conn']
def S(k): return [l for l in out('z60').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"三组实测(每个 znode 的路径名固定 8 个字符):5 万 × 100 字节堆增量 {pts[0]['heap']:.1f} MiB、5 万 × 1000 字节 {pts[1]['heap']:.1f} MiB、15 万 × 100 字节 {pts[2]['heap']:.1f} MiB;快照 {pts[0]['snap']:.1f} / {pts[1]['snap']:.1f} / {pts[2]['snap']:.1f} MiB。最小二乘估计:每个 znode 约 {cf[0]:.0f} 字节的固定开销加每个数据字节约 {cf[1]:.2f} 字节。", t=tl(S(1)), b=bars([[f"{p['N'] // 1000}k × {p['size']}B", p['heap'], f"{p['heap']:.0f} MiB"] for p in pts], max(p['heap'] for p in pts) * 1.1, done=[0, 1, 2]), kv=KV([['每个 znode', f"≈ {cf[0]:.0f} B + 数据"], ['每个数据字节', f"≈ {cf[1]:.2f} B"]], ['每个 znode'])),
    step(f"用它预测一个没测过的配置:10 万个 znode × 500 字节,预测堆增量 {pr['pred']:.1f} MiB,实测 {pr['real']:.1f} MiB,误差 {abs(pr['pred'] - pr['real']) / pr['real'] * 100:.1f}%;快照文件 {pr['snap']:.1f} MiB。在路径长度固定的前提下,这个线性模型够用来估算。", t=tl(S(2)), done=[0], kv=KV([['预测 vs 实测', f"{pr['pred']:.1f} vs {pr['real']:.1f} MiB"]], ['预测 vs 实测'])),
    step(f"连接与 watch 另算:同样 5 万 × 100 字节的树,加 300 个连接和 6000 个 watch,堆增量 {cn['with_conn']:.1f} MiB,比没有它们时({cn['without']:.1f} MiB)多 {cn['with_conn'] - cn['without']:.1f} MiB——相对数据本身很小,但要看连接数的规模。", t=tl(S(3)), done=[0], kv=KV([['300 连接 + 6000 watch', f"+{cn['with_conn'] - cn['without']:.1f} MiB"]], ['300 连接 + 6000 watch'])),
]
A = dict(
    n=60, series='zookeeper', tags='ZooKeeper,容量规划,内存,真实验证,动画演示',
    desc=f'ZooKeeper 容量规划:由三组实测拟合堆占用 ≈ 每个 znode {cf[0]:.0f} 字节 + 每个数据字节 {cf[1]:.2f} 字节,预测 10 万 × 500 字节为 {pr["pred"]:.1f} MiB、实测 {pr["real"]:.1f} MiB(误差 {abs(pr["pred"] - pr["real"]) / pr["real"] * 100:.1f}%);300 连接 + 6000 watch 另加 {cn["with_conn"] - cn["without"]:.1f} MiB。',
    lead='要给 ZooKeeper 配多大的堆、多大的磁盘?拍脑袋不如拟合:用几组真实的 znode 数与数据大小测出堆占用,拟合一个线性模型,再拿一个没测过的配置验证预测。',
    facts=[(f'≈ {cf[0]:.0f} B + 数据', '每个 znode 的堆开销(路径 8 字符)'), (f'{abs(pr["pred"] - pr["real"]) / pr["real"] * 100:.1f}%', '预测 10 万 × 500 字节的误差'), (f'{pr["snap"]:.0f} MiB', '该配置的快照文件大小(磁盘规划用)')],
    body=[
        sec('三个测量点', '', term('', blk('z60', 1)), '<p>拟合只用了 3 个点、2 个参数,所以它只是「数量级估计」。路径越长、子节点越多,每个 znode 的开销越大(本文没有改变路径长度)。</p>'),
        sec('预测与验证', '', term('', blk('z60', 2))),
        sec('连接和 watch', '', term('', blk('z60', 3))),
        sec('规划时还要考虑的', '', '<p>这篇只量了堆。磁盘要按「快照大小 × 保留份数 + 事务日志」估算(第 54 篇);堆要在预测值之上留出 GC 余量(第 62 篇看 GC 停顿);连接数、watch 数按第 18 篇的单价估算。这些是规划思路,不是本文实验的结论。</p>'),
        sec('分步演示', '', demo('容量估算', [('t', 'term', '输出'), ('b', 'bars', '堆增量'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。JVM 堆 512 MiB,堆增量 = GC 之后的已用堆 − 空节点基线;路径固定 8 个字符;3 个拟合点 + 1 个验证点 + 1 个连接 / watch 点', '没有验证:路径长度、父子层级、临时节点、ACL 对每个 znode 开销的影响;G1 之外的垃圾回收器;堆使用率到多少会引起明显的 GC 压力'],
)
