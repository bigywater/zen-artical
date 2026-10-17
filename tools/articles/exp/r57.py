import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r57'); R = {}
M = Node(7165, name='m57', conf={'appendonly': 'yes', 'appendfsync': 'everysec'}).start()
B = Node(7166, name='b57', conf={'replicaof': '127.0.0.1 7165', 'appendonly': 'yes'}).start(); Cn = Node(7167, name='c57', conf={'replicaof': '127.0.0.1 7165', 'appendonly': 'yes'}).start()
m, b, cc = M.c(), B.c(), Cn.c(); wait_link(b); wait_link(cc)
def timed(*a):
    t = time.perf_counter(); r = m.do(*a); return r, (time.perf_counter() - t) * 1000
print('== 一:两个从库都正常:SET 之后 WAIT 2 100,返回已确认的从库数和耗时')
L = []
for i in range(200):
    m.do('SET', 'k', i); r, ms = timed('WAIT', 2, 100); L.append((r, ms))
print(f'200 次:返回值集合 {sorted(set(x[0] for x in L))};耗时 中位 {statistics.median(x[1] for x in L):.2f} ms,最大 {max(x[1] for x in L):.2f} ms')
R['ok'] = [statistics.median(x[1] for x in L), max(x[1] for x in L)]
print()
print('== 二:把从库 B 冻结(SIGSTOP):WAIT 2 200 等满超时,只能确认 1 个;WAIT 1 200 很快就返回')
B.p.send_signal(signal.SIGSTOP); time.sleep(0.2)
m.do('SET', 'k', 'during-freeze')
r2, ms2 = timed('WAIT', 2, 200); print(f'WAIT 2 200 → {r2},耗时 {ms2:.0f} ms')
m.do('SET', 'k', 'during-freeze2'); r1, ms1 = timed('WAIT', 1, 200); print(f'WAIT 1 200 → {r1},耗时 {ms1:.2f} ms')
R['freeze'] = dict(r2=r2, ms2=ms2, r1=r1, ms1=ms1)
print()
print('== 三:WAIT 返回 1(没到 2)不代表写入失败或回滚:主库上已经生效,冻结的从库恢复后会追上')
print('主库 GET k =', m.do('GET', 'k'), '  从库 C GET k =', cc.do('GET', 'k'))
B.p.send_signal(signal.SIGCONT); time.sleep(0.5); wait_link(b)
print('B 恢复后 GET k =', b.do('GET', 'k'))
print()
print('== 四:WAIT 只等复制(内存里收到);WAITAOF 等 AOF 落盘(主库与从库都开了 appendonly yes,appendfsync everysec)')
LW = []
for i in range(10):
    m.do('SET', 'w', i); r, ms = timed('WAIT', 2, 3000); LW.append((r, ms))
print(f'WAIT 2 3000:      返回 {sorted(set(x[0] for x in LW))},耗时 最小 {min(x[1] for x in LW):.2f}  中位 {statistics.median(x[1] for x in LW):.2f}  最大 {max(x[1] for x in LW):.2f} ms')
R['waitaof'] = {'wait': [min(x[1] for x in LW), statistics.median(x[1] for x in LW), max(x[1] for x in LW)]}
for name, args in (('WAITAOF 1 0 3000(仅本地 fsync)', (1, 0, 3000)), ('WAITAOF 1 1 3000', (1, 1, 3000)), ('WAITAOF 1 2 3000', (1, 2, 3000))):
    L = []
    for i in range(6):
        m.do('SET', 'w', i); r, ms = timed('WAITAOF', *args); L.append((r, ms))
    print(f'{name:<30} 返回 {[x[0] for x in L][:3]}…  耗时 最小 {min(x[1] for x in L):.0f}  中位 {statistics.median(x[1] for x in L):.0f}  最大 {max(x[1] for x in L):.0f} ms')
    R['waitaof'][args] = [L[0][0], min(x[1] for x in L), statistics.median(x[1] for x in L), max(x[1] for x in L)]
R['waitaof'] = {k if isinstance(k, str) else '_'.join(map(str, k)): v for k, v in R['waitaof'].items()}
print()
print('== 五:两个从库都冻结时,WAIT 1 300:')
B.p.send_signal(signal.SIGSTOP); Cn.p.send_signal(signal.SIGSTOP); time.sleep(0.2)
m.do('SET', 'k', 'all-frozen'); r, ms = timed('WAIT', 1, 300); print(f'WAIT 1 300 → {r},耗时 {ms:.0f} ms')
R['allfrozen'] = [r, ms]
B.p.send_signal(signal.SIGCONT); Cn.p.send_signal(signal.SIGCONT)
save('r57', R); cleanup([M, B, Cn])
