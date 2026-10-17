import json
from lib import *
R = J('r107'); C_ = {(a, b): r for a, b, r in R['c']}; lf = R['lf']
e0, e1, a0, a1 = C_[('everysec', False)], C_[('everysec', True)], C_[('always', False)], C_[('always', True)]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("Redis 有几个后台线程(BIO,background I/O),专门做「会阻塞的系统调用」:AOF 的 fsync、大对象的内存释放(lazy free),以及关闭/删除大文件(这一项我没有实测)。它们让主线程不必等磁盘或释放内存。", t=tm(['BIO 后台线程', '· AOF fsync(appendfsync everysec)', '· 大对象内存释放(lazy free)', '· 关闭 / 删除文件(未实测)'], cur=[1, 2]), kv=KV([['BIO', '把会阻塞的事挪出主线程']], ['BIO'])),
    step(f"验证 fsync 在后台:让另一个进程持续大量写并 fsync 同一块磁盘(制造磁盘拥塞),同时单客户端同步 SET 8 秒。appendfsync everysec:没有负载时 p99 {e0['p99']:.3f} ms、max {e0['mx']:.1f} ms;有负载时 p99 {e1['p99']:.3f} ms、max {e1['mx']:.1f} ms——p50/p99 几乎没变,只有偶发的毫秒级尖峰。", b=bars([['everysec 无负载 p99', e0['p99'], f"{e0['p99']:.3f} ms"], ['everysec 有负载 p99', e1['p99'], f"{e1['p99']:.3f} ms"], ['everysec 无负载 max', e0['mx'], f"{e0['mx']:.1f} ms"], ['everysec 有负载 max', e1['mx'], f"{e1['mx']:.1f} ms"]], 20, done=[0, 1], mark=[3]), kv=KV([['everysec', '磁盘拥塞时 p99 不变']], ['everysec'])),
    step(f"对照 appendfsync always(fsync 在请求路径上):无负载 p50 {a0['p50']:.1f} ms、p99 {a0['p99']:.1f} ms;有磁盘负载时 p99 涨到 {a1['p99']:.1f} ms、p99.9 {a1['p999']:.0f} ms、最大 {a1['mx']:.0f} ms。同一块拥塞的磁盘,一个几乎无感,一个尖峰可达 {a1['mx']:.0f} ms。", b=bars([['always 无负载 p99', a0['p99'], f"{a0['p99']:.1f} ms"], ['always 有负载 p99', a1['p99'], f"{a1['p99']:.1f} ms"], ['always 有负载 max', a1['mx'], f"{a1['mx']:.0f} ms"]], a1['mx'], mark=[1, 2], done=[0]), kv=KV([['always', f"有负载 max {a1['mx']:.0f} ms"]], ['always'])),
    step(f"吞吐也说明问题:8 秒内 everysec 完成 {e0['n']} / {e1['n']} 条(无 / 有负载),always 只有 {a0['n']} / {a1['n']} 条。aof_delayed_fsync 四种情形都是 0——fsync 一直跟得上,everysec 没有进入「fsync 太慢、主线程被迫等待」的状态。", b=bars([['everysec 无负载', e0['n'] / 1000, f"{e0['n']/1000:.0f}k"], ['everysec 有负载', e1['n'] / 1000, f"{e1['n']/1000:.0f}k"], ['always 无负载', a0['n'] / 1000, f"{a0['n']/1000:.1f}k"], ['always 有负载', a1['n'] / 1000, f"{a1['n']/1000:.1f}k"]], e1['n'] / 1000, done=[0, 1], mark=[2, 3]), kv=KV([['aof_delayed_fsync', '0 / 0 / 0 / 0']], ['aof_delayed_fsync'])),
    step(f"lazy free 任务:UNLINK 200 万成员的集合后,INFO memory 的 lazyfree_pending_objects = 1 持续了约 100 ms(每 20 ms 采样 {len(lf)} 次,前 5 次都是 1),之后变为 0、lazyfreed_objects 变成 1——释放在后台线程里完成。", t=tm([f'采样 {i+1}: lazyfree_pending_objects={p}, lazyfreed_objects={d}' for i, (p, d) in enumerate(lf)], mark=[len(lf) - 1]), kv=KV([['pending → freed', '1 → 0,lazyfreed 0 → 1']], ['pending → freed'])),
]
A = dict(
    n=107, series='redis', tags='Redis,BIO,后台线程,真实验证,动画演示',
    desc=f'验证 BIO 后台线程的作用:磁盘被大量 fsync 写入占满时,appendfsync everysec 的 SET p99 仍是 {e1["p99"]:.3f} ms(无负载 {e0["p99"]:.3f} ms),而 always 的 p99 从 {a0["p99"]:.1f} ms 涨到 {a1["p99"]:.1f} ms、最大 {a1["mx"]:.0f} ms;UNLINK 大集合后 lazyfree_pending_objects = 1 持续约 100 ms 后被后台线程释放。',
    lead='Redis 的主线程不想等任何慢的系统调用,所以把其中几类交给后台线程(BIO):AOF 的 fsync、大对象的内存释放、文件的关闭/删除。这篇不数线程,而是用行为来验证:制造磁盘拥塞,看 fsync 在主线程上和在后台线程上的延迟有多大差别;再看后台释放大对象时的计数器。',
    facts=[(f'{e1["p99"]:.3f} ms', f'磁盘拥塞时 everysec 的 SET p99(无负载 {e0["p99"]:.3f} ms)——fsync 在后台线程'), (f'{a1["p99"]:.0f} ms / {a1["mx"]:.0f} ms', '同样的磁盘拥塞下 always 的 p99 / 最大延迟——fsync 在请求路径上'), ('pending 1 → 0', 'UNLINK 大集合后 lazyfree_pending_objects 的变化(约 100 ms)')],
    body=[
        sec('fsync:后台 vs 请求路径', '一个进程持续写 4 MB 块并 fsync,占满磁盘;Redis 端单客户端同步 SET 8 秒', term('', blk('r107', 1)), f'<p>appendfsync everysec 下,fsync 由后台线程每秒做一次:磁盘拥塞时请求延迟的 p50/p99 几乎不变(p99 {e0["p99"]:.3f} → {e1["p99"]:.3f} ms),最大值有偶发的毫秒级尖峰({e1["mx"]:.1f} ms)。appendfsync always 下,fsync 在请求路径上:无负载已经是 p50 {a0["p50"]:.1f} ms,磁盘拥塞时 p99 {a1["p99"]:.1f} ms、最大 {a1["mx"]:.0f} ms。(磁盘拥塞是我用另一个进程的持续 fsync 制造的,macOS + SSD;不同磁盘上的绝对数字会不同。)</p><p>everysec 也不是永远安全:按文档的说法,如果一次 fsync 耗时过长(约 2 秒),主线程会被迫等待并增加 <code>aof_delayed_fsync</code>——这次实验里它始终是 0,没有触发,所以这一点没有验证。</p>'),
        sec('lazy free:后台释放', '', term('', blk('r107', 2)), '<p>UNLINK 一个 200 万成员的集合:主线程只把 key 摘下并交给后台线程,<code>INFO memory</code> 的 <code>lazyfree_pending_objects</code> 显示 1 个待释放对象,大约 100 ms 后归 0、<code>lazyfreed_objects</code> 加 1。lazy free 各开关的效果见第 108 篇。</p>'),
        sec('这次没有验证的部分', '', '<p>BIO 还有一类任务是「关闭/删除大文件」(比如 AOF 重写完成后删除旧文件),我没有找到办法在这台机器上单独观察它;线程的名字与具体数量在 macOS 上也看不到(第 106 篇只数出了线程总数)。所以这里说的三类任务里,fsync 与 lazy free 是我用行为验证的,文件关闭是按 Redis 文档转述的。</p>'),
        sec('分步演示:BIO 帮主线程挡住了什么', '', demo('Redis BIO 后台线程', [('t', 'term', '说明'), ('b', 'bars', '延迟 / 吞吐'), ('kv', 'kv', '要点')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。磁盘拥塞由另一个 Python 进程的连续 4 MB 写 + fsync 制造;每种配置 8 秒;macOS + SSD', '没有验证:Linux 上 fsync 的行为差异、BIO 线程的具体数量与名字、文件关闭任务、磁盘更慢时 everysec 触发 aof_delayed_fsync 的情形'],
)
