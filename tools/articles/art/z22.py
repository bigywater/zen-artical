from lib import *
R = J('z22'); rows = R['rows']; lg = R['log']; wt = R['watch']
def S(k): return [l for l in out('z22').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("不同 value 大小的同步写 / 读延迟(每种 30 次取中位数,单机):" + ';'.join(f"{kb} KiB 写 {w:.2f} ms / 读 {r:.2f} ms" for kb, w, r in rows) + "。从 1 KiB 到 100 KiB 写延迟几乎不变(约 3 ms,被事务日志 fsync 主导),500 KiB 以后才明显上升;读延迟也随大小缓慢增长。", t=tl(S(1)), b=bars([[f'{kb} KiB 写', w, f'{w:.2f} ms'] for kb, w, r in rows], max(w for kb, w, r in rows) * 1.1, done=list(range(len(rows)))), kv=KV([['小 value', '延迟被 fsync 主导'], ['接近 1 MiB', '写 4.5 ms、读 0.7 ms(本机)']], ['小 value'])),
    step(f"代价在事务日志:对一个 100 KiB 的 znode 连续 set 1000 次,用时 {lg['s']:.1f} s;事务日志实际占盘增长 {lg['mib']:.0f} MiB(约等于写入的 ~98 MiB 数据加预分配),但内存里这个 znode 始终只有 100 KiB。每次 set 都把整份新值写进日志,频繁改大 value 会让日志和快照快速增长(第 54 篇)。", t=tl(S(2)), kv=KV([['每次 set', '整份新值写进事务日志']], ['每次 set'])),
    step(f"对大 value 做 watch:set 1000 KiB 后通知在 {wt['notify']:.1f} ms 到达——通知本身很小(不带数据);通知之后读取这 1000 KiB 又用了 {wt['read']:.1f} ms。如果很多 watcher 同时重读,大 value 会被重复发送给每一个(第 17 篇的惊群 × 大小)。", t=tl(S(3)), kv=KV([['通知', '很小,不带数据'], ['重读', '每个 watcher 各读一份整值']], ['重读'])),
]
A = dict(
    n=22, series='zookeeper', tags='ZooKeeper,大value,性能,事务日志,真实验证,动画演示',
    desc=f'大 value 对性能的影响:1 KiB~100 KiB 写延迟都约 3 ms(被 fsync 主导),1000 KiB 写 {rows[-1][1]:.2f} ms / 读 {rows[-1][2]:.2f} ms;1000 次 set 100 KiB 使事务日志增长 {lg["mib"]:.0f} MiB;watch 通知不带数据,但重读要读整份。',
    lead='ZooKeeper 的 value 上限约 1 MiB,但这不代表可以放心用到上限。这篇量不同大小的 value 的读写延迟、频繁改大 value 对事务日志的影响,以及大 value 配上 watch 的放大效应。',
    facts=[('约 3 ms', '1 KiB~100 KiB 的同步写延迟几乎不变(fsync 主导)'), (f'{lg["mib"]:.0f} MiB', '对 100 KiB 的 znode 连续 set 1000 次后事务日志的增长'), ('通知小、重读大', 'watch 事件不带数据,但每个 watcher 重读都读整份值')],
    body=[
        sec('延迟与大小', '', term('', blk('z22', 1)), '<p>这是单机、本机回环的数字,真实网络下大 value 的传输时间会更显著(本文没有测)。</p>'),
        sec('事务日志的增长', '', term('', blk('z22', 2))),
        sec('大 value 与 watch', '', term('', blk('z22', 3))),
        sec('分步演示', '', demo('大 value', [('t', 'term', '输出'), ('b', 'bars', '写延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,JVM 堆 256 MiB;每种大小 30 次中位数;事务日志占盘取自 st_blocks', '没有验证:集群里大 value 的复制延迟、网络带宽受限时的表现、压缩后的快照大小、小于 1 KiB 的极小 value、客户端侧序列化开销'],
)
