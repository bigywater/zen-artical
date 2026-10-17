import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r76'); R = {}
def stats(c):
    d = {}
    for l in c.do('CLUSTER', 'INFO').splitlines():
        if ':' in l:
            k, v = l.strip().split(':', 1); d[k] = v
    return d
KEYS = ('cluster_stats_messages_auth-req_sent', 'cluster_stats_messages_auth-req_received', 'cluster_stats_messages_auth-ack_sent', 'cluster_stats_messages_auth-ack_received')
def snap(cl, alive):
    return {n.port: {k: int(stats(n.c()).get(k, 0)) for k in KEYS} for n in cl.nodes if n.port in alive}
def logs(node, keys=('Failover', 'election', 'vote', 'Currently unable', 'FAIL message', 'attempt')):
    out = []
    for l in node.log().splitlines():
        if any(k in l for k in keys):
            out.append(l.split('* ', 1)[-1].split('# ', 1)[-1][:170])
    return out
def scenario(name, masters, kill_masters, base, wait=12):
    cl = Cluster(base, masters, 1, name=name); time.sleep(1)
    nd = cluster_nodes(cl.nodes[0].c())
    ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
    victims = ms[:kill_masters]
    reps = {v['id']: [x for x in nd if x['master'] == v['id']][0] for v in victims}
    alive = [n.port for n in cl.nodes if n.port not in {v['port'] for v in victims}]
    before = snap(cl, alive)
    t0 = time.perf_counter()
    for v in victims: cl.nodes[[n.port for n in cl.nodes].index(v['port'])].kill9()
    promoted = {}
    obs = C(alive[0]); state = None
    while time.perf_counter() - t0 < wait:
        try:
            cn = cluster_nodes(obs)
            for v in victims:
                r = reps[v['id']]
                if any(x['id'] == r['id'] and 'master' in x['flags'] for x in cn) and v['id'] not in promoted: promoted[v['id']] = time.perf_counter() - t0
            state = stats(obs)['cluster_state']
        except Exception: pass
        if len(promoted) == len(victims): break
        time.sleep(0.02)
    time.sleep(1.0)
    after = snap(cl, alive)
    diff = {p: {k.replace('cluster_stats_messages_', ''): after[p][k] - before[p][k] for k in KEYS} for p in alive}
    rolemap = {}
    for x in cluster_nodes(C(alive[0])): rolemap[x['port']] = ','.join(f for f in x['flags'] if f in ('master', 'slave', 'fail', 'fail?'))
    res = dict(masters=masters, killed=[v['port'] for v in victims], promoted={reps[k]['port']: v for k, v in promoted.items()}, state=state, diff=diff, roles=rolemap,
               replogs={reps[v['id']]['port']: logs(cl.nodes[[n.port for n in cl.nodes].index(reps[v['id']]['port'])]) for v in victims},
               voterlogs={p: [l for l in logs(cl.nodes[[n.port for n in cl.nodes].index(p)]) if 'auth' in l.lower() or 'vote' in l.lower()] for p in alive if p in {m['port'] for m in ms} - {v['port'] for v in victims}})
    cl.cleanup(); time.sleep(1.0)
    return res
print('== 一:3 主 3 从,kill 掉 1 个主库:谁投了票')
A = scenario('c76a', 3, 1, 7400); R['A'] = A
print(f'被杀主库 {A["killed"]};升主的从库及耗时(ms):{ {k: round(v*1000) for k, v in A["promoted"].items()} };cluster_state = {A["state"]}')
print('各幸存节点 CLUSTER INFO 里投票消息数的变化(auth-req = 要票,auth-ack = 投票):')
for p, d in sorted(A['diff'].items()): print(f'  {p} {A["roles"].get(p, "?"):<10} {d}')
print('从库的日志:'); [print('   ', l) for r_, L in A['replogs'].items() for l in L]
print('投票的主库的日志:')
for p, L in A['voterlogs'].items():
    for l in L: print(f'   [{p}]', l)
print()
print('== 二:3 主 3 从,同时 kill 掉 2 个主库:只剩 1 个主库,拿不到多数票')
B = scenario('c76b', 3, 2, 7410, wait=15); R['B'] = B
print(f'被杀主库 {B["killed"]};15 秒内升主的从库:{ {k: round(v*1000) for k, v in B["promoted"].items()} or "无"};cluster_state = {B["state"]}')
print('各幸存节点的角色:', B['roles'])
print('幸存节点上投票消息数的变化:')
for p, d in sorted(B['diff'].items()): print(f'  {p} {B["roles"].get(p, "?"):<10} {d}')
print('从库的日志(节选):')
for r_, L in B['replogs'].items():
    for l in L[:6]: print(f'   [{r_}]', l)
print()
print('== 三:5 主 5 从,同时 kill 掉 2 个主库:还剩 3 个主库 = 多数,两个从库都能升主')
C_ = scenario('c76c', 5, 2, 7420, wait=20); R['C'] = C_
print(f'被杀主库 {C_["killed"]};升主的从库及耗时(ms):{ {k: round(v*1000) for k, v in C_["promoted"].items()} };cluster_state = {C_["state"]}')
print('幸存节点上投票消息数的变化:')
for p, d in sorted(C_['diff'].items()): print(f'  {p} {C_["roles"].get(p, "?"):<10} {d}')
save('r76', R)
