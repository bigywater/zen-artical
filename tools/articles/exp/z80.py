import sys, os, time, json, re, subprocess, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z80'); R = {}
n = Node('z80', 7300, conf={'tickTime': 1000}).start(); admin = client('127.0.0.1:7300')
lf = ZDATA / 'z80' / 'el.log'; lf.parent.mkdir(exist_ok=True)
def spawn(name, tmo=3, extra=None): return subprocess.Popen([sys.executable, str(HERE / 'procs' / 'elect.py'), '7300', name, str(tmo), str(lf)] + ([extra] if extra else []))
def parse():
    ev = []
    for l in lf.read_text().splitlines():
        t, nm, msg = l.split(' ', 2); ev.append((float(t), nm, msg))
    return ev
print('== 一:5 个候选进程竞选(kazoo Election 配方,每个进程一个会话,会话超时 3 s);谁先创建临时顺序节点谁当选')
lf.write_text(''); ps = {}
for nm in 'ABCDE': ps[nm] = spawn(nm); time.sleep(0.4)
time.sleep(2); ev = parse(); leaders = [nm for t, nm, m in ev if m == 'LEAD_START']; print('  当选者:', leaders, '| /election 的子节点数 =', len(admin.get_children('/election'))); R['first'] = leaders
print('  同一时刻只有一个在发心跳:', len({nm for t, nm, m in ev if m == 'BEAT' and t > ev[-1][0] - 1}) == 1)
print()
print('== 二:kill -9 杀掉 leader,看新 leader 什么时候出现(4 次,每次杀当前 leader)')
print(f'  {"次":>2} {"被杀":>4} {"新 leader":>9} {"空窗期 s(最后一次心跳 → 新 leader 开始)":>34} {"期间是否有两个 leader":>18}')
R['runs'] = []; alive = dict(ps)
for r in range(4):
    ev = parse(); cur = [nm for t, nm, m in ev if m == 'LEAD_START'][-1]; last_beat = max(t for t, nm, m in ev if nm == cur and m == 'BEAT'); k0 = time.time(); alive[cur].kill(); del alive[cur]
    t0 = time.time()
    while time.time() - t0 < 20:
        ev = parse(); leads = [(t, nm) for t, nm, m in ev if m == 'LEAD_START' and t > k0]
        if leads: break
        time.sleep(0.1)
    t_new, new = leads[0]; time.sleep(1); ev = parse()
    last_beat = max(t for t, nm, m in ev if nm == cur and m == 'BEAT'); gap = t_new - last_beat; overlap = any(nm == cur and t > t_new for t, nm, m in ev if m == 'BEAT')
    R['runs'].append(dict(killed=cur, new=new, gap=gap, overlap=overlap)); print(f'  {r + 1:>2} {cur:>4} {new:>9} {gap:>34.2f} {"有" if overlap else "没有":>18}')
import statistics
g = [x['gap'] for x in R['runs']]; print(f'  空窗期中位 {statistics.median(g):.2f} s(会话超时 3 s + 选举)'); R['gap_med'] = statistics.median(g)
print()
print('== 三:leader 主动让位(resign,正常退出,会话关闭):没有空窗')
for p in alive.values(): p.kill()
time.sleep(1); lf.write_text(''); admin.delete('/election', recursive=True) if admin.exists('/election') else None
a = spawn('X', 3, 'resign'); time.sleep(0.5); b = spawn('Y'); 
t0 = time.time()
while time.time() - t0 < 20:
    ev = parse()
    if any(nm == 'Y' and m == 'LEAD_START' for t, nm, m in ev): break
    time.sleep(0.1)
ev = parse(); lastx = max(t for t, nm, m in ev if nm == 'X' and m == 'BEAT'); starty = [t for t, nm, m in ev if nm == 'Y' and m == 'LEAD_START'][0]
print(f'  X 当选并在 1.6 秒后让位(进程退出时关闭会话):X 最后一次心跳到 Y 开始 = {starty - lastx:.2f} s'); R['resign_gap'] = starty - lastx
a.kill(); b.kill(); admin.stop(); n.stop(); save('z80', R)
