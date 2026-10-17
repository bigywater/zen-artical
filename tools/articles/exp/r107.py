import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r107'); R = {}
def diskload(stop, path):
    buf = os.urandom(4 * 1024 * 1024)
    with open(path, 'wb') as f:
        while not stop.is_set():
            f.write(buf); f.flush(); os.fsync(f.fileno())
            if f.tell() > 2 * 1024 ** 3: f.seek(0)
def case(fsync, load, port):
    n = Node(port, name=f'r107_{fsync}_{load}', conf={'appendonly': 'yes', 'appendfsync': fsync}).start(); c = n.c()
    stop = threading.Event(); th = None
    if load: th = threading.Thread(target=diskload, args=(stop, str(n.dir / 'diskload.bin'))); th.start(); time.sleep(1.0)
    L = []; t_end = time.perf_counter() + 8
    while time.perf_counter() < t_end:
        t = time.perf_counter(); c.do('SET', 'k', 'x' * 100); L.append((time.perf_counter() - t) * 1000)
    ip = info(c, 'persistence'); stop.set()
    if th: th.join()
    L.sort(); r = dict(n=len(L), p50=L[len(L) // 2], p99=L[int(len(L) * .99)], p999=L[int(len(L) * .999)], mx=L[-1], delayed=int(ip['aof_delayed_fsync']))
    cleanup([n]); time.sleep(1); return r
print('== 一:磁盘被另一个进程的大量 fsync 写入占满时,单客户端同步 SET(8 秒)的延迟')
print(f'{"appendfsync":<10} {"磁盘负载":<8} {"条数":>7} {"p50 ms":>8} {"p99 ms":>8} {"p99.9 ms":>9} {"max ms":>8} {"aof_delayed_fsync":>18}')
R['c'] = []
for k, (fs, ld) in enumerate((('everysec', False), ('everysec', True), ('always', False), ('always', True))):
    r = case(fs, ld, 8130 + k); R['c'].append((fs, ld, r))
    print(f'{fs:<10} {"有" if ld else "无":<8} {r["n"]:>7} {r["p50"]:>8.3f} {r["p99"]:>8.3f} {r["p999"]:>9.2f} {r["mx"]:>8.1f} {r["delayed"]:>18}')
print()
print('== 二:lazyfree 任务:UNLINK 大对象之后,INFO 里 lazyfree_pending_objects 与 lazyfreed_objects 的变化')
n = Node(8140, name='r107b').start(); c = n.c()
for i in range(0, 2000000, 20000): c.pipeline([['SADD', 'big'] + [f'm{i+j}' for j in range(20000)]])
c.do('UNLINK', 'big'); rows = []
for _ in range(6):
    m = info(c, 'memory'); rows.append((m['lazyfree_pending_objects'], m['lazyfreed_objects'])); time.sleep(0.02)
print('  UNLINK 之后每 ~20 ms 采样 (lazyfree_pending_objects, lazyfreed_objects):', rows); R['lf'] = rows
save('r107', R); cleanup([n])
