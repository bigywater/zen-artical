import json
from lib import *
R = J('r100'); tp = R['tp']; om = R['omem']
per = om[-1][2] / om[-1][0]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step(f"MONITOR 把服务器收到的每条命令实时推给监控客户端。基线:管道 SET 20 万条,没有 MONITOR 时 {tp['base']/1000:.0f}k 条/秒。", b=bars([['没有 MONITOR', tp['base'] / 1000, f"{tp['base']/1000:.0f}k/s"]], tp['base'] / 1000, done=[0]), kv=KV([['基线', f"{tp['base']/1000:.0f}k/s"]], ['基线'])),
    step(f"挂上一个及时读取的 MONITOR 客户端(redis-cli monitor):吞吐降到 {tp['mon']/1000:.0f}k 条/秒,降低 {(1-tp['mon']/tp['base'])*100:.0f}%——每条命令都要多格式化、多写一份给监控客户端。", b=bars([['没有 MONITOR', tp['base'] / 1000, f"{tp['base']/1000:.0f}k/s"], ['有 MONITOR', tp['mon'] / 1000, f"{tp['mon']/1000:.0f}k/s"]], tp['base'] / 1000, done=[0], mark=[1]), kv=KV([['吞吐下降', f"{(1-tp['mon']/tp['base'])*100:.0f}%"]], ['吞吐下降'])),
    step(f"更危险的:MONITOR 客户端连着但不读取(我让它的接收缓冲只有 4 KB)。normal 客户端的 client-output-buffer-limit 默认是 0 0 0(没有上限),服务器只能一直缓冲:执行 20 万条命令后该连接 omem = {om[0][2]/1e6:.0f} MB,100 万条后 {om[-1][2]/1e6:.0f} MB——约每条命令 {per:.0f} 字节,线性增长。", b=bars([[f'{n_//1000}k 条命令后 omem', o, f'{o/1e6:.0f} MB'] for n_, u, o in om], om[-1][2], mark=[len(om) - 1]), kv=KV([['omem', ' → '.join(f'{o/1e6:.0f}' for _, _, o in om) + ' MB'], ['上限', '无(normal 0 0 0)']], ['omem'])),
    step("关闭这个卡住的连接后,used_memory 立刻回到开始水平(多出 0.0 MB)。所以它是「只要还连着就一直涨」的内存占用,而不是泄漏——但在这期间足以把实例撑到 maxmemory 以上。", b=bars([['关闭连接后多出的内存', 0.3, '0.0 MB']], 80, done=[0]), kv=KV([['关闭后', '回到基线']], ['关闭后'])),
    step("MONITOR 输出的格式:时间戳 [库号 客户端地址] \"命令\" \"参数\"…。AUTH 的参数被替换成 \"(redacted)\";Lua 脚本里执行的命令显示为 [0 lua] \"INCR\" \"n\"。其它命令的参数(包括业务数据)都是明文的。", t=tm(['1790706215.568948 [0 127.0.0.1:58177] "SET" "hello" "world"', '… "AUTH" "(redacted)" "(redacted)"', '… [0 127.0.0.1:58177] "EVAL" "return redis.call(\'INCR\',\'n\')" "0"', '… [0 lua] "INCR" "n"'], mark=[1, 3]), kv=KV([['敏感信息', 'AUTH 被屏蔽,数据不屏蔽']], ['敏感信息'])),
]
A = dict(
    n=100, series='redis', tags='Redis,MONITOR,性能,真实验证,动画演示',
    desc=f'实测 MONITOR 的代价:一个及时读取的 MONITOR 客户端让管道 SET 吞吐从 {tp["base"]/1000:.0f}k 降到 {tp["mon"]/1000:.0f}k 条/秒(-{(1-tp["mon"]/tp["base"])*100:.0f}%);不读取的 MONITOR 连接输出缓冲无上限(normal 0 0 0),100 万条命令后占 {om[-1][2]/1e6:.0f} MB(约 {per:.0f} 字节/条);AUTH 参数被屏蔽,Lua 内命令标为 [0 lua]。',
    lead='MONITOR 是调试利器,也是生产事故的常见来源。这篇量它的两笔代价:吞吐下降多少,以及一个「忘了关的、不读取的」MONITOR 连接会让服务器内存涨到多大。',
    facts=[(f'-{(1-tp["mon"]/tp["base"])*100:.0f}%', f'一个及时读取的 MONITOR 客户端对管道 SET 吞吐的影响({tp["base"]/1000:.0f}k → {tp["mon"]/1000:.0f}k /s)'), (f'{om[-1][2]/1e6:.0f} MB', '不读取的 MONITOR 连接,在执行 100 万条命令后占用的输出缓冲'), ('无上限', 'normal 客户端的 client-output-buffer-limit 默认 0 0 0')],
    body=[
        sec('吞吐', '', term('', blk('r100', 1)), f'<p>管道 SET 20 万条,每种情形测 3 次取中位:没有 MONITOR {tp["base"]/1000:.0f}k/s,有一个及时读取的 <code>redis-cli monitor</code> {tp["mon"]/1000:.0f}k/s。这是本机、每条命令很小、单个监控客户端下的数字;命令越多、参数越大,代价越明显。</p>'),
        sec('卡住的 MONITOR:内存无上限', '', term('', blk('r100', 2)), f'<p>我让一个 MONITOR 连接不读取(并把它的接收缓冲调到 4 KB)。<code>CONFIG GET client-output-buffer-limit</code> 里 <code>normal</code> 是 <code>0 0 0</code>——MONITOR 客户端属于 normal 类,没有上限。20 万条命令后它的 <code>omem</code> 是 {om[0][2]/1e6:.0f} MB,之后线性增长到 100 万条时 {om[-1][2]/1e6:.0f} MB,约 {per:.0f} 字节/条。关掉连接后 <code>used_memory</code> 立刻回到起点。</p>'),
        sec('MONITOR 的输出', '', term('', blk('r100', 3)), '<p>每条命令一行,带微秒时间戳、数据库号和客户端地址。<code>AUTH</code> 的参数被替换为 <code>(redacted)</code>;Lua 脚本里的命令显示为 <code>[0 lua]</code>。其它命令的参数(包括业务数据)原样出现,所以 MONITOR 本身也是一个信息泄露面。</p>'),
        sec('分步演示:MONITOR 的两笔代价', '', demo('MONITOR 的性能代价', [('b', 'bars', '数据'), ('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。单实例,本机回环;卡住的 MONITOR 连接是我用原始 socket 建立的;吞吐每种情形 3 次取中位', '没有验证:多个 MONITOR 客户端同时连接的叠加效应、命令更大/更多时的降幅、给 normal 客户端设置 client-output-buffer-limit 是否会断开 MONITOR 连接(本文没有测)、Linux 上的数字'],
)
