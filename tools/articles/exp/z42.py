import sys, os, time, json, re, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z42'); R = {}
def short(l): return re.sub(r'\s+', ' ', re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l))[:140]
def scenario_lag(label, nwrites, jvm=(), base=7300):
    e = Ensemble('z42l', 3, base=base); [setattr(nd, 'jvm', list(jvm)) for nd in e.nodes]; e.start()
    ld = e.leader(); f = e.followers()[0]; z = client(f'127.0.0.1:{ld.cport}')
    z.create('/seed', b'x'); f.stop(); time.sleep(0.5)
    rs = [z.create_async(f'/g{i}', b'x' * 20) for i in range(nwrites)]; [r.get() for r in rs]
    nb = len(ld.log().splitlines()); t0 = time.perf_counter(); f.start(wipe=False, wait=False)
    while time.perf_counter() - t0 < 60:
        if f.mode() == 'follower' and f.srvr().get('zxid') == ld.srvr().get('zxid'): break
        time.sleep(0.05)
    dt = (time.perf_counter() - t0) * 1000
    L = [short(l) for l in ld.log().splitlines()[nb:] if 'Synchronizing with Learner' in l or 'Sending DIFF' in l or 'Sending snapshot' in l or 'Cannot send TRUNC' in l or 'Unhandled scenario' in l or 'Sending TRUNC' in l]
    F = [short(l) for l in f.log().splitlines() if 'synchronization - ' in l][-1:]
    print(f'  [{label}] 落后 {nwrites} 个事务的 follower 重启:追上用时 {dt:.0f} ms'); [print('    leader:', l) for l in L]; [print('    follower:', l) for l in F]
    z.stop(); e.stop(); return dict(n=nwrites, ms=dt, leader=L, follower=F)
print('== 一:follower 只落后一点点 → DIFF(leader 把缺的事务逐条发过去)')
R['diff'] = scenario_lag('DIFF', 10)
print()
print('== 二:follower 的数据被清空(换了一块新盘)后重新加入 → SNAP(leader 发整份快照)')
e = Ensemble('z42s', 3, base=7310).start(); ld = e.leader(); f = e.followers()[0]; z = client(f'127.0.0.1:{ld.cport}')
rs = [z.create_async(f'/g{i}', b'x' * 20) for i in range(1000)]; [r.get() for r in rs]
f.stop(); import shutil; shutil.rmtree(f.dir / 'data' / 'version-2'); nb = len(ld.log().splitlines()); t0 = time.perf_counter(); f.start(wipe=False, wait=False)
while time.perf_counter() - t0 < 60:
    if f.mode() == 'follower' and f.srvr().get('zxid') == ld.srvr().get('zxid'): break
    time.sleep(0.05)
dt = (time.perf_counter() - t0) * 1000
L = [short(l) for l in ld.log().splitlines()[nb:] if 'Synchronizing with Learner' in l or 'Sending DIFF' in l or 'Sending snapshot' in l or 'Cannot send TRUNC' in l or 'Unhandled scenario' in l or 'Sending TRUNC' in l]
F = [short(l) for l in f.log().splitlines() if 'synchronization - ' in l][-1:]
print(f'  清空数据目录后重启,追上用时 {dt:.0f} ms,znode 数', kv(f.four('mntr')).get('zk_znode_count')); [print('    leader:', l) for l in L]; [print('    follower:', l) for l in F]
R['snap'] = dict(ms=dt, leader=L, follower=F); z.stop(); e.stop()
print()
print('== 三:旧 leader 被网络隔离后收下一条没有多数派确认的写,重新加入时怎么同步(用 TCP 代理切断节点间通信)')
e = NetEnsemble('z42t', 3, base=7320, conf={'tickTime': 500, 'syncLimit': 2, 'initLimit': 4}).start(); ld = e.leader(); others = [n.myid for n in e.nodes if n is not ld]
z = client(f'127.0.0.1:{ld.cport}', timeout=30); z.create('/ok', b'1'); time.sleep(0.3)
e.partition([ld.myid], others)
res = z.create_async('/extra', b'never-committed'); time.sleep(0.5)
print('  旧 leader 被隔离后,发给它的 create /extra:ready =', res.ready(), '(它收下并写进了自己的事务日志,但凑不齐多数派)')
time.sleep(4)
print('  隔离 4 秒后各节点:', {n.name: n.mode() or '不服务' for n in e.nodes})
nl = next(n for n in e.nodes if n is not ld and n.mode() == 'leader'); z2 = client(','.join(f'127.0.0.1:{n.cport}' for n in e.nodes if n is not ld))
print('  多数派一侧的新 leader:', nl.name, '| /extra 在多数派一侧存在吗:', z2.exists('/extra') is not None); z2.create('/after', b'2')
nb = len(nl.log().splitlines()); e.heal(); time.sleep(8)
print('  网络恢复后各节点:', {n.name: n.mode() for n in e.nodes})
L = [short(l) for l in nl.log().splitlines()[nb:] if 'Synchronizing with Learner' in l or 'Sending DIFF' in l or 'Sending snapshot' in l or 'Cannot send TRUNC' in l or 'Unhandled scenario' in l or 'Sending TRUNC' in l]
F = [short(l) for l in ld.log().splitlines() if 'synchronization - ' in l][-1:]
for l in L: print('    新 leader:', l)
for l in F: print('    旧 leader(现 follower):', l)
z3 = client(f'127.0.0.1:{ld.cport}'); print('  旧 leader 上读 /extra:', z3.exists('/extra'), '| 读 /after:', z3.get('/after')[0])
try: res.get(timeout=3); r = '成功'
except Exception as ex: r = type(ex).__name__
print('  当初那个 create /extra 调用的结果:', r); R['trunc'] = dict(leader=L, follower=F, extra_gone=z3.exists('/extra') is None, client=r)
z.stop(); z2.stop(); z3.stop(); e.stop(); save('z42', R)
