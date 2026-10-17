import json
from lib import *
R = J('r46'); ak = R['ack']; dl = R['del']; tr = R['trim']; mn = R['minid']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
M = lambda x: f'{x/1e6:.2f} MB'
base = ak[0][2]
def bars(items, cur=(), mark=(), done=()): return {'items': items, 'max': ak[1][2], 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step(f"写入 10 万条消息(每条值 100 字节),XLEN = 100000,占 {M(ak[0][2])},radix 树 {ak[0][1]} 个节点。", b=bars([['写入完成', ak[0][2], M(ak[0][2])]], cur=[0]), kv=KV([['XLEN', '100000'], ['radix-keys', str(ak[0][1])]], ['XLEN'])),
    step(f"消费组把 10 万条全读走、不 ack:内存涨到 {M(ak[1][2])}(多出来的是 PEL)。", b=bars([['写入完成', ak[0][2], M(ak[0][2])], ['读取但未 ack', ak[1][2], M(ak[1][2])]], cur=[1]), kv=KV([['PEL', '10 万条'], ['内存', M(ak[1][2])]], ['内存'])),
    step(f"全部 XACK 之后:内存回到 {M(ak[2][2])},比写入时只多 {ak[2][2]-ak[0][2]} 字节;XLEN 仍是 {ak[2][0]}。ack 只回收 PEL,不回收消息。", b=bars([['写入完成', ak[0][2], M(ak[0][2])], ['读取但未 ack', ak[1][2], M(ak[1][2])], ['全部 XACK', ak[2][2], M(ak[2][2])]], done=[2]), kv=KV([['XLEN', str(ak[2][0])], ['内存', M(ak[2][2])]], ['XLEN'])),
    step(f"隔一条 XDEL 一条(删一半):XLEN 变成 {dl['alt'][0]},内存仍是 {M(dl['alt'][2])},radix 节点数一个没少({dl['alt'][1]})。XDEL 在 listpack 里只是打「已删除」标记,空间没有归还。", b=bars([['基线', ak[0][2], M(ak[0][2])], ['隔一条删一条', dl['alt'][2], M(dl['alt'][2])]], mark=[1]), kv=KV([['XLEN', str(dl['alt'][0])], ['radix-keys', str(dl['alt'][1])]], ['radix-keys'])),
    step(f"连续删前一半:radix 节点从 {ak[0][1]} 降到 {dl['front'][1]},内存降到 {M(dl['front'][2])}(约一半)。整个节点的消息都被删空时,这个节点才会被释放。", b=bars([['基线', ak[0][2], M(ak[0][2])], ['隔一条删一条', dl['alt'][2], M(dl['alt'][2])], ['连续删前一半', dl['front'][2], M(dl['front'][2])]], done=[2]), kv=KV([['XLEN', str(dl['front'][0])], ['radix-keys', str(dl['front'][1])]], ['radix-keys'])),
    step(f"XTRIM MINID(按 ID 裁掉旧数据)的效果与「连续删前一半」相同:XLEN 50000、内存 {M(mn[2])}。XTRIM MAXLEN 0 清空:内存只剩 {tr[2]} 字节。", b=bars([['基线', ak[0][2], M(ak[0][2])], ['XTRIM MINID(留一半)', mn[2], M(mn[2])], ['XTRIM MAXLEN 0', max(tr[2], 1), f'{tr[2]} B']], done=[1, 2]), kv=KV([['MAXLEN 0 之后', f'XLEN {tr[0]},radix-keys {tr[1]}']], ['MAXLEN 0 之后'])),
]
A = dict(
    n=46, series='redis', tags='Redis,Stream,内存,真实验证,动画演示',
    desc=f'10 万条消息的 Stream 内存回收实测:XACK 全部确认后内存回到 {M(ak[2][2])}(只回收 PEL,XLEN 不变);XDEL 隔一条删一条内存不变({M(dl["alt"][2])}),连续删前一半才降到 {M(dl["front"][2])};XTRIM MINID 效果与连续删除相同,XTRIM MAXLEN 0 清空后内存只剩 {tr[2]} 字节。',
    lead='消息被消费、被 ack 之后,Stream 里的内存什么时候还回去?很多人以为 XACK 或 XDEL 之后内存自然就少了。这篇用 10 万条消息量一量:ack、隔一条删一条、连续删除、XTRIM 各自能回收多少,以及为什么「删了一半」不等于「省了一半」。(「回收」在这里指内存回收;PEL 里消息的转移回收见第 44、45 篇。)',
    facts=[(M(ak[2][2]), f'全部 XACK 后的内存(写入时 {M(ak[0][2])});XLEN 仍是 {ak[2][0]}'), (M(dl['alt'][2]), '隔一条 XDEL 一条(删一半)后的内存——几乎没变'), (M(dl['front'][2]), '连续删前一半后的内存——约减半')],
    body=[
        sec('XACK:只回收 PEL', '', term('', blk('r46', 1)), f'<p>读走不 ack 时,内存从 {M(ak[0][2])} 涨到 {M(ak[1][2])};全部 ack 后回到 {M(ak[2][2])}(比写入时多 {ak[2][2]-ak[0][2]} 字节)。XLEN、radix-tree-keys 都没变:<b>ack 只是清理了 PEL,消息一条也没有被回收</b>。</p>'),
        sec('XDEL:取决于删得连不连续', '', term('', blk('r46', 2)), f'<p>同样是删掉 5 万条:隔一条删一条,内存 {dl["alt"][2]} 字节,与基线({ak[0][2]})几乎相同,radix 节点数一个没少;连续删前一半,radix 节点数从 {ak[0][1]} 降到 {dl["front"][1]},内存降到 {dl["front"][2]}。原因:一个节点里的消息只要还有一条没被删,这个节点(那段 listpack)就还在;被删的消息只是被打上标记。<b>零星地 XDEL,几乎不省内存。</b>(我只从节点数与内存的变化推断标记机制,没有拆 listpack 验证。)</p>'),
        sec('XTRIM:按前缀整段裁掉', '', term('', blk('r46', 3)), f'<p><code>XTRIM MINID</code> 裁掉一半旧数据的结果({mn[2]} 字节,{mn[1]} 个节点)与「连续删前一半」相同;<code>XTRIM MAXLEN 0</code> 后 XLEN 0、radix 节点 {tr[1]} 个,MEMORY USAGE 只剩 {tr[2]} 字节。日志类的 Stream 通常应该靠 <code>XTRIM</code> 从头部裁剪,而不是零散 XDEL。</p>'),
        sec('XDEL 只是打标记', '', term('', blk('r46', 4)), '<p>删除 5 万条之后:<code>length</code> 是 50000,<code>entries-added</code> 仍是 100000,<code>max-deleted-entry-id</code> 前进到被删的最大 ID。这些计数是 Stream 自己维护的,消费组的 lag 计算依赖它们。</p>'),
        sec('分步演示:每种操作能回收多少内存', '条形长度是 MEMORY USAGE', demo('Stream 内存回收', [('b', 'bars', 'MEMORY USAGE'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。10 万条消息,每条一个字段(值 100 字节),默认 stream-node-max-entries=100', '没有验证:XDEL 标记在 listpack 内的具体形式;Redis 内存分配器层面的碎片(MEMORY USAGE 是 Redis 计的逻辑占用,不等于进程 RSS);在有多个消费组 / 大 PEL 时 XTRIM 的行为(XTRIM 与 PEL、消费组的交互)'],
)
