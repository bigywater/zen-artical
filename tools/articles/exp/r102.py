import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r102'); R = {}
n = Node(8060, name='r102').start()
print('== 一:往返时间(RTT)决定同步请求的上限;管道把 N 条命令合成一次往返。单向延迟 0 / 0.5 / 2 ms,共 5000 条 SET,每格 3 次取中位')
print(f'{"RTT":>8} {"同步(1 条/次)":>15} {"管道 10":>10} {"管道 100":>10} {"管道 1000":>11}   (单位:条/秒)')
R['t'] = {}
for d in (0, 0.5, 2):
    pr = DelayProxy(8061, 8060, d) if d else None
    port = 8061 if d else 8060
    row = []
    for b in (1, 10, 100, 1000):
        v = []
        for _ in range(3):
            c = C(port); N = 5000 if d else 20000; N = min(N, 2000) if (b == 1 and d) else N
            t = time.perf_counter()
            for i in range(0, N, b):
                if b == 1: c.do('SET', f'k{i}', i)
                else: c.pipeline([['SET', f'k{i+j}', i] for j in range(b)])
            v.append(N / (time.perf_counter() - t)); c.close()
        row.append(statistics.median(v))
    R['t'][str(d)] = row
    print(f'{2*d:>6.1f}ms {row[0]:>15.0f} {row[1]:>10.0f} {row[2]:>10.0f} {row[3]:>11.0f}')
    if pr: pr.close()
print()
print('== 二:管道不是事务:客户端 A 发 2000 条 INCR 的管道,客户端 B 同时反复 GET 这个计数器 —— B 能看到中间值')
c0 = n.c(); c0.do('SET', 'cnt', 0)
seen = []; stop = threading.Event()
def reader():
    cb = n.c()
    while not stop.is_set(): seen.append(int(cb.do('GET', 'cnt')))
th = threading.Thread(target=reader); th.start(); time.sleep(0.05)
ca = n.c()
for _ in range(20): ca.pipeline([['INCR', 'cnt'] for _ in range(2000)])
stop.set(); th.join()
mid = sorted(set(x for x in seen if x % 2000 != 0))
print(f'  A 共发了 20 个管道(每个 2000 条 INCR),B 读到 {len(seen)} 次,其中 {sum(1 for x in seen if x % 2000 != 0)} 次读到的值不是 2000 的整数倍(即某个管道执行到一半);例如 {mid[:5]}')
R['mid'] = dict(n=len(seen), mid=sum(1 for x in seen if x % 2000 != 0))
print()
print('== 三:管道里某条命令出错,其它命令照常执行,回复按顺序返回(错误也在对应位置)')
r = ca.pipeline([['SET', 'a', 1], ['LPUSH', 'a', 'x'], ['INCR', 'a'], ['GET', 'a']])
print('  ', r)
R['err'] = [str(x) for x in r]
save('r102', R); cleanup([n])
