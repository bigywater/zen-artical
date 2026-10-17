import sys, os, time, json, re, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z39'); R = {}
e = Ensemble('z39', 3, base=7300).start(); z = client(e.hosts()); [z.create(f'/n{i}', b'x') for i in range(30)]; z.stop()
def tod(): n = datetime.datetime.now(); return n.hour * 3600 + n.minute * 60 + n.second + n.microsecond / 1e6
ld = e.leader(); nb = {n.name: len(n.log().splitlines()) for n in e.nodes}
print(f'== 一:杀掉 leader({ld.name}),看新一任 leader 与 follower 的日志,按 ZAB 的三个阶段(发现 / 同步 / 广播)归类')
tk = tod(); ld.kill(); time.sleep(5)
nl = e.leader(); fo = e.followers()[0]
def phases(nd, pats):
    out = []
    for l in nd.log().splitlines()[nb[nd.name]:]:
        if any(p in l for p in pats):
            out.append(((tsec(l) - tk) * 1000, re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:100]))
    return out
PL = ['Peer state changed', 'LEADER ELECTION TOOK', 'Synchronizing with', 'Sending DIFF', 'Sending SNAP', 'Sending TRUNC', 'Sending NEWLEADER', 'Received NEWLEADER-ACK', 'Have quorum', 'Sending UPTODATE']
PF = ['Peer state changed', 'LEADER ELECTION TOOK', 'Learner received NEWLEADER', 'Set the current epoch', 'Sent NEWLEADER ack', 'Learner received UPTODATE']
print(f'  新 leader {nl.name} 的日志(相对杀 leader 的毫秒):'); L = phases(nl, PL)
for t, m in L: print(f'    +{t:>5.0f} ms  {m}')
print(f'  follower {fo.name} 的日志:'); F = phases(fo, PF)
for t, m in F: print(f'    +{t:>5.0f} ms  {m}')
R['leader'] = [(round(t), m) for t, m in L]; R['follower'] = [(round(t), m) for t, m in F]
print()
print('== 二:每个阶段花了多久(leader 视角)')
def at(L, key): return next((t for t, m in L if key in m), None)
d0, s0, b0, e0 = at(L, 'leading - discovery'), at(L, 'leading - synchronization'), at(L, 'leading - broadcast'), at(L, 'LEADER ELECTION TOOK')
print(f'  选出 leader(进入 discovery)+{d0:.0f} ms → 进入 synchronization +{s0:.0f} ms(discovery 用 {s0 - d0:.0f} ms)→ 进入 broadcast +{b0:.0f} ms(synchronization 用 {b0 - s0:.0f} ms)'); R['phase_ms'] = dict(discovery=s0 - d0, sync=b0 - s0)
print()
print('== 三:日志里没有出现的消息(没有验证):FOLLOWERINFO / LEADERINFO / ACKEPOCH 这些发现阶段的消息在 INFO 日志里没有打印')
print('  在 INFO 日志里能搜到的协议消息关键字:', sorted({k for k in ('NEWLEADER', 'UPTODATE', 'DIFF', 'SNAP', 'TRUNC', 'FOLLOWERINFO', 'LEADERINFO', 'ACKEPOCH') if any(k in l for l in nl.log().splitlines() + fo.log().splitlines())}))
R['found'] = sorted({k for k in ('NEWLEADER', 'UPTODATE', 'DIFF', 'SNAP', 'TRUNC', 'FOLLOWERINFO', 'LEADERINFO', 'ACKEPOCH') if any(k in l for l in nl.log().splitlines() + fo.log().splitlines())})
e.stop(); save('z39', R)
