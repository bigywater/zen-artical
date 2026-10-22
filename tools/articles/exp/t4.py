import sys, os, itertools, heapq; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import tee
tee('t4')
N = 3
PARTS = [(0, 1, 2), ]   # 占位,下面生成所有集合划分
def set_partitions(items):
    items = list(items)
    if not items: yield []; return
    first, rest = items[0], items[1:]
    for p in set_partitions(rest):
        yield [[first]] + p
        for i in range(len(p)): yield p[:i] + [[first] + p[i]] + p[i + 1:]
PARTS = [sorted([sorted(g) for g in p]) for p in set_partitions(range(N))]
def pname(p): return '|'.join(''.join(f'P{i + 1}' for i in g) for g in p)

# ---------------------------------------------------------------- 协议模型
# 协调者按固定顺序给参与者发消息(全都投 YES 的情形);崩溃点 j = 协调者发出了前 j 条消息之后挂掉(永远不回来)。
SEQ = {'2PC': [('PREPARE', i) for i in range(N)] + [('COMMIT', i) for i in range(N)],
       '3PC': [('CANCOMMIT', i) for i in range(N)] + [('PRECOMMIT', i) for i in range(N)] + [('DOCOMMIT', i) for i in range(N)]}
NEXT = {'2PC': {'PREPARE': 'READY', 'COMMIT': 'COMMIT'}, '3PC': {'CANCOMMIT': 'READY', 'PRECOMMIT': 'PRECOMMIT', 'DOCOMMIT': 'COMMIT'}}
def states_after(proto, j):
    st = ['INIT'] * N
    for m, i in SEQ[proto][:j]: st[i] = NEXT[proto][m]
    return st
def terminate(proto, group_states):
    """一个互相连得通的参与者小组(协调者已经不在)按各自的状态做终止协议。返回 (决定, 依据)。"""
    s = set(group_states)
    if 'COMMIT' in s: return 'COMMIT', '组里有人已经 COMMIT'
    if 'ABORT' in s: return 'ABORT', '组里有人已经 ABORT'
    if proto == '2PC':
        if 'INIT' in s: return 'ABORT', '组里有人还没投过票(INIT),它可以单方面 ABORT'
        return 'BLOCKED', '全部是 READY:已经投了 YES,不知道协调者的决定,既不能提交也不能回滚'
    if 'PRECOMMIT' in s: return 'COMMIT', '组里有人收到了 PRECOMMIT:说明所有人都投过 YES,可以 COMMIT'
    return 'ABORT', '没有人收到 PRECOMMIT(全是 READY / INIT):不可能有人已经 COMMIT,可以 ABORT'
def outcome(proto, j, partition):
    st = states_after(proto, j); res = []
    for g in partition: res.append((g, terminate(proto, [st[i] for i in g])))
    dec = {d for _, (d, _) in res}
    if 'COMMIT' in dec and 'ABORT' in dec: return 'INCONSISTENT', res
    if 'BLOCKED' in dec: return 'BLOCKED', res
    return 'OK', res
def label(proto, j):
    seq = SEQ[proto]
    return '协调者已发完全部消息' if j == len(seq) else ('协调者什么都没发' if j == 0 else f'已发 {seq[j - 1][0]} 给 P{seq[j - 1][1] + 1}')

# ---------------------------------------------------------------- 一
print('== 一:没有故障时的代价(离散事件模拟:每条消息单程 5 ms,协调者和参与者的处理时间不计;每次写日志都算一次强制落盘)')
def simulate(proto, d=5.0):
    t = 0.0; ev = []; msgs = 0; forced = 0; done_at = {}; log = []
    def send(at, kind, src, dst): 
        nonlocal msgs; msgs += 1; heapq.heappush(ev, (at + d, msgs, kind, src, dst))
    # 协调者:强制写 START(2PC 不写也行,这里按教科书 2PC 的写法只在决定时写)
    phases = ['PREPARE', 'COMMIT'] if proto == '2PC' else ['CANCOMMIT', 'PRECOMMIT', 'DOCOMMIT']
    for i in range(N): send(0.0, phases[0], 'C', i)
    votes = {}; acks = {k: 0 for k in phases}
    while ev:
        t, _, kind, src, dst = heapq.heappop(ev)
        if dst != 'C':                                    # 参与者收到消息
            if kind in ('PREPARE', 'CANCOMMIT'): forced += 1; send(t, 'VOTE-YES', dst, 'C')      # 投 YES 前先落盘(prepare 记录)
            elif kind == 'PRECOMMIT': forced += 1; send(t, 'ACK-PRECOMMIT', dst, 'C')
            elif kind in ('COMMIT', 'DOCOMMIT'): forced += 1; done_at[dst] = t; send(t, 'ACK-COMMIT', dst, 'C')
        else:                                             # 协调者收到
            if kind == 'VOTE-YES':
                votes[src] = t
                if len(votes) == N:
                    if proto == '2PC': forced += 1; log.append(f'{t:5.1f} ms  协调者收齐 {N} 票 YES,强制写 COMMIT 决定,发 COMMIT'); [send(t, 'COMMIT', 'C', i) for i in range(N)]
                    else: log.append(f'{t:5.1f} ms  协调者收齐 {N} 票 YES,发 PRECOMMIT'); [send(t, 'PRECOMMIT', 'C', i) for i in range(N)]
            elif kind == 'ACK-PRECOMMIT':
                acks['PRECOMMIT'] += 1
                if acks['PRECOMMIT'] == N: forced += 1; log.append(f'{t:5.1f} ms  协调者收齐 {N} 个 PRECOMMIT 的确认,强制写 COMMIT 决定,发 DOCOMMIT'); [send(t, 'DOCOMMIT', 'C', i) for i in range(N)]
    return msgs, forced, max(done_at.values()), log
R = {}
for proto in ('2PC', '3PC'):
    R[proto] = simulate(proto)
    m, f, t, lg = R[proto]
    print(f'  {proto}:{m} 条消息(含确认),{f} 次强制落盘,从协调者开始到最后一个参与者提交 {t:.0f} ms = {t / 5:.0f} 个单程延迟')
    for l in lg: print('     ', l)
print(f'  3PC 比 2PC 多 {R["3PC"][0] - R["2PC"][0]} 条消息、多 {R["3PC"][1] - R["2PC"][1]} 次落盘、多 {R["3PC"][2] - R["2PC"][2]:.0f} ms(多一个往返)')

# ---------------------------------------------------------------- 二
print('== 二:协调者在每个位置崩溃、没有网络分区,参与者小组 {P1,P2,P3} 靠终止协议自己收尾')
for proto in ('2PC', '3PC'):
    print(f'  --- {proto}(协调者共发 {len(SEQ[proto])} 条消息,崩溃点 0 到 {len(SEQ[proto])})')
    for j in range(len(SEQ[proto]) + 1):
        st = states_after(proto, j); o, res = outcome(proto, j, [[0, 1, 2]])
        print(f'    崩溃点 {j:2d}({label(proto, j)}):状态 {" / ".join(st)} -> {res[0][1][0]:7s} {res[0][1][1]}')
blk = {p: sum(outcome(p, j, [[0, 1, 2]])[0] == 'BLOCKED' for j in range(len(SEQ[p]) + 1)) for p in SEQ}
print(f'  没有分区时:2PC 有 {blk["2PC"]} / {len(SEQ["2PC"]) + 1} 个崩溃点会让参与者阻塞;3PC 有 {blk["3PC"]} / {len(SEQ["3PC"]) + 1} 个')

# ---------------------------------------------------------------- 三
print('== 三:同样的崩溃点,再叠加一次网络分区(协调者挂掉的同时,参与者被切成互相连不通的小组,每个小组各自跑终止协议)')
tot = {}
for proto in ('2PC', '3PC'):
    c = {'OK': 0, 'BLOCKED': 0, 'INCONSISTENT': 0}
    for j in range(len(SEQ[proto]) + 1):
        for p in PARTS: c[outcome(proto, j, p)[0]] += 1
    tot[proto] = c
    print(f'  {proto}:{sum(c.values())} 个场景({len(SEQ[proto]) + 1} 个崩溃点 × {len(PARTS)} 种分区 {[pname(p) for p in PARTS]}):  正常收尾 {c["OK"]}  阻塞 {c["BLOCKED"]}  结果不一致 {c["INCONSISTENT"]}')
print('  3PC 里结果不一致的场景(崩溃点 / 分区 / 各小组的决定):')
for j in range(len(SEQ['3PC']) + 1):
    for p in PARTS:
        o, res = outcome('3PC', j, p)
        if o == 'INCONSISTENT': print(f'    崩溃点 {j:2d}({label("3PC", j)})  分区 {pname(p):9s}  ' + ';  '.join(f'{"".join("P" + str(i + 1) for i in g)} → {d}' for g, (d, _) in res))
print('  2PC 在分区下从不出现不一致:它宁可阻塞(READY 的小组什么也不决定)')

# ---------------------------------------------------------------- 四
print('== 四:一个具体的 3PC 不一致过程:协调者只把 PRECOMMIT 发给了 P1 就挂了,同时 P1 和 P2、P3 被分在两边')
j = 4; st = states_after('3PC', j)
print(f'  协调者发出的消息:{", ".join(f"{m}→P{i + 1}" for m, i in SEQ["3PC"][:j])};之后挂掉')
print('  此刻状态:' + ', '.join(f'P{i + 1}={s}' for i, s in enumerate(st)))
for g in ([0], [1, 2]):
    d, why = terminate('3PC', [st[i] for i in g]); print(f'  小组 {"".join("P" + str(i + 1) for i in g)}:超时 → {d}({why})')
print('  P1 提交了,P2 和 P3 回滚了:分区恢复之后这笔事务在 P1 和 P2/P3 上的结局永远对不上')

# ---------------------------------------------------------------- 五
print('== 五:同样的场景换成 2PC:协调者只把 COMMIT 发给了 P1 就挂了,P1 和 P2、P3 被分在两边')
j = 4; st = states_after('2PC', j)
print(f'  协调者发出的消息:{", ".join(f"{m}→P{i + 1}" for m, i in SEQ["2PC"][:j])};之后挂掉')
print('  此刻状态:' + ', '.join(f'P{i + 1}={s}' for i, s in enumerate(st)))
for g in ([0], [1, 2]):
    d, why = terminate('2PC', [st[i] for i in g]); print(f'  小组 {"".join("P" + str(i + 1) for i in g)}:{d}({why})')
print('  P1 已经提交,P2 和 P3 不敢动,等分区恢复后向 P1 打听到 COMMIT 再提交:代价是这段时间它们的锁一直握着,但结局是对的')
