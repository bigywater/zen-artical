import json
from lib import *
R = J('r58'); rows = R['rows']; two = R['two']; ld = R['ld_disabled']; ls = R['ld_swapdb']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step("默认配置(本机 CONFIG GET):repl-diskless-sync = yes,repl-diskless-sync-delay = 5,repl-diskless-sync-max-replicas = 0,repl-diskless-load = disabled。", n=cells(['sync yes', 'delay 5 s', 'max-replicas 0', 'load disabled']), kv=KV([['默认', '无盘发送,先等 5 秒']], ['默认'])),
    step(f"30 万个 key 的同一份数据,三种主库配置各同步一次:磁盘方式 {rows['disk']['ta']:.2f} s(主库磁盘上留下 dump.rdb);无盘、延迟 0:{rows['dl0']['ta']:.2f} s(主库磁盘上没有 dump.rdb);无盘、默认延迟 5:{rows['dl5']['ta']:.2f} s。", b=bars([['磁盘方式', rows['disk']['ta'], f"{rows['disk']['ta']:.2f} s"], ['无盘 delay 0', rows['dl0']['ta'], f"{rows['dl0']['ta']:.2f} s"], ['无盘 delay 5(默认)', rows['dl5']['ta'], f"{rows['dl5']['ta']:.2f} s"]], rows['dl5']['ta'], mark=[2], done=[1]), kv=KV([['dump.rdb', '磁盘方式:有;无盘:无']], ['dump.rdb'])),
    step("默认的 5 秒延迟就是为了「等更多从库」:日志「Delay next BGSAVE for diskless SYNC」,5 秒过后才「Starting BGSAVE for SYNC with target: replicas sockets (rdb-channel)」,子进程直接把 RDB 写进从库的 socket,不经过磁盘。", n=cells(['Delay next BGSAVE', '等待 ~5 s', 'BGSAVE → replicas sockets', 'Streamed RDB transfer … succeeded'], cur=[1], done=[0]), kv=KV([['目标', 'replicas sockets (rdb-channel)']], ['目标'])),
    step(f"延迟窗口内第二个从库来了(晚 1 秒,延迟设 3 秒):A 在 {two['ta']:.2f} s、B 在 {two['tb']:.2f} s 同时完成,主库只有 {two['bgsave']} 次「Starting BGSAVE for SYNC」——一次子进程给两个从库都发了。", n=cells(['A 连接', 'B 连接(+1 s)', '一次 BGSAVE', 'A、B 同时完成'], done=[0, 1, 2, 3]), kv=KV([['BGSAVE 次数', str(two['bgsave'])], ['A / B 完成', f"{two['ta']:.2f} s / {two['tb']:.2f} s"]], ['BGSAVE 次数'])),
    step(f"从库侧的 repl-diskless-load:默认 disabled,从库先把收到的 RDB 存成文件(目录里出现 dump.rdb)再加载,本次同步 {ld['ta']:.2f} s;改成 swapdb,从库直接从 socket 加载,目录里没有 dump.rdb,同步 {ls['ta']:.2f} s。", n=cells(['disabled: ' + ', '.join(ld['rdir']), 'swapdb: ' + ', '.join(ls['rdir'])], mark=[0], done=[1]), kv=KV([['disabled', f"{ld['ta']:.2f} s,有 dump.rdb"], ['swapdb', f"{ls['ta']:.2f} s,无 dump.rdb"]], ['swapdb'])),
]
A = dict(
    n=58, series='redis', tags='Redis,复制,无盘复制,真实验证,动画演示',
    desc=f'本机实测无盘复制:默认 repl-diskless-sync yes + repl-diskless-sync-delay 5,30 万 key 同步耗时 {rows["dl5"]["ta"]:.2f} s(delay 0 时 {rows["dl0"]["ta"]:.2f} s、磁盘方式 {rows["disk"]["ta"]:.2f} s);无盘时主库磁盘没有 dump.rdb;延迟窗口内的两个从库共用一次 BGSAVE({two["bgsave"]} 次);从库 repl-diskless-load swapdb 不落盘。',
    lead='传统的全量同步要先把 RDB 写到主库磁盘,再读出来发给从库。无盘复制(diskless)让子进程直接把 RDB 写进从库的连接。新版本里它已经是默认值——而且默认带一个 5 秒的等待。这篇量一量它对同步时间的影响,以及那 5 秒是干什么的。',
    facts=[(f'{rows["dl5"]["ta"]:.2f} s', f'默认配置(delay 5)下的同步耗时;delay 0 是 {rows["dl0"]["ta"]:.2f} s'), ('无 dump.rdb', '无盘发送时,主库磁盘上不产生 RDB 文件'), (f'{two["bgsave"]} 次', '延迟窗口内先后到达的两个从库,共用的 BGSAVE 次数')],
    body=[
        sec('先看默认值', '', term('', blk('r58', 1)), '<p>这台机器上的 Redis 默认:无盘发送 <code>repl-diskless-sync yes</code>,等待 <code>repl-diskless-sync-delay 5</code>(秒),<code>repl-diskless-sync-max-replicas 0</code>,从库加载 <code>repl-diskless-load disabled</code>。</p>'),
        sec('同步耗时:磁盘 vs 无盘 vs 默认延迟', '30 万个 key,每种配置一个新主库 + 一个新从库', term('', blk('r58', 2)), f'<p>磁盘方式 {rows["disk"]["ta"]:.2f} s,无盘 delay 0 {rows["dl0"]["ta"]:.2f} s,两者接近(单次测量,差别在噪声范围内,我没有多次重复);<b>默认的无盘配置是 {rows["dl5"]["ta"]:.2f} s——多出的 5 秒是 delay,不是传输慢</b>。磁盘方式时主库目录里留下了 <code>dump.rdb</code>,两种无盘配置没有。</p>'),
        sec('那 5 秒在等什么', '', term('', blk('r58', 3)), '<p>日志里先是 <code>Delay next BGSAVE for diskless SYNC</code>,延迟结束后才 <code>Starting BGSAVE for SYNC with target: replicas sockets (rdb-channel)</code>:子进程把 RDB 直接写到从库的连接上;最后 <code>Streamed RDB transfer with replica … succeeded (socket)</code>。这里的 <code>rdb-channel</code> 是这个版本日志里出现的目标名,我没有深入验证它对应的协议细节。</p>'),
        sec('延迟窗口就是为了共用', '延迟设 3 秒,第二个从库晚 1 秒到', term('', blk('r58', 4)), f'<p>两个从库的完成时间都是 {two["ta"]:.2f} s、{two["tb"]:.2f} s,主库日志只有 {two["bgsave"]} 次 <code>Starting BGSAVE for SYNC</code>,然后两次 <code>Streamed RDB transfer</code>:一个子进程,同一份 RDB,发给了两个从库。这就是等待窗口的用途——多个从库同时上线(比如主库重启后所有从库一起重连)时只 fork 一次。代价是单个从库的同步被推迟。</p>'),
        sec('从库端:repl-diskless-load', '', term('', blk('r58', 5)), f'<p>默认 <code>disabled</code>:从库先把收到的 RDB 落成 <code>dump.rdb</code>,再加载;目录里能看到这个文件。<code>swapdb</code>:同步之后目录里没有 dump.rdb,说明从库没有把收到的 RDB 落盘(同步 {ls["ta"]:.2f} s,对比 {ld["ta"]:.2f} s,同样是单次测量)。</p>'),
        sec('分步演示:五个对比', '', demo('无盘复制', [('n', 'cells', '配置 / 阶段'), ('b', 'bars', '同步耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。每种配置一个新的主库(30 万个 key,value 是随机小数字符串)和新从库,本机回环;每种配置只测一次,差别很小的数字不要当结论', '没有验证:跨机器网络下无盘与磁盘方式的差别、repl-diskless-sync-max-replicas 提前触发、rdb-channel 的协议细节、swapdb 加载失败时的回滚、大数据集下无盘对主库内存(COW)的影响'],
)
