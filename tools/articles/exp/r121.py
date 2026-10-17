import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r121'); R = {}
n = Node(8300, name='r121', conf={'enable-debug-command': 'yes'}).start(); c = n.c()
N = 100000
for i in range(0, N, 20000): c.pipeline([['SET', f'k:{i+j}', 'v' * 50] for j in range(20000)])
rnd = random.Random(7)
# 一份固定的、带热点的操作序列:key 服从 Zipf(s≈1.1)近似,读 80% / 写 15% / hash 5%
weights = [1 / (i + 1) ** 1.1 for i in range(N)]; cum = []; t_ = 0
for w in weights: t_ += w; cum.append(t_)
import bisect
def key(): return f'k:{bisect.bisect_left(cum, rnd.random() * t_)}'
ops = []
for _ in range(300000):
    r = rnd.random(); k = key()
    ops.append(['GET', k] if r < 0.80 else (['SET', k, 'v' * 50] if r < 0.95 else ['HSET', 'h:' + k, 'f', 'v']))
cnt = collections.Counter(o[1] for o in ops)
print(f'== 一:负载:Zipf 热点 + 80% GET / 15% SET / 5% HSET;最热 key {cnt.most_common(1)[0]},前 10 个 key 占全部请求的 {sum(v for _, v in cnt.most_common(10))/len(ops)*100:.0f}%')
DUR = 10.0; RATE = 5000
def stalls():
    for t in (2.0, 5.0, 8.0):
        time.sleep(max(0, t0 - time.perf_counter() + t)); n.c().do('DEBUG', 'SLEEP', 0.3)
def pct(L, p): L = sorted(L); return L[min(len(L) - 1, int(len(L) * p))]
def run(mode):
    global t0
    cc = n.c(); lat_intended = []; lat_actual = []; i = 0
    t0 = time.perf_counter(); th = threading.Thread(target=stalls); th.start()
    while time.perf_counter() - t0 < DUR:
        if mode == 'open':
            intended = t0 + i / RATE
            while time.perf_counter() < intended: pass
        else: intended = time.perf_counter()
        t = time.perf_counter(); cc.do(*ops[i % len(ops)]); e = time.perf_counter()
        lat_actual.append((e - t) * 1000); lat_intended.append((e - intended) * 1000); i += 1
    th.join(); return i, lat_actual, lat_intended
print()
print(f'== 二:同一个 {DUR:.0f} 秒的测试,在第 2、5、8 秒各让服务器阻塞 300 ms(DEBUG SLEEP 0.3)。三种测量方式:')
print(f'{"测量方式":<32} {"请求数":>8} {"p50 ms":>8} {"p99 ms":>8} {"p99.9 ms":>9} {"max ms":>8} {">100ms 的请求数":>14}')
R['rows'] = {}
for name, mode, which in (('闭环(发一条等一条),从实际发送算', 'closed', 1), ('开环(固定 5000/s),从实际发送算', 'open', 1), ('开环(固定 5000/s),从「应该发送」的时刻算', 'open', 2)):
    i, la, li = run(mode); L = la if which == 1 else li
    row = dict(n=i, p50=pct(L, .5), p99=pct(L, .99), p999=pct(L, .999), mx=max(L), slow=sum(1 for x in L if x > 100)); R['rows'][name] = row
    print(f'{name:<28} {i:>8} {row["p50"]:>8.3f} {row["p99"]:>8.2f} {row["p999"]:>9.1f} {row["mx"]:>8.0f} {row["slow"]:>14}')
    time.sleep(1)
save('r121', R); cleanup([n])
