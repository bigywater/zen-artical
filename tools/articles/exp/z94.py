import sys, os, time, json, re, subprocess, signal, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z94'); R = {}
n = Node('z94', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
CUR = HERE.parent / 'curator'; CP = f'{CUR}/lib/*:{CUR}'; J_ = ['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', CP]
r = subprocess.run(J_ + ['Z94', str(n.p.pid)], capture_output=True, text=True, timeout=200); out_ = r.stdout.rstrip(); print(out_)
if r.returncode: print('EXIT', r.returncode, r.stderr[-800:])
R['stdout'] = out_
print()
print('== 四:5 个独立 JVM 进程竞选(LeaderLatch,会话超时 3 s),kill -9 当前 leader 的进程 3 次:最后一次心跳 → 新 leader 开始')
lf = ZDATA / 'z94' / 'l.log'; lf.parent.mkdir(exist_ok=True); lf.write_text('')
ps = {f'P{i}': subprocess.Popen(J_ + ['LeaderProc', '7300', f'P{i}', str(lf)], stderr=subprocess.DEVNULL) for i in range(5)}
def ev(): return [(float(l.split(' ', 2)[0]), l.split(' ', 2)[1], l.split(' ', 2)[2]) for l in lf.read_text().splitlines() if l.strip()]
t0 = time.time()
while not any(x[2] == 'LEADER_START' for x in ev()) and time.time() - t0 < 30: time.sleep(0.1)
time.sleep(1.0); gaps = []
for k in range(3):
    e = ev(); cur = [x for x in e if x[2] == 'LEADER_START'][-1][1]; time.sleep(0.5); ps.pop(cur).kill(); tk = time.time(); n0 = len([x for x in ev() if x[2] == 'LEADER_START'])
    while time.time() - tk < 20 and len([x for x in ev() if x[2] == 'LEADER_START']) <= n0 - 0 and not any(x[2] == 'LEADER_START' and x[0] > tk for x in ev()): time.sleep(0.02)
    e = ev(); last = max(x[0] for x in e if x[1] == cur and x[2] == 'BEAT'); nx = [x for x in e if x[2] == 'LEADER_START' and x[0] > tk][0]
    gaps.append(nx[0] - last); print(f'  kill -9 {cur} → 新 leader {nx[1]},最后一次心跳到新 leader 开始 {nx[0] - last:.2f} s')
    time.sleep(1.0)
both = 0; e = ev(); st = {}
for x in e:
    if x[2] == 'BEAT': st[x[1]] = x[0]
    cur_ = [k for k, v in st.items() if x[0] - v < 0.2]
    if len(cur_) > 1: both += 1
print(f'  期间同时有两个进程在发 leader 心跳的采样点数:{both}')
R['kill'] = dict(gaps=gaps, both=both)
for p in ps.values(): p.kill()
n.stop(); save('z94', R); os._exit(0)
