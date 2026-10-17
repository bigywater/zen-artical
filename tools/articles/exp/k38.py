import sys, os, re, time, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k38')
cn, dt_up = up('sched', cfg=config(workers=4))
load('busybox:1.36'); wait_nodes_ready()
NODES = ['kx-sched-worker', 'kx-sched-worker2', 'kx-sched-worker3', 'kx-sched-worker4']
ZONE = {NODES[0]: 'a', NODES[1]: 'a', NODES[2]: 'b', NODES[3]: 'c'}
for n, z in ZONE.items(): k('label', 'node', n, f'zone={z}', '--overwrite')
NS = ns('k38')
def dep(name, replicas, spread='', ns_=NS, extra=''):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {ns_}}}
spec:
  replicas: {replicas}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 0
{extra}{spread}      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
'''
def tsc(key, skew=1, when='DoNotSchedule', app='x', more=''):
    return f'      topologySpreadConstraints:\n      - {{maxSkew: {skew}, topologyKey: {key}, whenUnsatisfiable: {when}, labelSelector: {{matchLabels: {{app: {app}}}}}{more}}}\n'
def dist(app):
    ps = kj('get', 'pods', '-n', NS, '-l', f'app={app}')['items']
    nodes = collections.Counter(p['spec'].get('nodeName') for p in ps if p['spec'].get('nodeName')); pend = sum(1 for p in ps if not p['spec'].get('nodeName'))
    zones = collections.Counter(ZONE[n] for n in nodes.elements())
    return zones, nodes, pend
def fmt(app):
    z, n, pend = dist(app)
    return 'zone ' + ' '.join(f'{k_}={z.get(k_, 0)}' for k_ in 'abc') + ';节点 ' + ' '.join(f'{k_.replace("kx-sched-", "")}={v}' for k_, v in sorted(n.items())) + (f';Pending {pend} 个' if pend else '')
def settle(app, n, t=40): until(lambda: sum(dist(app)[0].values()) + dist(app)[2] >= n and True, t); time.sleep(3)
print(f'集群 {cn}(1 控制面 + 4 个 worker;给 worker 打 zone 标签:worker、worker2 → a,worker3 → b,worker4 → c)')
rc, o = k('get', 'nodes', '-L', 'zone,topology.kubernetes.io/zone', '--no-headers'); print('  ' + o.strip().replace('\n', '\n  '))

print('== 一:maxSkew=1、按 zone 分布——6 个副本')
k('apply', '-f', '-', input=dep('s1', 6, tsc('zone', app='s1'))); settle('s1', 6)
print(f'  topologySpreadConstraints(maxSkew 1,topologyKey zone,DoNotSchedule):{fmt("s1")}')
k('apply', '-f', '-', input=dep('s0', 6)); settle('s0', 6)
print(f'  对照:同样 6 个副本,没有任何约束:{fmt("s0")}')
k('delete', 'deploy', 's0', 's1', '-n', NS, '--wait=true', timeout=60)

print('== 二:已有的失衡不会被纠正——只是让新 Pod 避开多的那一边')
for i in range(4): k('apply', '-f', '-', input=dep(f'pin{i}', 1, extra=f'      nodeName: {NODES[i % 2]}\n').replace(f'app: pin{i}', 'app: s2'))
time.sleep(5)
print(f'  先用 nodeName 把 4 个 app=s2 的 Pod 强行放在 zone a 的两个节点上:{fmt("s2")}')
k('apply', '-f', '-', input=dep('s2new', 3, tsc('zone', app='s2')).replace('app: s2new', 'app: s2')); time.sleep(8)
z, n, pend = dist('s2'); print(f'  再加 3 个带 maxSkew=1 约束的 Pod:{fmt("s2")}(zone a 从 4 个没有再增加)')
for p in kj('get', 'pods', '-n', NS, '-l', 'app=s2')['items']:
    if p['metadata']['name'].startswith('s2new'): print(f'    新 Pod {p["metadata"]["name"][-5:]} → {p["spec"].get("nodeName", "(未调度)").replace("kx-sched-", "")}(zone {ZONE.get(p["spec"].get("nodeName"), "-")})')
k('delete', 'deploy', '-n', NS, '--all', '--wait=true', timeout=90)

print('== 三:zone c 的唯一节点不可用(打了污点)——DoNotSchedule 会让 Pod 卡住,除非忽略污点节点或改成 ScheduleAnyway')
k('taint', 'node', NODES[3], 'dedicated=other:NoSchedule', '--overwrite')
k('apply', '-f', '-', input=dep('t1', 6, tsc('zone', app='t1'))); settle('t1', 6); time.sleep(5)
print(f'  默认(nodeTaintsPolicy 缺省 = Ignore:统计 zone 时还把带污点的 worker4 算进去):{fmt("t1")}')
pend = [p for p in kj('get', 'pods', '-n', NS, '-l', 'app=t1')['items'] if not p['spec'].get('nodeName')]
if pend: print(f'    Pending Pod 的原因:{[c for c in pend[0]["status"]["conditions"] if c["type"] == "PodScheduled"][0].get("message", "")[:180]}')
k('apply', '-f', '-', input=dep('t2', 6, tsc('zone', app='t2', more=', nodeTaintsPolicy: Honor'))); settle('t2', 6); time.sleep(5)
print(f'  加 nodeTaintsPolicy: Honor(统计 zone 时排除掉 Pod 容忍不了污点的节点):{fmt("t2")}')
k('apply', '-f', '-', input=dep('t3', 6, tsc('zone', app='t3', when='ScheduleAnyway'))); settle('t3', 6); time.sleep(5)
print(f'  whenUnsatisfiable: ScheduleAnyway(只是“尽量”):{fmt("t3")}')
k('delete', 'deploy', '-n', NS, '--all', '--wait=true', timeout=90); k('taint', 'node', NODES[3], 'dedicated-')

print('== 四:多个约束一起算——zone 和 hostname 同时 maxSkew=1')
both = '      topologySpreadConstraints:\n      - {maxSkew: 1, topologyKey: zone, whenUnsatisfiable: DoNotSchedule, labelSelector: {matchLabels: {app: m1}}}\n      - {maxSkew: 1, topologyKey: kubernetes.io/hostname, whenUnsatisfiable: DoNotSchedule, labelSelector: {matchLabels: {app: m1}}}\n'
k('apply', '-f', '-', input=dep('m1', 6, both)); settle('m1', 6); time.sleep(4)
print(f'  zone 与 hostname 两个约束(都是 maxSkew 1):{fmt("m1")}')
k('scale', 'deploy/m1', '-n', NS, '--replicas=9'); settle('m1', 9); time.sleep(4); print(f'  扩到 9 个:{fmt("m1")}')
for n in NODES: k('label', 'node', n, 'zone-')
rmns(NS)
