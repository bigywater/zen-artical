import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r116'); R = {}
n = Node(8260, name='r116', conf={'enable-debug-command': 'yes'}).start(); c = n.c()
for i in range(0, 300000, 20000): c.pipeline([['SET', f'small:{i+j}', 'v' * 20] for j in range(20000)])
c.do('SET', 'big:string', 'x' * (5 * 1024 * 1024))
for i in range(0, 200000, 20000): c.pipeline([['RPUSH', 'big:list'] + [f'e{i+j}' for j in range(20000)]])
for i in range(0, 100000, 10000): c.pipeline([['HSET', 'big:hash'] + [x for j in range(10000) for x in (f'f{i+j}', f'value-{i+j}')]])
for i in range(0, 150000, 30000): c.pipeline([['SADD', 'big:set'] + [f'm{i+j}' for j in range(30000)]])
for i in range(0, 50000, 10000): c.pipeline([['ZADD', 'big:zset'] + [x for j in range(10000) for x in (i + j, f'z{i+j}')]])
c.do('HSET', 'small:hash', 'a', 1)
print(f'== 一:数据集:30 万个小 key + 5 个大 key(DBSIZE = {c.do("DBSIZE")})')
print('== 二:MEMORY USAGE 对每个大 key 的结果与耗时(SAMPLES 0 = 精确遍历所有元素,默认 SAMPLES 5)')
print(f'{"key":<12} {"类型":<7} {"元素数":>8} {"MEMORY USAGE 字节":>18} {"SAMPLES 默认(5)耗时 µs":>22} {"SAMPLES 0 耗时 µs":>18} {"SAMPLES 5 结果":>14}')
R['mu'] = []
for k, len_cmd in (('big:string', 'STRLEN'), ('big:list', 'LLEN'), ('big:hash', 'HLEN'), ('big:set', 'SCARD'), ('big:zset', 'ZCARD')):
    tp = c.do('TYPE', k); ln = c.do(len_cmd, k)
    t0 = time.perf_counter(); m5 = c.do('MEMORY', 'USAGE', k); d5 = (time.perf_counter() - t0) * 1e6
    t0 = time.perf_counter(); m0 = c.do('MEMORY', 'USAGE', k, 'SAMPLES', 0); d0 = (time.perf_counter() - t0) * 1e6
    print(f'{k:<12} {tp:<7} {ln:>8} {m0:>18} {d5:>22.0f} {d0:>18.0f} {m5:>14}'); R['mu'].append((k, tp, ln, m0, d5, d0, m5))
print()
print('== 三:自己写脚本找大 key:SCAN COUNT 1000 + 每批用管道发 TYPE 和 MEMORY USAGE(SAMPLES 5),扫 30 万个 key 的总耗时与对其它连接的影响')
stop = threading.Event(); lat = []
def pr():
    cp = n.c()
    while not stop.is_set(): t = time.perf_counter(); cp.do('PING'); lat.append((time.perf_counter() - t) * 1000); time.sleep(0.0005)
th = threading.Thread(target=pr); th.start(); time.sleep(0.1)
t0 = time.perf_counter(); cur = '0'; top = []; scanned = 0
while True:
    r = c.do('SCAN', cur, 'COUNT', 1000); cur = r[0]; ks = r[1]
    if ks:
        mu = c.pipeline([['MEMORY', 'USAGE', k] for k in ks]); scanned += len(ks)
        top += [(m, k) for m, k in zip(mu, ks) if m and m > 100000]
    if cur == '0': break
dt = time.perf_counter() - t0; time.sleep(0.05); stop.set(); th.join()
top.sort(reverse=True)
print(f'  扫描 {scanned} 个 key 用了 {dt:.2f} s({scanned/dt/1000:.0f}k key/秒);期间另一个连接 PING 最大停顿 {max(lat):.2f} ms;超过 100 KB 的 key:', [(k, m) for m, k in top])
R['scan'] = dict(n=scanned, s=dt, stall=max(lat), top=[(k, m) for m, k in top])
print()
print('== 四:DEBUG OBJECT 给出序列化长度(RDB 里的大小)与内存占用不同')
for k in ('big:list', 'big:hash'): print(f'  {k}: {c.do("DEBUG", "OBJECT", k)}')
R['dbg'] = [c.do('DEBUG', 'OBJECT', k) for k in ('big:list', 'big:hash')]
save('r116', R); cleanup([n])
