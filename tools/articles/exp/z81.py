import sys, os, time, json, re, subprocess, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z81'); R = {}
n = Node('z81', 7300, conf={'tickTime': 1000, 'maxClientCnxns': 200}).start(); z = client('127.0.0.1:7300')
for p in ('/tasks', '/assign', '/workers', '/done'): z.ensure_path(p)
lf = ZDATA / 'z81' / 'mw.log'; lf.parent.mkdir(exist_ok=True); lf.write_text('')
def spawn(role, name, tmo=3): return subprocess.Popen([sys.executable, str(HERE / 'procs' / 'mw.py'), role, '7300', name, str(tmo), str(lf)])
def ev(): return [(float(l.split(' ', 2)[0]), l.split(' ', 2)[1], l.split(' ', 2)[2]) for l in lf.read_text().splitlines() if l.strip()]
print('== 一:启动 2 个 master 候选(一个当选、一个待命)与 3 个 worker,放入 300 个任务')
m1 = spawn('master', 'M1'); time.sleep(0.5); m2 = spawn('master', 'M2'); ws = {w: spawn('worker', w) for w in ('W1', 'W2', 'W3')}; time.sleep(2.5)
print('  /workers =', sorted(z.get_children('/workers')), '| /master-election 子节点数 =', len(z.get_children('/master-election')))
T = 300; t0 = time.time(); [z.create_async(f'/tasks/t-{i:04d}', b'x') for i in range(T)]; time.sleep(1.2)
print(f'  1.2 秒后:已完成 {len(z.get_children("/done"))} / {T}')
print()
print('== 二:任务进行中 kill -9 一个 worker(W2):master 发现它的会话过期后,把它名下未完成的任务放回 /tasks 重新分配')
tk = time.time(); ws['W2'].kill(); 
while time.time() - tk < 30 and len(z.get_children('/done')) < T: time.sleep(0.2)
e = ev(); lost = [(t - tk, m) for t, nm, m in e if m.startswith('WORKER_LOST')]; print('  master 日志里的事件:', [f'+{t:.1f}s {m}' for t, m in lost])
done = z.get_children('/done'); dup = sum(1 for t, nm, m in e if m.startswith('DUPLICATE')); print(f'  最终 /done 里 {len(done)} / {T} 个任务;重复执行 {dup} 次;全部完成用时 {time.time() - t0:.1f} s'); R['w_crash'] = dict(done=len(done), dup=dup, lost=[round(t, 1) for t, m in lost], total_s=time.time() - t0)
per = collections.Counter(nm for t, nm, m in e if m.startswith('DONE')); print('  各 worker 完成的任务数:', dict(per)); R['per'] = dict(per)
print()
print('== 三:再放入 200 个任务,同时 kill -9 当前 master(M1):待命的 M2 接管,从 ZooKeeper 里读状态继续分配')
leaders = [nm for t, nm, m in ev() if m == 'MASTER_START']; cur = leaders[0]; mm = m1 if cur == 'M1' else m2
tk2 = time.time(); [z.create_async(f'/tasks/u-{i:04d}', b'x') for i in range(200)]; time.sleep(0.2); mm.kill()
while time.time() - tk2 < 40 and len(z.get_children('/done')) < T + 200: time.sleep(0.2)
e = ev(); starts = [(t - tk2, nm) for t, nm, m in e if m == 'MASTER_START']; print('  MASTER_START 事件(相对 kill):', [f'{nm}@+{t:.1f}s' for t, nm in starts]); print(f'  最终 /done = {len(z.get_children("/done"))} / {T + 200};重复执行 {sum(1 for t, nm, m in e if m.startswith("DUPLICATE"))} 次;总用时 {time.time() - tk2:.1f} s'); R['m_crash'] = dict(done=len(z.get_children('/done')), starts=[(round(t, 1), nm) for t, nm in starts], dup=sum(1 for t, nm, m in e if m.startswith('DUPLICATE')))
for p in list(ws.values()) + [m1, m2]:
    try: p.kill()
    except Exception: pass
z.stop(); n.stop(); save('z81', R)
