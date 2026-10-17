import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r120'); R = {}
n = Node(8290, name='r120').start(); c = n.c()
def rb(args, timeout=300):
    r = subprocess.run(['redis-benchmark', '-p', '8290', '-q'] + args, capture_output=True, text=True, timeout=timeout)
    m = re.search(r'([\d.]+) requests per second', r.stdout.replace('\r', '\n')); return float(m.group(1)) if m else None
def med(args, k=3): return statistics.median(rb(args) for _ in range(k))
print('== 一:同一个配置连续跑 5 次:结果的波动(SET,50 连接,20 万次)')
v = [rb(['-t', 'set', '-n', '200000', '-c', '50']) for _ in range(5)]
print('  5 次结果:', [f'{x/1000:.0f}k' for x in v], f' 最大/最小 = {max(v)/min(v):.2f}'); R['var'] = v
print()
c.do('CONFIG', 'SET', 'maxmemory', '1gb'); c.do('CONFIG', 'SET', 'maxmemory-policy', 'allkeys-lru')
print('== 二:key 空间:redis-benchmark 默认所有请求打同一个 key;-r 100 万 让 key 随机(SET,50 连接,100 万次,每格 3 次取中位)')
c.do('FLUSHALL')
a = med(['-t', 'set', '-n', '1000000', '-c', '50']); m1 = int(info(c, 'memory')['used_memory']); k1 = c.do('DBSIZE')
b = med(['-t', 'set', '-n', '1000000', '-c', '50', '-r', '1000000']); m2 = int(info(c, 'memory')['used_memory']); k2 = c.do('DBSIZE')
print(f'  默认(同一个 key):{a/1000:.0f}k/s,跑完后 DBSIZE = {k1},used_memory {m1/1e6:.1f} MB')
print(f'  -r 1000000:      {b/1000:.0f}k/s,跑完后 DBSIZE = {k2},used_memory {m2/1e6:.1f} MB')
R['keyspace'] = dict(same=a, rnd=b, k1=k1, k2=k2, m1=m1, m2=m2)
print()
print('== 三:value 大小(SET,50 连接,-r 1000 限制 key 数以免占满内存):3 / 100 / 1024 / 10240 / 102400 字节')
R['size'] = {}
for d in (3, 100, 1024, 10240, 102400):
    x = med(['-t', 'set', '-n', '300000', '-c', '50', '-d', str(d), '-r', '1000']); R['size'][d] = x; print(f'  -d {d:>6}: {x/1000:6.0f}k 条/秒  ≈ {x*d/1e6:7.0f} MB/s 负载')
print()
print('== 四:管道(-P)与连接数(-c):GET,3 字节,-r 100000')
R['pc'] = {}
for P in (1, 16):
    for cc in (1, 10, 50, 500):
        x = med(['-t', 'get', '-n', '600000' if P == 16 else '300000', '-c', str(cc), '-P', str(P), '-r', '100000']); R['pc'][f'{P}_{cc}'] = x; print(f'  P={P:<2} c={cc:<4}: {x/1000:7.0f}k 条/秒')
save('r120', R); cleanup([n])
