import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r66'); R = {}
def pct(L, p): L = sorted(L); return L[min(len(L) - 1, int(len(L) * p))]
def loop(c, N, dur=None, until=None, rnd=None):
    """同步 SET(随机覆盖已有 key,会触发写时复制);返回 [(t, 延迟µs)]"""
    S = []; rnd = rnd or random.Random(7)
    while True:
        t = time.perf_counter()
        if dur is not None and t - loop.t0 > dur: break
        if until is not None and until(): break
        c.do('SET', f'key:{rnd.randrange(N)}', 'w' * 100); S.append((t, (time.perf_counter() - t) * 1e6))
    return S
def run(N, port):
    n = Node(port, name=f'p66_{N}', conf={'save': '""'}).start(); c = n.c()
    for i in range(0, N, 5000): c.pipeline([['SET', f'key:{i+j}', 'v' * 100] for j in range(5000)])
    used = int(info(c, 'memory')['used_memory'])
    loop.t0 = time.perf_counter(); base = loop(c, N, dur=2.0)
    w = n.c(); done = {}
    def bg():
        time.sleep(0.5); done['t0'] = time.perf_counter(); w.do('BGSAVE')
        while info(w, 'persistence')['rdb_bgsave_in_progress'] == '1': time.sleep(0.005)
        done['t1'] = time.perf_counter()
    th = threading.Thread(target=bg); th.start()
    loop.t0 = time.perf_counter(); S = loop(c, N, until=lambda: 't1' in done and time.perf_counter() - done['t1'] > 0.3)
    th.join()
    dur = [l for t, l in S if done['t0'] <= t <= done['t1']]
    st = info(c, 'stats'); ps = info(c, 'persistence')
    r = dict(N=N, used=used, base=[len(base), pct([l for t, l in base], .5), pct([l for t, l in base], .99), max(l for t, l in base)],
             dur=[len(dur), pct(dur, .5), pct(dur, .99), max(dur)], fork_us=int(st['latest_fork_usec']), bgsave_s=done['t1'] - done['t0'], cow=int(ps['rdb_last_cow_size']))
    cleanup([n]); return r
print('== 一:BGSAVE 的 fork 停顿与写时复制(COW),不同数据集大小(单客户端持续随机覆盖写)')
print(f'{"key 数":>9} {"内存 MB":>8} {"fork µs":>9} {"BGSAVE 耗时":>10} | {"基线 p50":>8} {"基线 max":>9} | {"期间 p50":>8} {"期间 p99":>8} {"期间 max":>9} | {"COW MB":>7}')
rows = []
for i, N in enumerate((100000, 1000000, 3000000)):
    r = run(N, 7260 + i); rows.append(r)
    print(f'{N:>9} {r["used"]/1e6:>8.0f} {r["fork_us"]:>9} {r["bgsave_s"]:>9.2f}s | {r["base"][1]:>8.0f} {r["base"][3]:>9.0f} | {r["dur"][1]:>8.0f} {r["dur"][2]:>8.0f} {r["dur"][3]:>9.0f} | {r["cow"]/1e6:>7.1f}')
R['rows'] = rows
print()
print('说明:fork µs 来自 INFO stats 的 latest_fork_usec;COW MB 来自 INFO persistence 的 rdb_last_cow_size;延迟单位 µs。')
save('r66', R)
