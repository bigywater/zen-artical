import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z47'); R = {}
e = NetEnsemble('z47', 3, base=7300, conf={'tickTime': 500, 'syncLimit': 2, 'initLimit': 4}).start(); ld = e.leader(); maj = [n for n in e.nodes if n is not ld]
tl = []; stop = threading.Event(); t0 = [0.0]
def poll():
    last = {}
    while not stop.is_set():
        for n in e.nodes:
            m = n.mode() or '不服务'
            if last.get(n.name) != m: tl.append((time.perf_counter() - t0[0], n.name, m)); last[n.name] = m
        time.sleep(0.1)
th = threading.Thread(target=poll); t0[0] = time.perf_counter(); th.start(); time.sleep(1)
print(f'== 一:把 leader({ld.name})单独隔离(节点间通信悄悄丢包,连接不断,客户端端口不受影响),观察各节点的角色变化')
tp = time.perf_counter() - t0[0]; e.partition([ld.myid], [n.myid for n in maj]); time.sleep(8); th_ = time.perf_counter() - t0[0]
e.heal(); time.sleep(8); stop.set(); th.join()
for t, nm, m in tl: print(f'  +{(t - tp) * 1000:>7.0f} ms  {nm} → {m}')
R['timeline'] = [(round((t - tp) * 1000), nm, m) for t, nm, m in tl]
print(f'  (隔离发生在 +0 ms;恢复网络在 +{(th_ - tp) * 1000:.0f} ms)')
print()
print('== 二:隔离期间两侧的写入:分区前就连在当前 leader 上的客户端 vs 多数派一侧的客户端')
ld = e.leader(); maj = [n for n in e.nodes if n is not ld]; print(f'  当前 leader = {ld.name}(被隔离的就是它)')
zi = client(f'127.0.0.1:{ld.cport}', timeout=20); zm = client(','.join(f'127.0.0.1:{n.cport}' for n in maj), timeout=20)
e.partition([ld.myid], [n.myid for n in maj])
res = zi.create_async('/from-isolated', b'x'); t1 = time.perf_counter()
from kazoo.retry import KazooRetry
try: KazooRetry(max_tries=30, delay=0.1, max_delay=0.5)(zm.create, '/from-majority', b'y'); okm = '成功(带重试)'
except Exception as ex: okm = type(ex).__name__
tm = (time.perf_counter() - t1) * 1000
print(f'  多数派一侧的客户端 create /from-majority:{okm}(分区后 {tm:.0f} ms 完成,含故障检测与重新选举)')
time.sleep(3); print('  被隔离的旧 leader 上的那次 create /from-isolated,3 秒后:ready =', res.ready())
R['write'] = dict(majority=okm, majority_ms=tm, isolated_ready=res.ready())
e.heal(); time.sleep(10)
try: r = res.get(timeout=5); ri = '成功'
except Exception as ex: ri = type(ex).__name__
print('  网络恢复后,被隔离侧那次 create 的结果:', ri); R['isolated_result'] = ri
z = client(e.hosts()); print('  恢复后读两个路径:/from-majority →', z.exists('/from-majority') is not None, '| /from-isolated →', z.exists('/from-isolated') is not None); R['final'] = dict(maj=z.exists('/from-majority') is not None, iso=z.exists('/from-isolated') is not None)
print('  各节点 Mode:', {n.name: n.mode() for n in e.nodes}, '| Zxid:', {n.name: n.srvr().get('zxid') for n in e.nodes})
zi.stop(); zm.stop(); z.stop(); e.stop(); save('z47', R)
