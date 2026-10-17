import sys, os, time, json, re, threading, subprocess, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.lock import Lock
tee('z79'); R = {}
n = Node('z79', 7300, xmx=256, conf={'maxClientCnxns': 1000, 'tickTime': 1000}).start(); admin = client('127.0.0.1:7300')
admin.create('/counter', b'0')
print('== 一:互斥:10 个客户端各自「读计数器 → 加 1 → 写回」20 次(共 200 次),有锁 vs 没有锁')
def run(use_lock):
    admin.set('/counter', b'0'); ths = []; cl = [client('127.0.0.1:7300') for _ in range(10)]
    def work(i):
        c = cl[i]; lk = Lock(c, '/lock', f'c{i}')
        for _ in range(20):
            if use_lock: lk.acquire()
            v = int(c.get('/counter')[0]); c.set('/counter', str(v + 1).encode())
            if use_lock: lk.release()
    t0 = time.perf_counter(); ths = [threading.Thread(target=work, args=(i,)) for i in range(10)]; [t.start() for t in ths]; [t.join() for t in ths]; el = time.perf_counter() - t0
    final = int(admin.get('/counter')[0]); [c.stop() for c in cl]; return final, el
a, ta = run(False); b, tb = run(True)
print(f'  没有锁:最终 {a} / 期望 200(丢失 {200 - a} 次更新),用时 {ta:.1f} s'); print(f'  有锁:  最终 {b} / 期望 200,用时 {tb:.1f} s'); R['mutex'] = dict(nolock=a, lock=b, t_no=ta, t_lock=tb)
print()
print('== 二:锁在 ZooKeeper 里的样子:持有者与排队者都是 /lock 下的「临时 + 顺序」节点;每个排队者只监听它前面那一个(不会惊群)')
holders = [client('127.0.0.1:7300') for _ in range(6)]; locks = [Lock(c, '/lock2', f'w{i}') for i, c in enumerate(holders)]
locks[0].acquire(); ths = [threading.Thread(target=lambda l=l: l.acquire()) for l in locks[1:]]; [t.start() for t in ths]; time.sleep(1)
print('  /lock2 的子节点(按序号;名字是 <客户端 uuid>__lock__<10 位序号>):', sorted([x[:6] + '…' + x[-18:] for x in admin.get_children('/lock2')], key=lambda y: y[-10:])); print('  服务端的 watch:', ' '.join(four(7300, 'wchs').split())); R['nodes'] = sorted(x[:6] + '…' + x[-18:] for x in admin.get_children('/lock2'))
R['wchs'] = ' '.join(four(7300, 'wchs').split())
locks[0].release(); time.sleep(0.5); print('  持有者释放后,下一个排队者拿到了锁;/lock2 的子节点数 =', len(admin.get_children('/lock2')))
for l in locks[1:]:
    try: l.release()
    except Exception: pass
[t.join(5) for t in ths]; [c.stop() for c in holders]
print()
print('== 三:惊群对照:30 个排队者,每次释放产生多少请求?kazoo 的锁(各监听前一个)vs 朴素做法(所有人 watch 父节点,变化后全部重新 get_children)')
def herd(naive, N=30):
    cl = [client('127.0.0.1:7300') for _ in range(N + 1)]; path = '/herd-naive' if naive else '/herd-kazoo'; admin.ensure_path(path)
    if naive:
        got = []; lock = threading.Lock(); my = {}
        def contend(i):
            c = cl[i]; node = c.create(f'{path}/n-', b'', ephemeral=True, sequence=True); my[i] = node.rsplit('/', 1)[1]
            while True:
                ev = threading.Event(); kids = sorted(c.get_children(path, watch=lambda e: ev.set()))
                if kids[0] == my[i]: got.append(i); return
                ev.wait(30)
        ths = [threading.Thread(target=contend, args=(i,), daemon=True) for i in range(N)]; [t.start() for t in ths]; time.sleep(2)
        p0 = int(kv(four(7300, 'mntr'))['zk_packets_received']); t0 = time.perf_counter(); first = cl[0]
        for rnd in range(5):
            holder = got[-1]; cl[holder].delete(f'{path}/{my[holder]}'); time.sleep(0.5)
        p1 = int(kv(four(7300, 'mntr'))['zk_packets_received']); res = (p1 - p0) / 5
    else:
        locks = [Lock(cl[i], path, f'c{i}') for i in range(N)]; order = []
        def contend(i): locks[i].acquire(); order.append(i)
        locks[0].acquire(); order.append(0); ths = [threading.Thread(target=contend, args=(i,), daemon=True) for i in range(1, N)]; [t.start() for t in ths]; time.sleep(2)
        p0 = int(kv(four(7300, 'mntr'))['zk_packets_received'])
        for rnd in range(5): holder = order[-1]; locks[holder].release(); time.sleep(0.5)
        p1 = int(kv(four(7300, 'mntr'))['zk_packets_received']); res = (p1 - p0) / 5
    for c in cl:
        try: c.stop()
        except Exception: pass
    return res
k_ = herd(False); nv = herd(True)
print(f'  每次释放,服务端多收到的请求包:kazoo 锁 {k_:.0f} 个;朴素做法(30 人 watch 父节点){nv:.0f} 个'); R['herd'] = dict(kazoo=k_, naive=nv)
print()
print('== 四:持有者崩溃:持有锁的进程被 kill -9(会话超时 3 s),排队者什么时候拿到锁')
lf = ZDATA / 'z79' / 'lock.log'; lf.write_text('') if lf.exists() else (lf.parent.mkdir(exist_ok=True), lf.write_text(''))
a = subprocess.Popen([sys.executable, str(HERE / 'procs' / 'lockproc.py'), '7300', 'A', '3', str(lf), '300']); time.sleep(2)
b = client('127.0.0.1:7300', timeout=3); lb = Lock(b, '/lk', 'B'); tk = time.time(); a.kill(); lb.acquire(); tg = time.time(); print(f'  kill -9 后 {tg - tk:.1f} s,B 拿到了锁(会话超时 3 s)'); R['crash'] = tg - tk; lb.release(); b.stop()
print()
print('== 五:持有者被冻结(GC 长停顿)超过会话超时:锁被别人拿走,冻结的进程醒来还以为自己有锁')
lf.write_text(''); a = subprocess.Popen([sys.executable, str(HERE / 'procs' / 'lockproc.py'), '7300', 'A', '3', str(lf), '9']); time.sleep(2)
a.send_signal(signal.SIGSTOP); b = client('127.0.0.1:7300', timeout=3); lb = Lock(b, '/lk', 'B'); lb.acquire(); tb = time.time(); print('  A 被冻结;B 拿到了锁'); a.send_signal(signal.SIGCONT); time.sleep(8); a.wait(20)
print('  A 醒来后的日志(时间顺序):'); L = [l.strip().split(' ', 1)[1] for l in lf.read_text().splitlines()]; [print('   ', l) for l in L]; R['frozen'] = L
print('  fencing token:锁节点的 czxid 单调递增,可以让被保护的资源拒绝旧 token(第 4 步的实现留给应用)'); lb.release(); b.stop()
admin.stop(); n.stop(); save('z79', R)
