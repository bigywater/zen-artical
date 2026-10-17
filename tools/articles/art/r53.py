import json
from lib import *
R = J('r53'); ring = R['ring']; gap = R['gap']
ok = [g for g in gap if g['res'] == '部分重同步']; bad = [g for g in gap if g['res'] == '全量同步']
lo, hi = ok[-1]['wrote'], bad[0]['wrote']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step("还没有从库连过时,repl_backlog_active = 0:backlog 没有创建,histlen = 0。第一个从库连上之后变成 1,first_byte_offset = 1。", n=cells(['backlog 未创建', '第 1 个从库连上 → active'], cur=[1]), kv=KV([['repl_backlog_active', '0 → 1'], ['repl-backlog-size', '16384(本实验设置)']], ['repl_backlog_active'])),
    step(f"随着写入,histlen 跟着 master_repl_offset 增长:4119、12055、16407 都是「全部保留」;写到 30103 时 histlen 也是 30103——已经超过配置的 16384,并不是严格的 16 KB 上限。", n=cells([f'offset {r["master_repl_offset"]}: histlen {r["repl_backlog_histlen"]}' for r in ring[:4]], done=[0, 1, 2, 3]), kv=KV([['30103 字节时', 'histlen = 30103 > 16384']], ['30103 字节时'])),
    step(f"写到 {ring[4]['master_repl_offset']} 字节时才开始丢头部:histlen 降到 {ring[4]['repl_backlog_histlen']},first_byte_offset 前移到 {ring[4]['repl_backlog_first_byte_offset']}。", n=cells([f'offset {ring[4]["master_repl_offset"]}', f'保留 {ring[4]["repl_backlog_histlen"]} 字节', f'从 {ring[4]["repl_backlog_first_byte_offset"]} 开始'], mark=[1, 2]), kv=KV([['histlen', str(ring[4]['repl_backlog_histlen'])], ['first_byte_offset', str(ring[4]['repl_backlog_first_byte_offset'])]], ['first_byte_offset'])),
    step("用一个可随时断开的 TCP 转发模拟网络中断:从库断开期间主库写入 X 字节,重连时看是部分重同步还是全量。", n=cells(['从库 ⇄ 转发 ⇄ 主库', '断开 → 主库写 X 字节 → 恢复']), kv=KV([['判断依据', '主库 INFO stats 的 sync_full / sync_partial_ok']], [])),
    step("X 在 " + f"{ok[0]['wrote']}–{ok[-1]['wrote']} 字节之间都是部分重同步——包括远大于 16384 的 {ok[-1]['wrote']} 字节。", n=cells([f'{g["wrote"]} B' for g in ok], done=range(len(ok))), b=bars([[f'{g["wrote"]} B', g['wrote'], '部分重同步'] for g in ok], 110000, done=range(len(ok))), kv=KV([['最大仍成功', f'{lo} 字节']], ['最大仍成功'])),
    step(f"X 增大到 {hi} 字节及以上就退回全量同步(sync_full +1)。在这台实例上,断点落在 {lo}–{hi} 字节之间,约是 repl-backlog-size 的 2 倍。", n=cells([f'{g["wrote"]} B' for g in bad], mark=range(len(bad))), b=bars([[f'{g["wrote"]} B', g['wrote'], '全量同步'] for g in bad], 110000, mark=range(len(bad))), kv=KV([['第一个失败的 X', f'{hi} 字节']], ['第一个失败的 X'])),
    step("默认值:repl-backlog-size = 1048576(1 MB),repl-backlog-ttl = 3600(没有从库连接一小时后释放 backlog)。", n=cells(['size 1 MB', 'ttl 3600 s'], cur=[0, 1]), kv=KV([['CONFIG GET', 'repl-backlog-size 1048576 / repl-backlog-ttl 3600']], ['CONFIG GET'])),
]
A = dict(
    n=53, series='redis', tags='Redis,复制,backlog,真实验证,动画演示',
    desc=f'用可断开的 TCP 转发模拟从库断线,实测 repl-backlog-size=16 KB 时的部分重同步边界:断开期间主库写入 {lo} 字节仍是部分重同步、{hi} 字节起退回全量,约为配置值的 2 倍(backlog 的 histlen 会超过配置值:写入 30103 字节时 histlen = 30103);另附默认值 1 MB。',
    lead='复制积压缓冲区(replication backlog)决定了「从库断开多久还能只补差量」。文档里的说法是一个固定大小的环形缓冲。这篇不复述,直接量:把 backlog 设成最小的 16 KB,用一个能随时切断的 TCP 转发让从库断线,看主库写多少字节之后就再也补不上了。',
    facts=[(f'{lo} B', f'repl-backlog-size=16 KB 时,断线期间仍能部分重同步的最大写入量(本次采样点)'), (f'{hi} B', '本次采样里第一个退回全量同步的写入量'), ('1 MB', '默认 repl-backlog-size')],
    body=[
        sec('backlog 何时创建', '', term('', blk('r53', 1)), '<p>没有从库连接过的主库 <code>repl_backlog_active</code> 是 0;第一个从库连上之后变成 1。参数 <code>repl-backlog-size</code> 这里设成 16 KB(<code>CONFIG GET</code> 显示 16384)。</p>'),
        sec('backlog 里究竟保留了多少', '', term('', blk('r53', 2)), f'<p>写到 {ring[3]["master_repl_offset"]} 字节时 <code>repl_backlog_histlen</code> 仍等于 offset({ring[3]["repl_backlog_histlen"]}),已经超过了配置的 16384;写到 {ring[4]["master_repl_offset"]} 字节时才丢头部,histlen = {ring[4]["repl_backlog_histlen"]}、<code>first_byte_offset</code> = {ring[4]["repl_backlog_first_byte_offset"]}。<b>所以 backlog 实际保留量会略微超过配置值,不是严格的环形缓冲</b>(这一点是从上面的数字看出来的;为什么会这样——猜测是按块分配、整块释放——我没有读源码验证)。</p>'),
        sec('从库断线多久还能部分重同步', '用可断开的 TCP 转发模拟网络中断', term('', blk('r53', 3)), f'<p>做法:从库通过一个我写的 TCP 转发连主库;<code>cut()</code> 关闭转发并断开连接,主库继续写入 X 字节,<code>resume()</code> 之后从库自动重连,看主库 <code>INFO stats</code> 里是 <code>sync_partial_ok</code> 还是 <code>sync_full</code> 增加(表里最后一列是主库日志中 <code>Full resync requested</code> 与 <code>Partial resynchronization request</code> 的累计次数,两种判断方式的分类一致)。结果:X 到 {lo} 字节都是部分重同步——比 16384 大得多;{hi} 字节起全量同步。断点在本次采样的 {lo}–{hi} 之间,没有做更细的二分,也没有多次重复确认边界是否稳定。<b>不要把「16 KB 配置 ≈ 28 KB 可用」当成规律,只当作「实际余量不止配置值」的证据。</b></p>'),
        sec('默认值', '', term('', blk('r53', 4)), '<p>默认 <code>repl-backlog-size</code> 是 1048576 字节(1 MB),<code>repl-backlog-ttl</code> 是 3600 秒。每秒写入量 × 预期最长断线时间,再留余量,就是该设的大小。</p>'),
        sec('分步演示:断线补差量的边界', '', demo('复制积压缓冲区', [('n', 'cells', '状态 / 采样点'), ('b', 'bars', '写入量 与 结果'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。主库 repl-backlog-size=16kb;从库经过一个自写的 TCP 转发连接主库,转发被 cut()/resume() 模拟断线','没有验证:同样设置在 Redis 其他版本上的边界、多个从库时的边界、断开时间对 repl-backlog-ttl 的影响、backlog 内部数据结构'],
)
