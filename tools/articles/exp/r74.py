import sys, time, random, os, json, subprocess, signal, statistics, threading, socket, select, re, collections, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r74'); R = {}
ports = [7380, 7381, 7382]
nodes = [Node(p, name=f'c74_{p}', conf={'cluster-enabled': 'yes', 'cluster-config-file': 'nodes.conf', 'cluster-node-timeout': '3000'}).start() for p in ports]
cs = {p: n.c() for p, n in zip(ports, nodes)}
def view(p):
    """节点 p 眼里的其它节点:{port: 状态摘要}"""
    out = {}
    for nd in cluster_nodes(cs[p]):
        if 'myself' in nd['flags']: continue
        out[nd['port'] if nd['port'] else nd['id'][:6]] = ','.join(f for f in nd['flags'] if f != 'noaddr') + '/' + nd['link']
    return out
def info_(p, k): return [l.split(':')[1] for l in cs[p].do('CLUSTER', 'INFO').splitlines() if l.startswith(k + ':')][0]
print('== 一:三个刚启动的集群节点互相不认识')
for p in ports: print(f'  {p}: 已知节点 {info_(p, "cluster_known_nodes")} 个,cluster_state = {info_(p, "cluster_state")},current_epoch = {info_(p, "cluster_current_epoch")}')
print()
print('== 二:在 7380 上执行 CLUSTER MEET 7381;每 10 ms 采样 7380 与 7381 眼中的对方(只打印变化)')
t0 = time.perf_counter(); sh(cs[7380], 'CLUSTER', 'MEET', '127.0.0.1', 7381)
last = {}; tl = []
while time.perf_counter() - t0 < 2.0:
    for p in (7380, 7381):
        v = view(p)
        if v != last.get(p):
            last[p] = v; tl.append((time.perf_counter() - t0, p, dict(v))); print(f'  +{(time.perf_counter()-t0)*1000:6.0f} ms  {p} 眼中的其它节点: {v}')
    time.sleep(0.01)
R['meet'] = [(t, p, {str(k): v for k, v in d.items()}) for t, p, d in tl]
print()
print('== 三:然后只让 7381 去 MEET 7382,7380 和 7382 不直接见面——靠 gossip 互相发现')
t0 = time.perf_counter(); sh(cs[7381], 'CLUSTER', 'MEET', '127.0.0.1', 7382)
seen = {}
while time.perf_counter() - t0 < 4.0:
    for p in ports:
        v = view(p); known = sorted(k for k in v if isinstance(k, int))
        if (p, tuple(known)) not in seen:
            seen[(p, tuple(known))] = time.perf_counter() - t0
            print(f'  +{(time.perf_counter()-t0)*1000:6.0f} ms  {p} 认识的节点端口: {known}')
    if all(len([k for k in view(p) if isinstance(k, int)]) == 2 for p in ports): break
    time.sleep(0.01)
tfull = time.perf_counter() - t0
print(f'三个节点互相认识(每个都知道另外两个)用了 {tfull*1000:.0f} ms')
R['full_ms'] = tfull * 1000
print()
print('== 四:握手完成后每个节点的状态')
time.sleep(0.5)
for p in ports: print(f'  {p}: known_nodes = {info_(p, "cluster_known_nodes")},cluster_state = {info_(p, "cluster_state")}(还没分槽位),current_epoch = {info_(p, "cluster_current_epoch")}')
print('  7380 的 CLUSTER NODES:')
for nd in cluster_nodes(cs[7380]): print(f'    {nd["id"][:8]} {nd["addr"]:<16} {",".join(nd["flags"]):<14} link={nd["link"]}')
print()
print('== 五:分配槽位后 cluster_state 变 ok')
t0 = time.perf_counter()
cs[7380].do('CLUSTER', 'ADDSLOTSRANGE', 0, 5460); cs[7381].do('CLUSTER', 'ADDSLOTSRANGE', 5461, 10922); cs[7382].do('CLUSTER', 'ADDSLOTSRANGE', 10923, 16383)
while not all(info_(p, 'cluster_state') == 'ok' for p in ports): time.sleep(0.01)
print(f'  ADDSLOTS 后 {(time.perf_counter()-t0)*1000:.0f} ms,三个节点 cluster_state 都是 ok;current_epoch = {[info_(p, "cluster_current_epoch") for p in ports]}')
R['ok_ms'] = (time.perf_counter() - t0) * 1000
print()
print('== 六:握手对象根本不存在(MEET 一个没人监听的地址):handshake 节点会保留多久')
sh(cs[7380], 'CLUSTER', 'MEET', '127.0.0.1', 9, 10009)
t0 = time.perf_counter(); appeared = None; gone = None
while time.perf_counter() - t0 < 8:
    hs = [nd for nd in cluster_nodes(cs[7380]) if 'handshake' in nd['flags']]
    if hs and appeared is None: appeared = time.perf_counter() - t0; print(f'  +{appeared*1000:6.0f} ms  出现 handshake 节点:{hs[0]["addr"]} flags={hs[0]["flags"]}')
    if appeared is not None and not hs: gone = time.perf_counter() - t0; print(f'  +{gone*1000:6.0f} ms  handshake 节点消失(被丢弃)'); break
    time.sleep(0.01)
R['hs'] = [appeared, gone]
print('  已知节点数:', info_(7380, 'cluster_known_nodes'))
print()
print('== 七:nodes.conf 里持久化的内容(7380)')
print((nodes[0].dir / 'nodes.conf').read_text().strip().replace('\n', '\n  ')[:900])
save('r74', R); cleanup(nodes)
