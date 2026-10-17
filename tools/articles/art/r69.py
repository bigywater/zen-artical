import json
from lib import *
R = J('r69'); m = R['match']; d = R['dist']; p = R['ping']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step("key → 槽位:slot = CRC16(key) mod 16384。CRC16 用的是 XMODEM 变体:输入字符串 \"123456789\" 的校验值是 0x31C3(标准值),我自己用 30 行 Python 实现。", k=cells(['key', 'CRC16', '% 16384', '槽位'], cur=[1]), kv=KV([['crc16(\"123456789\")', '0x31C3 ✓']], ['crc16("123456789")'])),
    step(f"对照服务器:随机生成 {m[1]} 个 key(长度 1–23,含 {{ }} 字符),我算的槽位与 CLUSTER KEYSLOT 一致 {m[0]} 个,不一致 {m[1]-m[0]} 个。foo → 12182,bar → 5061,{{user1}}:a 与 {{user1}}:b 同为 8106(hash tag 只对花括号里的部分算 CRC16)。", k=cells(['foo 12182', 'bar 5061', '{user1}:a 8106', '{user1}:b 8106'], done=[0, 1, 2, 3]), kv=KV([['一致', f'{m[0]} / {m[1]}']], ['一致'])),
    step(f"分布:100 万个连续的 key(user:0…user:999999)落到 16384 个槽里,平均 {d['mean']:.1f} 个/槽,最少 {d['mn']}、最多 {d['mx']},标准差 {d['sd']:.2f}——比纯随机(泊松)期望 {d['mean']**.5:.2f} 还小。卡方 {d['chi']:.0f} 低于均匀随机的期望 16383:这批规则 key 比随机撒点更均匀。", b=bars([['实测标准差', d['sd'], f"{d['sd']:.2f}"], ['泊松期望', d['mean']**.5, f"{d['mean']**.5:.2f}"]], d['mean']**.5, done=[0], mark=[1]), kv=KV([['卡方', f"{d['chi']:.0f}(自由度 16383)"]], ['卡方'])),
    step(f"三段槽位各得 key 的比例:{d['share'][0]/1e4:.2f}% / {d['share'][1]/1e4:.2f}% / {d['share'][2]/1e4:.2f}%,几乎恰好三等分。", b=bars([[f'槽段 {i+1}', d['share'][i], f"{d['share'][i]/1e4:.2f}%"] for i in range(3)], max(d['share']), done=[0, 1, 2]), kv=KV([['三段', f"{d['share'][0]} / {d['share'][1]} / {d['share'][2]}"]], ['三段'])),
    step(f"为什么是 16384?看集群总线消息:让一个节点 MEET 我伪造的对端,读它发来的第一条消息——总长度 {p['totlen']} 字节,其中一个 {p['bitmap_len']} 字节的位图就是「本节点负责哪些槽」(16384 位)。我给节点分配了槽 0–100,位图里置位的正好是 {p['bits']} 个。", k=cells(['头部', f'位图 {p["bitmap_len"]} 字节', '其它字段'], cur=[1]), kv=KV([['totlen', f"{p['totlen']} B"], ['位图', f"{p['bitmap_len']} B(16384 位)"], ['置位数', str(p['bits'])]], ['位图'])),
    step(f"这个位图每次心跳都带着。槽位数 16384 → {16384//8} 字节;如果是 65536 个槽就是 {65536//8} 字节。(这是简单的除法,「集群节点不建议超过 1000 个」等理由是官方的设计说明,我没有在这里验证。)", b=bars([['16384 个槽', 16384 // 8, f'{16384//8} B'], ['65536 个槽', 65536 // 8, f'{65536//8} B']], 65536 // 8, done=[0], mark=[1]), kv=KV([['位图大小', '2048 B vs 8192 B']], ['位图大小'])),
]
A = dict(
    n=69, series='redis', tags='Redis,Cluster,CRC16,真实验证,动画演示',
    desc=f'验证 Redis Cluster 的槽位算法:自己实现 CRC16(XMODEM)算出的槽位与 CLUSTER KEYSLOT 在 {m[1]} 个随机 key 上全部一致;100 万个连续 key 落到 16384 个槽里标准差 {d["sd"]:.2f}(比纯随机的 {d["mean"]**.5:.2f} 还均匀);并用伪造对端截获集群总线消息,证实每条消息带着一个 {p["bitmap_len"]} 字节(16384 位)的槽位位图,总长 {p["totlen"]} 字节。',
    lead='槽位号是怎么来的?为什么是 16384 而不是 65536?这篇不背答案:先用自己写的 CRC16 去对拍服务器的 CLUSTER KEYSLOT,再量 100 万个 key 在槽里的分布,最后伪造一个集群总线对端,抓下节点发来的第一条消息,看看那个「槽位位图」到底有多大。',
    facts=[(f'{m[0]} / {m[1]}', '自己实现的 CRC16 与服务器 CLUSTER KEYSLOT 结果一致的 key 数'), (f'{p["bitmap_len"]} B', f'集群总线消息(总长 {p["totlen"]} B)里的槽位位图 = 16384 位'), (f'σ = {d["sd"]:.2f}', f'100 万个连续 key 在槽里的标准差(纯随机期望 {d["mean"]**.5:.2f})')],
    body=[
        sec('算法:CRC16 mod 16384', '', term('', blk('r69', 1)), f'<p>槽位 = <code>CRC16(key) mod 16384</code>,CRC16 是 XMODEM 变体(多项式 0x1021,初值 0)。我用 Python 写了一个表驱动的实现,输入 <code>"123456789"</code> 得到标准校验值 <code>0x31C3</code>;随机生成的 {m[1]} 个 key(包含花括号)全部与 <code>CLUSTER KEYSLOT</code> 一致,包括 hash tag 的规则(<code>{{user1}}:a</code> 与 <code>{{user1}}:b</code> 都是 8106;<code>a{{}}b</code> 里花括号是空的,整个 key 参与计算)。</p>'),
        sec('分布:比随机还均匀', '', term('', blk('r69', 2)), f'<p>100 万个连续 key(<code>user:0</code>…<code>user:999999</code>)在 16384 个槽里,平均 {d["mean"]:.1f} 个,最少 {d["mn"]}、最多 {d["mx"]},标准差 {d["sd"]:.2f},<b>低于</b>纯随机撒点的期望 {d["mean"]**.5:.2f};卡方 {d["chi"]:.0f} 也低于期望 16383(±181)。也就是说,对「前缀相同、后缀是递增数字」这类规则的 key,CRC16 的分散效果比随机更均匀。这一点只对我测的这批 key 成立,不代表任意 key 集合。三段槽位各拿到约三分之一的 key。</p>'),
        sec('为什么是 16384:看心跳里的位图', '', term('', blk('r69', 3)), f'<p>做法:开一个单节点的集群实例,分配槽 0–100,再让它 <code>CLUSTER MEET</code> 一个我用 socket 伪造的对端(监听总线端口 17331)。节点连过来,发来的第一条消息以 <code>RCmb</code> 开头,总长度 {p["totlen"]} 字节;从偏移 80 开始有 {p["bitmap_len"]} 字节——那是本节点的槽位位图,16384 位,我分配的 101 个槽对应 {p["bits"]} 个置位。发送方 ID 也与 <code>CLUSTER MYID</code> 一致。</p><p>这条消息里没有 gossip 条目(count = 0),因为节点还不认识别人;有邻居时会在头部之后追加条目。<b>位图是固定大小,每次心跳都带</b>:槽位数是 16384 时是 {16384//8} 字节,是 65536 时会是 {65536//8} 字节。这就是常被引用的理由之一;另外「集群不超过约 1000 个主节点」的设计假设也是官方说法,我没有做这一部分的实验。</p>'),
        sec('分步演示:从 key 到槽位,再到心跳', '', demo('CRC16 与 16384 个槽位', [('k', 'cells', '步骤'), ('b', 'bars', '数据'), ('kv', 'kv', '观察')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。集群总线消息由一个单节点集群实例主动发给我伪造的监听端口(CLUSTER MEET 触发)', '没有验证:集群总线消息中 gossip 条目的大小、6 节点以上集群的心跳流量、为什么官方选 16384 而不是别的数(只验证了位图大小)、CRC16 对非规则 key 集合的分布'],
)
