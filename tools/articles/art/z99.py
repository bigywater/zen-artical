import re, pathlib
from lib import *
R = J('z99'); T = R['table']
def S(k): return [x for x in out('z99').split('== ')[k].splitlines()[1:] if x.strip()]
SRC = pathlib.Path(__file__).resolve().parents[2] / 'zksrc' / 'org/apache/zookeeper/server/quorum/FastLeaderElection.java'
L = SRC.read_text().splitlines()
def lines(a, b): return '\n'.join(L[a - 1:b])
def find(pat, start=0):
    for i in range(start, len(L)):
        if pat in L[i]: return i + 1
a = find('protected boolean totalOrderPredicate'); w = find('getWeight(newId) == 0', a); rt = find('return ((newEpoch > curEpoch)', a); pred = lines(a, a) + '\n        ...  // LOG.debug(...)\n' + lines(w, w + 2) + '\n        ...  // 注释:三种情形\n' + lines(rt, rt + 4) + '\n    }'
b = find('if (voteSet.hasAllQuorums())'); fin = '\n'.join(l for l in L[b - 1:b + 20] if l.strip() and not l.strip().startswith('/*') and not l.strip().startswith('*'))[:900]; fin = fin[:fin.index('return endVote;') + len('return endVote;')] + '\n                            }\n                        }'
c = find('notTimeout = Math.min(notTimeout << 1'); bo = lines(c, c)
tk = R['took']; bf = R['backoff']; ob = R['obs']
steps = [
    step("totalOrderPredicate 的规则(来自源码):先比 epoch(大者胜),epoch 相同比 zxid(大者胜),都相同比 sid(大者胜);前三个参数是「收到的票」,后三个是「当前的投票」,返回 true 表示收到的票更好、应改投。对真实类用反射穷举 64 种组合:与上面规则 0 组不一致。", t=tl(S(1)), done=[0], kv=KV([['比较顺序', 'epoch → zxid → sid'], ['穷举 64 组', '与源码规则一致']], ['比较顺序'])),
    step("几个具体例子:同 epoch 时 zxid 小的票挑战 zxid 大的 → false;sid 更大但 zxid 更小的票 → false(所以数据落后的 sid=3 当不上);epoch 更大的票即使 zxid 小得多也胜 → true;完全相同的两张票 → false。这些与第 35 篇里「落后节点改投」的日志一致。", t=tl(S(1)), mark=[len(S(1)) - 1], kv=KV([['数据落后但 sid 大', '当不上'], ['epoch 大', '压过 zxid']], ['epoch 大'])),
    step("观察者没有选举权:它的初始选票是 (id, zxid, epoch) 全为 Long.MIN_VALUE。用同一个反射方法验证:观察者的票去挑战任何参与者的票 → false,参与者的票挑战观察者 → true。对应日志里观察者的「New election. My id = 4, proposed zxid=0x8000000000000000」,参与者是 0x0。", t=tl(S(4)), done=[0], kv=KV([['观察者的票', '全为 MIN_VALUE'], ['能否赢参与者', '不能']], ['观察者的票'])),
    step(f"finalizeWait = 200:凑够过半票之后,源码不立刻宣布,而是在 recvqueue 上最多再等 200 ms 看有没有更好的票,没有才结束。验证:3 节点 5 次 kill -9 leader,新 leader 日志里「LEADER ELECTION TOOK」是 {', '.join(map(str, tk))} ms,最小 {min(tk)} ms ≥ 200 —— 一轮选举的耗时下限就是这 200 ms 加上收票与通信的开销。", t=tl(S(2)), b=bars([[f'第 {i+1} 次', t, f'{t} ms'] for i, t in enumerate(tk)], 250, done=list(range(len(tk)))), kv=KV([['选举耗时', f'{min(tk)}–{max(tk)} ms'], ['finalizeWait', '200 ms']], ['选举耗时'])),
    step(f"选票没凑够时的退避:源码每次超时把 notTimeout 翻倍(上限 maxNotificationInterval,默认 60000 ms)。3 节点集群只起 1 个,14 秒内日志里的 Notification time out 依次是 {', '.join(bf)} ms(日志打印的是翻倍后的值,第一次等待是 200 ms)。", t=tl(S(3)), b=bars([[f'第 {i+1} 次', int(x), f'{x} ms'] for i, x in enumerate(bf)], 13000, done=list(range(len(bf)))), kv=KV([['超时序列', ' → '.join(bf[:4]) + ' …'], ['上限', '60000 ms']], ['超时序列'])),
]
A = dict(
    n=99, series='zookeeper', tags='ZooKeeper,源码,选举,FastLeaderElection,真实验证,动画演示',
    desc=f'读 ZooKeeper 3.9.6 的 FastLeaderElection 源码并逐条验证:totalOrderPredicate 用反射穷举 64 组与源码规则一致;观察者的选票全为 MIN_VALUE;finalizeWait=200 ms 使选举耗时 {min(tk)}–{max(tk)} ms;通知超时按 200→400→800 ms 指数退避。',
    lead='看源码最怕的是「读懂了」只是你以为。这篇读 FastLeaderElection 里最关键的三段 —— 选票比较、凑够票后的等待、超时退避 —— 每一条结论都对真实的 3.9.6 类或日志做一次验证,而不是只复述注释。',
    facts=[('64 / 64', '反射穷举 totalOrderPredicate,与读源码得到的规则一致'), (f'≥ 200 ms', f'finalizeWait 使一轮选举耗时下限(实测 {min(tk)}–{max(tk)} ms)'), ('MIN_VALUE', '观察者的初始选票,永远赢不了参与者')],
    body=[
        sec('选票比较', '', src('org/apache/zookeeper/server/quorum/FastLeaderElection.java(3.9.6,节选,省略了 debug 日志与注释)', pred), '<p>注意源码里的参数名:前三个是<em>新收到的票</em>(newId、newZxid、newEpoch),后三个是当前投票;函数头的 debug 日志里把名字写反了,别被误导。开头还有一个 <code>getWeight(newId) == 0</code> 的检查 —— 在普通的多数派配置(QuorumMaj)里权重恒为 1,所以它对观察者不起作用;观察者是靠另一个机制(下面)挡住的。</p>', term('', blk('z99', 1))),
        sec('观察者为什么永远不会赢', '', term('', blk('z99', 4)), '<p>源码里 <code>getInitId()</code> 对不在投票成员里的节点返回 <code>Long.MIN_VALUE</code>,<code>getInitLastLoggedZxid()</code> 对非参与者同样返回 <code>Long.MIN_VALUE</code>,所以观察者的票在上面的比较里永远输。</p>'),
        sec('凑够票之后还要再等 200 ms', '', src('同一文件,lookForLeader 中收齐过半票之后的段落', fin), term('', blk('z99', 2)), '<p>这就是<a href="zookeeper-leader-reelection.html">选举期间写不可用约 400 多毫秒</a>的一部分来源:至少 200 ms 的 finalizeWait,加上失败检测与通信。</p>'),
        sec('超时退避', '', src('同一文件', bo), term('', blk('z99', 3)), '<p>退避是在没有收到足够通知时(比如对端都没起来)才会发生。</p>'),
        sec('分步演示', '', demo('读源码 + 验证', [('t', 'term', '验证输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。源码来自 Maven Central 的 zookeeper-3.9.6-sources.jar;反射验证用 sun.misc.Unsafe 分配 FastLeaderElection 实例后设置 self 字段并调用 protected 方法;kill -9 与单节点启动用 Ensemble 工具', '没有验证:lookForLeader 对 FOLLOWING / LEADING 通知的处理(receivedFollowingNotification 等)、checkLeader 的两个分支、QuorumOracleMaj 两节点场景、maxNotificationInterval 的 60 秒上限(日志里没有跑到)'],
)
