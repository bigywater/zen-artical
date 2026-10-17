import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r109'); R = {}
def bench(port, cc, P, n=2000000, th=4):
    r = subprocess.run(['redis-benchmark', '-p', str(port), '-q', '-n', str(n), '-c', str(cc), '-P', str(P), '--threads', str(th), '-t', 'get'], capture_output=True, text=True, timeout=300)
    m = re.search(r'([\d.]+) requests per second', r.stdout.replace('\r', '\n')); return float(m.group(1))
print('== 一:io-threads 1 / 2 / 4 / 8,redis-benchmark GET(value 3 字节,8 个客户端线程),三种负载,每格 3 次取中位')
print(f'{"io-threads":>10} {"50 连接 无管道":>16} {"400 连接 无管道":>16} {"50 连接 管道 16":>16}')
R['t'] = {}; R['dist'] = {}
for k, io in enumerate((1, 2, 4, 8)):
    n = Node(8160 + k, name=f'r109_{io}', conf={'io-threads': io} if io > 1 else {}).start(); c = n.c()
    for i in range(1000): c.do('SET', f'key:{i:012d}', 'x' * 3)
    v = [statistics.median(bench(8160 + k, cc, P, 1500000 if P == 1 else 6000000, 8) for _ in range(3)) for cc, P in ((50, 1), (400, 1), (50, 16))]
    R['t'][io] = v; R['dist'][io] = info(c, 'threads')
    print(f'{io:>10} {v[0]:>16.0f} {v[1]:>16.0f} {v[2]:>16.0f}')
    cleanup([n]); time.sleep(0.5)
print()
print('== 二:INFO threads:每个 I/O 线程处理的读/写次数(最后一格负载之后)')
for io, d in R['dist'].items():
    print(f'  io-threads {io}:', '  '.join(f'{k}:{v}' for k, v in d.items()))
save('r109', R)
