import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r81'); R = {}
A = Node(7530, name='m81a').start(); B = Node(7531, name='m81b').start(); a, b = A.c(), B.c()
print('== 一:基本语义:MIGRATE 把 key 搬过去(源端删除),TTL 保留;COPY 不删源;目标已有同名 key 需要 REPLACE')
a.do('SET', 'k1', 'v1'); a.do('SET', 'k2', 'v2', 'EX', 100); a.do('RPUSH', 'l', 1, 2, 3); a.do('HSET', 'h', 'f', 'x'); a.do('ZADD', 'z', 1, 'm')
sh(a, 'MIGRATE', '127.0.0.1', 7531, 'k1', 0, 5000)
print('  源 EXISTS k1 =', a.do('EXISTS', 'k1'), ' 目标 GET k1 =', b.do('GET', 'k1'))
sh(a, 'MIGRATE', '127.0.0.1', 7531, 'k2', 0, 5000)
print('  目标 TTL k2 =', b.do('TTL', 'k2'), '(源上设的是 100 秒)')
sh(a, 'MIGRATE', '127.0.0.1', 7531, 'nosuch', 0, 5000)
sh(a, 'MIGRATE', '127.0.0.1', 7531, 'l', 0, 5000, 'COPY')
print('  COPY 之后:源 LLEN l =', a.do('LLEN', 'l'), ' 目标 LLEN l =', b.do('LLEN', 'l'))
sh(a, 'MIGRATE', '127.0.0.1', 7531, 'l', 0, 5000, 'COPY')
sh(a, 'MIGRATE', '127.0.0.1', 7531, 'l', 0, 5000, 'COPY', 'REPLACE')
sh(a, 'MIGRATE', '127.0.0.1', 7531, '', 0, 5000, 'KEYS', 'h', 'z')
print('  批量 KEYS:目标 HGETALL h =', b.do('HGETALL', 'h'), ' ZRANGE z =', b.do('ZRANGE', 'z', 0, -1))
print()
print('== 二:大 value 会阻塞源和目标:量另一个连接的 PING 停顿(1 ms 间隔探测)')
def probe(port, stop, out):
    c = C(port);
    while not stop.is_set():
        t = time.perf_counter(); c.do('PING'); d = (time.perf_counter() - t) * 1000; out.append((t, d)); time.sleep(0.001)
print(f'{"value 大小":>10} {"MIGRATE 耗时":>12} {"源上 PING 最大停顿":>16} {"目标上 PING 最大停顿":>17}')
R['big'] = []
for mb in (10, 100, 300):
    a.do('FLUSHALL'); b.do('FLUSHALL')
    a.do('SET', 'big', 'x' * (mb * 1024 * 1024))
    stop = threading.Event(); oa, ob = [], []
    ta = threading.Thread(target=probe, args=(7530, stop, oa)); tb = threading.Thread(target=probe, args=(7531, stop, ob)); ta.start(); tb.start(); time.sleep(0.3)
    t = time.perf_counter(); r = a.do('MIGRATE', '127.0.0.1', 7531, 'big', 0, 60000); dt = (time.perf_counter() - t) * 1000
    time.sleep(0.3); stop.set(); ta.join(); tb.join()
    ma = max(d for tt, d in oa if t - 0.05 <= tt <= t + dt / 1000 + 0.05); mb_ = max(d for tt, d in ob if t - 0.05 <= tt <= t + dt / 1000 + 0.05)
    print(f'{mb:>8} MB {dt:>10.0f} ms {ma:>14.0f} ms {mb_:>15.0f} ms   (返回 {r},目标 STRLEN = {b.do("STRLEN", "big")//1024//1024} MB)')
    R['big'].append(dict(mb=mb, ms=dt, src=ma, dst=mb_))
a.do('FLUSHALL'); b.do('FLUSHALL')
print()
print('== 三:批量 MIGRATE ... KEYS vs 逐个 MIGRATE:1000 个小 key')
for i in range(1000): a.do('SET', f'bk:{i}', 'v' * 100)
t = time.perf_counter()
for i in range(1000): a.do('MIGRATE', '127.0.0.1', 7531, f'bk:{i}', 0, 5000, 'COPY')
one = (time.perf_counter() - t) * 1000
b.do('FLUSHALL')
t = time.perf_counter(); a.do('MIGRATE', '127.0.0.1', 7531, '', 0, 5000, 'COPY', 'KEYS', *[f'bk:{i}' for i in range(1000)]); batch = (time.perf_counter() - t) * 1000
print(f'逐个 MIGRATE(1000 次调用):{one:.0f} ms;一次 MIGRATE ... KEYS(1000 个 key):{batch:.0f} ms;快 {one/batch:.1f} 倍;目标 DBSIZE = {b.do("DBSIZE")}')
R['batch'] = dict(one=one, batch=batch)
a.do('FLUSHALL'); b.do('FLUSHALL')
print()
print('== 四:目标卡住(SIGSTOP)时的 MIGRATE:超时、源上还有没有、解冻后目标有没有')
a.do('SET', 'k', 'important')
B.p.send_signal(signal.SIGSTOP); time.sleep(0.2)
t = time.perf_counter(); r = a.do('MIGRATE', '127.0.0.1', 7531, 'k', 0, 800, raise_err=False); dt = (time.perf_counter() - t) * 1000
print(f'MIGRATE(timeout 800 ms)→ {r},耗时 {dt:.0f} ms;此刻源上 EXISTS k = {a.do("EXISTS", "k")}')
B.p.send_signal(signal.SIGCONT); time.sleep(0.5)
b = B.c()
print(f'目标解冻后:EXISTS k = {b.do("EXISTS", "k")},GET = {b.do("GET", "k")};源上 EXISTS k = {a.do("EXISTS", "k")}')
R['freeze'] = dict(r=str(r), src=a.do('EXISTS', 'k'), dst=b.do('EXISTS', 'k'))
save('r81', R); cleanup([A, B])
