import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r64'); R = {}
here = os.path.dirname(os.path.abspath(__file__))
modes = ['always', 'everysec', 'no']
print('== 一:一个客户端,同步 SET(每条等回复),3000 条的延迟分布')
print(f'{"appendfsync":<12} {"p50 µs":>9} {"p99 µs":>9} {"max µs":>9} {"平均 µs":>9}')
R['seq'] = {}
for i, m in enumerate(modes):
    n = Node(7240 + i, name=f'p64_{m}', conf={'appendonly': 'yes', 'appendfsync': m}).start(); c = n.c()
    for _ in range(200): c.do('SET', 'w', 1)
    L = []
    for j in range(3000):
        t = time.perf_counter(); c.do('SET', f'k{j}', 'x' * 64); L.append((time.perf_counter() - t) * 1e6)
    L.sort(); r = dict(p50=L[1500], p99=L[2970], mx=L[-1], mean=sum(L) / len(L)); R['seq'][m] = r
    print(f'{m:<12} {r["p50"]:>9.0f} {r["p99"]:>9.0f} {r["mx"]:>9.0f} {r["mean"]:>9.0f}')
    R.setdefault('delayed', {})[m] = info(c, 'persistence')['aof_delayed_fsync']
    cleanup([n])
print()
print('== 二:管道写入吞吐(2000 条一批,共 20 万条)')
R['pipe'] = {}
for i, m in enumerate(modes):
    n = Node(7243 + i, name=f'p64p_{m}', conf={'appendonly': 'yes', 'appendfsync': m}).start(); c = n.c()
    t = time.perf_counter()
    for k in range(0, 200000, 2000): c.pipeline([['SET', f'k{k+j}', 'x' * 64] for j in range(2000)])
    dt = time.perf_counter() - t; R['pipe'][m] = 200000 / dt
    print(f'{m:<12} {200000/dt/1000:8.0f}k 条/秒')
    cleanup([n])
print()
print('== 三:多个客户端(独立进程,各自同步 SET)同时写:1 个 vs 8 个客户端的总吞吐')
R['multi'] = {}
print(f'{"appendfsync":<12} {"1 客户端":>12} {"8 客户端":>12} {"放大倍数":>8}')
for i, m in enumerate(modes):
    n = Node(7246 + i, name=f'p64m_{m}', conf={'appendonly': 'yes', 'appendfsync': m}).start()
    cnt = 1500 if m == 'always' else 6000
    def run(k):
        ps = [subprocess.Popen([sys.executable, os.path.join(here, 'w64.py'), str(7246 + i), str(cnt), f'c{j}'], stdout=subprocess.PIPE, text=True) for j in range(k)]
        ts = [float(p.communicate()[0]) for p in ps]; return k * cnt / max(ts)
    a, b = run(1), run(8); R['multi'][m] = [a, b]
    print(f'{m:<12} {a:>10.0f}/s {b:>10.0f}/s {b/a:>8.1f}')
    cleanup([n])
print()
print('== 四:INFO persistence 的 aof_delayed_fsync(fsync 太慢导致写入被延迟的次数)')
print(R['delayed'])
save('r64', R)
