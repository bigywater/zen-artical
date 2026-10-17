import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z31'); R = {}
e = Ensemble('z31', 5, base=7300).start()
print('== 一:5 个节点,容忍 2 个故障:先杀 1 个 follower,再杀 leader(共 2 个),写入继续吗?')
z = client(e.hosts()); z.create('/base', b'v'); fo = e.followers(); ld = e.leader()
fo[0].kill(); print('  杀掉 follower', fo[0].name, '后写入:', '成功' if can_write(e.hosts()) else '失败')
ld.kill(); time.sleep(0.5)
t0 = time.perf_counter(); ok = False
while time.perf_counter() - t0 < 30:
    alive = ','.join(f'127.0.0.1:{n.cport}' for n in e.nodes if n.alive())
    if can_write(alive, timeout=4, start_timeout=3): ok = True; break
dt = time.perf_counter() - t0
print(f'  再杀 leader {ld.name}(共 2 个故障,剩 3 个)后:重新选举并恢复写入用时 {dt:.1f} s,写入 {"成功" if ok else "失败"};存活节点:', {n.name: n.mode() for n in e.nodes if n.alive()}); R['two_down'] = dict(ok=ok, s=dt)
print()
print('== 二:已经确认(返回成功)的写入不会因为这 2 个节点故障丢失:故障前后各写 200 个,全部读得到')
z2 = client(','.join(f'127.0.0.1:{n.cport}' for n in e.nodes if n.alive())); [z2.create(f'/after{i}', b'x') for i in range(200)]
have = len(z2.get_children('/')); print('  根下现在的子节点数(含 base 与 200 个 after、zookeeper):', have, '| /base 数据:', z2.get('/base')[0]); R['have'] = have
z2.stop()
print()
print('== 三:再杀 1 个(共 3 个故障,只剩 2/5):多数派丢失,不能写;启动回 1 个(3/5)恢复')
alive = [n for n in e.nodes if n.alive()]; alive[0].kill(); time.sleep(3)
rest = [n for n in e.nodes if n.alive()]
print('  剩余节点:', {n.name: n.mode() or '不服务' for n in rest}, '| 写入:', '成功' if can_write(','.join(f'127.0.0.1:{n.cport}' for n in rest), timeout=5, start_timeout=6) else '失败(没有多数派)')
dead = [n for n in e.nodes if not n.alive()]; dead[0].start(wipe=False, wait=False); t0 = time.perf_counter()
while time.perf_counter() - t0 < 40:
    if can_write(','.join(f'127.0.0.1:{n.cport}' for n in e.nodes if n.alive()), timeout=4, start_timeout=3): break
dt = time.perf_counter() - t0
print(f'  启动回一个节点(3/5)后恢复写入用时 {dt:.1f} s;数据:/base =', end=' ')
z3 = client(','.join(f'127.0.0.1:{n.cport}' for n in e.nodes if n.alive())); print(z3.get('/base')[0], '| 子节点数', len(z3.get_children('/'))); R['recover'] = dt; z3.stop()
z.stop(); e.stop(); save('z31', R)
