import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k69')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS, NSB = ns('k69'), ns('k69b')
k('label', 'ns', NS, 'team=blue', '--overwrite'); k('label', 'ns', NSB, 'team=red', '--overwrite')
def pod(name, ns_, labels, image='busybox:1.36', cmd='[sleep, "3600"]'):
    lb = ', '.join(f'{a}: {b}' for a, b in labels.items())
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {ns_}, labels: {{{lb}}}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: {image}, imagePullPolicy: IfNotPresent, command: {cmd}}}]\n---\n'
k('apply', '-f', '-', input=pod('server', NS, {'app': 'server'}, 'nginx:1.27-alpine', '[nginx, "-g", "daemon off;"]') + pod('front', NS, {'role': 'frontend'}) + pod('other', NS, {'role': 'other'}) + pod('front', NSB, {'role': 'frontend'}))
for n_, p_ in ((NS, 'server'), (NS, 'front'), (NS, 'other'), (NSB, 'front')): k('wait', '--for=condition=Ready', f'pod/{p_}', '-n', n_, '--timeout=90s')
SIP = kj('get', 'pod', 'server', '-n', NS)['status']['podIP']
CL = [('同命名空间 role=frontend', NS, 'front'), ('同命名空间 role=other', NS, 'other'), ('k69b 命名空间 role=frontend', NSB, 'front')]
def conn(ns_, p_, target=SIP, t=2):
    t0 = time.time(); rc, o = k('exec', p_, '-n', ns_, '--', 'sh', '-c', f'wget -qO- -T {t} http://{target}:80 2>&1 | head -c 60'); dt = time.time() - t0
    return 'ok' if '<' in o or 'Welcome' in o else (f'超时' if dt > t * 0.9 else f'拒绝/失败')
def matrix(): return {lbl: conn(n_, p_) for lbl, n_, p_ in CL}
def apply_pol(y): k('apply', '-f', '-', input=y)
print(f'集群 {cn}(kindnet 自带 NetworkPolicy 实现);server({SIP}:80)在命名空间 {NS}(label team=blue),另有 k69b(team=red);三个客户端:{[c[0] for c in CL]}')

print('== 一:没有任何 NetworkPolicy——全都能通')
print(f'  连通性:{matrix()}')

print('== 二:default-deny ingress——选中所有 Pod、不写任何允许规则')
t0 = time.time(); apply_pol(f'apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata: {{name: deny-all, namespace: {NS}}}\nspec:\n  podSelector: {{}}\n  policyTypes: [Ingress]\n')
v, dt = until(lambda: conn(NS, 'front', t=1) != 'ok', 30, 0.2)
print(f'  应用策略后,第一次探测到 frontend 连不上用了 {dt:.1f} 秒(探测本身每次最多等 1 秒)')
t1 = time.time(); r = conn(NS, 'front', t=3); el = time.time() - t1
print(f'  连通性:{matrix()}')
print(f'  被拒的连接表现为“{r}”(wget -T 3 用时 {el:.1f} 秒)——包被 DROP,没有 RST,客户端只能等超时')
rc, o = k('exec', 'front', '-n', NS, '--', 'sh', '-c', 'nslookup kubernetes.default.svc.cluster.local 2>&1 | tail -2'); print(f'  default-deny ingress 只管进来的:front 自己往外查 DNS 仍然成功(退出码 {rc})→ {" ".join(o.split())[:90]!r}')

print('== 三:放行规则的语义——podSelector 与 namespaceSelector 是“或”还是“且”')
apply_pol(f'''apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: allow-front, namespace: {NS}}}
spec:
  podSelector: {{matchLabels: {{app: server}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
    - podSelector: {{matchLabels: {{role: frontend}}}}
''')
time.sleep(3); print(f'  只写 podSelector(role=frontend):{matrix()}(podSelector 不带 namespaceSelector 时只匹配策略所在命名空间的 Pod)')
apply_pol(f'''apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: allow-front, namespace: {NS}}}
spec:
  podSelector: {{matchLabels: {{app: server}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: {{matchLabels: {{team: red}}}}
      podSelector: {{matchLabels: {{role: frontend}}}}
''')
time.sleep(3); print(f'  同一个 from 条目里 namespaceSelector(team=red)+ podSelector(role=frontend)= 且:{matrix()}')
apply_pol(f'''apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: allow-front, namespace: {NS}}}
spec:
  podSelector: {{matchLabels: {{app: server}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: {{matchLabels: {{team: red}}}}
    - podSelector: {{matchLabels: {{role: frontend}}}}
''')
time.sleep(3); print(f'  拆成两个 from 条目(多了一个短横线)= 或:{matrix()}(team=red 的所有 Pod + 本命名空间的 frontend)')

print('== 四:策略叠加是并集;egress default-deny 会连 DNS 一起拦')
apply_pol(f'''apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: allow-other, namespace: {NS}}}
spec:
  podSelector: {{matchLabels: {{app: server}}}}
  policyTypes: [Ingress]
  ingress:
  - from:
    - podSelector: {{matchLabels: {{role: other}}}}
''')
time.sleep(3); print(f'  再加一条 allow-other(放行 role=other):{matrix()}(多条策略取并集,没有“拒绝”规则)')
k('delete', 'netpol', 'deny-all', 'allow-front', 'allow-other', '-n', NS)
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Service\nmetadata: {{name: server, namespace: {NS}}}\nspec: {{selector: {{app: server}}, ports: [{{port: 80}}]}}\n'); time.sleep(3)
print(f'  先删掉所有策略,front 用 Service 名访问:{conn(NS, "front", target="server")}')
apply_pol(f'apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata: {{name: deny-egress, namespace: {NS}}}\nspec:\n  podSelector: {{matchLabels: {{role: frontend}}}}\n  policyTypes: [Egress]\n')
time.sleep(3); print(f'  对 role=frontend 加 default-deny egress:用 IP 访问 {conn(NS, "front")};用 Service 名访问 {conn(NS, "front", target="server")}(DNS 查询也走 egress,被一起拦了)')
rc, o = k('exec', 'front', '-n', NS, '--', 'sh', '-c', 'nslookup server 2>&1 | head -3'); print(f'    nslookup server:{o.strip().splitlines()[-1] if o.strip() else ""}')
apply_pol(f'''apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: deny-egress, namespace: {NS}}}
spec:
  podSelector: {{matchLabels: {{role: frontend}}}}
  policyTypes: [Egress]
  egress:
  - to:
    - namespaceSelector: {{matchLabels: {{kubernetes.io/metadata.name: kube-system}}}}
    ports: [{{port: 53, protocol: UDP}}, {{port: 53, protocol: TCP}}]
  - to:
    - podSelector: {{matchLabels: {{app: server}}}}
    ports: [{{port: 80}}]
''')
time.sleep(3); print(f'  放行到 kube-system:53 和到 server:80 之后:用 IP {conn(NS, "front")};用 Service 名 {conn(NS, "front", target="server")}')
k('delete', 'ns', NS, NSB, '--wait=false')
