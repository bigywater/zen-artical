import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r103'); R = {}
n = Node(8070, name='r103').start(); c0 = n.c()
V = 'v' * 100
for i in range(0, 100000, 5000): c0.pipeline([['SET', f'k{i+j}', V] for j in range(5000)])
print('== 一:批量大小 vs 吞吐(GET 100 字节 value,共 40 万条,每格 3 次取中位;本机回环)')
print(f'{"批量":>8} {"条/秒":>10}')
R['bs'] = []
for b in (1, 2, 5, 10, 50, 100, 500, 1000, 5000, 20000, 100000):
    N = 40000 if b == 1 else 400000; v = []
    for _ in range(3):
        c = n.c(); t = time.perf_counter()
        for i in range(0, N, b):
            if b == 1: c.do('GET', f'k{i % 100000}')
            else: c.pipeline([['GET', f'k{(i+j) % 100000}'] for j in range(b)])
        v.append(N / (time.perf_counter() - t)); c.close()
    m = statistics.median(v); print(f'{b:>8} {m:>10.0f}'); R['bs'].append((b, m))
print()
print('== 二:批量太大的代价:一个客户端一次发 N 条 GET(1 KB value),另一个客户端每 1 ms PING,记录最大停顿与服务器输出缓冲')
for i in range(0, 20000, 5000): c0.pipeline([['SET', f'big{i+j}', 'x' * 1024] for j in range(5000)])
print(f'{"N":>8} {"另一个客户端 PING 最大停顿":>22} {"完成耗时":>10} {"peak 输出缓冲(client_recent_max_output_buffer)":>44}')
R['big'] = []
for N in (1000, 10000, 100000, 1000000):
    stop = threading.Event(); lat = []
    def probe():
        cp = n.c()
        while not stop.is_set():
            t = time.perf_counter(); cp.do('PING'); lat.append((t, (time.perf_counter() - t) * 1000)); time.sleep(0.001)
    th = threading.Thread(target=probe); th.start(); time.sleep(0.2)
    c = n.c(); cmds = [['GET', f'big{i % 20000}'] for i in range(N)]
    s = socket.create_connection(('127.0.0.1', 8070)); buf = b''.join(C.enc(x) for x in cmds)
    n.c().do('CONFIG', 'RESETSTAT')
    t0 = time.perf_counter(); s.sendall(buf)
    got = 0; f = s.makefile('rb'); 
    for _ in range(N):
        l = f.readline(); ln = int(l[1:-2]); f.read(ln + 2)
    dt = time.perf_counter() - t0; time.sleep(0.2); stop.set(); th.join(); s.close()
    mx = max(d for t, d in lat if t0 - 0.01 <= t <= t0 + dt + 0.01) if any(t0 <= t <= t0 + dt for t, d in lat) else 0
    ob = int(info(n.c(), 'clients')['client_recent_max_output_buffer'])
    print(f'{N:>8} {mx:>19.1f} ms {dt*1000:>8.0f} ms {ob/1e6:>36.1f} MB')
    R['big'].append(dict(N=N, stall=mx, ms=dt * 1000, ob=ob))
save('r103', R); cleanup([n])
