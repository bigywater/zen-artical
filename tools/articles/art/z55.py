from lib import *
R = J('z55'); d, ns, wn, bt = R['default'], R['nosync'], R['warn'], R['batch']
def S(k): return [l for l in out('z55').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"fsync 的代价:默认(每批事务 fsync)同步写 p50 {d['p50']:.2f} ms,异步写 {d['tput']:.0f} 次/秒,服务端 fsync 平均 {d['fsync_avg']} ms;-Dzookeeper.forceSync=no(只写进系统缓存,不强制落盘)同步写 p50 {ns['p50']:.2f} ms(快 {d['p50'] / ns['p50']:.0f} 倍),异步写 {ns['tput']:.0f} 次/秒(没有更快,因为异步下 fsync 本来就被分摊了),fsync 统计为 0。代价:断电或操作系统崩溃时可能丢掉已经「确认」的写。", t=tl(S(1)), b=bars([['默认 p50', d['p50'], f"{d['p50']:.2f} ms"], ['forceSync=no p50', ns['p50'], f"{ns['p50']:.2f} ms"]], d['p50'] * 1.15, mark=[0], done=[1]), kv=KV([['forceSync=no', f"同步写快 {d['p50'] / ns['p50']:.0f} 倍,但不保证落盘"]], ['forceSync=no'])),
    step(f"fsync 慢的日志告警:把 zookeeper.fsync.warningthresholdms 调到 1 ms,压测中出现 {wn['warns']} 条警告「fsync-ing the write ahead log in SyncThread:0 took 5ms which will adversely effect operation latency.File size is …」。默认阈值是 1000 ms(我没有测默认值),用它可以发现磁盘变慢。mntr 的 zk_avg_fsynctime / zk_max_fsynctime 是同一件事的指标版。", t=tl(S(2)), mark=[1], kv=KV([['警告阈值', 'fsync.warningthresholdms'], ['指标', 'zk_avg_fsynctime / zk_max_fsynctime']], ['警告阈值'])),
    step(f"组提交:300 次串行同步写之后 avg_sync_processor_batch_size = 1.0、fsync 次数 {bt['sync_cnt']}(基本每个事务一次);再异步写 20000 个,平均批大小 {bt['avg_batch']},20000 个事务只多出 {bt['async_extra']} 次 fsync——并发写入时多个事务共用一次 fsync,所以异步 / 并发写的吞吐远高于串行同步写。", t=tl(S(3)), b=bars([['串行:每事务 fsync', 1.0, '1.0'], ['异步:平均批大小', float(bt['avg_batch']), str(bt['avg_batch'])]], float(bt['avg_batch']) * 1.1, done=[0, 1]), kv=KV([['并发写', '多个事务共用一次 fsync']], ['并发写'])),
]
A = dict(
    n=55, series='zookeeper', tags='ZooKeeper,事务日志,fsync,真实验证,动画演示',
    desc=f'事务日志预分配与 fsync 实测:默认同步写 p50 {d["p50"]:.2f} ms,forceSync=no 降到 {ns["p50"]:.2f} ms;fsync 慢时日志出现「fsync-ing the write ahead log … took 5ms」;异步写时平均批大小 {bt["avg_batch"]},20000 个事务只多出 {bt["async_extra"]} 次 fsync。',
    lead='ZooKeeper 的写延迟主要是什么?答案是 fsync。这篇用三个实验验证:去掉 fsync 会怎样、fsync 慢时日志长什么样、并发时多个事务怎么共用一次 fsync。',
    facts=[(f'{d["p50"] / ns["p50"]:.0f} 倍', 'forceSync=no 对同步写延迟的改善(代价是不保证落盘)'), (f'{bt["avg_batch"]}', '异步高并发下平均每次 fsync 提交的事务数'), ('fsync-ing the write ahead log', '磁盘变慢时服务端日志里的告警')],
    body=[
        sec('fsync 的代价', '', term('', blk('z55', 1)), '<p><code>forceSync=no</code> 只用来说明 fsync 占了多少,不建议在生产环境使用。</p>'),
        sec('fsync 慢的告警', '', term('', blk('z55', 2))),
        sec('批量提交', '', term('', blk('z55', 3))),
        sec('分步演示', '', demo('事务日志 fsync', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;fsync 耗时取自 mntr;macOS 上 Java 的 force() 与 F_FULLFSYNC 耗时相近(第 56 篇)', '没有验证:预分配大小 preAllocSize 的影响、默认告警阈值 1000 ms 的触发、事务日志放在独立磁盘(第 5 篇只验证了分开存放)、断电后 forceSync=no 的实际丢失量'],
)
