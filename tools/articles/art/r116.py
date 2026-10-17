import json
from lib import *
R = J('r116'); mu = R['mu']; sc = R['scan']; dbg = R['dbg']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("数据集:30 万个 20 字节的小 key,外加 5 个大 key:5 MB 字符串、20 万元素的 list、10 万字段的 hash、15 万成员的 set、5 万成员的 zset。目标:不停服务地把这 5 个大 key 找出来。", t=tm(['300000 个 small:*', 'big:string(5 MB)', 'big:list(20 万元素)', 'big:hash(10 万字段)', 'big:set(15 万成员)', 'big:zset(5 万成员)']), kv=KV([['目标', '找出 5 个大 key']], ['目标'])),
    step("单个 key 的内存:MEMORY USAGE key。这个版本上 5 个大 key 的结果是:string 5259293、list 1700350、hash 5450727、set 6784700、zset 4254435 字节。按字节数排:set > hash > string > zset > list——和「元素个数」的排序(string 最大、然后 list、set、hash、zset)不同。", b=bars([[f"{m[0].replace('big:','')}({m[2]} 元素)", m[3] / 1e6, f'{m[3]/1e6:.2f} MB'] for m in sorted(mu, key=lambda x: -x[3])], max(m[3] for m in mu) / 1e6, mark=[0]), kv=KV([['字节最大', 'big:set 6.78 MB']], ['字节最大'])),
    step(f"每次 MEMORY USAGE 只花约 0.1 ms:五个 key 的 SAMPLES 默认(5)耗时 {min(m[4] for m in mu):.0f}–{max(m[4] for m in mu):.0f} µs;SAMPLES 0(要求精确)也是 {min(m[5] for m in mu):.0f}–{max(m[5] for m in mu):.0f} µs,结果与 SAMPLES 5 完全相同。文档里 SAMPLES 0 是 O(N) 的说法,在这个版本、这些数据上没有体现出来(我没有查为什么)。", b=bars([[f"{m[0].replace('big:','')} SAMPLES 默认", m[4], f'{m[4]:.0f} µs'] for m in mu] + [[f"{m[0].replace('big:','')} SAMPLES 0", m[5], f'{m[5]:.0f} µs'] for m in mu[:2]], 150, done=range(7)), kv=KV([['MEMORY USAGE', '约 0.1 ms/次,与元素数无关(本版本)']], ['MEMORY USAGE'])),
    step(f"扫全库:SCAN COUNT 1000,每批用管道对本批所有 key 发 MEMORY USAGE。{sc['n']} 个 key 共 {sc['s']:.2f} s({sc['n']/sc['s']/1000:.0f}k key/秒),期间另一个连接 PING 最大停顿 {sc['stall']:.1f} ms。挑出超过 100 KB 的 key:" + '、'.join(f"{k}({m/1e6:.2f} MB)" for k, m in sc['top']) + "——5 个大 key 一个不漏。", b=bars([['扫描总耗时(s)', sc['s'], f"{sc['s']:.2f} s"], ['PING 最大停顿(ms)', sc['stall'], f"{sc['stall']:.1f} ms"]], 1, done=[0, 1]), kv=KV([['结果', '5 个大 key 全部找出']], ['结果'])),
    step("DEBUG OBJECT key 给出的是别的口径:big:list 的 serializedlength 是 776101(RDB 序列化后的长度),而 MEMORY USAGE 是 1700350(内存占用);它还给出编码(quicklist、hashtable)与 quicklist 的节点数。要找「RDB 里占多大」用前者,「内存里占多大」用后者。", t=tm([dbg[0][:150], dbg[1][:120]], cur=[0, 1]), kv=KV([['两种口径', '序列化长度 ≠ 内存占用']], ['两种口径'])),
]
A = dict(
    n=116, series='redis', tags='Redis,大Key,SCAN,真实验证,动画演示',
    desc=f'在有 5 个大 key(5 MB 字符串、20 万元素 list、10 万字段 hash、15 万成员 set、5 万成员 zset)和 30 万个小 key 的实例上手写大 key 扫描:SCAN COUNT 1000 + 管道 MEMORY USAGE,{sc["n"]} 个 key 用 {sc["s"]:.2f} s、PING 最大停顿 {sc["stall"]:.1f} ms,5 个大 key 全部找出;MEMORY USAGE 每次约 0.1 ms;按字节与按元素数排序的结果不同。',
    lead='大 key 会拖慢删除、迁移、复制,得先找到它们。找的时候不能反过来把线上服务拖慢。这篇手写一个大 key 扫描器(SCAN + MEMORY USAGE),在一个埋了 5 个大 key 的库里量它:能不能找全、要多久、对其它请求有多大影响。',
    facts=[(f'{sc["n"]/sc["s"]/1000:.0f}k key/秒', f'SCAN + MEMORY USAGE 管道扫描的速度(全库 {sc["s"]:.2f} s)'), (f'{sc["stall"]:.1f} ms', '扫描期间另一个连接 PING 的最大停顿'), ('5 / 5', '埋入的大 key 被找出的个数')],
    body=[
        sec('MEMORY USAGE', '', term('', blk('r116', 2)), '<p><code>MEMORY USAGE key</code> 返回 key 及其值占用的字节数。按字节排序和按元素个数排序结论不同:字节最多的是 15 万成员的 set(6.78 MB),元素最多的是 5 MB 字符串。所以只看元素数会漏掉「元素少但每个很大」的 key。每次调用约 0.1 ms;<code>SAMPLES 0</code>(理论上是精确遍历)在这些数据上耗时和默认值一样、结果完全相同——这与文档里对 SAMPLES 的说明不一致,我没有追究原因。</p>'),
        sec('自己写扫描器', '', term('', blk('r116', 3)), f'<p>SCAN 分批取 key(COUNT 1000),每批用管道发 <code>MEMORY USAGE</code>,把超过阈值(100 KB)的记下来。{sc["n"]} 个 key 扫描 {sc["s"]:.2f} s,PING 最大停顿只有 {sc["stall"]:.1f} ms;5 个大 key 一个不漏。这是本机、小 key 为主的库;key 数更多、单批里有大 key(<code>MEMORY USAGE</code> 变慢)时要相应加大批与批之间的间隔。</p>'),
        sec('DEBUG OBJECT', '', term('', blk('r116', 4)), '<p><code>DEBUG OBJECT</code>(需要 <code>enable-debug-command</code>)给出编码、引用计数、<code>serializedlength</code>(RDB 序列化后的长度)等。<code>serializedlength</code> 与 <code>MEMORY USAGE</code> 口径不同:big:list 是 776101 对 1700350。</p>'),
        sec('分步演示:找出 5 个大 key', '', demo('Redis Big Key 扫描', [('t', 'term', '说明'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。5 个大 key 是我构造的;MEMORY USAGE 用默认 SAMPLES;PING 每 0.5 ms 一次', '没有验证:集群上逐节点扫描、key 数上亿时的耗时、MEMORY USAGE 在嵌套/压缩编码上的精度、扫描期间有写入时大 key 的变化'],
)
