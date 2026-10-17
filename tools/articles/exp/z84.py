import sys, os, time, json, re, subprocess, signal, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z84'); R = {}
n = Node('z84', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
lf = ZDATA / 'z84' / 'tpc.log'; lf.parent.mkdir(exist_ok=True); lf.write_text(''); P = str(HERE / 'procs' / 'tpc.py')
def ev(): return [(float(l.split(' ', 2)[0]), l.split(' ', 2)[1], l.split(' ', 2)[2]) for l in lf.read_text().splitlines() if l.strip()]
def coord(txid, parts, mode='normal'): return subprocess.Popen([sys.executable, P, 'coord', '7300', 'COORD', str(lf), txid, ','.join(parts), mode])
tx = [f't{i:02d}' for i in range(20)] + ['tno', 'tdie', 'tcoord']
ps = {nm: subprocess.Popen([sys.executable, P, 'participant', '7300', nm, str(lf)] + tx) for nm in ('P1', 'P2', 'P3')}
z.ensure_path('/members')
while len(z.get_children('/members')) < 3: time.sleep(0.1)
PARTS = ['P1', 'P2', 'P3']
print('== 一:三个参与者,协调者发起 20 个事务,全部投 yes:从 prepare 发出到最后一个参与者应用 commit 的时间')
lat = []
for t in tx[:20]:
    coord(t, PARTS).wait(); time.sleep(0.15)
    e = [x for x in ev() if t in x[2]]; t0 = [x[0] for x in e if x[2].startswith('PREPARE_SENT')][0]; ap = [x[0] for x in e if x[2].startswith('APPLIED') and x[1] != 'COORD']
    lat.append((max(ap) - t0) * 1000 if len(ap) == 3 else None)
ok = [x for x in lat if x]; ok_s = sorted(ok)
print(f'  20 个事务中应用完成的:{len(ok)};耗时(ms)中位 {statistics.median(ok):.0f},最小 {ok_s[0]:.0f},最大 {ok_s[-1]:.0f}')
print('  一个事务在 ZooKeeper 里的节点:', sorted(z.get_children('/tx/t00')), '| votes:', sorted(z.get_children('/tx/t00/votes')), '| decision =', z.get('/tx/t00/decision')[0].decode())
R['happy'] = dict(n=len(ok), med=statistics.median(ok), mn=ok_s[0], mx=ok_s[-1])
print()
print('== 二:P2 投 no:协调者写 abort,所有参与者看到的是 abort')
coord('tno', PARTS).wait(); time.sleep(0.3)
e = [x for x in ev() if 'tno' in x[2] or x[2].startswith('VOTES')][-6:]
for x in ev():
    if 'tno' in x[2]: print(f'  {x[1]:<6} {x[2]}')
dec = z.get('/tx/tno/decision')[0].decode(); applied = sorted(x[1] for x in ev() if x[2] == 'APPLIED tno abort')
print(f'  decision = {dec};应用了 abort 的参与者:{applied}')
R['no'] = dict(decision=dec, applied=applied)
print()
print('== 三:P3 在收到 prepare 之后、投票之前被 kill -9:协调者等不到它的票,3 秒后超时写 abort')
t0 = time.time(); coord('tdie', PARTS).wait(); el = time.time() - t0
print(f'  协调者用时 {el:.1f} s(投票超时 3 s);decision = {z.get("/tx/tdie/decision")[0].decode()};votes 目录里有 {sorted(z.get_children("/tx/tdie/votes"))}')
time.sleep(0.5); print('  P1、P2 应用了:', sorted((x[1], x[2]) for x in ev() if x[2].startswith('APPLIED tdie')))
print('  /members 现在:', sorted(z.get_children('/members')), '(协调者已等了 3 秒,P3 的会话已过期、临时节点已消失)')
R['die'] = dict(wait=el, decision=z.get('/tx/tdie/decision')[0].decode())
print()
print('== 四:协调者收齐票之后、写 decision 之前被 kill -9(经典的 2PC 阻塞):参与者都投了 yes,在等决定')
c = coord('tcoord', ['P1', 'P2'], 'stall')
while not any(x[2] == 'STALLED' for x in ev()): time.sleep(0.05)
tk = time.time(); c.kill(); time.sleep(5)
ap = [x for x in ev() if x[2].startswith('APPLIED tcoord')]
print(f'  协调者被杀后 5 秒:/tx/tcoord/decision 存在 = {z.exists("/tx/tcoord/decision") is not None};已应用的参与者数 = {len(ap)};votes = { {k: z.get("/tx/tcoord/votes/" + k)[0].decode() for k in z.get_children("/tx/tcoord/votes")} }')
tr = time.time(); subprocess.Popen([sys.executable, P, 'recover', '7300', 'RECOVER', str(lf), 'tcoord']).wait(); time.sleep(0.5)
for x in ev():
    if x[0] >= tr - 0.01 and ('tcoord' in x[2] or x[1] == 'RECOVER'): print(f'  +{x[0]-tr:5.2f}s  {x[1]:<8} {x[2]}')
ap = [x for x in ev() if x[2].startswith('APPLIED tcoord')]
print(f'  恢复者读出所有票为 yes → 写 commit;参与者应用数 = {len(ap)}')
R['stall'] = dict(blocked_applied=0, recovered_applied=len(ap), decision=z.get('/tx/tcoord/decision')[0].decode())
for p in ps.values(): p.kill()
z.stop(); n.stop(); save('z84', R); os._exit(0)
