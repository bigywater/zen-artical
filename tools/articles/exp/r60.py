import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r60'); R = {}
n = Node(7201, name='p60', conf={'appendonly': 'yes', 'appendfsync': 'everysec', 'auto-aof-rewrite-percentage': '0', 'save': '""'}).start(); c = n.c()
aofdir = n.dir / 'appendonlydir'
N = 1500000
for i in range(0, N, 5000): c.pipeline([['SET', f'k{i+j}', 'v' * 100] for j in range(5000)])
time.sleep(1.2)
def files():
    return {p.name: p.stat().st_size for p in aofdir.iterdir() if not p.name.endswith('.manifest') and not p.name.startswith('temp')}
print('== 一:INFO persistence 里和 AOF 重写相关的字段(Redis 8.x)')
pi = info(c, 'persistence')
print(', '.join(k for k in pi if k.startswith('aof_')))
print('包含 "buffer" 的字段:', [k for k in pi if 'buffer' in k] or '(没有)')
print()
print('== 二:150 万个 key 的数据集;重写期间 4 个线程持续 INCR seq + SET live:*(每条都等回复)')
stop = threading.Event(); acked = [0] * 4
def writer(t):
    w = n.c()
    while not stop.is_set():
        w.do('INCR', 'seq'); acked[t] += 1
ths = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
[t.start() for t in ths]; time.sleep(0.5)
f0 = files(); t0 = time.time()
c.do('BGREWRITEAOF')
tl = []; last = None
while True:
    pi = info(c, 'persistence'); f = files(); man = (aofdir / 'appendonly.aof.manifest').read_text()
    state = (tuple(sorted(f)), pi['aof_rewrite_in_progress'])
    if state != last:
        tl.append((time.time() - t0, sorted(f.items()), pi['aof_rewrite_in_progress'], [l for l in man.splitlines()]))
        last = state
    if pi['aof_rewrite_in_progress'] == '0' and time.time() - t0 > 0.05: break
    time.sleep(0.003)
tend = time.time() - t0
time.sleep(0.5); stop.set(); [t.join() for t in ths]
print(f'重写开始前的文件:{sorted(f0.items())}')
for t, f, ip, man in tl:
    print(f'+{t:5.2f}s  aof_rewrite_in_progress={ip}  文件:{[(a.replace("appendonly.aof.", ""), b) for a, b in f]}')
print(f'重写共耗时约 {tend:.2f} s;期间写入线程共完成 INCR {sum(acked)} 次(重写前 0.5 s 已经在写)')
R['tl'] = [(t, f, ip) for t, f, ip, m in tl]; R['tend'] = tend; R['acked'] = sum(acked)
print('最终 manifest:'); print((aofdir / 'appendonly.aof.manifest').read_text().strip())
print()
print('== 三:重写期间没有丢写:等 fsync 后 kill -9,从 AOF 重启,对比 seq 与写线程确认过的 INCR 数')
seq_before = int(c.do('GET', 'seq')); time.sleep(1.3)
n.kill9(); time.sleep(0.3)
t1 = time.time(); n.start(rewrite=False); wait_loaded(n); c = n.c(); load = time.time() - t1
seq_after = int(c.do('GET', 'seq'))
print(f'写线程确认的 INCR 次数 = {sum(acked)};kill -9 前 seq = {seq_before};重启后从 AOF 恢复的 seq = {seq_after};dbsize = {c.do("DBSIZE")}')
print(f'重启加载耗时约 {load:.2f} s')
R['seq'] = [sum(acked), seq_before, seq_after]
save('r60', R); cleanup([n])
