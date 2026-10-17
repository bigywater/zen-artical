import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z48'); R = {}
e = NetEnsemble('z48', 5, base=7300, conf={'tickTime': 500, 'syncLimit': 2, 'initLimit': 4}).start(); ld = e.leader()
f1 = e.followers()[0]; minority = [ld, f1]; majority = [n for n in e.nodes if n not in minority]
print(f'== 一:5 个节点分成 {{{ld.myid},{f1.myid}}}(含 leader {ld.name})和 {{{",".join(str(n.myid) for n in majority)}}} 两半(悄悄丢包)。每 100 ms 采样每个节点的 Mode,看有没有同时出现两个 leader')
samples = []; stop = threading.Event()
def poll():
    while not stop.is_set():
        row = {n.name: (n.mode() or '不服务') for n in e.nodes}; samples.append((time.perf_counter(), row)); time.sleep(0.1)
zm = client(','.join(f'127.0.0.1:{n.cport}' for n in majority), timeout=20); zn = client(f'127.0.0.1:{ld.cport}', timeout=20)
th = threading.Thread(target=poll); th.start(); time.sleep(1); t0 = time.perf_counter()
e.partition([n.myid for n in minority], [n.myid for n in majority])
resn = zn.create_async('/from-minority', b'x')
from kazoo.retry import KazooRetry
t1 = time.perf_counter()
try: KazooRetry(max_tries=40, delay=0.1, max_delay=0.5)(zm.create, '/from-majority', b'y'); okm = '成功'
except Exception as ex: okm = type(ex).__name__
tm = (time.perf_counter() - t1) * 1000; time.sleep(6)
e.heal(); time.sleep(10); stop.set(); th.join()
two = [(round((t - t0) * 1000), [k for k, v in row.items() if v == 'leader']) for t, row in samples if t > t0 and sum(1 for v in row.values() if v == 'leader') >= 2]
mx = max(sum(1 for v in row.values() if v == 'leader') for t, row in samples)
print(f'  共采样 {len(samples)} 次;任一时刻同时报告 leader 的节点数最大 = {mx};出现 ≥2 个 leader 的采样 {len(two)} 次', ('(例:' + str(two[:2]) + ')') if two else '')
print('  多数派一侧的客户端写 /from-majority:', okm, f'(分区后 {tm:.0f} ms)')
R['max_leaders'] = mx; R['two_samples'] = two[:3]; R['majority_write'] = dict(ok=okm, ms=tm)
print()
print('== 二:少数派一侧的写入:没有多数派就不能提交(旧 leader 收下的写在恢复后也不会出现)')
try: resn.get(timeout=5); rn = '成功'
except Exception as ex: rn = type(ex).__name__
print('  连在旧 leader 上的客户端 create /from-minority 的结果:', rn); R['minority_write'] = rn
z = client(e.hosts()); print('  网络恢复后读:/from-majority →', z.exists('/from-majority') is not None, '| /from-minority →', z.exists('/from-minority') is not None); R['final'] = dict(maj=z.exists('/from-majority') is not None, mino=z.exists('/from-minority') is not None)
print('  各节点 Mode:', {n.name: n.mode() for n in e.nodes}); print('  各节点 Zxid:', {n.name: n.srvr().get('zxid') for n in e.nodes}); R['zxids'] = {n.name: n.srvr().get('zxid') for n in e.nodes}
print('  各节点上 /from-majority 的数据:', {n.name: (lambda c: c.get('/from-majority')[0])(client(f'127.0.0.1:{n.cport}')) for n in e.nodes})
zm.stop(); zn.stop(); z.stop(); e.stop(); save('z48', R)
