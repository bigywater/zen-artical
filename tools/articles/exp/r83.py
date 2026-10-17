import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r83'); R = {'trials': []}
def stat(c):
    d = {}
    for l in c.do('CLUSTER', 'INFO').splitlines():
        if ':' in l:
            k, v = l.strip().split(':', 1); d[k] = v
    return d
def trial(k, base):
    cl = Cluster(base, 3, 1, name=f'c83_{k}'); time.sleep(1)
    nd = cluster_nodes(cl.nodes[0].c())
    ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
    X = ms[0]; nodeX = [n for n in cl.nodes if n.port == X['port']][0]
    others = [n for n in cl.nodes if n.port != X['port']]
    own = slot_owner_map(cl.nodes[0].c())
    key = next(f'p:{i}' for i in range(1000) if own[keyslot(f'p:{i}')] == X['port'])
    cX = C(X['port'], timeout=3)
    res = []; state = []; stop = threading.Event()
    def writer():
        c = C(X['port'], timeout=3); i = 0
        while not stop.is_set():
            t = time.perf_counter()
            try:
                r = c.do('SET', key, i, raise_err=False); res.append((t, 'OK' if r == 'OK' else str(r)[:24], i))
            except Exception as e:
                res.append((t, type(e).__name__, i))
            i += 1; time.sleep(0.005)
    th = threading.Thread(target=writer); th.start(); time.sleep(1.0)
    t0 = time.perf_counter()
    for n in others: n.p.send_signal(signal.SIGSTOP)
    # 观察 X 眼中的集群状态
    st_first = {}
    while time.perf_counter() - t0 < 12:
        try:
            s = stat(cX); cur = (s['cluster_state'])
            if cur not in st_first: st_first[cur] = time.perf_counter() - t0
            nn = cluster_nodes(cX)
            for x in nn:
                if x['id'] != X['id'] and ('fail?' in x['flags'] or 'fail' in x['flags']):
                    st_first.setdefault('first_pfail', time.perf_counter() - t0)
        except Exception: pass
        time.sleep(0.02)
    t_heal = time.perf_counter()
    for n in others: n.p.send_signal(signal.SIGCONT)
    heal = {}
    while time.perf_counter() - t_heal < 12:
        try:
            s = stat(cX);
            if s['cluster_state'] == 'ok' and 'ok' not in heal: heal['ok'] = time.perf_counter() - t_heal
            roles = {x['port']: ','.join(f for f in x['flags'] if f in ('master', 'slave', 'fail', 'fail?')) for x in cluster_nodes(cX)}
            heal['roles'] = roles
        except Exception: pass
        if 'ok' in heal and time.perf_counter() - t_heal > heal['ok'] + 3: break
        time.sleep(0.05)
    stop.set(); th.join()
    frz = [(t, r) for t, r, i in res if t0 <= t <= t_heal]
    first_reject = next((t for t, r in frz if r != 'OK'), None)
    ok_frozen = sum(1 for t, r in frz if r == 'OK'); rej = sum(1 for t, r in frz if r != 'OK')
    rec = dict(first_reject=(first_reject - t0) if first_reject else None, ok_frozen=ok_frozen, rej=rej, states=st_first, heal_ok=heal.get('ok'), roles=heal.get('roles'), errs=collections.Counter(r for t, r in frz if r != 'OK').most_common(3),
               log=[l.split('# ', 1)[-1].split('* ', 1)[-1][:140] for l in nodeX.log().splitlines() if any(s in l for s in ('Cluster state', 'cluster state', 'quorum', 'majority', 'Marking node', 'CLUSTER'))][-8:])
    cl.cleanup(); time.sleep(1.0); return rec
print('== 把除 X 之外的 5 个节点全部 SIGSTOP(从 X 的角度看,它和其余所有节点断开了),X 自己仍在运行并被客户端不停写入,12 秒后恢复其余节点')
print('   cluster-node-timeout = 3000 ms;重复 3 次')
for k in range(3):
    r = trial(k, 7550); R['trials'].append(r)
    f = lambda v: f'{v*1000:.0f} ms' if v is not None else '—'
    print(f'第 {k+1} 次:X 眼中 cluster_state 变 fail {f(r["states"].get("fail"))};X 上第一条被拒写入 {f(r["first_reject"])};12 秒里被接受(OK)的写入 {r["ok_frozen"]} 条,被拒 {r["rej"]} 条({r["errs"]});恢复后 cluster_state = ok 用了 {f(r["heal_ok"])}')
    print(f'         恢复后 X 看到的角色:{r["roles"]}')
print()
print('X 的日志(第 3 次):')
for l in R['trials'][-1]['log']: print('  ', l)
save('r83', R)
