import json
from lib import *
R = J('r112'); om = R['omem']; q = R['qbuf']; cn = R['clients']; idle = R['idle']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step(f"每个连接在服务器里有两块缓冲:读客户端请求的「查询缓冲」(CLIENT LIST 里的 qbuf、qbuf-free)和给客户端回复的「输出缓冲」(omem、obl、oll)。一个刚 PING 过的空闲连接:qbuf {idle['qbuf']}、omem {idle['omem']}、rbs(读缓冲大小){idle['rbs']} 字节,整个连接 tot-mem 只有 {idle['tot-mem']} 字节。", t=tm([f"qbuf={idle['qbuf']}  qbuf-free={idle['qbuf-free']}  argv-mem={idle['argv-mem']}", f"obl={idle['obl']}  oll={idle['oll']}  omem={idle['omem']}", f"rbs={idle['rbs']}  rbp={idle['rbp']}  tot-mem={idle['tot-mem']}"], cur=[0, 1, 2]), kv=KV([['空闲连接', f"tot-mem {idle['tot-mem']} 字节"]], ['空闲连接'])),
    step(f"输出缓冲怎么涨:GET 一个 1 MB 的 value,客户端不读(我把它的接收缓冲调到 4 KB):1 个 GET → omem {om[1][1]/1e6:.1f} MB;5 个 → {om[2][1]/1e6:.1f} MB;20 个 → {om[3][1]/1e6:.1f} MB;100 个 → {om[4][1]/1e6:.0f} MB。基本是每个未读回复 1 MB,线性增长、没有上限(normal 类默认不限制,第 113 篇)。", b=bars([[f'{k} 个未读回复', o / 1e6, f'{o/1e6:.1f} MB'] for k, o, _, _, _ in om[1:]], om[4][1] / 1e6, mark=[3]), kv=KV([['100 个未读的 1 MB 回复', f"omem {om[4][1]/1e6:.0f} MB"]], ['100 个未读的 1 MB 回复'])),
    step(f"查询缓冲怎么涨:发一个 SET,声明 value 长度 50 MB,只发 10 MB 就停:qbuf = {q['qbuf']/1e6:.1f} MB,qbuf-free = {q['qbuf-free']/1e6:.1f} MB,整个连接 tot-mem = {q['tot-mem']/1e6:.1f} MB——服务器按声明的 50 MB 预先分配了缓冲(已用 10.5 MB + 空闲 42 MB),而不是按实际收到的。", b=bars([['qbuf(已用)', q['qbuf'] / 1e6, f"{q['qbuf']/1e6:.1f} MB"], ['qbuf-free(预留)', q['qbuf-free'] / 1e6, f"{q['qbuf-free']/1e6:.1f} MB"], ['tot-mem', q['tot-mem'] / 1e6, f"{q['tot-mem']/1e6:.1f} MB"]], q['tot-mem'] / 1e6, mark=[1]), kv=KV([['声明 50 MB,发了 10 MB', f"占 {q['tot-mem']/1e6:.0f} MB"]], ['声明 50 MB,发了 10 MB'])),
    step(f"这意味着:proto-max-bulk-len(默认 512 MB)限制的是「客户端声明的大小」,一个连接只需要声明一个很大的 bulk 就能让服务器为它预留内存。多个这样的连接就能占用可观的内存(第 105 篇里 client-query-buffer-limit 是另一道防线)。", t=tm(['声明 $52428800 → 服务器预留 ≈ 52 MB', '实际只收到 10 MB'], mark=[0]), kv=KV([['风险', '声明大小 ≠ 实际大小']], ['风险'])),
    step(f"基础开销:200 个空闲连接时 INFO 里 mem_clients_normal = {cn['mem']/1e6:.2f} MB(connected_clients = {cn['n']}),平均每个连接约 {cn['mem']/cn['n']/1024:.1f} KB。连接数很多时这笔开销要计入 maxmemory 之外的余量(第 114 篇看连接数上限)。", b=bars([['mem_clients_normal', cn['mem'] / 1e6, f"{cn['mem']/1e6:.2f} MB"]], 2, done=[0]), kv=KV([['每个空闲连接', f"约 {cn['mem']/cn['n']/1024:.1f} KB"]], ['每个空闲连接'])),
]
A = dict(
    n=112, series='redis', tags='Redis,网络缓冲区,内存,真实验证,动画演示',
    desc=f'从 CLIENT LIST 的 qbuf/omem 等字段看 Redis 的每连接缓冲:空闲连接 tot-mem {idle["tot-mem"]} 字节;不读取的客户端每个 1 MB 的 GET 回复让 omem 增加约 1 MB(100 个 → {om[4][1]/1e6:.0f} MB);声明 50 MB 的 bulk 只发 10 MB 就让连接占用 {q["tot-mem"]/1e6:.0f} MB(服务器按声明大小预留了 qbuf-free {q["qbuf-free"]/1e6:.0f} MB);200 个空闲连接的 mem_clients_normal 平均约 {cn["mem"]/cn["n"]/1024:.1f} KB/个。',
    lead='Redis 为每个连接维护两块缓冲:读请求的查询缓冲和写回复的输出缓冲。它们平时很小,但可以在一个连接上涨到很大。这篇用 CLIENT LIST 里的字段把两块缓冲各自「怎么涨」量出来,并发现一个反直觉的细节:查询缓冲是按客户端声明的大小预留的。',
    facts=[(f'{om[4][1]/1e6:.0f} MB', '客户端不读取时,100 个 1 MB 的 GET 回复堆积成的输出缓冲(omem)'), (f'{q["tot-mem"]/1e6:.0f} MB', '声明 50 MB 的 bulk、只发 10 MB 时该连接占用的内存'), (f'{cn["mem"]/cn["n"]/1024:.1f} KB', '空闲连接的平均内存(200 个连接,mem_clients_normal ÷ 连接数)')],
    body=[
        sec('CLIENT LIST 里的缓冲字段', '', term('', blk('r112', 1)), '<p><code>qbuf</code> / <code>qbuf-free</code> 是查询缓冲的已用与空闲;<code>argv-mem</code> 是已解析出来的参数占用;<code>obl</code> / <code>oll</code> / <code>omem</code> 描述输出缓冲;<code>rbs</code> / <code>rbp</code> 是读缓冲的当前大小与峰值;<code>tot-mem</code> 是整个连接占用的内存。空闲连接总共只有 2 KB 左右。(<code>obl</code> 与 <code>oll</code> 各自的确切含义——固定缓冲字节与链表节点数——我没有单独验证。)</p>'),
        sec('输出缓冲:未读的回复线性堆积', '', term('', blk('r112', 2)), f'<p>客户端只发 GET 而不读回复(并把自己的接收缓冲调到 4 KB),服务器为每个未读的 1 MB 回复多缓冲约 1 MB:{om[1][0]} 个 → {om[1][1]/1e6:.1f} MB,{om[3][0]} 个 → {om[3][1]/1e6:.0f} MB,{om[4][0]} 个 → {om[4][1]/1e6:.0f} MB。normal 类客户端默认没有输出缓冲上限,所以这会一直涨到你设置限制为止(第 113 篇)。</p>'),
        sec('查询缓冲:按声明大小预留', '', term('', blk('r112', 3)), f'<p>发 <code>SET k</code>,声明 value 长度 52428800 字节(50 MB),只发送 10 MB 后不再发送:<code>qbuf</code> = {q["qbuf"]/1e6:.1f} MB,<code>qbuf-free</code> = {q["qbuf-free"]/1e6:.1f} MB,合计 {q["tot-mem"]/1e6:.1f} MB。也就是说,服务器在收到头部之后就为声明的 50 MB 预先分配了缓冲,而不是随实际收到的数据增长。所以<b>「声明一个很大的 bulk」本身就能让服务器占内存</b>,上限由 <code>proto-max-bulk-len</code> 决定(默认 512 MB;本实验里调成了 100 MB)。</p>'),
        sec('连接的基础开销', '', term('', blk('r112', 4)), f'<p>200 个空闲连接:<code>mem_clients_normal</code> {cn["mem"]/1e6:.2f} MB,平均每个连接约 {cn["mem"]/cn["n"]/1024:.1f} KB。(第 114 篇用 <code>used_memory</code> 的变化量得到 1000 个连接每个约 17 KB,口径不同:那里包含了连接相关的其它分配。)</p>'),
        sec('分步演示:两块缓冲', '', demo('Redis 网络缓冲区', [('t', 'term', '字段'), ('b', 'bars', '内存'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。缓冲数据来自 CLIENT LIST;不读取的客户端是原始 socket,接收缓冲设为 4 KB', '没有验证:obl/oll 的确切语义、多线程 I/O 开启后的缓冲行为、TLS 连接的额外缓冲、大量小 key 的 pipeline 下的输出缓冲增长'],
)
