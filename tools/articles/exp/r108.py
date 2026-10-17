import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r108'); R = {}
n = Node(8120, name='r108').start(); c = n.c()
print('== 一:这个版本的 lazyfree 相关默认值')
for k in ('lazyfree-lazy-user-del', 'lazyfree-lazy-eviction', 'lazyfree-lazy-expire', 'lazyfree-lazy-server-del', 'lazyfree-lazy-user-flush', 'replica-lazy-flush'): print(f'  {k:<28} {c.do("CONFIG", "GET", k)[1]}')
def mk(key, N=2000000):
    c.do('DEL', key)
    for i in range(0, N, 20000): c.pipeline([['SADD', key, *[f'member-{i+j}' for j in range(0, 20000, 1)]]] if False else [['SADD', key] + [f'member-{i+j}' for j in range(20000)]])
def stall(action):
    stop = threading.Event(); lat = []
    def probe():
        cp = n.c()
        while not stop.is_set():
            t = time.perf_counter(); cp.do('PING'); lat.append((t, (time.perf_counter() - t) * 1000)); time.sleep(0.0005)
    th = threading.Thread(target=probe); th.start(); time.sleep(0.2)
    t0 = time.perf_counter(); r = action(); dt = (time.perf_counter() - t0) * 1000; time.sleep(0.3); stop.set(); th.join()
    m = max((d for t, d in lat if t0 - 0.002 <= t <= t0 + dt / 1000 + 0.05), default=0)
    return dt, m
print()
print('== 二:释放一个 200 万成员的集合(约 100 MB):命令耗时与另一个连接 PING 的最大停顿')
print(f'{"方式":<44} {"命令耗时":>9} {"PING 最大停顿":>13}')
R['del'] = {}
mk('big'); print('  (集合已建好:SCARD =', c.do('SCARD', 'big'), f',used_memory {int(info(c, "memory")["used_memory"])/1e6:.0f} MB)')
for name, setup, act in (
    ('DEL(默认 lazyfree-lazy-user-del no)', None, lambda: n.c().do('DEL', 'big')),
    ('UNLINK', None, lambda: n.c().do('UNLINK', 'big')),
    ('DEL + lazyfree-lazy-user-del yes', lambda: c.do('CONFIG', 'SET', 'lazyfree-lazy-user-del', 'yes'), lambda: n.c().do('DEL', 'big')),
):
    mk('big')
    if setup: setup()
    dt, m = stall(act); R['del'][name] = (dt, m); print(f'{name:<40} {dt:>7.1f} ms {m:>11.1f} ms   lazyfreed_objects={info(c, "memory")["lazyfreed_objects"]}')
    c.do('CONFIG', 'SET', 'lazyfree-lazy-user-del', 'no')
print()
print('== 三:FLUSHALL vs FLUSHALL ASYNC(300 万个小 key)')
R['flush'] = {}
for name in ('FLUSHALL', 'FLUSHALL ASYNC'):
    for i in range(0, 3000000, 50000): c.pipeline([['SET', f'f{i+j}', 'v'] for j in range(50000)])
    dt, m = stall(lambda: n.c().do(*name.split())); R['flush'][name] = (dt, m); print(f'  {name:<18} 命令耗时 {dt:>7.1f} ms   PING 最大停顿 {m:>7.1f} ms   lazyfree_pending_objects(命令刚返回后)见下')
print()
print('== 四:过期的大 key:EXPIRE 到期时主动删除会不会卡主线程?lazyfree-lazy-expire no vs yes')
R['exp'] = {}
for mode in ('no', 'yes'):
    c.do('CONFIG', 'SET', 'lazyfree-lazy-expire', mode); mk('bigexp'); c.do('PEXPIRE', 'bigexp', 500)
    stop = threading.Event(); lat = []
    def probe():
        cp = n.c()
        while not stop.is_set(): t = time.perf_counter(); cp.do('PING'); lat.append((t, (time.perf_counter() - t) * 1000)); time.sleep(0.0005)
    th = threading.Thread(target=probe); th.start(); time.sleep(3.0); stop.set(); th.join()
    m = max(d for t, d in lat); ex = c.do('EXISTS', 'bigexp'); R['exp'][mode] = m
    print(f'  lazyfree-lazy-expire {mode:<4} 3 秒观察期内 PING 最大停顿 {m:.1f} ms;bigexp 是否还存在 = {ex}')
c.do('CONFIG', 'SET', 'lazyfree-lazy-expire', 'no')
save('r108', R); cleanup([n])
