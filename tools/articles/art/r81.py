import json
from lib import *
R = J('r81'); bg = R['big']; bt = R['batch']; fz = R['freeze']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
b100 = [x for x in bg if x['mb'] == 100][0]; b300 = [x for x in bg if x['mb'] == 300][0]
steps = [
    step("MIGRATE 目标主机 端口 key 目标库 超时 [COPY] [REPLACE] [KEYS ...]:把 key 序列化后发给目标执行 RESTORE,目标回 OK 后源再删除。基本用法:MIGRATE k1 → OK,源上 EXISTS k1 = 0,目标 GET k1 = v1。不存在的 key 返回 NOKEY。", n=fl([['源', 'k1 已删除'], ['目标', 'k1 = v1']], done=[1], mark=[0]), t=tm(['> MIGRATE 127.0.0.1 7531 k1 0 5000', '"OK"', '> MIGRATE … nosuch …', '"NOKEY"'], cur=[1], mark=[3]), kv=KV([['返回', 'OK / NOKEY']], ['返回'])),
    step("过期时间会一并搬过去:源上 k2 设了 100 秒,搬到目标后 TTL k2 = 100。list、hash、zset 也一样(用 KEYS 批量搬 h、z,目标上都完整)。", n=fl([['源 k2', 'EX 100'], ['目标 k2', 'TTL = 100']], done=[1]), kv=KV([['TTL', '保留']], ['TTL'])),
    step("COPY 不删源(源 LLEN l = 3、目标 LLEN l = 3);目标已有同名 key 时 MIGRATE 报 BUSYKEY Target key name already exists,要加 REPLACE 才会覆盖。", n=fl([['源', 'l 保留'], ['目标', 'l 已存在 → BUSYKEY']], mark=[1]), t=tm(['> MIGRATE … l 0 5000 COPY', '"OK"', '> MIGRATE … l 0 5000 COPY', '(error) … BUSYKEY Target key name already exists.', '> … COPY REPLACE', '"OK"'], mark=[3], cur=[5]), kv=KV([['BUSYKEY', '加 REPLACE 覆盖']], ['BUSYKEY'])),
    step(f"代价:MIGRATE 在源上是同步执行的。{b100['mb']} MB 的字符串,MIGRATE 用了 {b100['ms']:.0f} ms,同时另一个连接在源上的 PING 最大停顿 {b100['src']:.0f} ms(几乎等于整个 MIGRATE),目标上也停了 {b100['dst']:.0f} ms(处理 RESTORE)。", n=fl([['源', f"阻塞 {b100['src']:.0f} ms"], ['目标', f"阻塞 {b100['dst']:.0f} ms"]], mark=[0, 1]), b=bars([['MIGRATE 耗时', b100['ms'], f"{b100['ms']:.0f} ms"], ['源 PING 最大停顿', b100['src'], f"{b100['src']:.0f} ms"], ['目标 PING 最大停顿', b100['dst'], f"{b100['dst']:.0f} ms"]], b100['ms'], mark=[1, 2]), kv=KV([['100 MB', f"源阻塞 {b100['src']:.0f} ms"]], ['100 MB'])),
    step(f"随大小线性增长:10 MB {bg[0]['ms']:.0f} ms、100 MB {bg[1]['ms']:.0f} ms、300 MB {bg[2]['ms']:.0f} ms;源上停顿同步增长({bg[0]['src']:.0f}/{bg[1]['src']:.0f}/{bg[2]['src']:.0f} ms)。所以迁移含大 key 的槽,会让源节点整体卡住。", b=bars([[f"{x['mb']} MB:源停顿", x['src'], f"{x['src']:.0f} ms"] for x in bg] + [[f"{x['mb']} MB:目标停顿", x['dst'], f"{x['dst']:.0f} ms"] for x in bg], b300['src'], mark=[0, 1, 2], done=[3, 4, 5]), kv=KV([['10 / 100 / 300 MB', f"{bg[0]['src']:.0f} / {bg[1]['src']:.0f} / {bg[2]['src']:.0f} ms"]], ['10 / 100 / 300 MB'])),
    step(f"批量 MIGRATE ... KEYS:1000 个小 key,逐个调用 1000 次 {bt['one']:.0f} ms,一次 KEYS 调用 {bt['batch']:.0f} ms,快 {bt['one']/bt['batch']:.1f} 倍(省的是往返和连接建立)。redis-cli 迁移槽时用的就是批量形式。", b=bars([['逐个 MIGRATE ×1000', bt['one'], f"{bt['one']:.0f} ms"], ['MIGRATE … KEYS(1000 个)', max(bt['batch'], 0.5), f"{bt['batch']:.0f} ms"]], bt['one'], mark=[0], done=[1]), kv=KV([['倍数', f"{bt['one']/bt['batch']:.1f}×"]], ['倍数'])),
    step(f"失败的一面:把目标进程 SIGSTOP 冻结,MIGRATE(超时 800 ms)→ 报 IOERR error or timeout reading to target instance,源上 key 还在。但解冻目标之后,目标上也出现了这个 key(EXISTS = {fz['dst']})——RESTORE 请求其实已经发出,目标醒来就执行了。此时 key 两边都有:源 EXISTS = {fz['src']}、目标 EXISTS = {fz['dst']}。", n=fl([['源', 'key 仍在(没收到 OK)'], ['目标(解冻后)', 'key 也在']], mark=[0, 1]), kv=KV([['IOERR 之后', '不能假设 key 没到目标']], ['IOERR 之后'])),
]
A = dict(
    n=81, series='redis', tags='Redis,Cluster,MIGRATE,真实验证,动画演示',
    desc=f'实测 MIGRATE:搬走源端 key、TTL 保留、COPY/REPLACE/BUSYKEY/NOKEY 的语义;它在源上同步执行——100 MB 的字符串 MIGRATE {b100["ms"]:.0f} ms、源节点被阻塞 {b100["src"]:.0f} ms(目标也阻塞 {b100["dst"]:.0f} ms);KEYS 批量比逐个快 {bt["one"]/bt["batch"]:.0f} 倍;目标冻结导致超时(IOERR)后,解冻的目标上出现了同一个 key,而源上仍在——两边都有。',
    lead='MIGRATE 是集群迁移槽位的底层动作。它看起来只是「把 key 挪到另一个实例」,但有几个细节直接影响线上迁移:它是同步的(大 key 会阻塞源)、它有批量形式(快很多)、它超时失败之后 key 到底在哪(不一定只在一边)。这篇把每一点都在真实实例上量出来。',
    facts=[(f'{b100["src"]:.0f} ms', f'MIGRATE 一个 100 MB 字符串时,源节点上另一个连接 PING 的最大停顿(MIGRATE 共 {b100["ms"]:.0f} ms)'), (f'{bt["one"]/bt["batch"]:.0f} 倍', '一次 MIGRATE … KEYS(1000 个)比逐个 MIGRATE 1000 次快多少'), ('两边都有', '目标冻结导致 IOERR 后,解冻的目标上出现了这个 key,源上也还在')],
    body=[
        sec('基本语义', '', term('', blk('r81', 1)), '<p><code>MIGRATE host port key db timeout</code>:把 key 序列化,发给目标执行 RESTORE,目标回 OK 之后源再删掉。结果:成功 <code>OK</code>,源上没有这个 key <code>NOKEY</code>。TTL 一并保留(源 100 秒 → 目标 TTL 100);list/hash/zset 都能搬。<code>COPY</code> 不删源;目标已有同名 key 时报 <code>BUSYKEY</code>,加 <code>REPLACE</code> 才覆盖;<code>KEYS k1 k2 …</code> 是批量形式(此时 key 参数写空字符串 <code>""</code>)。</p>'),
        sec('大 value:同步执行,阻塞两端', '另一个连接每 1 ms 发一次 PING,记录 MIGRATE 期间的最大停顿', term('', blk('r81', 2)), f'<p>MIGRATE 在源上是同步执行的:{b100["mb"]} MB 的字符串用了 {b100["ms"]:.0f} ms,同时源上另一个连接的 PING 最大停顿 {b100["src"]:.0f} ms——<b>整个 MIGRATE 期间源节点几乎不响应任何命令</b>。目标也被阻塞({b100["dst"]:.0f} ms,处理 RESTORE 的那一段)。耗时与大小近似线性:10 MB {bg[0]["ms"]:.0f} ms、100 MB {bg[1]["ms"]:.0f} ms、300 MB {bg[2]["ms"]:.0f} ms。这是本机回环上的数字;跨机器的网络传输会让源上的阻塞更长。所以<b>含大 key 的槽,迁移时会让这个节点的所有槽一起卡住</b>(第 82 篇)。</p>'),
        sec('批量 KEYS', '', term('', blk('r81', 3)), f'<p>1000 个 100 字节的小 key:逐个调用 MIGRATE 1000 次花了 {bt["one"]:.0f} ms,一次 <code>MIGRATE … KEYS</code> 只要 {bt["batch"]:.0f} ms,快 {bt["one"]/bt["batch"]:.0f} 倍。这是本机回环上的比值;跨机器时每次往返更贵,批量的优势会更大(我没有测)。</p>'),
        sec('目标卡住:失败之后 key 在哪', '用 SIGSTOP 冻结目标进程', term('', blk('r81', 4)), f'<p>把目标进程冻结,MIGRATE(超时 800 ms)等到超时返回 <code>IOERR error or timeout reading to target instance</code>,源上 key 还在(没收到目标的 OK,不会删)。<b>但是</b>:解冻目标之后,它读到了早先发出的 RESTORE 并执行了——目标上也出现了这个 key。两边都有这个 key。所以<b>MIGRATE 报 IOERR 时,不能假设 key 没有到达目标</b>;重试要用 <code>REPLACE</code> 或先检查目标,否则会遇到 <code>BUSYKEY</code>;(集群迁移期间这个「两边都有」的状态会不会带来问题,我没有验证。)</p>'),
        sec('分步演示:MIGRATE 的语义与代价', '', demo('Redis MIGRATE', [('n', 'flow', '源与目标'), ('t', 'term', '命令'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。两个独立实例(非集群);value 是 x 重复的字符串;停顿由另一个连接每 1 ms 一次的 PING 测得;失败实验用 SIGSTOP', '没有验证:跨机器网络下的耗时与阻塞、list/hash 等大集合的 MIGRATE 耗时、AUTH/AUTH2 选项、集群里对 MIGRATE 与 RESTORE-ASKING 的关系、IOERR 后目标上 key 是否总会出现(这里只观察了一次冻结)'],
)
