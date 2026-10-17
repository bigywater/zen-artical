import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k62')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS = ns('k62')
def ex(name, cmd): return k('exec', name, '-n', NS, '--', 'sh', '-c', cmd)[1].strip()
def addrs(name, typ=''):
    o = ex('cli', f'nslookup {typ} {name} 2>&1')
    r = []
    for l in o.splitlines():
        l = l.strip()
        if l.startswith('Address') and ':53' not in l: r.append(l.split()[-1])
        elif 'service =' in l: r.append(l.split('service =')[1].strip())
    return r or ['(无记录)']
POD = lambda name, extra='': f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
'''
k('apply', '-f', '-', input=POD('cli'))
k('apply', '-f', '-', input=f'''apiVersion: apps/v1
kind: StatefulSet
metadata: {{name: web, namespace: {NS}}}
spec:
  serviceName: hl
  replicas: 3
  podManagementPolicy: Parallel
  selector: {{matchLabels: {{app: web}}}}
  template:
    metadata: {{labels: {{app: web}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: web
        image: nginx:1.27-alpine
        imagePullPolicy: IfNotPresent
        ports: [{{name: http, containerPort: 80}}]
        readinessProbe: {{httpGet: {{path: /, port: 80}}, periodSeconds: 1}}
---
apiVersion: v1
kind: Service
metadata: {{name: hl, namespace: {NS}}}
spec: {{clusterIP: None, selector: {{app: web}}, ports: [{{name: http, port: 80}}]}}
---
apiVersion: v1
kind: Service
metadata: {{name: cip, namespace: {NS}}}
spec: {{selector: {{app: web}}, ports: [{{name: http, port: 80}}]}}
''')
k('rollout', 'status', 'sts/web', '-n', NS, '--timeout=120s'); until(lambda: kj('get', 'pod', 'cli', '-n', NS)['status'].get('phase') == 'Running', 60, 0.3)
pods = {p['metadata']['name']: p['status']['podIP'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']}
print(f'集群 {cn};headless Service(clusterIP: None)没有虚拟 IP,DNS 直接返回后端 Pod 的 IP')
print(f'  3 个 Pod:{dict(sorted(pods.items()))}')

print('== 一:普通 Service 与 headless Service 的 A 记录')
print(f'  普通 Service cip({kj("get", "svc", "cip", "-n", NS)["spec"]["clusterIP"]}):nslookup cip → {addrs("cip")}')
hl = addrs('hl'); print(f'  headless Service hl:nslookup hl → {hl}(是否恰好是三个 Pod IP:{sorted(hl) == sorted(pods.values())})')
orders = []
for i in range(4): orders.append([ip.split(".")[-1] for ip in addrs('hl')])
print(f'  连续查 4 次 hl 的返回顺序(只显示 IP 最后一段):{orders}(CoreDNS 默认会打乱 A 记录的顺序,客户端拿到的第一个不固定)')
rc, o = k('get', 'svc', 'hl', '-n', NS); print('  kubectl get svc hl:' + o.strip().splitlines()[-1])

print('== 二:StatefulSet 给每个 Pod 一个稳定的 DNS 名')
for i in range(3):
    print(f'  web-{i}.hl.{NS}.svc.cluster.local → {addrs(f"web-{i}.hl.{NS}.svc.cluster.local")}(Pod IP {pods[f"web-{i}"]})')
old = pods['web-1']; k('delete', 'pod', 'web-1', '-n', NS, '--wait=true', timeout=60); k('rollout', 'status', 'sts/web', '-n', NS, '--timeout=90s')
until(lambda: kj('get', 'pod', 'web-1', '-n', NS)['status'].get('podIP'), 30, 0.3)
t0 = time.time(); new = kj('get', 'pod', 'web-1', '-n', NS)['status']['podIP']
print(f'  删掉 web-1 并等它重建:IP {old} → {new};web-1.hl 现在解析为 {addrs(f"web-1.hl.{NS}.svc.cluster.local")}(名字不变,IP 跟着变)')
rc, o = k('exec', 'cli', '-n', NS, '--', 'nslookup', 'web-1.cip'); print(f'  普通 Service 没有这种名字:nslookup web-1.cip → {addrs(f"web-1.cip.{NS}.svc.cluster.local")}')

print('== 三:没就绪的 Pod 默认不在 DNS 里;publishNotReadyAddresses 改变它')
k('exec', 'web-2', '-n', NS, '--', 'sh', '-c', 'mv /usr/share/nginx/html/index.html /usr/share/nginx/html/index.bak')
until(lambda: not [c for c in kj('get', 'pod', 'web-2', '-n', NS)['status']['conditions'] if c['type'] == 'Ready' and c['status'] == 'True'], 30, 0.5)
pods = {p['metadata']['name']: p['status']['podIP'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']}
time.sleep(6)
print(f'  让 web-2 的就绪探针失败(把 index.html 移走):hl 返回 {len(addrs("hl"))} 个地址 {sorted(a.split(".")[-1] for a in addrs("hl"))};web-2 的 IP 末段是 {pods["web-2"].split(".")[-1]}')
print(f'    web-2.hl 单独解析:{addrs(f"web-2.hl.{NS}.svc.cluster.local")}')
k('patch', 'svc', 'hl', '-n', NS, '--type=merge', '-p', '{"spec":{"publishNotReadyAddresses":true}}'); time.sleep(8)
print(f'  给 hl 加 publishNotReadyAddresses: true:hl 返回 {len(addrs("hl"))} 个地址 {sorted(a.split(".")[-1] for a in addrs("hl"))};web-2.hl → {addrs(f"web-2.hl.{NS}.svc.cluster.local")}(没就绪的 Pod 也出现了)')

print('== 四:SRV 记录——端口名也在 DNS 里')
srv = ex('cli', f'nslookup -type=SRV _http._tcp.hl.{NS}.svc.cluster.local 2>&1'); lines = [l.split('service =')[1].strip() for l in srv.splitlines() if 'service =' in l]
print(f'  nslookup -type=SRV _http._tcp.hl.{NS}.svc.cluster.local:{len(lines)} 条;例:{lines[:2]}')
print(f'  普通 Service:SRV _http._tcp.cip → {[l.split('service =')[1].strip() for l in ex("cli", f"nslookup -type=SRV _http._tcp.cip.{NS}.svc.cluster.local 2>&1").splitlines() if "service =" in l]}(指向 Service 自身的名字,端口 80)')
k('delete', 'ns', NS, '--wait=false')
