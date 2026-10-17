import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k105')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k105')
W = 'kx-main-worker'
def short(o, n=3, w=360): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def ex(p_, c): return k('exec', p_, '-n', NS, '--', 'sh', '-c', c)[1].strip()
print(f'集群 {cn};Downward API 把 Pod 自己的元数据和资源信息,以环境变量或文件的形式交给容器,容器不需要(也不应该)为此去调 API Server')
POD = f'''apiVersion: v1
kind: Pod
metadata:
  name: me
  namespace: {NS}
  labels: {{app: demo, tier: web}}
  annotations: {{owner: team-a}}
spec:
  nodeName: {W}
  serviceAccountName: default
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sleep, "3600"]
    resources: {{requests: {{cpu: 250m, memory: 64Mi}}, limits: {{cpu: 500m, memory: 128Mi}}}}
    env:
    - {{name: POD_NAME, valueFrom: {{fieldRef: {{fieldPath: metadata.name}}}}}}
    - {{name: POD_NS, valueFrom: {{fieldRef: {{fieldPath: metadata.namespace}}}}}}
    - {{name: POD_UID, valueFrom: {{fieldRef: {{fieldPath: metadata.uid}}}}}}
    - {{name: NODE_NAME, valueFrom: {{fieldRef: {{fieldPath: spec.nodeName}}}}}}
    - {{name: SA_NAME, valueFrom: {{fieldRef: {{fieldPath: spec.serviceAccountName}}}}}}
    - {{name: POD_IP, valueFrom: {{fieldRef: {{fieldPath: status.podIP}}}}}}
    - {{name: HOST_IP, valueFrom: {{fieldRef: {{fieldPath: status.hostIP}}}}}}
    - {{name: LABEL_APP, valueFrom: {{fieldRef: {{fieldPath: "metadata.labels['app']"}}}}}}
    - {{name: LABEL_TIER, valueFrom: {{fieldRef: {{fieldPath: "metadata.labels['tier']"}}}}}}
    - {{name: ANN_OWNER, valueFrom: {{fieldRef: {{fieldPath: "metadata.annotations['owner']"}}}}}}
    - {{name: CPU_LIMIT, valueFrom: {{resourceFieldRef: {{resource: limits.cpu}}}}}}
    - {{name: CPU_LIMIT_M, valueFrom: {{resourceFieldRef: {{resource: limits.cpu, divisor: 1m}}}}}}
    - {{name: MEM_LIMIT, valueFrom: {{resourceFieldRef: {{resource: limits.memory}}}}}}
    - {{name: MEM_LIMIT_MI, valueFrom: {{resourceFieldRef: {{resource: limits.memory, divisor: 1Mi}}}}}}
    - {{name: MEM_REQ_MI, valueFrom: {{resourceFieldRef: {{resource: requests.memory, divisor: 1Mi}}}}}}
    volumeMounts: [{{name: info, mountPath: /etc/podinfo}}]
  volumes:
  - name: info
    downwardAPI:
      items:
      - {{path: labels, fieldRef: {{fieldPath: metadata.labels}}}}
      - {{path: annotations, fieldRef: {{fieldPath: metadata.annotations}}}}
      - {{path: cpu_limit, resourceFieldRef: {{containerName: c, resource: limits.cpu, divisor: 1m}}}}
'''
k('apply', '-f', '-', input=POD); k('wait', '--for=condition=Ready', 'pod/me', '-n', NS, '--timeout=60s')

print('== 一:环境变量——fieldRef 与 resourceFieldRef')
for v_ in ('POD_NAME', 'POD_NS', 'POD_UID', 'NODE_NAME', 'SA_NAME', 'POD_IP', 'HOST_IP', 'LABEL_APP', 'ANN_OWNER'): print(f'  {v_:<10}= {ex("me", "echo $" + v_)}')
print(f'  对照 Pod 对象:uid={kj("get", "pod", "me", "-n", NS)["metadata"]["uid"]};podIP={kj("get", "pod", "me", "-n", NS)["status"]["podIP"]};hostIP={kj("get", "pod", "me", "-n", NS)["status"]["hostIP"]}')

print('== 二:资源信息和 divisor(单位换算)')
for v_, d in (('CPU_LIMIT', 'limits.cpu(默认 divisor 1,向上取整成核)'), ('CPU_LIMIT_M', 'limits.cpu, divisor: 1m'), ('MEM_LIMIT', 'limits.memory(默认字节)'), ('MEM_LIMIT_MI', 'limits.memory, divisor: 1Mi'), ('MEM_REQ_MI', 'requests.memory, divisor: 1Mi')): print(f'  {v_:<13}= {ex("me", "echo $" + v_):<12}({d})')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: nolimit, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n    env:\n    - {{name: CPU_LIMIT_M, valueFrom: {{resourceFieldRef: {{resource: limits.cpu, divisor: 1m}}}}}}\n    - {{name: MEM_LIMIT_MI, valueFrom: {{resourceFieldRef: {{resource: limits.memory, divisor: 1Mi}}}}}}\n')
k('wait', '--for=condition=Ready', 'pod/nolimit', '-n', NS, '--timeout=60s'); n = kj('get', 'node', W)['status']['allocatable']
print(f'  没有写 limits 的容器:CPU_LIMIT_M={ex("nolimit", "echo $CPU_LIMIT_M")}、MEM_LIMIT_MI={ex("nolimit", "echo $MEM_LIMIT_MI")}——退回节点的 allocatable(节点 cpu={n["cpu"]} 核、memory={n["memory"]}),不是 0 或空')

print('== 三:卷里的文件会更新,环境变量不会')
print(f'  /etc/podinfo/labels:{ex("me", "cat /etc/podinfo/labels").splitlines()};annotations:{[l for l in ex("me", "cat /etc/podinfo/annotations").splitlines() if "kubernetes.io" not in l]};cpu_limit={ex("me", "cat /etc/podinfo/cpu_limit")}')
k('label', 'pod', 'me', '-n', NS, 'tier=db', 'extra=yes', '--overwrite'); t0 = time.time()
v, dt = until(lambda: 'tier="db"' in ex('me', 'cat /etc/podinfo/labels'), 150, 1)
print(f'  用 kubectl label 把 tier 改成 db 并新增 extra=yes:文件 {dt:.0f} 秒后变化:{ex("me", "cat /etc/podinfo/labels").splitlines()}')
print(f'  同一时刻环境变量 LABEL_TIER 仍是 {ex("me", "echo $LABEL_TIER")!r}(创建时的值),而文件里已经是 tier="db"——环境变量在容器启动时一次性取值;要看到变化就得读卷里的文件')
print(f'  文件路径是符号链接:{ex("me", "ls -l /etc/podinfo | tail -n +2 | awk \'{print $9, $10, $11}\' | head -4").replace(chr(10), ";")}(同 ConfigMap 的 ..data 原子切换)')

print('== 四:能写什么、不能写什么')
for desc, fp in (('metadata.labels(整个 map,环境变量里)', 'metadata.labels'), ('status.phase', 'status.phase'), ('spec.containers[0].name', 'spec.containers[0].name'), ('metadata.name 拼写错 metadata.nam', 'metadata.nam')):
    y = f'apiVersion: v1\nkind: Pod\nmetadata: {{name: bad, namespace: {NS}}}\nspec:\n  containers:\n  - name: c\n    image: busybox:1.36\n    env: [{{name: X, valueFrom: {{fieldRef: {{fieldPath: "{fp}"}}}}}}]\n'
    rc, o = k('apply', '-f', '-', '--dry-run=server', input=y); print(f'  环境变量 fieldPath: {desc}:退出码 {rc};{short(o, 2, 360)[-1] if rc else "通过"}')
y = f'apiVersion: v1\nkind: Pod\nmetadata: {{name: bad, namespace: {NS}}}\nspec:\n  containers:\n  - name: c\n    image: busybox:1.36\n    volumeMounts: [{{name: i, mountPath: /i}}]\n  volumes:\n  - name: i\n    downwardAPI:\n      items: [{{path: phase, fieldRef: {{fieldPath: status.phase}}}}]\n'
rc, o = k('apply', '-f', '-', '--dry-run=server', input=y); print(f'  卷里写 status.phase:退出码 {rc};{short(o, 2, 360)[-1] if rc else "通过"}')
k('delete', 'ns', NS, '--wait=false')
