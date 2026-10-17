import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r78'); R = {}
cl = Cluster(7460, 3, 1, name='c78'); time.sleep(1)
byport = {n.port: n for n in cl.nodes}
nd = cluster_nodes(cl.nodes[0].c())
ms = sorted([x for x in nd if 'master' in x['flags']], key=lambda x: x['port'])
def rep_of(m): return [x for x in nd if x['master'] == m['id']][0]
cc = CC([7460])
for i in range(20000): cc.do(f'k:{i}', 'SET', f'k:{i}', i)
time.sleep(1)
def view(port, id_):
    for x in cluster_nodes(C(port)):
        if x['id'] == id_: return ','.join(f for f in x['flags'] if f != 'noaddr')
    return '(不在节点表里)'
def known(port): return int([l for l in C(port).do('CLUSTER', 'INFO').splitlines() if l.startswith('cluster_known_nodes')][0].split(':')[1])
alive = lambda ex: [p for p in byport if p not in ex]

print('== 一:从库崩溃再重启(nodes.conf 还在):自动回来')
M = ms[0]; Rr = rep_of(M); mp = C(M['port'])
s0 = repl_stats(mp)
byport[Rr['port']].kill9(); t0 = time.perf_counter(); watch = C(ms[1]['port'])
while 'fail' not in view(ms[1]['port'], Rr['id']).split(',') and time.perf_counter() - t0 < 20: time.sleep(0.02)
t_fail = time.perf_counter() - t0
print(f'  从库 {Rr["port"]} 被 kill -9,{t_fail*1000:.0f} ms 后在其它节点眼中变成:{view(ms[1]["port"], Rr["id"])};集群状态(旁观节点):', [l for l in watch.do('CLUSTER', 'INFO').splitlines() if 'cluster_state' in l][0])
for i in range(20000, 25000): cc.do(f'k:{i}', 'SET', f'k:{i}', i)
t1 = time.perf_counter(); byport[Rr['port']].start(rewrite=False)
rc = C(Rr['port'])
while time.perf_counter() - t1 < 30:
    try:
        i_ = info(rc, 'replication')
        if i_.get('master_link_status') == 'up' and 'fail' not in view(ms[1]['port'], Rr['id']): break
    except Exception: pass
    time.sleep(0.02)
t_back = time.perf_counter() - t1
time.sleep(0.5); s1 = repl_stats(mp)
print(f'  重启后 {t_back*1000:.0f} ms:link up,在其它节点眼中 = {view(ms[1]["port"], Rr["id"])};节点 ID 不变(仍是 {Rr["id"][:8]});DBSIZE 从库/主库 = {rc.do("DBSIZE")} / {mp.do("DBSIZE")}')
print(f'  主库同步统计变化:full +{s1["sync_full"]-s0["sync_full"]},partial_ok +{s1["sync_partial_ok"]-s0["sync_partial_ok"]}')
print('  主库日志:'); [print('    ', l.split('* ', 1)[-1].split('# ', 1)[-1][:150]) for l in byport[M['port']].log().splitlines() if any(k in l.lower() for k in ('resynchron', 'full resync', 'starting bgsave', 'streamed rdb', 'synchronization with replica'))][-6:]
print('  从库日志:'); [print('    ', l.split('* ', 1)[-1].split('# ', 1)[-1][:150]) for l in byport[Rr['port']].log().splitlines() if any(k in l.lower() for k in ('sync', 'master'))][-8:]
R['a'] = dict(t_fail=t_fail, t_back=t_back, full=s1['sync_full'] - s0['sync_full'], part=s1['sync_partial_ok'] - s0['sync_partial_ok'])
print()
print('== 二:节点被清空(丢了 nodes.conf 和数据)后重启:它是一个全新的节点,旧 ID 成了幽灵')
M2 = ms[1]; R2 = rep_of(M2); oldid = R2['id']
byport[R2['port']].kill9(); time.sleep(0.3)
d = byport[R2['port']].dir
for f in list(d.iterdir()):
    if f.name in ('nodes.conf', 'dump.rdb') or f.name.startswith('appendonly'): f.unlink() if f.is_file() else shutil.rmtree(f)
byport[R2['port']].start(rewrite=False)
newid = C(R2['port']).do('CLUSTER', 'MYID')
print(f'  {R2["port"]} 新 ID {newid[:8]}(旧 ID {oldid[:8]});它自己已知节点 {known(R2["port"])} 个')
t0 = time.perf_counter()
while 'fail' not in view(ms[0]['port'], oldid).split(',') and time.perf_counter() - t0 < 20: time.sleep(0.05)
print(f'  其它节点眼中旧 ID:{view(ms[0]["port"], oldid)};已知节点数(含幽灵)= {known(ms[0]["port"])}')
sh(C(ms[0]['port']), 'CLUSTER', 'FORGET', oldid)
tf = time.perf_counter(); prev = None; tl = []
while time.perf_counter() - tf < 3.0:
    cur = {p: known(p) for p in alive([R2['port']])}
    if cur != prev: prev = cur; tl.append(((time.perf_counter() - tf) * 1000, dict(cur))); print(f'  +{(time.perf_counter()-tf)*1000:5.0f} ms  各节点已知节点数(只在 {ms[0]["port"]} 上执行过 FORGET): {cur}')
    time.sleep(0.05)
print(f'  旧 ID 在 {ms[2]["port"]} 眼中 = {view(ms[2]["port"], oldid)}')
R['b'] = dict(tl=tl)
print()
print('== 三:让这个新节点重新加入并当 M2 的从库')
t0 = time.perf_counter()
sh(C(R2['port']), 'CLUSTER', 'MEET', '127.0.0.1', ms[0]['port'])
while known(R2['port']) < 6 and time.perf_counter() - t0 < 20: time.sleep(0.05)
print(f'  MEET 后 {(time.perf_counter()-t0)*1000:.0f} ms 认识全部 {known(R2["port"])} 个节点')
time.sleep(1)
sh(C(R2['port']), 'CLUSTER', 'REPLICATE', M2['id'])
rc2 = C(R2['port']); t1 = time.perf_counter()
while time.perf_counter() - t1 < 30:
    i_ = info(rc2, 'replication')
    if i_.get('master_link_status') == 'up': break
    time.sleep(0.02)
print(f'  REPLICATE 后 {(time.perf_counter()-t1)*1000:.0f} ms:link up,DBSIZE = {rc2.do("DBSIZE")},角色 = {view(ms[0]["port"], newid)}')
R['c'] = dict(meet=time.perf_counter() - t0, link=time.perf_counter() - t1)
print()
print('== 四:旧主库崩溃、从库升主之后,旧主库重启:自动变成从库')
X = ms[2]; Rx = rep_of(X)
byport[X['port']].kill9(); t0 = time.perf_counter(); rx = C(Rx['port'])
while 'master' not in rx.do('ROLE')[0] and time.perf_counter() - t0 < 30: time.sleep(0.02)
tprom = time.perf_counter() - t0
print(f'  {X["port"]} 被杀,{Rx["port"]} 在 {tprom*1000:.0f} ms 后升主')
t1 = time.perf_counter(); byport[X['port']].start(rewrite=False)
while time.perf_counter() - t1 < 30:
    try:
        if 'slave' in C(X['port']).do('ROLE')[0] and info(C(X['port']), 'replication').get('master_link_status') == 'up': break
    except Exception: pass
    time.sleep(0.02)
t_rejoin = time.perf_counter() - t1
print(f'  旧主库重启后 {t_rejoin*1000:.0f} ms:角色 = {C(X["port"]).do("ROLE")[0]},master = {C(X["port"]).do("ROLE")[2]}(新主库端口 {Rx["port"]}),ID 不变 {C(X["port"]).do("CLUSTER", "MYID")[:8]}')
R['d'] = dict(prom=tprom, rejoin=t_rejoin)
save('r78', R); cl.cleanup()
