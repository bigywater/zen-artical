import sys, os, time, json, re, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z32'); R = {}
e = Ensemble('z32', 3, base=7300).start(); ld = e.leader()
def tod(): n = datetime.datetime.now(); return n.hour * 3600 + n.minute * 60 + n.second + n.microsecond / 1e6
fo = e.followers(); watch = fo[0]
print(f'== 一:一个 follower({watch.name})从启动到稳定的状态变化(日志里的 Peer state changed,相对该节点第一条日志的毫秒)')
lg = log_lines(watch, ['Peer state changed', 'LEADER ELECTION TOOK']); t0 = tsec(lg[0])
for l in lg[:9]: print(f'  +{(tsec(l) - t0) * 1000:>5.0f} ms  {re.sub(r"^\S+ ", "", l)[:90]}')
R['startup'] = [re.sub(r'^\S+ ', '', l)[:90] for l in lg[:9]]
print()
print(f'== 二:杀掉 leader({ld.name}),存活节点的状态变化(相对杀的时刻)')
n_before = {n.name: len(log_lines(n, ['Peer state changed'])) for n in e.nodes}
tk = tod(); ld.kill(); time.sleep(6)
R['kill'] = {}
for nd in e.nodes:
    if nd is ld: continue
    lg = log_lines(nd, ['Peer state changed', 'LEADER ELECTION TOOK'])[n_before[nd.name]:]
    print(f'  {nd.name}(现在 {nd.mode()}):'); R['kill'][nd.name] = []
    for l in lg: s = f'+{(tsec(l) - tk) * 1000:>5.0f} ms  {re.sub(r"^\S+ ", "", l)[:80]}'; print('    ' + s); R['kill'][nd.name].append(s)
print()
print('== 三:四个状态的含义对照(srvr 的 Mode 与日志里的 QuorumPeer 状态)')
print('  LOOKING → 还没有 leader,在选举(此时 srvr 返回「不在服务」);FOLLOWING / LEADING / OBSERVING → 对应 Mode follower / leader / observer')
looking = [n for n in e.nodes if n.alive()]
ld.start(wipe=False, wait=False); time.sleep(0.3)
rs = four(ld.cport, 'srvr'); print('  重新启动原 leader 0.3 秒后看它的 srvr:', '「not currently serving requests」(正在 LOOKING / 同步)' if 'not currently serving' in rs else ('Mode: ' + kv(rs).get('mode', '?')) if rs.strip() else '(端口还没有响应)')
time.sleep(4); print('  几秒后:', ld.mode()); R['restart_mode'] = ld.mode()
e.stop(); save('z32', R)
