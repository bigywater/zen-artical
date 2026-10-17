import json
from lib import *
R = J('r45'); rounds = R['rounds']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=(), ptr=None): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim), 'ptr': ptr or {}}
base = [f'{i}' for i in range(1, 11)]
def own(k, who='B'):
    return cells([f'{i} {who}' if i <= k else f'{i} A' for i in range(1, 11)], done=range(k), cur=range(max(0, k - 3), k))
steps = [
    step("A 读了 10 条没 ack,全在 A 名下的 PEL 里。B 想接手,但不知道有哪些 ID。XAUTOCLAIM 不需要先查 ID,从游标 0-0 开始,COUNT 3 每次最多认领 3 条。", own=cells([f'{i} A' for i in range(1, 11)]), kv=KV([['首次调用', 'XAUTOCLAIM s g B 500 0-0 COUNT 3']], [])),
    step(f"第 1 次:游标 0-0 → 认领 {rounds[0]['ids']},返回的下一个游标是 {rounds[0]['nxt']}。", own=own(3), kv=KV([['返回', f"[{rounds[0]['nxt']}, 3 条消息, 已删除 []]"]], ['返回'])),
    step(f"第 2 次:从 {rounds[1]['cur']} 继续 → 认领 {rounds[1]['ids']},下一个游标 {rounds[1]['nxt']}。", own=own(6), kv=KV([['返回', f"[{rounds[1]['nxt']}, 3 条, []]"]], ['返回'])),
    step(f"第 3 次:{rounds[2]['ids']},下一个游标 {rounds[2]['nxt']}。", own=own(9), kv=KV([['返回', f"[{rounds[2]['nxt']}, 3 条, []]"]], ['返回'])),
    step(f"第 4 次:只剩 {rounds[3]['ids']},游标返回 0-0——约定:游标回到 0-0 表示扫描完毕。共 {len(rounds)} 次调用。", own=own(10), kv=KV([['返回', '[0-0, 1 条, []]'], ['结束标志', '游标 = 0-0']], ['结束标志'])),
    step("认领后每条消息 idle 被重置(1 ms)、投递次数变成 2。马上再来一轮 XAUTOCLAIM(C,min-idle 500):什么都没认领到——都还不满 500 ms。", own=own(10), kv=KV([['XPENDING', 'owner=B, idle=1, deliveries=2'], ['C 再来一轮', '[0-0, [], []]']], ['C 再来一轮'])),
    step("加 JUSTID:只转移所有权、不返回消息体,而且不增加投递次数(认领后 deliveries 仍是 2)。适合先「圈地」再慢慢处理。", own=cells([f'{i} C' if i <= 3 else f'{i} B' for i in range(1, 11)], mark=[0, 1, 2]), kv=KV([['JUSTID 返回', '只有 ID 列表'], ['deliveries', '仍是 2']], ['deliveries'])),
    step("如果 PEL 里的某条消息已被 XDEL(4-0、5-0),XAUTOCLAIM 会把它们从 PEL 里删掉,并在返回值第三个元素里列出。之后 XPENDING 的总数从 10 降到 8。", own=cells(['1 D', '2 D', '3 D', '4 ✗', '5 ✗', '6 D', '7 D', '8 D', '9 D', '10 D'], mark=[3, 4]), kv=KV([['返回第 3 项', '["4-0", "5-0"]'], ['PEL', '10 → 8']], ['返回第 3 项'])),
]
A = dict(
    n=45, series='redis', tags='Redis,Stream,XAUTOCLAIM,真实验证,动画演示',
    desc=f'在本机 Redis 上验证 XAUTOCLAIM:用游标翻页认领超时未 ack 的消息(10 条 pending、COUNT 3 共 {len(rounds)} 次调用,游标回到 0-0 表示结束),认领后 idle 归零且投递次数 +1,JUSTID 不增加投递次数,PEL 中已被 XDEL 的消息会被清掉并在返回值第三项列出。',
    lead='上一篇里,认领崩溃消费者遗留的消息要靠 XCLAIM,而 XCLAIM 需要你事先知道 ID。XAUTOCLAIM 把「找出超时的消息」和「认领」合成一步,用游标翻页。这篇验证它的返回值、翻页规则、JUSTID,以及消息在流里已被删除时的处理。',
    facts=[(f'{len(rounds)} 次', '10 条 pending、COUNT 3:翻页扫完所需的调用次数'), ('0-0', '返回游标回到 0-0 = 扫描完毕'), ('JUSTID', '只转移所有权,不返回消息体,投递次数不 +1')],
    body=[
        sec('用游标翻页认领', '', term('', blk('r45', 1)), f'<p>A 读了 10 条不 ack。B 用 <code>XAUTOCLAIM s g B 500 0-0 COUNT 3</code> 从游标 <code>0-0</code> 开始认领空闲 ≥ 500 ms 的消息,每次最多 3 条。返回的三项依次是:下一个游标、被认领的消息(带内容)、已被删除的 ID 列表。把返回的游标传给下一次调用,直到游标回到 <code>0-0</code>——{len(rounds)} 次调用扫完 10 条。</p>'),
        sec('认领之后 idle 归零', '', term('', blk('r45', 2)), '<p>认领让消息的 idle 重置(1 ms)、投递次数从 1 变成 2。所以马上再来一轮返回空——所有消息都还没空闲到 500 ms。这正是多个恢复进程并行跑 XAUTOCLAIM 时不会重复认领的原因。</p>'),
        sec('JUSTID', '', term('', blk('r45', 3)), '<p>加上 <code>JUSTID</code> 之后,返回值里只有 ID,没有消息内容,并且<b>不增加投递次数</b>(XPENDING 里 1-0 到 3-0 的次数仍是 2,和上一步相同),但所有权确实转给了 C。</p>'),
        sec('消息已被删除时', '', term('', blk('r45', 4)), '<p>把 4-0、5-0 XDEL 之后,D 执行 XAUTOCLAIM:这两条从 PEL 中被移除(XPENDING 总数从 10 降到 8),并列在返回值的第三个元素里,其余 8 条正常认领。</p>'),
        sec('翻页的调用次数', '', term('', blk('r45', 5)), ''),
        sec('分步演示:游标翻页与所有权转移', '', demo('XAUTOCLAIM', [('own', 'cells', '10 条消息当前的所有者'), ('kv', 'kv', '返回值 / 观察')], steps, '本次认领的消息')),
    ],
    refs=[ENV_R, '没有验证:XAUTOCLAIM 在旧版本上的行为(只测了本机这一个版本)、PEL 很大时的耗时、COUNT 的上限'],
)
