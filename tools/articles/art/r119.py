import json
from lib import *
R = J('r119'); rows = R['rows']; sc = R['scan']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
r = {x[0]: x for x in rows}
steps = [
    step("KEYS pattern 一次性遍历整个库,把所有匹配的 key 返回。它是 O(N):代价与「库里有多少 key」成正比,与「有多少匹配」无关,并且在主线程里不间断执行。", t=tm(['KEYS pattern:遍历全部 N 个 key,做模式匹配', '执行期间其它命令排队']), kv=KV([['复杂度', 'O(N),N = key 总数']], ['复杂度'])),
    step(f"KEYS *(全部匹配)期间另一个连接 PING 的最大停顿:10 万个 key → {r[100000][2]:.0f} ms;50 万 → {r[500000][2]:.0f} ms;100 万 → {r[1000000][2]:.0f} ms;300 万 → {r[3000000][2]:.0f} ms。随 key 数近似线性增长。", b=bars([[f'{N//10000} 万个 key', r[N][2], f'{r[N][2]:.0f} ms'] for N in (100000, 500000, 1000000, 3000000)], r[3000000][2], mark=[3]), kv=KV([['300 万个 key', f'PING 停顿 {r[3000000][2]:.0f} ms']], ['300 万个 key'])),
    step(f"KEYS nomatch*(几乎没有匹配)同样要遍历全部 key:100 万个 key 时命令耗时 {r[1000000][3]:.0f} ms、PING 停顿 {r[1000000][4]:.0f} ms;300 万个时 {r[3000000][3]:.0f} ms / {r[3000000][4]:.0f} ms。比 KEYS * 小是因为不用构造和发送大回复,但「遍历」这部分的代价仍在。", b=bars([[f'{N//10000} 万个 key,无匹配', r[N][4], f'{r[N][4]:.0f} ms'] for N in (100000, 500000, 1000000, 3000000)], r[3000000][2], mark=[3]), kv=KV([['无匹配的 KEYS', f'300 万个 key 仍停顿 {r[3000000][4]:.0f} ms']], ['无匹配的 KEYS'])),
    step(f"替代方案:SCAN COUNT 1000 遍历 300 万个 key 共 {sc['calls']} 次调用、总耗时 {sc['ms']:.0f} ms,期间另一个连接 PING 的最大停顿只有 {sc['stall']:.2f} ms——比同样规模的 KEYS(约 {r[3000000][2]:.0f} ms 停顿)小两个数量级(第 118 篇)。", b=bars([['KEYS * 时 PING 停顿', r[3000000][2], f'{r[3000000][2]:.0f} ms'], ['SCAN COUNT 1000', max(sc['stall'], 0.3), f"{sc['stall']:.2f} ms"]], r[3000000][2], mark=[0], done=[1]), kv=KV([['SCAN 的停顿', f"{sc['stall']:.2f} ms"]], ['SCAN 的停顿'])),
    step("彻底禁止:用 ACL 给应用用户去掉 keys 命令(ACL SETUSER app … +@all -keys)。这个用户再执行 KEYS * 得到 NOPERM User app has no permissions to run the 'keys' command,而 GET 照常可用。", t=tm(['> KEYS *', "(error) NOPERM User app has no permissions to run the 'keys' command", '> GET key:1', '"v"'], mark=[1]), kv=KV([['ACL', '可以禁用 KEYS']], ['ACL'])),
]
A = dict(
    n=119, series='redis', tags='Redis,KEYS,阻塞,真实验证,动画演示',
    desc=f'实测 KEYS 的风险:另一个连接 PING 的最大停顿随 key 数线性增长——10 万个 {r[100000][2]:.0f} ms、100 万个 {r[1000000][2]:.0f} ms、300 万个 {r[3000000][2]:.0f} ms;几乎无匹配的 KEYS 同样要遍历全部 key(300 万个时停顿 {r[3000000][4]:.0f} ms);SCAN COUNT 1000 遍历同样多 key 只造成 {sc["stall"]:.2f} ms 停顿;可用 ACL 禁掉 KEYS。',
    lead='「生产上不要用 KEYS」几乎是 Redis 的第一条军规。它到底有多危险?危险与什么有关?这篇在 10 万到 300 万个 key 的库上量 KEYS 的阻塞时间,对比 SCAN,并演示怎么从权限上直接禁掉它。',
    facts=[(f'{r[1000000][2]:.0f} ms', '100 万个 key 时 KEYS * 让另一个连接 PING 的最大停顿'), (f'{r[3000000][4]:.0f} ms', '300 万个 key 时,几乎没有匹配的 KEYS 造成的停顿(遍历本身的代价)'), (f'{sc["stall"]:.2f} ms', 'SCAN COUNT 1000 遍历 300 万个 key 期间 PING 的最大停顿')],
    body=[
        sec('KEYS 的代价', '每个库大小测两次:KEYS * 与 KEYS nomatch*;另一个连接每 0.5 ms 发一次 PING', term('', blk('r119', 1)), f'<p>停顿随 key 数近似线性增长:10 万个 key {r[100000][2]:.0f} ms、100 万个 {r[1000000][2]:.0f} ms、300 万个 {r[3000000][2]:.0f} ms。对没有匹配的模式,命令耗时和停顿都小很多({r[3000000][4]:.0f} ms @ 300 万),因为不用构造大回复——但遍历部分的开销没有免除:<b>危险与「key 总数」有关,与「匹配了多少」关系不大</b>。</p>'),
        sec('替代:SCAN', '', term('', blk('r119', 2)), f'<p>SCAN COUNT 1000 遍历 300 万个 key,{sc["calls"]} 次调用共 {sc["ms"]:.0f} ms,期间 PING 最大停顿 {sc["stall"]:.2f} ms。总耗时和 KEYS 一个量级,但每次只占主线程很短一段。</p>'),
        sec('从权限上禁用', '', term('', blk('r119', 3)), '<p>ACL 可以把 <code>keys</code> 从某个用户的权限里去掉:该用户执行 KEYS 得到 <code>NOPERM</code>,其它命令不受影响。ACL 的细节见第 122–125 篇。</p>'),
        sec('分步演示:KEYS 的阻塞', '', demo('KEYS 的风险', [('t', 'term', '说明'), ('b', 'bars', '停顿'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。单实例,key 形如 key:N,值 v;PING 探测间隔 0.5 ms;数字是单次测量', '没有验证:key 名更长或库里有大 key 时的耗时、集群/多库下的行为、rename-command 方式禁用(第 131 篇)、KEYS 在 Lua 中被调用时的行为'],
)
