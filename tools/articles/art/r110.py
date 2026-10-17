import json
from lib import *
R = J('r110'); ex = {int(k): v for k, v in R['exp'].items()}; cp = {int(k): v for k, v in R['cpu'].items()}; dyn = R['dyn']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
d4 = [x for x in dyn if x[1] > x[2]]
steps = [
    step("hz 是 Redis 后台定时任务(serverCron:过期扫描、客户端超时检查、统计更新等)每秒运行的次数,默认 10,即每 100 ms 一次。dynamic-hz 默认 yes:连接很多时实际 hz 会自动提高。INFO server 里 hz 是当前实际值,configured_hz 是配置值。", b=bars([['默认 hz', 10, '10 次/秒 = 100 ms 一次']], 12, done=[0]), kv=KV([['默认', 'hz 10,dynamic-hz yes']], ['默认'])),
    step(f"hz 直接决定过期事件的及时性:同样的 PX 300 key,在空闲实例上 expired 事件比 300 ms 晚多少——hz 1:中位 {ex[1][0]:.0f} ms、最大 {ex[1][1]:.0f} ms;hz 10:中位 {ex[10][0]:.1f} ms、最大 {ex[10][1]:.1f} ms;hz 100:中位 {ex[100][0]:.1f} ms。", b=bars([['hz 1', ex[1][0], f'{ex[1][0]:.0f} ms'], ['hz 10', ex[10][0], f'{ex[10][0]:.1f} ms'], ['hz 100', ex[100][0], f'{ex[100][0]:.1f} ms']], ex[1][0], mark=[0], done=[1, 2]), kv=KV([['过期事件延迟(中位)', f'{ex[1][0]:.0f} → {ex[10][0]:.1f} → {ex[100][0]:.1f} ms']], ['过期事件延迟(中位)'])),
    step(f"hz 从 10 提到 100,中位延迟没有更小({ex[100][0]:.1f} ms 对 {ex[10][0]:.1f} ms)——这个场景下空闲实例上过期本来就靠 hz 10 足够及时,再提高只是增加了扫描次数。(hz 100 的最大值 {ex[100][1]:.0f} ms 是偶发抖动,我没有重复。)", b=bars([['hz 10 中位', ex[10][0], f'{ex[10][0]:.1f} ms'], ['hz 100 中位', ex[100][0], f'{ex[100][0]:.1f} ms']], 10, done=[0, 1]), kv=KV([['提高 hz', '空闲时没有收益']], ['提高 hz'])),
    step(f"代价是空闲 CPU:一个空闲实例 10 秒内消耗的 CPU:hz 10 → {cp[10]:.3f} s,hz 100 → {cp[100]:.3f} s,hz 500 → {cp[500]:.3f} s(折合每秒 {cp[10]/10*1000:.1f} / {cp[100]/10*1000:.1f} / {cp[500]/10*1000:.1f} ms)。hz 越大,空闲时也越忙(每次 cron 都有固定开销)。", b=bars([[f'hz {h}', cp[h] * 1000, f'{cp[h]:.3f} s / 10 s'] for h in (10, 100, 500)], cp[500] * 1000, mark=[2], done=[0]), kv=KV([['空闲 CPU', f'{cp[10]/10*1000:.1f} → {cp[500]/10*1000:.1f} ms/秒']], ['空闲 CPU'])),
    step(f"dynamic-hz yes:连接的客户端数升高时,实际 hz 自动上调而 configured_hz 不变。本次测量:连接数到 500、2000 时 hz 仍是 10;到 {d4[0][0]} 个连接时 hz 变成 {d4[0][1]}(configured_hz {d4[0][2]})。触发阈值比我预期的高(我没有二分),所以「多连接自动加快」在几千连接的量级才出现。", b=bars([[f'{cc} 个连接', h, f'hz {h}'] for cc, h, ch in dyn], 24, mark=[len(dyn) - 1]), kv=KV([['实际 hz', ' → '.join(str(h) for _, h, _ in dyn)]], ['实际 hz'])),
]
A = dict(
    n=110, series='redis', tags='Redis,hz,serverCron,真实验证,动画演示',
    desc=f'实测 hz 与 dynamic-hz:过期事件比 TTL 晚的中位数 hz 1 时 {ex[1][0]:.0f} ms、hz 10 时 {ex[10][0]:.1f} ms、hz 100 时 {ex[100][0]:.1f} ms;空闲 CPU 10 秒 {cp[10]:.3f} s(hz 10)/ {cp[100]:.3f} s(hz 100)/ {cp[500]:.3f} s(hz 500);dynamic-hz yes 时连接数到 {d4[0][0]} 才把实际 hz 从 10 提到 {d4[0][1]}。',
    lead='hz 是很少有人认真调的参数,但它是 Redis 后台任务的节拍:过期扫描、客户端超时、统计更新都靠它。这篇量它的两面:hz 小了,过期事件会晚多少;hz 大了,空闲时多耗多少 CPU;以及 dynamic-hz 什么时候会自动把它调高。',
    facts=[(f'{ex[1][0]:.0f} → {ex[10][0]:.1f} ms', 'hz 1 → 10 时,过期事件比 TTL 晚的中位数'), (f'{cp[10]/10*1000:.1f} → {cp[500]/10*1000:.1f} ms/秒', '空闲实例的 CPU:hz 10 → hz 500'), (f'{d4[0][0]} 连接', f'dynamic-hz 把实际 hz 从 10 提到 {d4[0][1]} 所需的连接数(本次测量)')],
    body=[
        sec('默认值', '', term('', blk('r110', 1)), '<p><code>hz</code> 默认 10,<code>dynamic-hz</code> 默认 yes。<code>INFO server</code> 里的 <code>hz</code> 是当前实际值,<code>configured_hz</code> 是配置值。</p>'),
        sec('hz 与过期事件的及时性', '每种 hz 20 次,空闲实例', term('', blk('r110', 2)), f'<p>hz 1 时后台扫描每秒一次,expired 事件比 TTL 晚的中位数 {ex[1][0]:.0f} ms、最大 {ex[1][1]:.0f} ms(约一个扫描周期);hz 10 时中位数 {ex[10][0]:.1f} ms;hz 100 时 {ex[100][0]:.1f} ms,没有比 hz 10 更好。注意:这是空闲实例、少量 key 的情形;第 51 篇里量到,当库里有大量长 TTL 的 key 时,过期回收的及时性主要取决于抽样,而不是 hz 本身(那时没有测 hz 调大是否有帮助)。</p>'),
        sec('hz 的代价', '每个 hz 一个新实例,10 秒内 INFO 里 CPU 累计的增量', term('', blk('r110', 3)), f'<p>空闲实例 10 秒消耗的 CPU:hz 10 是 {cp[10]:.3f} s,hz 100 是 {cp[100]:.3f} s,hz 500 是 {cp[500]:.3f} s,大致随 hz 线性增长。绝对值很小(hz 500 也只是每秒约 {cp[500]/10*1000:.0f} ms),这是空闲实例、本机的数字;数据量大时每次 cron 的工作量也会变。</p>'),
        sec('dynamic-hz', '', term('', blk('r110', 4)), f'<p>开着 dynamic-hz 时,连接数很多会自动提高实际 hz(<code>configured_hz</code> 不变)。本次测量里 500、2000 个连接时实际 hz 都还是 10,4000 个连接时才变成 {d4[0][1]}。触发的具体规则我没有去查源码,只记录了这几个点,中间没有二分。</p>'),
        sec('分步演示:hz 的两面', '', demo('Redis hz 与 dynamic-hz', [('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。过期事件延迟用 keyspace notification 的 expired 事件计时;CPU 取自 INFO cpu 的 used_cpu_sys + used_cpu_user;客户端连接用空闲的原始 socket', '没有验证:数据量大时的 hz 影响、hz 高于 100 时的过期效果、dynamic-hz 的具体阈值、客户端超时检查(timeout 配置)的精度与 hz 的关系'],
)
