import sys, os, re, time, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k39')
cn, dt_up = up('sched', cfg=config(workers=4))
load('busybox:1.36'); wait_nodes_ready()
NODES = ['kx-sched-worker', 'kx-sched-worker2', 'kx-sched-worker3', 'kx-sched-worker4']
ZONE = {NODES[0]: 'a', NODES[1]: 'a', NODES[2]: 'b', NODES[3]: 'c'}
for n, z in ZONE.items(): k('label', 'node', n, f'zone={z}', '--overwrite')
for n, c in zip(NODES, (2, 4, 8, 16)): k('label', 'node', n, f'cores={c}', '--overwrite')
NS = ns('k39')
def dep(name, replicas, aff='', extra='', labels=''):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: {replicas}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}{labels}}}}}
    spec:
      terminationGracePeriodSeconds: 0
{extra}{aff}      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
'''
def aff(body): return '      affinity:\n' + ''.join('        ' + l + '\n' for l in body.strip('\n').splitlines())
def dist(app):
    ps = kj('get', 'pods', '-n', NS, '-l', f'app={app}')['items']
    nodes = collections.Counter(p['spec'].get('nodeName') for p in ps if p['spec'].get('nodeName') and not p['metadata'].get('deletionTimestamp')); pend = [p for p in ps if not p['spec'].get('nodeName')]
    return nodes, pend
def fmt(app):
    n, pend = dist(app)
    return '节点 ' + (' '.join(f'{k_.replace("kx-sched-", "")}={v}' for k_, v in sorted(n.items())) or '(无)') + (f';Pending {len(pend)} 个' if pend else '')
def settle(app, n, t=30): until(lambda: sum(dist(app)[0].values()) + len(dist(app)[1]) >= n, t); time.sleep(5)
def pend_msg(app):
    n, pend = dist(app)
    return [c for c in pend[0]['status']['conditions'] if c['type'] == 'PodScheduled'][0].get('message', '')[:200] if pend else ''
print(f'集群 {cn}(1 控制面 + 4 个 worker);节点标签:zone(worker、worker2=a,worker3=b,worker4=c)与 cores(worker=2,worker2=4,worker3=8,worker4=16)')

print('== 一:nodeAffinity——required 是硬条件,preferred 只是加分')
req = aff('''nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
    - matchExpressions: [{key: zone, operator: In, values: [b]}]''')
k('apply', '-f', '-', input=dep('na-req', 4, req)); settle('na-req', 4); print(f'  required zone In [b](4 个副本):{fmt("na-req")}')
req2 = aff('''nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
    - matchExpressions: [{key: cores, operator: Gt, values: ["6"]}, {key: zone, operator: NotIn, values: [c]}]''')
k('apply', '-f', '-', input=dep('na-gt', 4, req2)); settle('na-gt', 4); print(f'  required cores Gt 6 且 zone NotIn [c](同一个 matchExpressions 里的条件是 AND):{fmt("na-gt")}(只有 cores=8 的 worker3 满足)')
req3 = aff('''nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
    - matchExpressions: [{key: zone, operator: In, values: [b]}]
    - matchExpressions: [{key: zone, operator: In, values: [c]}]''')
k('apply', '-f', '-', input=dep('na-or', 6, req3)); settle('na-or', 6); print(f'  两个 nodeSelectorTerms(之间是 OR):zone In [b] 或 zone In [c]:{fmt("na-or")}')
pref = aff('''nodeAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    preference: {matchExpressions: [{key: zone, operator: In, values: [c]}]}''')
k('apply', '-f', '-', input=dep('na-pref', 8, pref)); settle('na-pref', 8); print(f'  preferred zone=c(weight 100,8 个副本):{fmt("na-pref")}')
k('delete', 'deploy', '-n', NS, '--all', '--wait=true', timeout=90)

print('== 二:podAntiAffinity required(topologyKey hostname)——每个节点最多一个,放不下就 Pending')
anti = aff('''podAntiAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
  - topologyKey: kubernetes.io/hostname
    labelSelector: {matchLabels: {app: aa}}''')
k('apply', '-f', '-', input=dep('aa', 5, anti)); settle('aa', 5); print(f'  5 个副本、4 个可用的 worker(控制面有污点):{fmt("aa")}')
print(f'    Pending Pod 的原因:{pend_msg("aa")}')
k('scale', 'deploy/aa', '-n', NS, '--replicas=4'); time.sleep(6); print(f'  缩到 4 个副本:{fmt("aa")}')

print('== 三:preferred 的反亲和——尽量分开,放不下就挤在一起')
k('delete', 'deploy', 'aa', '-n', NS, '--wait=true', timeout=60)
anti2 = aff('''podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    podAffinityTerm:
      topologyKey: kubernetes.io/hostname
      labelSelector: {matchLabels: {app: ap}}''')
k('apply', '-f', '-', input=dep('ap', 5, anti2)); settle('ap', 5); print(f'  5 个副本:{fmt("ap")}(全部都调度了)')
k('scale', 'deploy/ap', '-n', NS, '--replicas=9'); settle('ap', 9); print(f'  扩到 9 个:{fmt("ap")}')
k('delete', 'deploy', 'ap', '-n', NS, '--wait=true', timeout=60)

print('== 四:IgnoredDuringExecution——调度之后条件变了,已经在运行的 Pod 不会被移走')
k('apply', '-f', '-', input=dep('cache', 1, extra='      nodeName: kx-sched-worker3\n'))
until(lambda: sum(dist('cache')[0].values()) == 1, 30); time.sleep(2)
colo = aff('''podAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
  - topologyKey: kubernetes.io/hostname
    labelSelector: {matchLabels: {app: cache}}''')
k('apply', '-f', '-', input=dep('web', 3, colo)); settle('web', 3); print(f'  web 要求和 app=cache 的 Pod 在同一个节点(podAffinity required,hostname):{fmt("web")}(cache 在 worker3)')
k('delete', 'deploy', 'cache', '-n', NS, '--wait=true', timeout=60); time.sleep(2)
print(f'  删掉 cache 之后:已经运行的 web Pod {fmt("web")}(没有被驱逐)')
k('scale', 'deploy/web', '-n', NS, '--replicas=5'); settle('web', 5); print(f'  把 web 扩到 5 个:{fmt("web")};Pending 原因:{pend_msg("web")}')
k('delete', 'deploy', 'web', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=dep('lbl', 2, req)); settle('lbl', 2)
k('label', 'node', 'kx-sched-worker3', 'zone-'); time.sleep(3)
print(f'  nodeAffinity required zone In [b] 的 2 个 Pod 调度后,把 worker3 的 zone 标签删掉:{fmt("lbl")}(没有被驱逐);再加 1 个副本:', end='')
k('scale', 'deploy/lbl', '-n', NS, '--replicas=3'); settle('lbl', 3); print(fmt('lbl') + f';原因:{pend_msg("lbl")}')
for n in NODES: k('label', 'node', n, 'zone-', 'cores-')
rmns(NS)
