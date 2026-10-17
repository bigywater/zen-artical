import sys, os, time, json, re, threading, subprocess, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.queue import Queue, LockingQueue
tee('z82'); R = {}
n = Node('z82', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
print('== 一:kazoo 的 Queue 在服务端是什么:/q 下的顺序节点(前缀 entry-),入队 = 建节点,出队 = 读最小序号并删除')
q = Queue(z, '/q')
for i in range(5): q.put(f'job-{i}'.encode(), priority=100)
q.put(b'urgent', priority=10)
print('  /q 子节点:', sorted(z.get_children('/q')))
print('  取出顺序(priority 小的先出,同优先级先进先出):', [q.get().decode() for _ in range(6)])
R['order'] = ['urgent', 'job-0', 'job-1', 'job-2', 'job-3', 'job-4']
print('  队列空时 get() 返回:', q.get())
print()
print('== 二:Queue 是「取出即删除」:消费者取出后崩溃,这条消息就丢了。入队 200 条,3 个消费者,处理中途 kill -9 其中一个')
lf = ZDATA / 'z82' / 'cons.log'; lf.parent.mkdir(exist_ok=True)
CONS = str(HERE / 'procs' / 'qcons.py')
# 朴素队列:用 Queue.get 取出后「处理 0.05 s」才记完成,被 kill 时已取出未完成的就丢了
code = '''
import sys, os, time
sys.path.insert(0, %r)
from zkl import client
from kazoo.recipe.queue import Queue
z = client("127.0.0.1:7300", timeout=3); q = Queue(z, "/q2"); name = sys.argv[1]
while True:
    it = q.get()
    if it is None: time.sleep(0.02); continue
    open(sys.argv[2], "a").write(f"{time.time():.3f} {name} TAKE {it.decode()}\\n"); time.sleep(0.05)
    open(sys.argv[2], "a").write(f"{time.time():.3f} {name} DONE {it.decode()}\\n")
''' % str(HERE)
(ZDATA / 'z82' / 'naive.py').write_text(code); lf2 = ZDATA / 'z82' / 'naive.log'; lf2.write_text('')
qn = Queue(z, '/q2')
for i in range(200): qn.put(f'm{i:03d}'.encode())
ps = [subprocess.Popen([sys.executable, str(ZDATA / 'z82' / 'naive.py'), f'C{i}', str(lf2)]) for i in range(3)]
time.sleep(1.0); ps[0].kill()
t0 = time.time()
while time.time() - t0 < 30 and z.get_children('/q2'): time.sleep(0.2)
time.sleep(1)
for p in ps: p.kill()
L = [l.split() for l in lf2.read_text().splitlines()]; take = {l[3] for l in L if l[2] == 'TAKE'}; done = {l[3] for l in L if l[2] == 'DONE'}
lost = sorted(take - done)
print(f'  队列最终为空;200 条中被取出 {len(take)},处理完成 {len(done)},被取出但没有完成(被杀的消费者手里那条)= {lost}')
R['naive'] = dict(take=len(take), done=len(done), lost=lost)
print()
print('== 三:LockingQueue(取出时加锁,处理完才 consume 删除):消费者崩溃后,消息在会话过期后重新可见,被别的消费者处理')
lf.write_text('')
lq = LockingQueue(z, '/lq')
for i in range(30): lq.put(f'j{i:02d}'.encode())
ps = [subprocess.Popen([sys.executable, CONS, '7300', f'C{i}', '3', str(lf), '0.3']) for i in range(3)]
time.sleep(1.5); tk = time.time(); ps[0].kill()
t0 = time.time()
while time.time() - t0 < 40 and z.get_children('/lq/entries'): time.sleep(0.2)
time.sleep(0.5)
for p in ps: p.kill()
L = [l.split() for l in lf.read_text().splitlines()]
gots = collections.Counter(l[3] for l in L if l[2] == 'GOT'); acks = collections.Counter(l[3] for l in L if l[2] == 'ACK')
dup = sorted(k for k, v in gots.items() if v > 1); noack = sorted(set(gots) - set(acks))
print(f'  30 条:被取出的消息数 {len(gots)},被确认 {len(acks)};被取出了 2 次的:{dup};取出却没确认的:{noack}')
for k in dup:
    ev = [(float(l[0]) - tk, l[1], l[2]) for l in L if l[3] == k]; print('   ', k, [f'{t:+.1f}s {c} {a}' for t, c, a in ev])
R['locking'] = dict(got=len(gots), ack=len(acks), dup=dup, noack=noack, dup_events=[[(round(float(l[0]) - tk, 1), l[1], l[2]) for l in L if l[3] == k] for k in dup])
print()
print('== 四:队列吞吐:单个生产者、单个消费者,Queue 与 LockingQueue 各 300 条')
def bench(cls, path):
    qq = cls(z, path); t0 = time.time()
    for i in range(300): qq.put(b'x' * 100)
    tp = time.time() - t0; t0 = time.time(); k = 0
    while k < 300:
        it = qq.get(timeout=1) if cls is LockingQueue else qq.get()
        if it is None: break
        if cls is LockingQueue: qq.consume()
        k += 1
    return 300 / tp, 300 / (time.time() - t0)
a = bench(Queue, '/bq'); b = bench(LockingQueue, '/blq')
print(f'  Queue:入队 {a[0]:.0f} 条/s,出队 {a[1]:.0f} 条/s;LockingQueue:入队 {b[0]:.0f} 条/s,出队+确认 {b[1]:.0f} 条/s')
R['bench'] = dict(q_put=a[0], q_get=a[1], lq_put=b[0], lq_get=b[1])
print('  /bq 里的单条消息大小限制:ZooKeeper 默认每个 znode ≤ 1 MiB(见第 1 篇);队列里所有未消费的消息都在内存与快照里(第 10 篇)')
z.stop(); n.stop(); save('z82', R)
