import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r50'); R = {}
n = Node(7150).start(); c = n.c()
print('== 一:消费者都离线时发 100 条,之后再上线')
c.do('XGROUP', 'CREATE', 's', 'g1', '0', 'MKSTREAM')
for i in range(100):
    c.do('PUBLISH', 'chan', i); c.do('XADD', 's', '*', 'i', i)
subs = [C(7150) for _ in range(3)]
for s in subs: s.do('SUBSCRIBE', 'chan')
got_ps = sum(1 for s in subs if s.avail(0.2))
print(f'Pub/Sub:3 个订阅者上线后 0.2 秒内,{got_ps} 个收到了东西(离线期间的 100 条不会补发)')
r = c.do('XREADGROUP', 'GROUP', 'g1', 'w1', 'COUNT', 1000, 'STREAMS', 's', '>')
print(f'Stream:消费组上线后 XREADGROUP 一次读到 {len(r[0][1])} 条(全部积压)')
R['offline'] = [got_ps, len(r[0][1])]
print()
print('== 二:发布 10 万条消息之后,Redis 里还留着多少内存')
m0 = used_mem(c)
for i in range(0, 100000, 5000): c.pipeline([['PUBLISH', 'chan2', 'x' * 100] for _ in range(5000)])
m1 = used_mem(c)
c.do('DEL', 's2')
for i in range(0, 100000, 5000): c.pipeline([['XADD', 's2', '*', 'p', 'x' * 100] for _ in range(5000)])
m2 = used_mem(c)
print(f'PUBLISH 10 万条(无订阅者):used_memory 变化 {m1-m0:+d} B')
print(f'XADD 10 万条:used_memory 变化 {m2-m1:+d} B  ({(m2-m1)/100000:.1f} B/条)')
R['mem'] = [m1 - m0, m2 - m1]
print()
print('== 三:一条 PUBLISH 要发给 N 个订阅者:同步往返耗时(每种 N 测 1000 次,取中位)')
for s in subs: s.close()
R['pub'] = []
def lat(cmd, k=1000):
    L = []
    for _ in range(k):
        t = time.perf_counter(); c.do(*cmd); L.append((time.perf_counter() - t) * 1e6)
    return statistics.median(L)
print(f'{"订阅者数 N":>10} {"PUBLISH 中位":>13} {"XADD 中位(对照)":>16}')
here = os.path.dirname(os.path.abspath(__file__))
for N in (0, 10, 100, 1000, 5000):
    p = None
    if N:
        p = subprocess.Popen([sys.executable, os.path.join(here, 'subs.py'), '7150', str(N), 'chan3'], stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(0.5)
    pu = lat(['PUBLISH', 'chan3', 'hello']); x = lat(['XADD', 's3', '*', 'v', 'hello'])
    ns = c.do('PUBSUB', 'NUMSUB', 'chan3')[1]
    print(f'{N:>10} {pu:>10.1f} µs {x:>13.1f} µs   (PUBSUB NUMSUB = {ns})'); R['pub'].append([N, pu, x])
    if p: p.kill(); p.wait(); time.sleep(0.5)
print()
print('== 四:语义:Pub/Sub 每个订阅者都收到;Stream 一个组内只有一个消费者收到')
a = [C(7150) for _ in range(3)]
for s in a: s.do('SUBSCRIBE', 'chan4')
c.do('PUBLISH', 'chan4', 'm1')
print('Pub/Sub 3 个订阅者:', [s.read()[2] if s.avail(0.3) else None for s in a])
c.do('XGROUP', 'CREATE', 's4', 'g', '0', 'MKSTREAM'); c.do('XADD', 's4', '*', 'v', 'm1')
print('Stream 同组 3 个消费者:', [ (lambda r: r[0][1][0][1][1] if r else None)(c.do('XREADGROUP', 'GROUP', 'g', w, 'COUNT', 1, 'STREAMS', 's4', '>')) for w in ('a', 'b', 'c')])
save('r50', R); cleanup([n])
