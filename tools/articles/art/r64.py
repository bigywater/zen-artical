import json
from lib import *
R = J('r64'); sq = R['seq']; pp = R['pipe']; mu = R['multi']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
al, ev, no = sq['always'], sq['everysec'], sq['no']
steps = [
    step(f"三种 appendfsync,同样是一个客户端同步 SET 3000 条。always:p50 {al['p50']/1000:.2f} ms、p99 {al['p99']/1000:.2f} ms、最大 {al['mx']/1000:.1f} ms——每条写命令的回复都要等 fsync 完成。", b=bars([['always p50', al['p50'], f"{al['p50']:.0f} µs"], ['always p99', al['p99'], f"{al['p99']:.0f} µs"]], al['p99'], mark=[0, 1]), kv=KV([['always 平均', f"{al['mean']/1000:.2f} ms/条 → 约 {1e6/al['mean']:.0f} 条/秒"]], ['always 平均'])),
    step(f"everysec:p50 {ev['p50']:.0f} µs、p99 {ev['p99']:.0f} µs、最大 {ev['mx']:.0f} µs;no:p50 {no['p50']:.0f} µs、p99 {no['p99']:.0f} µs。两者几乎一样——everysec 的 fsync 在后台线程里做,不在请求的路径上。always 的 p50 是 everysec 的 {al['p50']/ev['p50']:.0f} 倍。", b=bars([['always p50', al['p50'], f"{al['p50']:.0f} µs"], ['everysec p50', ev['p50'], f"{ev['p50']:.0f} µs"], ['no p50', no['p50'], f"{no['p50']:.0f} µs"]], al['p50'], mark=[0], done=[1, 2]), kv=KV([['always / everysec p50', f"{al['p50']/ev['p50']:.0f} 倍"]], ['always / everysec p50'])),
    step(f"管道写入吞吐(每批 2000 条):always {pp['always']/1000:.0f}k/s;everysec {pp['everysec']/1000:.0f}k/s;no {pp['no']/1000:.0f}k/s。批量之后 always 的代价从「每条 fsync」摊成「每批 fsync」,但仍是 everysec 的 {pp['everysec']/pp['always']:.1f} 倍慢。", b=bars([['always', pp['always']/1000, f"{pp['always']/1000:.0f}k/s"], ['everysec', pp['everysec']/1000, f"{pp['everysec']/1000:.0f}k/s"], ['no', pp['no']/1000, f"{pp['no']/1000:.0f}k/s"]], pp['no']/1000, mark=[0], done=[1, 2]), kv=KV([['everysec / always', f"{pp['everysec']/pp['always']:.1f} 倍"]], ['everysec / always'])),
    step(f"并发写入:8 个独立进程各自同步 SET,总吞吐比 1 个客户端 always 从 {mu['always'][0]:.0f}/s 涨到 {mu['always'][1]:.0f}/s({mu['always'][1]/mu['always'][0]:.1f} 倍)。多个客户端的写命令共用一次 fsync,所以并发越高,always 摊得越薄(everysec 是 {mu['everysec'][1]/mu['everysec'][0]:.1f} 倍、no 是 {mu['no'][1]/mu['no'][0]:.1f} 倍,那是 CPU 并行的提升)。", b=bars([['always 1 客户端', mu['always'][0]/1000, f"{mu['always'][0]:.0f}/s"], ['always 8 客户端', mu['always'][1]/1000, f"{mu['always'][1]:.0f}/s"], ['everysec 1 客户端', mu['everysec'][0]/1000, f"{mu['everysec'][0]:.0f}/s"], ['everysec 8 客户端', mu['everysec'][1]/1000, f"{mu['everysec'][1]:.0f}/s"]], mu['everysec'][1]/1000, mark=[0, 1], done=[2, 3]), kv=KV([['always 并发放大', f"{mu['always'][1]/mu['always'][0]:.1f} 倍"]], ['always 并发放大'])),
    step("aof_delayed_fsync(fsync 拖累了写入的次数)在三种模式下都是 0:这台机器的磁盘在这种负载下没有触发。它是 everysec 模式下判断「fsync 是否跟不上」的指标。", b=bars([['always', 0.2, '0'], ['everysec', 0.2, '0'], ['no', 0.2, '0']], 1, done=[0, 1, 2]), kv=KV([['aof_delayed_fsync', '0 / 0 / 0']], ['aof_delayed_fsync'])),
]
A = dict(
    n=64, series='redis', tags='Redis,AOF,fsync,真实验证,动画演示',
    desc=f'本机实测 appendfsync 三种模式:单客户端同步 SET 的 p50 是 always {al["p50"]/1000:.2f} ms、everysec {ev["p50"]:.0f} µs、no {no["p50"]:.0f} µs;管道吞吐 {pp["always"]/1000:.0f}k / {pp["everysec"]/1000:.0f}k / {pp["no"]/1000:.0f}k 条/秒;8 个客户端并发时 always 总吞吐放大 {mu["always"][1]/mu["always"][0]:.1f} 倍(多个写共用 fsync)。',
    lead='appendfsync 决定 AOF 什么时候真正落盘:always 每次写命令都 fsync,everysec 每秒一次,no 交给操作系统。教科书说 always 最安全、最慢。这篇量「慢」到底是多慢:延迟、吞吐、并发下的表现,数字都来自本机(苹果电脑的 SSD,fsync 成本与 Linux 服务器不同,请当作方法而不是结论)。',
    facts=[(f'{al["p50"]/1000:.2f} ms vs {ev["p50"]:.0f} µs', 'SET 的 p50 延迟:always vs everysec(单客户端同步)'), (f'{pp["everysec"]/pp["always"]:.1f} 倍', f'管道批量写入时 everysec 比 always 的吞吐优势({pp["everysec"]/1000:.0f}k vs {pp["always"]/1000:.0f}k/s)'), (f'{mu["always"][1]/mu["always"][0]:.1f} 倍', '8 个客户端并发时 always 的总吞吐放大(多个写共用一次 fsync)')],
    body=[
        sec('一个客户端:每条命令的延迟', '每种模式一个新实例,3000 条同步 SET,统计每条的往返', term('', blk('r64', 1)), f'<p>always 的每条写命令要等 fsync 完成才回复:p50 {al["p50"]/1000:.2f} ms、p99 {al["p99"]/1000:.2f} ms,一个客户端只能到约 {1e6/al["mean"]:.0f} 条/秒。everysec 和 no 的延迟几乎一样({ev["p50"]:.0f} µs 对 {no["p50"]:.0f} µs)——everysec 的 fsync 在后台线程里,不在请求路径上。</p>'),
        sec('批量写入:管道', '', term('', blk('r64', 2)), f'<p>管道 2000 条一批:always {pp["always"]/1000:.0f}k/s,everysec {pp["everysec"]/1000:.0f}k/s,no {pp["no"]/1000:.0f}k/s。批量之后 always 的 fsync 摊到整批,吞吐比单条同步高得多,但仍只有 everysec 的约 {pp["always"]/pp["everysec"]*100:.0f}%。</p>'),
        sec('并发客户端:always 会被「合并」', '', term('', blk('r64', 3)), f'<p>8 个独立进程各自同步 SET:always 的总吞吐从 {mu["always"][0]:.0f}/s 涨到 {mu["always"][1]:.0f}/s({mu["always"][1]/mu["always"][0]:.1f} 倍),放大倍数明显高于 everysec({mu["everysec"][1]/mu["everysec"][0]:.1f} 倍)和 no({mu["no"][1]/mu["no"][0]:.1f} 倍)。从数字看,多个客户端的写命令共用了 fsync;为什么能共用(猜测是同一轮事件循环里的写命令一起 fsync),我没有读源码验证。<b>所以 always 在高并发下的代价,比单客户端测出来的低得多。</b></p>'),
        sec('aof_delayed_fsync', '', term('', blk('r64', 4)), '<p>三种模式下 <code>aof_delayed_fsync</code> 都是 0,说明这台机器的磁盘在这种负载里跟得上。这个指标在 everysec 下用来发现「fsync 拖累了主线程」,如果它持续增长,说明磁盘慢。</p>'),
        sec('这个实验没有回答的问题', '', '<p><b>真正的持久性差别——断电时到底丢多少——没有测。</b>我用的是进程被杀、操作系统仍然存活的场景(第 60 篇),这时页缓存里的数据不会丢,三种模式看不出差别。断电级别的丢失需要真正切断电源或使用带故障注入的文件系统,这里做不到,所以本文只回答性能,不回答安全。</p>'),
        sec('分步演示:三种模式的代价', '', demo('appendfsync', [('b', 'bars', '延迟 / 吞吐'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。macOS + Apple SSD;Linux 服务器的 fsync 成本、磁盘类型不同,数字不可直接套用。并发实验用独立进程避开 GIL', '没有验证:断电场景的数据丢失量、Linux 下的数字、磁盘更慢或带写缓存电池时的差别、appendfsync everysec 下 fsync 阻塞主线程时的延迟(需要慢盘)、aof_delayed_fsync 增长的触发条件'],
)
