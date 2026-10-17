import sys, os, time, json, re, subprocess, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z99'); R = {}
CUR = HERE.parent / 'curator'
r = subprocess.run(['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', f'{CUR}/lib/*:{CUR}', 'Z99'], capture_output=True, text=True, timeout=100); print(r.stdout.rstrip()); R['table'] = r.stdout
print()
print('== 二:源码里 finalizeWait = 200 ms:选出票数过半的候选后,还要再等 200 ms 看有没有更优的票,所以一轮选举至少 200 ms。3 节点,5 次 kill -9 leader,取新 leader 日志里的「LEADER ELECTION TOOK」')
e = Ensemble('z99', 3, base=7300).start(); tooks = []
for k in range(5):
    ld = e.leader(); ld.kill(); t0 = time.time()
    while time.time() - t0 < 30 and not e.leader(): time.sleep(0.05)
    nl = e.leader(); time.sleep(0.5)
    ms = [int(x) for x in re.findall(r'LEADER ELECTION TOOK - (\d+) MS', nl.log())]
    fl = [int(x) for f in e.followers() for x in re.findall(r'FOLLOWING - LEADER ELECTION TOOK - (\d+) MS', f.log())]
    print(f'  第 {k + 1} 次:kill {ld.name} → 新 leader {nl.name};新 leader 日志里 LEADING 的选举耗时(历次):{ms[-1:]} ms;follower 日志里最近一次 FOLLOWING 的选举耗时:{fl[-1:]} ms')
    tooks.append(ms[-1] if ms else None); ld.start(wipe=False); time.sleep(1.5)
ok = [t for t in tooks if t]
print(f'  5 次 leader 选举耗时(ms):{ok},最小 {min(ok)} ms ≥ 200 ms:{min(ok) >= 200}')
R['took'] = ok
e.stop()
print()
print('== 三:选票没凑够时的指数退避(源码 notTimeout = min(notTimeout << 1, maxNotificationInterval)):3 节点的集群只启动 1 个,看它日志里的「Notification time out」')
e = Ensemble('z99b', 3, base=7400); e.nodes[0].start(wait=False); time.sleep(14)
tos = re.findall(r'Notification time out: (\d+) ms', e.nodes[0].log())
print(f'  14 秒内 Notification time out 依次为:{tos}(日志打印的是翻倍之后的值;第一次等待是 200 ms = finalizeWait,之后每次翻倍)')
R['backoff'] = tos
e.stop()
print()
print('== 四:观察者的选票:3 个参与者 + 1 个观察者,观察者与参与者日志里「New election」提议的 zxid')
e = Ensemble('z99c', 3, base=7500, observers=1).start(); time.sleep(1)
ob = e.nodes[3]; ne = re.findall(r'New election\. My id = (\d+), proposed zxid=(0x[0-9a-f]+)', ob.log())
print('  观察者(myid 4)日志里的 New election:', ne[:2]); R['obs'] = ne[:2]
pa = re.findall(r'New election\. My id = (\d+), proposed zxid=(0x[0-9a-f]+)', e.nodes[0].log()); print('  参与者(myid 1)日志里的 New election:', pa[:1])
print('  观察者最终 mode =', ob.mode(), '| leader =', e.leader().name)
e.stop(); save('z99', R); os._exit(0)
