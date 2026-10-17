import sys, time, random, os, json, subprocess, signal, statistics, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r48'); R = {}
n = Node(7148).start(); c = n.c()
N = 100000; PAY = 'x' * 64
print('== 一:内存:10 万条 64 字节消息,List vs Stream(未消费)')
c.do('DEL', 'L', 'S')
for i in range(0, N, 5000):
    c.pipeline([['LPUSH', 'L', PAY + '%06d' % (i + j)] for j in range(5000)])
    c.pipeline([['XADD', 'S', '*', 'p', PAY + '%06d' % (i + j)] for j in range(5000)])
ml, ms = c.do('MEMORY', 'USAGE', 'L', 'SAMPLES', 0), c.do('MEMORY', 'USAGE', 'S', 'SAMPLES', 0)
print(f'List   {ml:>9} B  ({ml/N:.1f} B/条)  encoding={c.do("OBJECT","ENCODING","L")}')
print(f'Stream {ms:>9} B  ({ms/N:.1f} B/条)  (每条含一个字段名 p)')
R['mem'] = [ml, ms]
print()
print('== 二:入队吞吐:管道 2000 条一批,写 20 万条,重复 3 次取中位')
def bench(mk, n_=200000):
    c.do('DEL', 'L', 'S'); t0 = time.perf_counter()
    for i in range(0, n_, 2000): c.pipeline([mk(i + j) for j in range(2000)])
    return n_ / (time.perf_counter() - t0)
for name, mk in (('LPUSH', lambda i: ['LPUSH', 'L', PAY]), ('XADD', lambda i: ['XADD', 'S', '*', 'p', PAY])):
    v = [bench(mk) for _ in range(3)]; print(f'{name:<6} {statistics.median(v)/1000:7.1f} k 条/秒 (三次: {", ".join(f"{x/1000:.0f}k" for x in v)})'); R.setdefault('tp', {})[name] = statistics.median(v)
print()
print('== 三:消费者崩溃:取出 5 条、处理到一半进程死掉(模拟为取出后不再处理)')
c.do('DEL', 'L', 'S', 'L:proc')
for i in range(1, 11): c.do('LPUSH', 'L', f'j{i}'); c.do('XADD', 'S', f'{i}-0', 'job', f'j{i}')
c.do('XGROUP', 'CREATE', 'S', 'g', '0')
got_l = [c.do('RPOP', 'L') for _ in range(5)]
got_s = [e[0] for e in c.do('XREADGROUP', 'GROUP', 'g', 'A', 'COUNT', 5, 'STREAMS', 'S', '>')[0][1]]
print('List:  RPOP 取出', got_l, '→ 崩溃后,这 5 条在 Redis 里还找得到吗?  LLEN =', c.do('LLEN', 'L'), '(只剩没取的 5 条)')
print('Stream: XREADGROUP 取出', got_s, '→ 崩溃后 XPENDING:')
sh(c, 'XPENDING', 'S', 'g')
print()
print('== 四:List 的"可靠队列"写法:LMOVE 到处理中列表,处理完 LREM')
c.do('DEL', 'L', 'L:proc')
for i in range(1, 6): c.do('LPUSH', 'L', f'j{i}')
got = [c.do('LMOVE', 'L', 'L:proc', 'RIGHT', 'LEFT') for _ in range(3)]
print('LMOVE 取出', got, ' 崩溃后 L:proc =', c.do('LRANGE', 'L:proc', 0, -1))
print('(要自己实现:超时检测、谁在处理、重试次数——Stream 的 PEL 里都有:消费者名、idle、delivery count)')
print()
print('== 五:多个消费方各读一份(扇出)与回看')
c.do('DEL', 'S'); [c.do('XADD', 'S', f'{i}-0', 'job', f'j{i}') for i in range(1, 6)]
c.do('XGROUP', 'CREATE', 'S', 'billing', '0'); c.do('XGROUP', 'CREATE', 'S', 'audit', '0')
for g in ('billing', 'audit'):
    r = c.do('XREADGROUP', 'GROUP', g, 'x', 'COUNT', 5, 'STREAMS', 'S', '>'); print(g, '读到', [e[0] for e in r[0][1]])
sh(c, 'XRANGE', 'S', '2-0', '3-0')
print('List 弹出即消失:同一条消息只能被一个消费者拿到,读过就不能回看')
print()
print('== 六:阻塞等待的延迟:消费者阻塞在 BRPOP / XREADGROUP BLOCK,生产者 500 次各发一条,量"发出→收到"')
def latency(kind, reps=500):
    lat = []; done = threading.Event(); ready = threading.Event()
    cc = n.c(timeout=20)
    if kind == 'x': cc.do('DEL', 'S2'); cc.do('XGROUP', 'CREATE', 'S2', 'g', '0', 'MKSTREAM')
    else: cc.do('DEL', 'L2')
    def consumer():
        cs = n.c(timeout=20); ready.set()
        for _ in range(reps):
            if kind == 'l':
                r = cs.do('BRPOP', 'L2', 5); tr = time.time(); ts = float(r[1])
            else:
                r = cs.do('XREADGROUP', 'GROUP', 'g', 'w', 'COUNT', 1, 'BLOCK', 5000, 'STREAMS', 'S2', '>')
                tr = time.time(); ts = float(r[0][1][0][1][1]); cs.do('XACK', 'S2', 'g', r[0][1][0][0])
            lat.append((tr - ts) * 1000)
        done.set()
    th = threading.Thread(target=consumer); th.start(); ready.wait(); time.sleep(0.1)
    for _ in range(reps):
        t = time.time()
        if kind == 'l': cc.do('LPUSH', 'L2', repr(t))
        else: cc.do('XADD', 'S2', '*', 't', repr(t))
        time.sleep(0.004)
    done.wait(30); th.join(); return lat
for k, name in (('l', 'LPUSH → BRPOP'), ('x', 'XADD → XREADGROUP BLOCK(不含 XACK)')):
    L = sorted(latency(k)); print(f'{name:<32} p50 {L[len(L)//2]:.3f} ms  p99 {L[int(len(L)*.99)]:.3f} ms  max {L[-1]:.3f} ms'); R.setdefault('lat', {})[k] = [L[len(L)//2], L[int(len(L)*.99)]]
save('r48', R); cleanup([n])
