import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k77')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k77')
W1, W2 = 'kx-main-worker', 'kx-main-worker2'
def pods(sel=None):
    a = ['get', 'pods', '-n', NS] + (['-l', sel] if sel else [])
    return [(p['metadata']['name'], p['spec'].get('nodeName', '-').replace('kx-main-', ''), 'Terminating' if p['metadata'].get('deletionTimestamp') else p['status'].get('phase')) for p in kj(*a)['items']]
def summary():
    r = {}
    for n, node, st in pods(): r.setdefault(node, []).append(re.sub(r'-[0-9a-f]{8,10}-\w{5}$', '', n) + ('(T)' if st == 'Terminating' else ''))
    return {n: sorted(v) for n, v in r.items()}
k('cordon', W2)
k('apply', '-f', '-', input=f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: dep, namespace: {NS}}}
spec:
  replicas: 3
  selector: {{matchLabels: {{app: dep}}}}
  template:
    metadata: {{labels: {{app: dep}}}}
    spec:
      terminationGracePeriodSeconds: 2
      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
---
apiVersion: apps/v1
kind: DaemonSet
metadata: {{name: ds, namespace: {NS}}}
spec:
  selector: {{matchLabels: {{app: ds}}}}
  template:
    metadata: {{labels: {{app: ds}}}}
    spec:
      terminationGracePeriodSeconds: 2
      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
---
apiVersion: v1
kind: Pod
metadata: {{name: bare, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 2
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
---
apiVersion: v1
kind: Pod
metadata: {{name: scratch, namespace: {NS}, labels: {{app: scratch}}}}
spec:
  terminationGracePeriodSeconds: 2
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"], volumeMounts: [{{name: v, mountPath: /v}}]}}]
  volumes: [{{name: v, emptyDir: {{}}}}]
''')
k('rollout', 'status', 'deploy/dep', '-n', NS, '--timeout=90s'); time.sleep(3)
print(f'集群 {cn};两个 worker。先 cordon worker2,让 Deployment(3 副本)、DaemonSet、裸 Pod bare、带 emptyDir 的 Pod scratch 都落在 worker 上,再 uncordon')
k('uncordon', W2); time.sleep(2); print(f'  uncordon 之后各节点上的 Pod:{summary()}')

print('== 一:cordon——只是不让新 Pod 来')
rc, o = k('cordon', W1); print(f'  kubectl cordon {W1.replace("kx-main-", "")}:{o.strip()}')
n = kj('get', 'node', W1); print(f'  节点 spec.unschedulable={n["spec"].get("unschedulable")};taints={[(t["key"], t["effect"]) for t in n["spec"].get("taints") or []]}')
rc, o = k('get', 'nodes'); print('  kubectl get nodes:' + ' | '.join(re.sub(r'\s+', ' ', l)[:50] for l in o.strip().splitlines()[1:]))
print(f'  已有的 Pod 不受影响:{summary()}')
k('scale', 'deploy/dep', '-n', NS, '--replicas=5'); k('rollout', 'status', 'deploy/dep', '-n', NS, '--timeout=60s'); time.sleep(2)
print(f'  扩到 5 个副本:新增的 2 个去了哪:{summary()}(只能去 worker2)')
k('scale', 'deploy/dep', '-n', NS, '--replicas=3'); time.sleep(3)

print('== 二:drain——先 cordon 再逐个驱逐,遇到不能驱逐的就拒绝')
rc, o = k('drain', W1, '--timeout=20s'); lines = [l for l in o.strip().splitlines() if l.strip()]
print(f'  直接 kubectl drain {W1.replace("kx-main-", "")}:退出码 {rc};' + ' / '.join(l[:520] for l in [x for x in lines if x.startswith('error')][:1]))
rc, o = k('drain', W1, '--ignore-daemonsets', '--timeout=20s'); lines = [l for l in o.strip().splitlines() if l.strip()]
print(f'  加 --ignore-daemonsets:退出码 {rc};' + ' / '.join(l[:520] for l in [x for x in lines if x.startswith('error')][:1]))
rc, o = k('drain', W1, '--ignore-daemonsets', '--delete-emptydir-data', '--timeout=20s'); lines = [l for l in o.strip().splitlines() if l.strip()]
print(f'  再加 --delete-emptydir-data:退出码 {rc};' + ' / '.join(l[:520] for l in [x for x in lines if x.startswith('error')][:1]))
t0 = time.time(); rc, o = k('drain', W1, '--ignore-daemonsets', '--delete-emptydir-data', '--force', '--timeout=90s'); el = time.time() - t0
print(f'  再加 --force:退出码 {rc},用时 {el:.1f} 秒;输出:')
for l in o.strip().splitlines(): print('    ' + l[:150])
time.sleep(3); print(f'  drain 之后各节点上的 Pod:{summary()}')
print(f'  bare(裸 Pod,--force 之后被直接删掉)还在吗:{any(n_ == "bare" for n_, _, _ in pods())};scratch(带 emptyDir 的裸 Pod)还在吗:{any(n_ == "scratch" for n_, _, _ in pods())};dep 的 3 个副本都在 worker2:{sum(1 for n_, nd, st in pods("app=dep") if nd == "worker2" and st == "Running")} 个;DaemonSet 在 worker 上的 Pod 还在:{any(n_.startswith("ds-") and nd == "worker" for n_, nd, _ in pods())}')

print('== 三:PodDisruptionBudget 会让 drain 卡住')
k('uncordon', W1)
k('apply', '-f', '-', input=f'apiVersion: policy/v1\nkind: PodDisruptionBudget\nmetadata: {{name: dep-pdb, namespace: {NS}}}\nspec:\n  minAvailable: 3\n  selector: {{matchLabels: {{app: dep}}}}\n'); time.sleep(3)
pdb = kj('get', 'pdb', 'dep-pdb', '-n', NS); print(f'  PDB dep-pdb:minAvailable=3;当前 healthy={pdb["status"]["currentHealthy"]};disruptionsAllowed={pdb["status"]["disruptionsAllowed"]}')
t0 = time.time(); rc, o = k('drain', W2, '--ignore-daemonsets', '--delete-emptydir-data', '--force', '--timeout=25s'); el = time.time() - t0
ls = [l for l in o.strip().splitlines() if l.strip()]
print(f'  drain {W2.replace("kx-main-", "")}(上面有 dep 的 3 个副本):{el:.0f} 秒后退出码 {rc};输出(去重):')
seen = []
for l in ls:
    key = re.sub(r'dep-\S+', 'dep-…', l)[:140]
    if key not in seen: seen.append(key)
for l in seen[:6]: print('    ' + l)
print(f'  这时 Pod 仍然在 worker2 上的有:{sorted(set(n_[:8] for n_, nd, st in pods() if nd == "worker2" and st == "Running" and n_.startswith("dep")))},节点已被 cordon:{kj("get", "node", W2)["spec"].get("unschedulable")}(drain 失败也不会撤销 cordon)')
k('delete', 'pdb', 'dep-pdb', '-n', NS); t0 = time.time(); rc, o = k('drain', W2, '--ignore-daemonsets', '--delete-emptydir-data', '--force', '--timeout=60s'); print(f'  删掉 PDB 后重新 drain:退出码 {rc},用时 {time.time() - t0:.1f} 秒;之后 {summary()}')

print('== 四:uncordon——只恢复调度,不会把 Pod 搬回来')
k('uncordon', W2); k('uncordon', W1); time.sleep(3)
print(f'  uncordon 两个节点后:{summary()}(Pod 不会自己迁回;需要重建/rollout 才会重新分布)')
n = kj('get', 'node', W2); print(f'  worker2 的 spec.unschedulable={n["spec"].get("unschedulable")};taints={n["spec"].get("taints")}')
k('delete', 'ns', NS, '--wait=false')
