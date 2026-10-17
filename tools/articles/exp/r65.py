import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r65'); R = {}
N = 2000000
def pct(L, p): L = sorted(L); return L[min(len(L) - 1, int(len(L) * p))]
def trial(fsync, onrw, port):
    n = Node(port, name=f'p65_{fsync}_{onrw}', conf={'appendonly': 'yes', 'appendfsync': fsync, 'no-appendfsync-on-rewrite': onrw, 'auto-aof-rewrite-percentage': '0'}).start(); c = n.c()
    for i in range(0, N, 5000): c.pipeline([['SET', f'k{i+j}', 'v' * 40] for j in range(5000)])
    time.sleep(1.5)
    ev = {}
    def trigger():
        cc = n.c(); time.sleep(1.0); ev['start'] = time.perf_counter(); cc.do('BGREWRITEAOF')
        while True:
            if info(cc, 'persistence')['aof_rewrite_in_progress'] == '0' and time.perf_counter() - ev['start'] > 0.05: break
            time.sleep(0.005)
        ev['end'] = time.perf_counter()
    th = threading.Thread(target=trigger); th.start()
    S = []; t0 = time.perf_counter()
    while 'end' not in ev or time.perf_counter() - ev['end'] < 1.0:
        t = time.perf_counter(); c.do('SET', f'w{len(S)}', 'x' * 40); S.append((t, (time.perf_counter() - t) * 1e6))
    th.join()
    pre = [l for t, l in S if t < ev['start']]; dur = [l for t, l in S if ev['start'] <= t <= ev['end']]; post = [l for t, l in S if t > ev['end']]
    res = dict(rw=ev['end'] - ev['start'], pre=[len(pre), pct(pre, .5), pct(pre, .99), max(pre)], dur=[len(dur), pct(dur, .5), pct(dur, .99), max(dur)], post=[len(post), pct(post, .5), pct(post, .99), max(post)])
    cleanup([n]); return res
print(f'== 一:{N} 个 key 的实例,单客户端同步 SET 不停地写,中途 BGREWRITEAOF;按「重写前 / 重写中 / 重写后」分段统计每条 SET 的延迟(µs)')
print(f'{"appendfsync":<10} {"on-rewrite":<10} {"轮":>2} {"重写耗时":>8}  {"阶段":<4} {"条数":>6} {"p50":>8} {"p99":>8} {"max":>9}')
i = 0
for rnd in (1, 2):
    for fs, onrw in (('always', 'no'), ('always', 'yes'), ('everysec', 'no'), ('everysec', 'yes')):
        r = trial(fs, onrw, 7250 + i); i += 1; R.setdefault(f'{fs}_{onrw}', []).append(r)
        for ph, nm in (('pre', '前'), ('dur', '中'), ('post', '后')):
            v = r[ph]; print(f'{fs:<10} {onrw:<10} {rnd:>2} {r["rw"]:>7.2f}s  {nm:<4} {v[0]:>6} {v[1]:>8.0f} {v[2]:>8.0f} {v[3]:>9.0f}')
save('r65', R)
