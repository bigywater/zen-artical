import sys, os, time, json, re, statistics, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from etcdl import *
tee('z44'); R = {}
print('== 一:ZooKeeper(ZAB)的读默认在本地:客户端 A 在一个 follower 上写,B 在另一个 follower 上读,写返回后马上读,会不会读到旧值?(3000 次)')
e = Ensemble('z44', 3, base=7300).start(); fo = e.followers()
a = client(f'127.0.0.1:{fo[0].cport}'); b = client(f'127.0.0.1:{fo[1].cport}'); a.create('/v', b'0')
def trial(use_sync):
    stale = 0
    for i in range(1, 3001):
        a.set('/v', str(i).encode())
        if use_sync: b.sync('/v')
        if int(b.get('/v')[0]) < i: stale += 1
    return stale
s1 = trial(False); s2 = trial(True)
print(f'  不调用 sync:读到旧值 {s1} / 3000 次;每次读之前先 sync():读到旧值 {s2} / 3000 次'); R['zk_stale'] = dict(nosync=s1, sync=s2)
a.stop(); b.stop(); e.stop()
print()
print('== 二:etcd(Raft)3 节点集群:默认的读是线性一致的;serializable 读在 follower 本地完成。同样的测试(3000 次)')
c = EtcdCluster('z44e', 3).start(); ld = c.leader(); fl = [n for n in c.nodes if n is not ld]
w, rd = fl[0], fl[1]; w.put('v', '0')
def etrial(ser):
    stale = 0
    for i in range(1, 3001):
        w.put('v', str(i)); v = rd.get('v', serializable=ser)
        if v is None or int(v) < i: stale += 1
    return stale
t1 = etrial(False); t2 = etrial(True)
print(f'  线性一致读(默认):读到旧值 {t1} / 3000 次;serializable 读(follower 本地):读到旧值 {t2} / 3000 次'); R['etcd_stale'] = dict(lin=t1, ser=t2)
print()
print('== 三:leader 被杀后恢复写入要多久:写线程每 10 ms 一次,杀 leader 5 次,看最大的两次成功之间的间隔(etcd 默认 election-timeout 1000 ms)')
def window(nd_list, killfn):
    log = []; stop = threading.Event()
    def writer():
        i = 0
        while not stop.is_set():
            t = time.perf_counter(); ok = False
            for nd in nd_list:
                if not nd.alive(): continue
                try:
                    s, d = nd.put(f'k{i}', 'x', timeout=1)
                    if s == 200: ok = True; break
                except Exception: pass
            log.append((t, ok)); i += 1; time.sleep(0.01)
    th = threading.Thread(target=writer); th.start(); time.sleep(1); killfn(); time.sleep(6); stop.set(); th.join()
    ok_ts = [t for t, ok in log if ok]; return max(b - a for a, b in zip(ok_ts, ok_ts[1:])) * 1000
ws = []
for r in range(5):
    ld = c.leader(); term0 = int(ld.status().get('raftTerm', 0))
    ws.append(window(c.nodes, lambda: ld.kill())); 
    ld.start(wipe=False, state='existing'); time.sleep(3); nl = c.leader(); term1 = int(nl.status().get('raftTerm', 0))
    print(f'  第 {r + 1} 次:写不可用 {ws[-1]:.0f} ms;raftTerm {term0} → {term1}')
print(f'  etcd 写不可用中位 {statistics.median(ws):.0f} ms(最小 {min(ws):.0f} / 最大 {max(ws):.0f});对照 ZooKeeper 第 36 篇的中位约 445 ms'); R['etcd_outage'] = dict(med=statistics.median(ws), mn=min(ws), mx=max(ws), runs=ws)
c.stop(); save('z44', R)
