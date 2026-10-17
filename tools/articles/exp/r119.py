import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r119'); R = {}
n = Node(8250, name='r119').start(); c = n.c()
def probe_during(fn):
    stop = threading.Event(); lat = []
    def pr():
        cp = n.c()
        while not stop.is_set(): t = time.perf_counter(); cp.do('PING'); lat.append((time.perf_counter() - t) * 1000); time.sleep(0.0005)
    th = threading.Thread(target=pr); th.start(); time.sleep(0.1); r = fn(); time.sleep(0.05); stop.set(); th.join(); return r, max(lat)
print('== 一:KEYS 的代价随 key 总数线性增长,与匹配多少无关(模式 "*" 与 "nomatch*",另一个连接 PING 的最大停顿)')
print(f'{"key 总数":>10} {"KEYS * 命令耗时 ms":>19} {"PING 最大停顿 ms":>17} {"KEYS nomatch* 耗时 ms":>22} {"PING 最大停顿 ms":>17}')
R['rows'] = []; have = 0
for N in (100000, 500000, 1000000, 3000000):
    while have < N:
        c.pipeline([['SET', f'key:{have+j}', 'v'] for j in range(20000)]); have += 20000
    def k1():
        t0 = time.perf_counter(); r = c.do('KEYS', '*'); return (time.perf_counter() - t0) * 1000
    def k2():
        t0 = time.perf_counter(); r = c.do('KEYS', 'nomatch*'); return (time.perf_counter() - t0) * 1000
    a, sa = probe_during(k1); b, sb = probe_during(k2)
    print(f'{N:>10} {a:>19.0f} {sa:>17.1f} {b:>22.0f} {sb:>17.1f}'); R['rows'].append((N, a, sa, b, sb))
print()
print('== 二:替代:SCAN COUNT 1000 遍历同样多的 key,另一个连接 PING 的最大停顿')
def scan_all():
    cur = '0'; t0 = time.perf_counter(); calls = 0
    while True:
        r = c.do('SCAN', cur, 'COUNT', 1000); cur = r[0]; calls += 1
        if cur == '0': break
    return (time.perf_counter() - t0) * 1000, calls
(dt, calls), st = probe_during(scan_all)
print(f'  {have} 个 key:SCAN 遍历总耗时 {dt:.0f} ms({calls} 次调用),期间另一个连接 PING 最大停顿 {st:.2f} ms')
R['scan'] = dict(ms=dt, calls=calls, stall=st, n=have)
print()
print('== 三:用 ACL 禁止 KEYS(第 122–125 篇会讲 ACL,这里只验证效果)')
c.do('ACL', 'SETUSER', 'app', 'on', '>pw', '~*', '+@all', '-keys')
s = C(8250); s.do('AUTH', 'app', 'pw')
sh(s, 'KEYS', '*'); sh(s, 'GET', 'key:1')
R['acl'] = str(s.do('KEYS', '*', raise_err=False))
save('r119', R); cleanup([n])
