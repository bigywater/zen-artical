import json
from lib import *
R = J('r60'); tl = R['tl']; seq = R['seq']
t0 = tl[0]; t1 = tl[1]
old_incr = [s for f, s in t0[1] if f.endswith('.1.incr.aof')][0]; new_incr0 = [s for f, s in t0[1] if f.endswith('.2.incr.aof')][0]
base2 = [s for f, s in t1[1] if f.endswith('.2.base.rdb')][0]; incr2 = [s for f, s in t1[1] if f.endswith('.2.incr.aof')][0]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def fl(nodes, cur=(), done=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done)}
M = lambda x: f'{x/1e6:.1f} MB'
steps = [
    step(f"150 万个 key 已经写入,当前 base 是 89 字节的空文件,所有写入都在 incr.1 里:{M(old_incr)}。这正是需要重写的场景。", f=fl([['base.1', '89 B'], ['incr.1', M(old_incr)]], cur=[1]), kv=KV([['INFO 中含 buffer 的字段', '只有 aof_buffer_length']], ['INFO 中含 buffer 的字段'])),
    step(f"4 个线程持续 INCR seq(每条等回复)。发出 BGREWRITEAOF 的瞬间(+{t0[0]:.2f} s),主进程新建 incr.2({new_incr0} 字节),旧的 incr.1 停止增长,固定在 {M(old_incr)}。", f=fl([['base.1', '89 B'], ['incr.1(冻结)', M(old_incr)], ['incr.2(新写入)', f'{new_incr0} B → …']], cur=[2], done=[1]), kv=KV([['新写入', '直接进 incr.2']], ['新写入'])),
    step(f"子进程把 150 万个 key 的快照写成新 base(约 {tl[1][0]:.2f} s)。这期间写入线程一直没停,完成了 {R['acked']} 次 INCR;它们全在 incr.2 里。", f=fl([['子进程', '写 temp base'], ['incr.2', '持续增长']], cur=[0, 1]), kv=KV([['重写耗时', f"{R['tend']:.2f} s"], ['INCR 完成数', str(R['acked'])]], ['INCR 完成数'])),
    step(f"重写完成:base.2 = {M(base2)}、incr.2 = {incr2} 字节({incr2/1e3:.0f} KB,就是重写期间的写入)。旧的 base.1 和 incr.1({M(old_incr)})被删除。INFO persistence 里没有任何「重写缓冲区」字段,只有 aof_buffer_length(等待写进 AOF 的普通缓冲)。", f=fl([['base.2', M(base2)], ['incr.2', f'{incr2/1e3:.0f} KB'], ['旧 base.1 + incr.1', '已删除']], done=[0, 1, 2]), b=bars([['重写前 incr.1', old_incr, M(old_incr)], ['重写后 base.2', base2, M(base2)], ['重写后 incr.2', max(incr2, 1), f'{incr2/1e3:.0f} KB']], old_incr, done=[1, 2]), kv=KV([['旧', f'{M(old_incr)} 已删'], ['新', f'{M(base2)} + {incr2/1e3:.0f} KB']], ['新'])),
    step(f"对账:等 fsync 后 kill -9,再从 AOF 重启:写线程确认的 INCR = {seq[0]},kill 前 seq = {seq[1]},重启恢复的 seq = {seq[2]}——三者一致,重写期间没有丢写。", f=fl([['确认 INCR', str(seq[0])], ['kill 前 seq', str(seq[1])], ['重启后 seq', str(seq[2])]], done=[0, 1, 2]), kv=KV([['结论', '重写期间的写入全部在 incr.2 里,恢复完整']], ['结论'])),
]
A = dict(
    n=60, series='redis', tags='Redis,AOF,持久化,真实验证,动画演示',
    desc=f'在 150 万个 key 的实例上观察 AOF Rewrite 期间的增量:发起重写的瞬间主进程新建 incr.2,旧 incr.1({M(old_incr)})停止增长;重写期间 4 个线程完成 {R["acked"]} 次 INCR 全部写进 incr.2;INFO 里没有重写缓冲区字段;kill -9 后从 AOF 重启,seq = {seq[2]} 与确认数 {seq[0]} 一致。',
    lead='老版本的 AOF 重写靠一块「重写缓冲区」:子进程写快照的同时,主进程把新命令攒在内存里,最后追加进新文件。这块缓冲区是重写期间内存暴涨的常见原因。Redis 7 之后的多文件 AOF 据说不再需要它。这篇不凭「据说」,而是在重写进行的那一秒里,每毫秒看一次 AOF 目录,再用 kill -9 验证有没有丢写。',
    facts=[(M(old_incr), '重写前 incr.1 的大小(150 万次 SET)'), (f"{R['acked']}", '重写期间(约 1 秒)写入线程完成的 INCR 次数,全部进了 incr.2'), (f'{seq[2]} = {seq[0]}', 'kill -9 后重启恢复的 seq = 写线程确认过的次数')],
    body=[
        sec('INFO 里有没有「重写缓冲区」', '', term('', blk('r60', 1)), '<p>Redis 8 的 <code>INFO persistence</code> 里以 <code>aof_</code> 开头的字段列在上面。包含 <code>buffer</code> 的只有 <code>aof_buffer_length</code>——从名字看是普通写入路径上的缓冲(我没有去验证它的确切含义)。没有类似 <code>aof_rewrite_buffer_length</code> 的字段(老版本的 INFO 里有,这一点来自我的记忆,本文没有用老版本验证)。</p>'),
        sec('重写的那一秒:目录里发生了什么', '每 3 ms 采样一次文件列表和 aof_rewrite_in_progress', term('', blk('r60', 2)),
            f'<p>发出 <code>BGREWRITEAOF</code> 的瞬间(+{t0[0]:.2f} s)目录里多了 <code>2.incr.aof</code>,旧的 <code>1.incr.aof</code> 停在 {old_incr} 字节不再变化——新的写入都去了 incr.2。约 {R["tend"]:.2f} s 后重写结束,目录只剩 <code>2.base.rdb</code>({M(base2)})和 <code>2.incr.aof</code>({incr2} 字节)。<b>重写期间的写入直接落进新的 incr 文件,不需要在内存里再攒一份。</b>所以重写期间额外占用内存的主要是 fork 的写时复制(COW),不是缓冲区(COW 的实测见第 66 篇)。</p>'),
        sec('重写期间没有丢写', '', term('', blk('r60', 3)), f'<p>为了验证,写线程每次 <code>INCR seq</code> 收到回复才计数。重写结束后再等 1.3 秒让 everysec 的 fsync 落盘,<code>kill -9</code> 主进程,重启并等加载完成(约 1 秒):恢复的 <code>seq</code> = {seq[2]},与确认次数 {seq[0]}、kill 前的 {seq[1]} 完全一致。注意这是「进程被杀」的场景,操作系统还在,页缓存里的数据不会丢;断电级别的丢失没有测(第 64 篇讨论 fsync 策略)。</p>'),
        sec('分步演示:重写的一秒', '', demo('AOF 重写期间的增量', [('f', 'flow', 'AOF 目录里的文件'), ('b', 'bars', '大小'), ('kv', 'kv', '观察')], steps, '本步涉及的文件')),
    ],
    refs=[ENV_R + '。appendonly yes、appendfsync everysec;150 万个 key(value 100 字节),4 个写线程各自同步 INCR', '没有验证:老版本 AOF 的重写缓冲区行为(只是对比记忆)、断电场景的持久性、重写期间主进程的内存与延迟(第 66 篇)、写入速率极高时 incr 文件的增长与磁盘压力'],
)
