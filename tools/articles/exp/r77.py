import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r77'); R = {}
def stat(c):
    d = {}
    for l in c.do('CLUSTER', 'INFO').splitlines():
        if ':' in l:
            k, v = l.strip().split(':', 1); d[k] = v
    return d
def eps(cl, ports=None):
    out = {}
    for n in cl.nodes:
        if ports and n.port not in ports: continue
        try:
            s = stat(n.c()); out[n.port] = (int(s['cluster_current_epoch']), int(s['cluster_my_epoch']))
        except Exception: pass
    return out
print('== 一:新建 3 主 3 从集群:每个节点的 (current_epoch, my_epoch)')
cl = Cluster(7430, 3, 1, name='c77a'); time.sleep(1)
nd = cluster_nodes(cl.nodes[0].c())
role = {x['port']: ('M' if 'master' in x['flags'] else 'S') for x in nd}
for p, e in sorted(eps(cl).items()): print(f'  {p} {role[p]}  current_epoch = {e[0]}  my_epoch(configEpoch) = {e[1]}')
R['init'] = {str(p): e for p, e in eps(cl).items()}
cl.cleanup(); time.sleep(1)
print()
print('== 二:两个节点手工设成同一个 configEpoch(冲突),再握手:服务器自动解决')
ports = [7440, 7441, 7442]
ns = [Node(p, name=f'c77b_{p}', conf={'cluster-enabled': 'yes', 'cluster-config-file': 'nodes.conf'}).start() for p in ports]
cs = [n.c() for n in ns]
for c in cs[:2]: c.do('CLUSTER', 'SET-CONFIG-EPOCH', 5)
sh(cs[2], 'CLUSTER', 'SET-CONFIG-EPOCH', 5) if False else None
for c, p in zip(cs, ports): print(f'  握手前 {p}: my_epoch = {stat(c)["cluster_my_epoch"]}')
cs[0].do('CLUSTER', 'MEET', '127.0.0.1', 7441); cs[0].do('CLUSTER', 'MEET', '127.0.0.1', 7442)
t0 = time.perf_counter(); last = None
while time.perf_counter() - t0 < 6:
    cur = tuple((int(stat(c)['cluster_my_epoch']), int(stat(c)['cluster_current_epoch'])) for c in cs)
    if cur != last: last = cur; print(f'  +{(time.perf_counter()-t0)*1000:6.0f} ms  各节点 (my_epoch, current_epoch): {dict(zip(ports, cur))}')
    time.sleep(0.02)
R['collision'] = list(last)
cleanup(ns); time.sleep(1)
print()
print('== 三:冻结旧主库(SIGSTOP)直到从库升主,再解冻(SIGCONT):比较 epoch,看旧主库怎么处理')
trials = []
for k in range(3):
    cl = Cluster(7450, 3, 1, name=f'c77c_{k}'); time.sleep(1)
    nd = cluster_nodes(cl.nodes[0].c())
    ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port']); X = ms[1]
    rep = [x for x in nd if x['master'] == X['id']][0]
    nodeX = [n for n in cl.nodes if n.port == X['port']][0]
    own = slot_owner_map(cl.nodes[0].c())
    key = next(f'z:{i}' for i in range(1000) if own[keyslot(f'z:{i}')] == X['port'])
    cX = C(X['port'], timeout=3); cX.do('SET', key, 'before')
    before = eps(cl)
    nodeX.p.send_signal(signal.SIGSTOP)
    obs = C(rep['port']); t0 = time.perf_counter()
    while time.perf_counter() - t0 < 20:
        if 'master' in obs.do('ROLE')[0]: break
        time.sleep(0.02)
    t_prom = time.perf_counter() - t0
    time.sleep(0.5); mid = eps(cl, [p for p in [n.port for n in cl.nodes] if p != X['port']])
    obs.do('SET', key, 'after-failover')
    nodeX.p.send_signal(signal.SIGCONT); t1 = time.perf_counter()
    # 解冻后立刻通过旧连接写一次:旧主库这时还以为自己是主库吗?
    try:
        r = cX.do('SET', key, 'stale-write', raise_err=False); wr = str(r)
    except Exception as e:
        wr = type(e).__name__
    t_w = (time.perf_counter() - t1) * 1000
    conv = None
    while time.perf_counter() - t1 < 10:
        try:
            if 'slave' in C(X['port'], timeout=1).do('ROLE')[0]: conv = time.perf_counter() - t1; break
        except Exception: pass
        time.sleep(0.005)
    time.sleep(1.0)
    after = eps(cl)
    v = C(rep['port']).do('GET', key)
    vX = C(X['port']).do('GET', key, raise_err=False)
    rec = dict(before={str(p): e for p, e in before.items()}, mid={str(p): e for p, e in mid.items()}, after={str(p): e for p, e in after.items()}, X=X['port'], rep=rep['port'], prom=t_prom, write_after_cont=wr, write_ms=t_w, conv=conv, final_new=v, final_old=str(vX))
    trials.append(rec)
    print(f'第 {k+1} 次:X={X["port"]} 从库={rep["port"]};从库升主用了 {t_prom*1000:.0f} ms')
    print(f'   X 的 (current,my) epoch:冻结前 {before[X["port"]]} → 解冻后 {after[X["port"]]};新主库 {rep["port"]}:{before[rep["port"]]} → {after[rep["port"]]}')
    print(f'   解冻后 {t_w:.1f} ms 内经旧连接 SET 的结果:{wr};旧主库变成从库用了 {conv*1000 if conv else float("nan"):.0f} ms;最终 key 在新主库上的值 = {v!r},在旧主库上 = {vX!r}')
    cl.cleanup(); time.sleep(1)
R['trials'] = trials
save('r77', R)
