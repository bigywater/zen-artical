import re
from lib import *
R = J('z94'); T = R['stdout']; kg = R['kill']['gaps']
def S(k): return [x for x in out('z94').split('== ')[k].splitlines()[1:] if x.strip()]
cg = [int(x) for x in re.findall(r'→ 新 leader C\d,(\d+) ms', T)]
steps = [
    step(f"5 个 LeaderLatch 候选:启动后 C0 是 leader,hasLeadership 为 true 的候选恰好 1 个;getParticipants 列出所有候选并标出 leader。依次 close() 当前 leader,新 leader 在 {min(cg)}–{max(cg)} ms 内出现(按序号接任)。主动 close 是「干净让位」,几乎没有空窗。", t=tl(S(1)), done=[0], b=bars([[f'第 {i+1} 次 close', g, f'{g} ms'] for i, g in enumerate(cg)], 15, done=[0, 1, 2, 3]), kv=KV([['close() 切换', f'{min(cg)}–{max(cg)} ms'], ['同时 leader 数', '1']], ['close() 切换'])),
    step("服务端被冻结 5 s(会话超时 6 s):LeaderLatch 在 4.1 s 收到 SUSPENDED 的同时就回调 notLeader(放弃领导权,即使会话其实还没过期);解冻后 RECONNECTED,5.9 s 重新 isLeader,最终 hasLeadership = true。这是 Curator 的保守默认:不确定自己是不是还持有时,先停手。", t=tl(S(2)), mark=[3], kv=KV([['SUSPENDED', '立即 notLeader'], ['RECONNECTED', '重新 isLeader']], ['SUSPENDED'])),
    step("LeaderSelector(autoRequeue):takeLeadership 持有 600 ms 后返回,3 个候选 12 秒内当 leader 的次数是 7 / 7 / 6,轮换顺序严格是 S0 → S1 → S2 → S0 …。适合「轮流干活」而不是「长期当 leader」的场景。", t=tl(S(3)), done=[0], kv=KV([['次数', 'S0=7 S1=7 S2=6'], ['顺序', '严格轮转']], ['次数'])),
    step(f"5 个独立 JVM 进程竞选,对当前 leader 的进程 kill -9 三次:从它最后一次心跳到新 leader 开始是 {', '.join(f'{g:.2f}' for g in kg)} s(会话超时 3 s);期间没有同时出现两个 leader 发心跳。进程崩溃的空窗 ≈ 会话超时,不是毫秒级。", t=tl(S(4)), mark=[0], b=bars([[f'第 {i+1} 次 kill -9', g, f'{g:.2f} s'] for i, g in enumerate(kg)], 4, done=[0, 1, 2]), kv=KV([['kill -9 空窗', f'{min(kg):.1f}–{max(kg):.1f} s'], ['两个 leader', '没有']], ['kill -9 空窗'])),
]
A = dict(
    n=94, series='zookeeper', tags='ZooKeeper,Curator,Leader选举,LeaderLatch,真实验证,动画演示',
    desc=f'Curator 5.7.1 的 LeaderLatch 与 LeaderSelector 实测:close() 切换 {min(cg)}–{max(cg)} ms;服务端冻结时 SUSPENDED 立刻放弃领导权、RECONNECTED 后重新当选;LeaderSelector 严格轮转;5 个 JVM 进程 kill -9 leader 空窗 {min(kg):.1f}–{max(kg):.1f} s、无双 leader。',
    lead='Curator 有两套选主:LeaderLatch(当选后一直当,直到你关闭)和 LeaderSelector(按次轮流)。这篇都跑一遍:主动让位多快、服务端不可达时 leader 的反应、轮转是否公平、进程崩溃后多久换主。',
    facts=[(f'{min(cg)}–{max(cg)} ms', 'close() 当前 leader 后新 leader 出现'), ('SUSPENDED', '服务端冻结时 leader 在此刻就放弃领导权(会话超时前)'), (f'{min(kg):.1f}–{max(kg):.1f} s', 'kill -9 leader 进程后新 leader 开始工作的空窗')],
    body=[
        sec('LeaderLatch:干净让位', '', term('', blk('z94', 1)), '<p>与 <a href="zookeeper-leader-election.html">kazoo 的 Election</a> 同源(临时顺序节点,序号最小者当选);Curator 的 LeaderLatch 提供 <code>hasLeadership()</code> 和监听回调。</p>'),
        sec('服务端不可达时 leader 怎么办', '', term('', blk('z94', 2)), '<p>默认的 ConnectionStateErrorPolicy 把 SUSPENDED 也当成「可能丢了领导权」,所以 leader 在 SUSPENDED 时就停手。这避免了「leader 已不是 leader 还在干活」的窗口,代价是网络抖动会让 leader 短暂中断(这里恢复后又当选)。</p>'),
        sec('LeaderSelector:轮流', '', term('', blk('z94', 3))),
        sec('进程崩溃', '', term('', blk('z94', 4)), '<p>和<a href="zookeeper-session-expire.html">会话超时</a>的关系:临时节点要到会话过期才删除,所以空窗至少接近会话超时。要更快的切换,只能缩短会话超时(代价是更容易误判)。</p>'),
        sec('分步演示', '', demo('Curator 选主', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Curator 5.7.1 + OpenJDK 17;第 1–3 项会话超时 6 s,第 4 项 3 s;冻结服务端用 kill -STOP / -CONT', '没有验证:ConnectionStateErrorPolicy 的其它取值(只对 LOST 敏感)下的行为、LeaderSelector 的 takeLeadership 被中断时的细节、真实网络分区、选主节点数很多(上百)时的惊群'],
)
