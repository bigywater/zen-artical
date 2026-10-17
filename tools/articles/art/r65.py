import json, statistics
from lib import *
R = J('r65')
def med(cfg, ph, k): return statistics.median(r[ph][k] for r in R[cfg])
def rw(cfg): return [r['rw'] for r in R[cfg]]
ano, ayes, eno, eyes = 'always_no', 'always_yes', 'everysec_no', 'everysec_yes'
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("场景:200 万个 key 的实例,一个客户端不停同步 SET,中途执行 BGREWRITEAOF;按「重写前 / 中 / 后」分段统计 SET 延迟。每种配置跑两轮。", b=bars([['always 不跳过', 1, ''], ['always 跳过', 1, ''], ['everysec 不跳过', 1, ''], ['everysec 跳过', 1, '']], 1), kv=KV([['变量', 'appendfsync × no-appendfsync-on-rewrite']], [])),
    step(f"appendfsync always + no-appendfsync-on-rewrite no(默认):重写期间每条 SET 仍要等 fsync,p50 {med(ano,'dur',1)/1000:.2f} ms;而且重写本身也变慢了——两轮分别耗时 {rw(ano)[0]:.1f} s 和 {rw(ano)[1]:.1f} s,而其它配置只要约 1.0–1.1 s。重写期间只写进 {int(med(ano,'dur',0))} 条 SET。", b=bars([['SET p50(µs)', med(ano, 'dur', 1), f"{med(ano,'dur',1):.0f}"], ['重写耗时(s×100)', statistics.mean(rw(ano)) * 100, f"{statistics.mean(rw(ano)):.1f} s"]], max(med(ano, 'dur', 1), statistics.mean(rw(ano)) * 100), mark=[0, 1]), kv=KV([['重写耗时', f'{rw(ano)[0]:.1f} s / {rw(ano)[1]:.1f} s'], ['期间 SET 条数', str(int(med(ano, 'dur', 0)))]], ['重写耗时'])),
    step(f"always + no-appendfsync-on-rewrite yes:重写期间主进程暂停 fsync,SET 的 p50 降到 {med(ayes,'dur',1):.0f} µs、p99 {med(ayes,'dur',2):.0f} µs(和 everysec 差不多),重写也只要 {statistics.mean(rw(ayes)):.2f} s,期间写了 {int(med(ayes,'dur',0))} 条。", b=bars([['always 不跳过', med(ano, 'dur', 1), f"{med(ano,'dur',1):.0f} µs"], ['always 跳过', med(ayes, 'dur', 1), f"{med(ayes,'dur',1):.0f} µs"]], med(ano, 'dur', 1), mark=[0], done=[1]), kv=KV([['p50', f"{med(ano,'dur',1):.0f} → {med(ayes,'dur',1):.0f} µs"]], ['p50'])),
    step(f"everysec 下这个开关几乎没有区别:重写期间 p50 都是 {med(eno,'dur',1):.0f} / {med(eyes,'dur',1):.0f} µs,重写耗时都约 1.0 s;最大延迟都在 10 ms 量级({med(eno,'dur',3)/1000:.1f} ms / {med(eyes,'dur',3)/1000:.1f} ms,fork 时的停顿)。", b=bars([['everysec 不跳过 p50', med(eno, 'dur', 1), f"{med(eno,'dur',1):.0f} µs"], ['everysec 跳过 p50', med(eyes, 'dur', 1), f"{med(eyes,'dur',1):.0f} µs"], ['everysec 不跳过 max', med(eno, 'dur', 3), f"{med(eno,'dur',3)/1000:.1f} ms"], ['everysec 跳过 max', med(eyes, 'dur', 3), f"{med(eyes,'dur',3)/1000:.1f} ms"]], med(eno, 'dur', 3), done=[0, 1], mark=[2, 3]), kv=KV([['结论', 'everysec 下开关无明显差别']], ['结论'])),
    step("代价:开关为 yes 时,重写期间「已回复」的写入没有 fsync——这段时间如果操作系统崩溃或断电,这些写入可能丢。这一点没有实测(见文末),只是设置的定义。", b=bars([['重写期间的写入', 1, '未 fsync']], 1, mark=[0]), kv=KV([['取舍', '延迟 ↔ 重写期间的持久性']], ['取舍'])),
]
A = dict(
    n=65, series='redis', tags='Redis,AOF,fsync,重写,真实验证,动画演示',
    desc=f'在 200 万个 key 的实例上对比 no-appendfsync-on-rewrite:appendfsync always 且不跳过时,重写期间 SET p50 仍是 {med(ano,"dur",1)/1000:.1f} ms,重写要 {min(rw(ano)):.1f}–{max(rw(ano)):.1f} s;设成 yes 后 p50 降到 {med(ayes,"dur",1):.0f} µs、重写 {statistics.mean(rw(ayes)):.1f} s;everysec 下开关没有明显差别。',
    lead='AOF 重写时,子进程在写大量数据,主进程如果还在频繁 fsync,两者会抢磁盘。no-appendfsync-on-rewrite 的意思是:重写期间主进程暂停 fsync。它到底有没有用?这篇用 200 万个 key、单客户端持续写入,把重写前、中、后的延迟分段量出来,每种配置跑两轮。',
    facts=[(f'{med(ano,"dur",1)/1000:.1f} ms → {med(ayes,"dur",1):.0f} µs', 'always 下重写期间 SET 的 p50:开关 no → yes'), (f'{statistics.mean(rw(ano)):.1f} s → {statistics.mean(rw(ayes)):.1f} s', '同样两种配置下 AOF 重写自身的耗时'), ('无差别', 'everysec 下这个开关对延迟没有明显影响')],
    body=[
        sec('做法', '', '<p>每种配置一个新实例:装入 200 万个 key,然后一个客户端不停地同步 <code>SET</code>(记录每条的往返时间);1 秒后另一个连接发出 <code>BGREWRITEAOF</code>,直到 <code>aof_rewrite_in_progress</code> 回到 0,再多记 1 秒。把所有 SET 按时间分成「重写前 / 中 / 后」三段,各段统计条数、p50、p99、最大值。四种组合:<code>appendfsync always / everysec</code> × <code>no-appendfsync-on-rewrite no / yes</code>,各跑两轮。</p>'),
        sec('结果', '单位 µs;「轮」是第几轮', term('', blk('r65', 1)),
            f'<p><b>always + 不跳过(默认)</b>:重写期间每条 SET 仍在等 fsync,p50 {med(ano,"dur",1)/1000:.2f} ms;更值得注意的是<b>重写本身也慢了</b>——两轮分别是 {rw(ano)[0]:.1f} s 和 {rw(ano)[1]:.1f} s,而其它三种配置都只要约 1.0–1.1 s。重写期间只写进 {int(med(ano,"dur",0))} 条 SET(其它配置写了三万多条)。为什么慢这么多?我的猜测是主进程的高频 fsync 和子进程的大量写盘在抢磁盘,但我没有做隔离实验去证明。</p><p><b>always + 跳过</b>:重写期间主进程不 fsync,SET 的 p50 降到 {med(ayes,"dur",1):.0f} µs,p99 {med(ayes,"dur",2):.0f} µs,与 everysec 相当,重写只要 {statistics.mean(rw(ayes)):.2f} s;重写一结束又回到每条 fsync(「后」阶段 p50 回到 3 ms 左右)。</p><p><b>everysec</b>:开不开关差别不大:p50 都是约 30 µs,重写都是约 1.0 s;最大延迟都是 10 ms 量级——那是 fork 本身的停顿,和 fsync 策略无关(第 66 篇)。</p>'),
        sec('取舍与边界', '', '<p>开关设成 <code>yes</code> 的代价是:重写期间「已经回复给客户端」的写入没有 fsync,这段时间里操作系统崩溃或断电会丢数据(丢多少取决于操作系统的写回策略)。这个后果我没有实测——同第 64 篇,我没有能力在这台机器上制造断电。实验也只用了单客户端、200 万个 key、Apple SSD;数据集更大、重写更久时,「always + 不跳过」的问题会更明显,「everysec」下的结论未必仍然成立。</p>'),
        sec('分步演示:开关的效果', '', demo('no-appendfsync-on-rewrite', [('b', 'bars', '延迟 / 耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。每种配置两轮,表中是每轮各阶段的 p50 / p99 / max;文中的 p50 等是两轮的中位', '没有验证:断电时重写期间写入的丢失量、Linux 与其它磁盘上的表现、多个客户端并发写时的表现、AOF 重写与 RDB 保存同时进行的情形、「always 不跳过」时重写变慢的具体原因'],
)
