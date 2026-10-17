import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k75')
cn, _ = up('main'); wait_nodes_ready()
W = 'kx-main-worker2'
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def lease(n=W): return kj('get', 'lease', n, '-n', 'kube-node-lease')
def ready(n=W): return next(c for c in kj('get', 'node', n)['status']['conditions'] if c['type'] == 'Ready')
print(f'集群 {cn};kubelet 用两种方式报告自己还活着:频繁更新 kube-node-lease 里的 Lease(很轻),低频更新 Node 的 status')

print('== 一:Lease 是什么样的')
L = lease(); sp = L['spec']
print(f'  Lease {W}(命名空间 kube-node-lease):holderIdentity={sp["holderIdentity"]};leaseDurationSeconds={sp["leaseDurationSeconds"]};ownerReferences={[(o["kind"], o["name"]) for o in L["metadata"].get("ownerReferences", [])]}')
print(f'  所有节点的 Lease:{[l["metadata"]["name"] for l in kj("get", "leases", "-n", "kube-node-lease")["items"]]}')
rts = []; last = None; t0 = time.time()
while time.time() - t0 < 65:
    r = lease()['spec']['renewTime']
    if r != last: rts.append(ts(r)); last = r
    time.sleep(0.5)
gaps = [round(b - a, 1) for a, b in zip(rts, rts[1:])]
print(f'  观察 65 秒:renewTime 变了 {len(rts) - 1} 次,相邻两次间隔(秒){gaps}(≈ 10 秒一次)')
nv = ready(); print(f'  同一节点 Ready 条件:lastHeartbeatTime={nv["lastHeartbeatTime"]},距现在 {time.time() - ts(nv["lastHeartbeatTime"]):.0f} 秒;lastTransitionTime 距现在 {time.time() - ts(nv["lastTransitionTime"]) :.0f} 秒')

print('== 二:Node status 的更新频率(没变化就 5 分钟一次)')
def node_rv(): return kj('get', 'node', W)['metadata']['resourceVersion']
def lease_rv(): return lease()['metadata']['resourceVersion']
n0, l0 = int(node_rv()), int(lease_rv()); hb0 = ready()['lastHeartbeatTime']; t0 = time.time()
changes = {'node': 0, 'lease': 0}; lastn, lastl = node_rv(), lease_rv(); hbs = set()
while time.time() - t0 < 100:
    a, b = node_rv(), lease_rv()
    if a != lastn: changes['node'] += 1; lastn = a
    if b != lastl: changes['lease'] += 1; lastl = b
    hbs.add(ready()['lastHeartbeatTime']); time.sleep(1)
print(f'  100 秒内:Node 对象的 resourceVersion 变了 {changes["node"]} 次;Lease 的 resourceVersion 变了 {changes["lease"]} 次(≈ 每 10 秒)')
print(f'  Ready 条件的 lastHeartbeatTime 在这 100 秒里出现过 {len(hbs)} 个不同值(从 {hb0[11:19]} 开始)——Node status 在没变化时每 5 分钟才更新一次')

print('== 三:心跳停了会怎样——停掉 worker2 的 kubelet')
t0 = time.time(); last_renew = lease()['spec']['renewTime']; nx(W, 'systemctl stop kubelet')
tl_ = {}
def check():
    r = ready()
    if r['status'] != 'True' and 'unknown' not in tl_: tl_['unknown'] = time.time() - t0; tl_['reason'] = (r['reason'], r['message'])
    tn = kj('get', 'node', W)['spec'].get('taints') or []
    if tn and 'taint' not in tl_: tl_['taint'] = time.time() - t0; tl_['taints'] = [(t['key'], t['effect']) for t in tn]
    return 'unknown' in tl_ and 'taint' in tl_
until(check, 150, 1)
print(f'  最后一次 renewTime={last_renew[11:19]};停掉 kubelet 之后:Ready 变成 {tl_.get("reason", ("?", ""))[0]} 用了 {tl_.get("unknown", 0):.0f} 秒(message:{tl_.get("reason", ("", ""))[1][:60]});出现污点 {tl_.get("taints")} 用了 {tl_.get("taint", 0):.0f} 秒')
print(f'  此时 Lease 的 renewTime 仍停在 {lease()["spec"]["renewTime"][11:19]}(没有再更新)')
nx(W, 'systemctl start kubelet'); t1 = time.time(); v, dt = until(lambda: ready()['status'] == 'True' and not (kj('get', 'node', W)['spec'].get('taints') or []), 120, 1)
print(f'  重新启动 kubelet:{dt:.0f} 秒后 Ready=True 且污点被清除;Lease renewTime={lease()["spec"]["renewTime"][11:19]}')

print('== 四:删掉 Lease')
old = lease()['metadata']['uid']; k('delete', 'lease', W, '-n', 'kube-node-lease'); t0 = time.time()
v, dt = until(lambda: (lease() or {'metadata': {'uid': old}})['metadata']['uid'] != old, 60, 0.5)
print(f'  kubectl delete lease {W}:{dt:.1f} 秒后 kubelet 又把它建回来(新 uid,holderIdentity={lease()["spec"]["holderIdentity"]});节点 Ready={ready()["status"]}')
