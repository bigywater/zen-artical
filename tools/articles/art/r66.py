import json
from lib import *
R = J('r66'); rows = R['rows']; a, b, c = rows
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
mb = lambda r: f'{r["used"]/1e6:.0f} MB'
per = lambda r: r['fork_us'] / (r['used'] / 1e6)
steps = [
    step("方法:三个数据集(10 万 / 100 万 / 300 万个 key,value 100 字节),一个客户端不停地随机覆盖写已有的 key;先测 2 秒基线,再发 BGSAVE,统计 BGSAVE 期间每条 SET 的延迟。fork 耗时取 INFO stats 的 latest_fork_usec。", b=bars([[f'{r["N"]} key({mb(r)})', 1, ''] for r in rows], 1), kv=KV([['变量', '数据集大小']], [])),
    step(f"基线:没有 BGSAVE 时 SET 的 p50 约 {a['base'][1]:.0f}–{c['base'][1]:.0f} µs,与数据集大小无关。", b=bars([[f'{r["N"]} key p50', r['base'][1], f'{r["base"][1]:.0f} µs'] for r in rows], 40, done=[0, 1, 2]), kv=KV([['基线 p50', '≈ 27 µs(三个数据集相同)']], ['基线 p50'])),
    step(f"fork 耗时随内存线性增长:{mb(a)} → {a['fork_us']/1000:.1f} ms;{mb(b)} → {b['fork_us']/1000:.1f} ms;{mb(c)} → {c['fork_us']/1000:.1f} ms。fork 需要复制页表,内存越大页表越大。", b=bars([[f'{r["N"]} key({mb(r)})', r['fork_us'], f'{r["fork_us"]/1000:.1f} ms'] for r in rows], c['fork_us'], mark=[0, 1, 2]), kv=KV([['fork 耗时', f"{a['fork_us']/1000:.1f} → {b['fork_us']/1000:.1f} → {c['fork_us']/1000:.1f} ms"]], ['fork 耗时'])),
    step(f"这段停顿直接体现在延迟上:BGSAVE 期间 SET 的最大延迟是 {a['dur'][3]/1000:.1f} / {b['dur'][3]/1000:.1f} / {c['dur'][3]/1000:.1f} ms,几乎等于 fork 耗时;而 p50 仍是约 {b['dur'][1]:.0f} µs、p99 也只有 {a['dur'][2]:.0f}–{c['dur'][2]:.0f} µs。停顿只发生在 fork 的那一下。", b=bars([[f'fork {mb(r)}', r['fork_us'], f'{r["fork_us"]/1000:.1f} ms'] for r in rows] + [[f'期间 max {mb(r)}', r['dur'][3], f'{r["dur"][3]/1000:.1f} ms'] for r in rows], c['dur'][3], cur=[0, 1, 2], mark=[3, 4, 5]), kv=KV([['期间最大延迟', f"{a['dur'][3]/1000:.1f} / {b['dur'][3]/1000:.1f} / {c['dur'][3]/1000:.1f} ms"]], ['期间最大延迟'])),
    step(f"BGSAVE 本身的耗时:{a['bgsave_s']:.2f} / {b['bgsave_s']:.2f} / {c['bgsave_s']:.2f} s(在子进程里,不占主线程)。COW(写时复制)的内存我没有量到:INFO 的 rdb_last_cow_size 在这台 macOS 上始终是 0,这个指标不能用于本机。", b=bars([[f'BGSAVE {mb(r)}', r['bgsave_s'], f'{r["bgsave_s"]:.2f} s'] for r in rows], c['bgsave_s'], done=[0, 1, 2]), kv=KV([['rdb_last_cow_size', '0(macOS 上没有数据)']], ['rdb_last_cow_size'])),
]
A = dict(
    n=66, series='redis', tags='Redis,RDB,fork,延迟,真实验证,动画演示',
    desc=f'量 BGSAVE 的 fork 停顿:内存 {mb(a)} / {mb(b)} / {mb(c)} 时 latest_fork_usec 分别是 {a["fork_us"]/1000:.1f} / {b["fork_us"]/1000:.1f} / {c["fork_us"]/1000:.1f} ms(约 {per(b):.0f} µs/MB),持续写入时 BGSAVE 期间 SET 的最大延迟几乎等于 fork 耗时,而 p50 与 p99 不受影响(约 30 µs / 50–70 µs)。',
    lead='RDB 快照和 AOF 重写都要 fork 一个子进程,这一下 fork 是主线程上唯一「随数据量增长」的停顿。多长?会不会拖累所有请求?这篇用三个大小的数据集实测 fork 耗时,并且在持续写入时看它到底体现成多大的延迟。',
    facts=[(f'{a["fork_us"]/1000:.1f} → {c["fork_us"]/1000:.1f} ms', f'fork 耗时:{mb(a)} → {mb(c)}(约 {per(b):.0f} µs/MB)'), (f'{c["dur"][3]/1000:.1f} ms', f'{mb(c)} 数据集 BGSAVE 期间 SET 的最大延迟(≈ fork 耗时)'), (f'{b["dur"][1]:.0f} µs', 'BGSAVE 期间 SET 的 p50,与没有 BGSAVE 时相同')],
    body=[
        sec('做法与结果', '', term('', blk('r66', 1)), f'<p>每个数据集一个新实例(<code>save ""</code>,没有自动快照)。装入 key 后,单客户端不停随机覆盖已有 key;先测 2 秒基线,再发 <code>BGSAVE</code>,统计从发出到 <code>rdb_bgsave_in_progress</code> 回到 0 期间每条 SET 的延迟。基线 p50 只有 {a["base"][1]:.0f}–{c["base"][1]:.0f} µs(与数据集大小无关)。</p>'),
        sec('fork 耗时随内存线性增长', '', '', f'<p><code>latest_fork_usec</code>:{mb(a)} 是 {a["fork_us"]/1000:.1f} ms,{mb(b)} 是 {b["fork_us"]/1000:.1f} ms,{mb(c)} 是 {c["fork_us"]/1000:.1f} ms;后两者每 MB 约 {per(b):.0f}–{per(c):.0f} µs。fork 需要复制父进程的页表,内存越大,页表越大——这是我对线性增长的解释,没有单独验证页表大小。据此,在这台机器上外推:1 GB 约 40 ms,10 GB 约 400 ms(<b>只是按线性外推,没有实测</b>;不同操作系统、是否使用大页,差别很大)。</p>'),
        sec('停顿体现在延迟上', '', '', f'<p>BGSAVE 期间,SET 的最大延迟是 {a["dur"][3]/1000:.1f} / {b["dur"][3]/1000:.1f} / {c["dur"][3]/1000:.1f} ms,几乎等于各自的 fork 耗时;而 p50 仍是 {b["dur"][1]:.0f} µs 左右、p99 也只有 {a["dur"][2]:.0f}–{c["dur"][2]:.0f} µs。也就是说停顿只发生在 fork 的那一下,子进程之后写快照,不占用主线程。对「p99 之内」的指标它没有影响,对「最大延迟」有。</p>'),
        sec('COW:这台机器没量到', '', '', f'<p>子进程运行期间,主进程修改的页会被复制(写时复制),额外占内存。我让客户端在 BGSAVE 期间随机覆盖写,但 <code>rdb_last_cow_size</code> 在这台 macOS 上始终是 0,日志里的 <code>Fork CoW … 0 MB</code> 也是 0——这个指标在这里不可用,所以<b>我没有量到 COW 的内存开销</b>。想量它需要在 Linux 上做。</p>'),
        sec('分步演示:fork 的代价', '', demo('持久化对延迟的影响', [('b', 'bars', '耗时 / 延迟'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。BGSAVE 用 save "" 关闭自动快照;每个数据集只测一次;fork 的成本取决于操作系统与硬件,Linux 上(特别是有 THP 时)差别会很大', '没有验证:Linux 上的 fork 耗时与 COW 内存、大页(THP)的影响、AOF 重写的 fork(应与 BGSAVE 类似但没有单独测)、多个并发客户端下的延迟、超过 500 MB 的数据集(1 GB、10 GB 的数字是线性外推)'],
)
