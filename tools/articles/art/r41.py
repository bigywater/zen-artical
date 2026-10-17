import json
from lib import *
R = J('r41'); got = R['got']; seq = R['seq']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
owner = {}
for k, v in got.items():
    for i in v: owner[i] = k
ids = [f'{i}-0' for i in range(1, 13)]
def cells(k): return {'values': [f'{i}' + (f'·{owner[ids[i-1]]}' if i <= k else '') for i in range(1, 13)], 'cur': [k - 1] if k else [], 'done': list(range(k - 1))}
steps = [
    step("流里有 12 条消息(1-0 … 12-0)。用 XGROUP CREATE s gall 0 创建消费组,起点 0 = 从头读;另建 gnew,起点 $ = 只看之后新写入的。", m=cells(0), kv=KV([['gall', 'last-delivered-id = 0-0'], ['gnew', 'last-delivered-id = 12-0($)']], ['gall'])),
    step("消费组自己记着一个游标 last-delivered-id。XREADGROUP ... > 每次都从游标之后取,取走就把游标往前推——这就是「同组内不重复」的机制。", m=cells(0), kv=KV([['XREADGROUP … >', '读游标之后的新消息'], ['读完后', '游标前进']], ['XREADGROUP … >'])),
    step(f"我按顺序让 c1、c2、c3 各读一条:{' '.join(seq[:3])}。它们拿到 1-0、2-0、3-0,互不重复。", m=cells(3), kv=KV([['c1', '1-0'], ['c2', '2-0'], ['c3', '3-0']], ['c3'])),
    step(f"继续按 {' '.join(seq[3:])} 的顺序读完:每条消息恰好交给一个消费者。最终 c1:{got['c1']};c2:{got['c2']};c3:{got['c3']}。谁读得勤谁拿得多,组不做均衡。", m=cells(12), kv=KV([[k, f'{len(v)} 条'] for k, v in got.items()], ['c1'])),
    step("再读一次,返回 nil——游标已经在 12-0,后面没有新消息了。XINFO GROUPS 里 pending = 12(全在 PEL 里,还没 ack),lag = 1(gall 创建之后又写入的 13-0 还没读)。", m=cells(12), kv=KV([['gall pending', '12'], ['gall lag', '1'], ['gall consumers', '3']], ['gall pending'])),
    step("另一个组 gnew 与 gall 完全独立:它创建于 $,读不到 1–12,写入 13-0 之后才读到 13-0。同一条消息可以被多个组各消费一次。", m=cells(12), kv=KV([['gnew 创建时读到', 'nil'], ['XADD 13-0 后读到', '13-0'], ['gall / gnew', '各自独立的游标和 PEL']], ['gnew 创建时读到'])),
]
A = dict(
    n=41, series='redis', tags='Redis,Stream,Consumer Group,真实验证,动画演示',
    desc='在本机 Redis 上验证 Stream Consumer Group:创建起点 $ 与 0 的区别,同组内 3 个消费者读同一条流时消息互不重复(各拿 4 条),不同组各自独立读全部消息,XINFO GROUPS 里的 pending / lag / last-delivered-id 各是什么意思,以及 MKSTREAM、BUSYGROUP、CREATECONSUMER、DESTROY 的行为。',
    lead='Stream 的消费组解决的是「多个消费者分担同一条流」的问题:组内每条消息只交给一个消费者,不同的组则各读一份。这篇在真实实例上把它拆开:组的游标、消费者怎么出现、消息怎么分配、几个 XINFO 字段的含义,以及创建时最容易踩的坑。',
    facts=[('4 / 4 / 4', '3 个消费者读完 12 条消息,各自拿到的条数(按我指定的读取顺序)'), ('$ vs 0', '创建消费组时的起点:只看新消息 vs 从头开始'), ('每个组一份', '不同组各自维护游标和 PEL,互不影响')],
    body=[
        sec('创建组:起点决定读得到什么', '', term('', blk('r41', 1)), '<p><code>$</code> 表示「当前最后一条之后」,创建后才写入的消息才会被这个组读到;<code>0</code> 表示从头开始。key 不存在时 <code>XGROUP CREATE</code> 会报错,要加 <code>MKSTREAM</code> 才会连流一起创建;同名组再创建报 <code>BUSYGROUP</code>。</p>'),
        sec('同一个组里:消息只交给一个消费者', '', term('', blk('r41', 2)), f'<p>三个消费者 c1、c2、c3 按我指定的顺序({" ".join(seq)})每次读 1 条(<code>XREADGROUP … COUNT 1 … &gt;</code>)。12 条消息被完整分配、没有重复,每人拿到 4 条。这个「平均」是我安排的读取顺序造成的:组本身没有轮询或均衡,谁先来读、谁就拿走游标后面的下一条。</p>'),
        sec('不同的组:各读各的', '', term('', blk('r41', 3)), '<p>组 <code>gnew</code> 创建于 <code>$</code>:那时流里已有 12 条,它一条也读不到(<code>nil</code>);之后写入 13-0,它才读到。而 <code>gall</code> 从头读过了全部消息——同一条消息被两个组各消费一次,这是 Stream 相对 List 队列的关键差别(见第 48 篇)。</p>'),
        sec('XINFO 看组和消费者的状态', '', term('', blk('r41', 4)), '<p>组的字段:<code>last-delivered-id</code> 是游标;<code>pending</code> 是 PEL 里未确认的条数(gall 读了 12 条都没 ack,所以是 12);<code>entries-read</code> 是组读过的条目总数;<code>lag</code> 是流里还没被这个组读到的条数(gall 是 1,因为 13-0 是它之后才写入的;gnew 是 0)。消费者的字段:<code>pending</code>、<code>idle</code>(距上次读的毫秒数)、<code>inactive</code>(距上次真正取到消息的毫秒数)。</p>'),
        sec('消费者不用预先创建', '', term('', blk('r41', 5)), '<p>消费者第一次 XREADGROUP 时自动出现;也可以显式 <code>XGROUP CREATECONSUMER</code>(新建返回 1,已存在返回 0)。<code>XGROUP DESTROY</code> 删掉整个组,第二次返回 0。</p>'),
        sec('分步演示:游标怎样把消息分给消费者', '格子上的字母是读到它的消费者', demo('Consumer Group', [('m', 'cells', '流里的 12 条消息(序号·被谁读走)'), ('kv', 'kv', '组的状态')], steps, '刚被读走的消息')),
    ],
    refs=[ENV_R, '没有验证:多个消费者并发读时的分配公平性(这里是我按固定顺序串行读)、组数量很多时的内存与性能、XGROUP SETID 与 ENTRIESREAD 的用法、集群下的行为'],
)
