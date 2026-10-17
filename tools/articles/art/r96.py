import json
from lib import *
R = J('r96'); en = R['entries']; q = R['queue']; tr = R['trunc']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("阈值 slowlog-log-slower-than = 10000 µs(10 ms)、slowlog-max-len = 5。50 万个 key 的实例里执行 DEBUG SLEEP 0.05、KEYS k:1*、SORT nosuch、SET fast 1:只有前两条超过阈值,被记录。", t=tm(['SLOWLOG LEN = 2', f'id=1  KEYS k:1*        {en[0][1]} µs', f'id=0  DEBUG SLEEP 0.05  {en[1][1]} µs'], mark=[1, 2]), kv=KV([['记录的条数', '2(SORT nosuch、SET 都很快)']], ['记录的条数'])),
    step("每条记录有:自增 id、时间戳、耗时(微秒)、命令与参数、客户端地址、客户端名字。最新的在前;id 只增不减。", t=tm(['id · 时间戳 · 耗时µs · [命令, 参数…] · 客户端地址 · 客户端名'], cur=[0]), kv=KV([['字段', '6 个']], ['字段'])),
    step(f"slowlog-max-len 是个环形队列:再制造 8 条慢命令,SLOWLOG LEN 仍是 5,留下的 id 是 {R['ring']}——最旧的被挤掉。所以慢日志只能看「最近的」慢命令。", t=tm([f'保留 id: {R["ring"]}', '更旧的 id 被丢弃'], mark=[0]), kv=KV([['SLOWLOG LEN', '5(上限)']], ['SLOWLOG LEN'])),
    step("阈值 0 = 记录所有命令(PING、GET 都进了慢日志,性能开销要自己评估);阈值 -1 = 关闭(DEBUG SLEEP 0.05 之后 SLOWLOG LEN = 0)。", t=tm(['阈值 0 → PING、GET、CONFIG SET 都被记录', '阈值 -1 → 慢命令也不记录(LEN = 0)'], mark=[0, 1]), kv=KV([['0', '记录一切'], ['-1', '关闭']], ['0'])),
    step(f"参数会被截断:MSET 80 个参数、value 各 300 字节,记录下来只有 {tr['n']} 个参数,value 被截成 148 字节(末尾是「... (172 more bytes)」),最后一个参数是「{tr['last']}」。所以慢日志里看不到完整的大命令。", t=tm([f"记录的参数个数 = {tr['n']}(最多 32)", '每个参数最多 128 字节 + 提示', tr['last']], mark=[0, 2]), kv=KV([['截断', '≤32 个参数,每个 ≤128 字节']], ['截断'])),
    step(f"最容易误会的一点:SLOWLOG 只记录「执行」耗时,不含排队、不含网络。一个连接被 DEBUG SLEEP 0.3 阻塞时,另一个连接的 PING 感受到 {q['ping_ms']:.0f} ms 延迟,但慢日志里只有那条 DEBUG({q['slowlog'][0][1]/1000:.0f} ms),PING 本身不在里面。", b=bars([['PING 客户端感受到', q['ping_ms'], f"{q['ping_ms']:.0f} ms"], ['慢日志里的 PING', 0.3, '不存在'], ['慢日志里的 DEBUG', q['slowlog'][0][1] / 1000, f"{q['slowlog'][0][1]/1000:.0f} ms"]], 320, mark=[0], done=[2]), kv=KV([['结论', '慢日志找的是「谁占着主线程」,不是「谁等了多久」']], ['结论'])),
]
A = dict(
    n=96, series='redis', tags='Redis,SLOWLOG,延迟,真实验证,动画演示',
    desc=f'实测 SLOWLOG:阈值 10 ms 时只记录超过阈值的命令(KEYS 21 ms、DEBUG SLEEP 50 ms);slowlog-max-len 5 是环形队列;阈值 0 记录一切、-1 关闭;参数最多记 32 个、每个 128 字节;被 DEBUG SLEEP 阻塞时另一个连接的 PING 感受到 {q["ping_ms"]:.0f} ms,慢日志里却只有那条 DEBUG。',
    lead='SLOWLOG 是排查 Redis 延迟的第一个工具,但它记录什么、不记录什么,很多人并不清楚。这篇用一个 50 万 key 的实例把它的边界逐条验证:阈值、队列长度、参数截断,以及最重要的一条——它不含排队时间。',
    facts=[('10 ms', '本例的慢日志阈值(slowlog-log-slower-than 10000 微秒)'), ('32 × 128 B', '每条记录最多保留的参数个数 × 每个参数的字节数'), (f'{q["ping_ms"]:.0f} ms vs 不在日志', '被阻塞的 PING 客户端感受到的延迟 vs 它在慢日志里的记录')],
    body=[
        sec('记录与字段', '', term('', blk('r96', 1)), '<p>超过阈值的 <code>KEYS</code>(约 21 ms)和 <code>DEBUG SLEEP 0.05</code>(约 50 ms)被记录;<code>SORT nosuch</code>、<code>SET</code> 很快,没有记录。</p>'),
        sec('环形队列', '', term('', blk('r96', 2)), '<p><code>slowlog-max-len 5</code>:超过 5 条后最旧的被挤掉,<code>id</code> 继续递增。生产上要把长度设得够大,或者定期用脚本把慢日志取走。</p>'),
        sec('阈值的特殊值', '', term('', blk('r96', 3)), '<p>0 = 记录所有命令;-1 = 关闭。</p>'),
        sec('参数截断', '', term('', blk('r96', 4)), '<p>记录下来的参数最多 32 个,每个参数最多 128 字节,超出部分用「... (N more arguments)」「... (N more bytes)」代替。</p>'),
        sec('它不含排队时间', '', term('', blk('r96', 5)), f'<p>一个连接执行 <code>DEBUG SLEEP 0.3</code> 占住主线程时,另一个连接的 <code>PING</code> 排队等了 {q["ping_ms"]:.0f} ms,但慢日志里只有那条 <code>DEBUG</code>({q["slowlog"][0][1]/1000:.0f} ms)。所以慢日志回答「谁占着主线程」;要回答「客户端为什么慢」,还要看延迟监控(第 97、98 篇)和客户端侧的测量。</p>'),
        sec('分步演示:SLOWLOG 的边界', '', demo('Redis SLOWLOG', [('t', 'term', '慢日志'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。50 万个 key;慢命令用 DEBUG SLEEP 与 KEYS 制造', '没有验证:Lua 脚本内部命令是否单独记录、阻塞命令(BLPOP)的记录方式、大量记录对性能的影响、SLOWLOG 与 latency-monitor 的关系(第 97、98 篇)'],
)
