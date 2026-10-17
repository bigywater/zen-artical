import sys, os, re, time, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k40')
cn, dt_up = up('sched', cfg=config(workers=4))
load('busybox:1.36'); wait_nodes_ready()
NODES = ['kx-sched-worker', 'kx-sched-worker2', 'kx-sched-worker3', 'kx-sched-worker4']
T = NODES[0]
NS = ns('k40')
def dep(name, replicas, tol='', extra=''):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: {replicas}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 0
{extra}{tol}      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
'''
def tolerations(*items): return '      tolerations:\n' + ''.join(f'      - {i}\n' for i in items)
def tol2(*items): return '  tolerations:\n' + ''.join(f'  - {i}\n' for i in items)
def dist(app):
    ps = kj('get', 'pods', '-n', NS, '-l', f'app={app}')['items']
    nodes = collections.Counter(p['spec'].get('nodeName') for p in ps if p['spec'].get('nodeName') and not p['metadata'].get('deletionTimestamp'))
    return nodes, [p for p in ps if not p['spec'].get('nodeName')]
def fmt(app):
    n, pend = dist(app); return '节点 ' + (' '.join(f'{k_.replace("kx-sched-", "")}={v}' for k_, v in sorted(n.items())) or '(无)') + (f';Pending {len(pend)} 个' if pend else '')
def settle(app, n, t=30): until(lambda: sum(dist(app)[0].values()) + len(dist(app)[1]) >= n, t); time.sleep(4)
print(f'集群 {cn}(1 控制面 + 4 个 worker);污点 = 节点上的“排斥”:key=value:effect,Pod 要有匹配的容忍才能(继续)待在上面')
rc, o = k('get', 'node', 'kx-sched-control-plane', '-o', 'jsonpath={.spec.taints}'); print(f'  kind 的控制面节点自带的污点:{o.strip()}')

print('== 一:NoSchedule——挡住新的 Pod,不动已有的')
k('apply', '-f', '-', input=dep('before', 8)); settle('before', 8); print(f'  先创建 8 个副本(此时没有污点):{fmt("before")}')
k('taint', 'node', T, 'k40=a:NoSchedule')
k('apply', '-f', '-', input=dep('after', 8)); settle('after', 8); print(f'  给 worker 打上 k40=a:NoSchedule 之后创建的 8 个副本:{fmt("after")}(worker 上一个都没有)')
print(f'  之前那 8 个副本:{fmt("before")}(worker 上原来的 Pod 没有被动)')
for nm, tol in (('tol-eq', tolerations('{key: k40, operator: Equal, value: a, effect: NoSchedule}')), ('tol-wrongval', tolerations('{key: k40, operator: Equal, value: b, effect: NoSchedule}')), ('tol-exists', tolerations('{key: k40, operator: Exists}')), ('tol-all', tolerations('{operator: Exists}'))):
    k('apply', '-f', '-', input=dep(nm, 4, tol, extra=f'      nodeSelector: {{kubernetes.io/hostname: {T}}}\n')); settle(nm, 4, 15)
    n, pend = dist(nm); print(f'  只能放在被打污点的 worker 上、容忍写成 {tol.splitlines()[1].strip()[2:]}:{"Running " + str(sum(n.values())) + " 个" if n else "全部 Pending"}' + (f';原因:{[c for c in pend[0]["status"]["conditions"] if c["type"] == "PodScheduled"][0].get("message", "")[:120]}' if pend else ''))
k('delete', 'deploy', '-n', NS, '--all', '--wait=true', timeout=90)

print('== 二:PreferNoSchedule——只是“尽量别来”')
k('taint', 'node', T, 'k40-', 'k40=a:PreferNoSchedule', '--overwrite'); k('taint', 'node', T, 'k40-')
k('apply', '-f', '-', input=dep('plain', 12)); settle('plain', 12); print(f'  没有污点:12 个副本 {fmt("plain")}')
k('delete', 'deploy', 'plain', '-n', NS, '--wait=true', timeout=60)
k('taint', 'node', T, 'k40=a:PreferNoSchedule')
k('apply', '-f', '-', input=dep('soft', 12)); settle('soft', 12); print(f'  worker 打上 PreferNoSchedule 之后:12 个副本 {fmt("soft")}')
k('apply', '-f', '-', input=dep('soft-only', 3, extra=f'      nodeSelector: {{kubernetes.io/hostname: {T}}}\n')); settle('soft-only', 3, 15); print(f'  但如果 Pod 只能去这个节点(nodeSelector):{fmt("soft-only")}(软的污点不阻止)')
k('delete', 'deploy', '-n', NS, '--all', '--wait=true', timeout=90); k('taint', 'node', T, 'k40-')

print('== 三:NoExecute——连正在运行的 Pod 也要赶走,tolerationSeconds 决定宽限')
def bare(name, tol=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {T}\n  terminationGracePeriodSeconds: 0\n{tol}  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
for nm, tol in (('no-tol', ''), ('tol-8s', tol2('{key: k40, operator: Exists, effect: NoExecute, tolerationSeconds: 8}')), ('tol-forever', tol2('{key: k40, operator: Exists, effect: NoExecute}'))): k('apply', '-f', '-', input=bare(nm, tol))
v_, _ = until(lambda: all((kj('get', 'pod', n, '-n', NS) or {}).get('status', {}).get('phase') == 'Running' for n in ('no-tol', 'tol-8s', 'tol-forever')), 60); assert v_, '裸 Pod 没有全部 Running'
print(f'  worker 上有 3 个裸 Pod:no-tol(没有容忍)、tol-8s(容忍 NoExecute,tolerationSeconds=8)、tol-forever(容忍,没写秒数)')
t0 = time.time(); k('taint', 'node', T, 'k40=a:NoExecute'); gone = {}
while time.time() - t0 < 25:
    for n in ('no-tol', 'tol-8s', 'tol-forever'):
        p = kj('get', 'pod', n, '-n', NS)
        if (not p or p['metadata'].get('deletionTimestamp')) and n not in gone: gone[n] = time.time() - t0
    time.sleep(0.25)
for n in ('no-tol', 'tol-8s', 'tol-forever'): print(f'    {n:<12} ' + (f'在打上 NoExecute 污点后 {gone[n]:.1f} 秒被驱逐' if n in gone else '25 秒后还在运行'))
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60); k('taint', 'node', T, 'k40-')

print('== 四:你没写,但已经存在的容忍')
k('apply', '-f', '-', input=bare('default-tol').replace(f'  nodeName: {T}\n', ''))
until(lambda: (kj('get', 'pod', 'default-tol', '-n', NS) or {}).get('spec', {}).get('nodeName'), 20)
p = kj('get', 'pod', 'default-tol', '-n', NS); print(f'  一个什么容忍都没写的 Pod,spec.tolerations 里被准入补上了:' + '; '.join(f'{t["key"]}:{t["effect"]}(tolerationSeconds={t.get("tolerationSeconds")})' for t in p['spec']['tolerations']))
cp = lambda nm, tol='': f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {nm}, namespace: {NS}}}\nspec:\n  nodeSelector: {{node-role.kubernetes.io/control-plane: ""}}\n  terminationGracePeriodSeconds: 0\n{tol}  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
k('apply', '-f', '-', input=cp('on-cp-no')); k('apply', '-f', '-', input=cp('on-cp-yes', tol2('{key: node-role.kubernetes.io/control-plane, operator: Exists, effect: NoSchedule}'))); time.sleep(6)
for nm in ('on-cp-no', 'on-cp-yes'):
    p = kj('get', 'pod', nm, '-n', NS); c = [x for x in p['status']['conditions'] if x['type'] == 'PodScheduled'][0]
    print(f'  nodeSelector 指向控制面,{"没有" if nm.endswith("no") else "写了"}对 control-plane 污点的容忍:phase={p["status"]["phase"]};nodeName={p["spec"].get("nodeName", "(未调度)")}' + (f';{c.get("message", "")[:110]}' if c['status'] != 'True' else ''))
rmns(NS)
