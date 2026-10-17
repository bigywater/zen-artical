import json
from lib import *
R = J('r50'); off = R['offline']; mem = R['mem']; pub = R['pub']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
p = {r[0]: r for r in pub}
steps = [
    step(f"消费者都离线时发了 100 条。3 个订阅者上线后,{off[0]} 个收到东西:Pub/Sub 只把消息推给「此刻在线」的连接。", m=cells(['Pub/Sub:100 条 → 上线后 0 条'], mark=[0]), kv=KV([['Pub/Sub 上线后收到', str(off[0]) + ' 个订阅者有消息']], ['Pub/Sub 上线后收到'])),
    step(f"同样的 100 条也写了一份到 Stream。消费组上线后 XREADGROUP 一次读到 {off[1]} 条——积压都在。", m=cells(['Stream:100 条 → 上线后 100 条'], done=[0]), kv=KV([['Stream 上线后读到', f'{off[1]} 条']], ['Stream 上线后读到'])),
    step(f"内存:PUBLISH 10 万条(无订阅者)used_memory 变化 {mem[0]:+d} B,可以忽略;XADD 10 万条增加 {mem[1]} B({mem[1]/100000:.1f} B/条)。Pub/Sub 不存;Stream 存到你删为止。", b=bars([['PUBLISH 10 万条', max(mem[0], 1), f'{mem[0]:+d} B'], ['XADD 10 万条', mem[1], f'{mem[1]/1e6:.1f} MB']], mem[1], mark=[1]), kv=KV([['Pub/Sub', '不占内存'], ['Stream', f'{mem[1]/100000:.1f} B/条']], ['Stream'])),
    step(f"扇出的代价:一条 PUBLISH 要写给每个订阅者。N=0 时 {p[0][1]:.0f} µs,N=10 时 {p[10][1]:.0f} µs,N=100 时 {p[100][1]:.0f} µs,N=1000 时 {p[1000][1]/1000:.1f} ms,N=5000 时 {p[5000][1]/1000:.1f} ms。而 XADD 恒为 {p[0][2]:.0f} µs 左右,与消费者多少无关。", b=bars([[f'PUBLISH N={N}', p[N][1], f'{p[N][1]:.0f} µs'] for N in (0, 10, 100, 1000, 5000)] + [['XADD(任意 N)', p[5000][2], f'{p[5000][2]:.0f} µs']], p[5000][1], mark=[4], done=[5]), kv=KV([['每个订阅者约', f'{(p[5000][1]-p[0][1])/5000:.1f} µs']], ['每个订阅者约'])),
    step("语义:3 个订阅者都收到同一条 m1(广播);Stream 同一个组里 3 个消费者,只有第一个读到 m1,另外两个是 nil(分担)。想广播要用多个消费组。", m=cells(['Pub/Sub: m1 m1 m1', 'Stream 同组: m1 nil nil'], cur=[0, 1]), kv=KV([['Pub/Sub', '广播给所有订阅者'], ['Stream 消费组', '组内分担、组间广播']], ['Pub/Sub'])),
]
A = dict(
    n=50, series='redis', tags='Redis,Pub/Sub,Stream,真实验证,动画演示',
    desc=f'把 Pub/Sub 与 Stream 放在同一实例上对比:消费者离线期间的 100 条,Pub/Sub 上线后一条也收不到、Stream 消费组一次读回 100 条;发布 10 万条 Pub/Sub 几乎不占内存、Stream 占 {mem[1]/1e6:.1f} MB;PUBLISH 耗时随订阅者数线性增长(N=5000 时 {p[5000][1]/1000:.1f} ms),XADD 不受消费者数量影响。',
    lead='上一篇看到 Pub/Sub 会丢消息;Stream 则会保留。这篇不再重复「丢不丢」,而是把两者放在同一台实例上,量四个维度:离线补读、内存占用、发布方的代价、分发语义。选哪个,取决于这些数字回答的问题对你重不重要。',
    facts=[(f'{off[0]} vs {off[1]}', '消费者离线期间发布 100 条,上线后读到的条数:Pub/Sub vs Stream'), (f'{p[5000][1]/1000:.1f} ms', f'向 5000 个订阅者 PUBLISH 一条消息的往返耗时(0 个订阅者 {p[0][1]:.0f} µs)'), (f'{mem[1]/100000:.0f} B/条', 'Stream 保留一条 100 字节消息的内存;Pub/Sub 保留 0')],
    body=[
        sec('离线之后:补不补得回来', '', term('', blk('r50', 1)), '<p>同样的 100 条,同时用 PUBLISH 和 XADD 各发一份。三个 Pub/Sub 订阅者上线后没有任何一个收到东西;Stream 的消费组一次 XREADGROUP 就拿回 100 条。</p>'),
        sec('内存:Pub/Sub 不存,Stream 存到你删为止', '', term('', blk('r50', 2)), f'<p>发布 10 万条(每条 100 字节)无订阅者的 PUBLISH,<code>used_memory</code> 只变了 {mem[0]:+d} 字节(测量噪声);XADD 同样数量增加了 {mem[1]} 字节。Stream 必须自己控制长度(<code>MAXLEN</code> / <code>XTRIM</code>,见第 47 篇)。</p>'),
        sec('发布方的代价:PUBLISH 是 O(订阅者数)', '同步往返,单连接,每种 N 测 1000 次取中位', term('', blk('r50', 3)),
            f'<p>订阅者放在另一个进程里持续排空,避免测量进程被拖慢。0 个订阅者时 PUBLISH 和 XADD 一样快({p[0][1]:.0f} µs vs {p[0][2]:.0f} µs);之后 PUBLISH 随订阅者数线性增加,约每个订阅者 {(p[5000][1]-p[0][1])/5000:.1f} µs,5000 个订阅者时一条 PUBLISH 要 {p[5000][1]/1000:.1f} ms;XADD 恒定在 {p[0][2]:.0f} µs 左右。<b>PUBLISH 是在主线程里同步地向所有订阅者的输出缓冲区写数据</b>——这点由耗时的线性增长间接印证,我没有做更细的剖析。</p>'),
        sec('语义:广播 vs 分担', '', term('', blk('r50', 4)), '<p>Pub/Sub 的一条消息被广播给所有订阅者;Stream 在同一个消费组里只交给一个消费者,不同的组才各得一份(第 41 篇)。所以「多个服务都要收到」用多个消费组,「多个实例分担」用同一个组。</p>'),
        sec('分步演示:四个维度', '', demo('Pub/Sub 与 Stream', [('m', 'cells', '离线补读 / 语义'), ('b', 'bars', '内存 / 耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。订阅者数很大的实验用单独进程排空订阅连接,PUBLISH 用同步往返计时', '没有验证:Pub/Sub 与 Stream 在集群下的差别(包括分片 Pub/Sub)、大消息时的吞吐对比、订阅者存在慢消费时对 PUBLISH 耗时的影响'],
)
