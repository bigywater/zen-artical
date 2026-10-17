import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k76')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k76')
W, W1 = 'kx-main-worker2', 'kx-main-worker'
def pod(name, tol='', node=W, grace=0):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {node}\n  terminationGracePeriodSeconds: {grace}\n{tol}  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n---\n'
T30 = '  tolerations:\n  - {key: node.kubernetes.io/unreachable, operator: Exists, effect: NoExecute, tolerationSeconds: 30}\n  - {key: node.kubernetes.io/not-ready, operator: Exists, effect: NoExecute, tolerationSeconds: 30}\n'
TINF = '  tolerations:\n  - {key: node.kubernetes.io/unreachable, operator: Exists, effect: NoExecute}\n  - {key: node.kubernetes.io/not-ready, operator: Exists, effect: NoExecute}\n'
k('apply', '-f', '-', input=pod('p-default') + pod('p-30s', T30, grace=30) + pod('p-forever', TINF) + f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: dep, namespace: {NS}}}
spec:
  replicas: 1
  selector: {{matchLabels: {{app: dep}}}}
  template:
    metadata: {{labels: {{app: dep}}}}
    spec:
      terminationGracePeriodSeconds: 30
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            preference: {{matchExpressions: [{{key: kubernetes.io/hostname, operator: In, values: [{W}]}}]}}
      tolerations:
      - {{key: node.kubernetes.io/unreachable, operator: Exists, effect: NoExecute, tolerationSeconds: 30}}
      - {{key: node.kubernetes.io/not-ready, operator: Exists, effect: NoExecute, tolerationSeconds: 30}}
      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
for p_ in ('p-default', 'p-30s', 'p-forever'): k('wait', '--for=condition=Ready', f'pod/{p_}', '-n', NS, '--timeout=60s')
k('rollout', 'status', 'deploy/dep', '-n', NS, '--timeout=60s'); time.sleep(2)
dep_pod = kj('get', 'pods', '-n', NS, '-l', 'app=dep')['items'][0]
print(f'集群 {cn};节点失联之后,node lifecycle 控制器先打污点,再按 Pod 的容忍时间驱逐。四个 Pod 在 {W.replace("kx-main-","")} 上:p-default(没写容忍,准入自动加 300 秒)、p-30s(tolerationSeconds=30,优雅期 30 秒)、p-forever(无限容忍)、Deployment dep 的 Pod(容忍 30 秒、优雅期 30 秒,落在 {dep_pod["spec"]["nodeName"].replace("kx-main-","")})')
tol = {t['key']: t.get('tolerationSeconds') for t in kj('get', 'pod', 'p-default', '-n', NS)['spec']['tolerations']}; print(f'  p-default 自动获得的容忍:{tol}')

print('== 一:停掉 kubelet,记录每一步的时间')
t0 = time.time(); nx(W, 'systemctl stop kubelet')
ev = {}
def node(): return kj('get', 'node', W)
def tick():
    t = time.time() - t0; n = node(); r = next(c for c in n['status']['conditions'] if c['type'] == 'Ready')
    if r['status'] != 'True': ev.setdefault('Ready=' + r['status'], t)
    for tn in n['spec'].get('taints') or []: ev.setdefault(f'taint {tn["key"].split("/")[-1]}:{tn["effect"]}', t)
    for p in kj('get', 'pods', '-n', NS)['items']:
        if p['metadata'].get('deletionTimestamp'): ev.setdefault(f'{p["metadata"]["name"][:9]} 被标记删除', t)
    deps = [p for p in kj('get', 'pods', '-n', NS, '-l', 'app=dep')['items'] if not p['metadata'].get('deletionTimestamp') and p['spec'].get('nodeName') == W1 and p['status'].get('phase') == 'Running']
    if deps: ev.setdefault('dep 的替换 Pod 在 worker 上 Running', t)
    return t > 110
until(tick, 130, 1)
for kk, vv in sorted(ev.items(), key=lambda x: x[1]): print(f'  +{vv:5.0f} 秒  {kk}')
rc, o = k('get', 'pods', '-n', NS, '-o', 'wide'); print('  kubectl get pods(+110 秒):'); [print('    ' + re.sub(r'\s+', ' ', l)[:120]) for l in o.strip().splitlines()]

print('== 二:kubelet 回来之后')
t1 = time.time(); nx(W, 'systemctl start kubelet')
def states(): return {p['metadata']['name'][:9]: ('Terminating' if p['metadata'].get('deletionTimestamp') else p['status'].get('phase')) for p in kj('get', 'pods', '-n', NS)['items']}
v, dt = until(lambda: 'p-30s' not in states() and not (node()['spec'].get('taints') or []) and sum(1 for n_ in states() if n_.startswith('dep')) == 1, 120, 1)
print(f'  重新启动 kubelet {dt:.0f} 秒后:污点 {[t["key"].split("/")[-1] for t in node()["spec"].get("taints") or []] or "已清除"};Pod 状态 {states()}')
print(f'  p-default 还在吗:{"p-default" in states()};p-forever 还在吗:{"p-forever" in states()}(它们没到驱逐时间,kubelet 回来后重新报告状态)')
k('delete', 'ns', NS, '--wait=false')
