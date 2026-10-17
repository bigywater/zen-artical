import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k68')
cn, _ = up('main'); wait_nodes_ready()
load('nginx:1.27-alpine')
NS = ns('k68')
CP, WA, WB = 'kx-main-control-plane', 'kx-main-worker', 'kx-main-worker2'
def nip(n): return next(a['address'] for a in kj('get', 'node', n)['status']['addresses'] if a['type'] == 'InternalIP')
IP = {n: nip(n) for n in (CP, WA, WB)}
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: ConfigMap
metadata: {{name: ngx, namespace: {NS}}}
data:
  default.conf: |
    server {{ listen 80; location / {{ default_type text/plain; return 200 "client=$remote_addr\\n"; }} }}
---
apiVersion: v1
kind: Pod
metadata: {{name: web, namespace: {NS}, labels: {{app: web}}}}
spec:
  nodeName: {WA}
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: nginx:1.27-alpine
    imagePullPolicy: IfNotPresent
    volumeMounts: [{{name: cfg, mountPath: /etc/nginx/conf.d}}]
  volumes: [{{name: cfg, configMap: {{name: ngx}}}}]
''')
k('wait', '--for=condition=Ready', 'pod/web', '-n', NS, '--timeout=90s')
def svc(name, policy, typ='NodePort'):
    return f'apiVersion: v1\nkind: Service\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  type: {typ}\n  externalTrafficPolicy: {policy}\n  selector: {{app: web}}\n  ports: [{{port: 80}}]\n'
def hit(frm, to, port, n=1):
    out = []
    for _ in range(n):
        t0 = time.time(); rc, o = nx(frm, f'curl -s -m 3 http://{to}:{port}/ 2>&1; echo "rc=$?"'); out.append((o.strip().replace('\n', ' '), round(time.time() - t0, 1)))
    return out
print(f'集群 {cn};后端 Pod web 只在 {WA.replace("kx-main-", "")}({IP[WA]})上,nginx 返回它看到的客户端地址;客户端用控制面节点({IP[CP]},模拟集群外)去访问各节点的 NodePort')
print(f'  节点 IP:{ {n.replace("kx-main-", ""): v for n, v in IP.items()} };Pod IP {kj("get", "pod", "web", "-n", NS)["status"]["podIP"]}')

print('== 一:externalTrafficPolicy: Cluster(默认)——后端看到的是被 SNAT 之后的地址')
k('apply', '-f', '-', input=svc('s-cluster', 'Cluster')); time.sleep(3); np1 = kj('get', 'svc', 's-cluster', '-n', NS)['spec']['ports'][0]['nodePort']
for tgt in (WA, WB):
    r = hit(CP, IP[tgt], np1)[0]; print(f'  控制面 → {tgt.replace("kx-main-", "")}:{np1}({"有后端" if tgt == WA else "没有后端,要转发到别的节点"}):{r[0]}(用时 {r[1]} 秒)')
print('  对照:控制面节点的 IP 是 ' + IP[CP] + ';后端看到的不是它——kube-proxy 对集群外来源的 NodePort 流量做了 SNAT')

print('== 二:externalTrafficPolicy: Local——保留客户端源 IP,但只转发给本节点的后端')
k('apply', '-f', '-', input=svc('s-local', 'Local')); time.sleep(3); sv = kj('get', 'svc', 's-local', '-n', NS); np2 = sv['spec']['ports'][0]['nodePort']
print(f'  Service s-local:externalTrafficPolicy={sv["spec"]["externalTrafficPolicy"]};healthCheckNodePort={sv["spec"].get("healthCheckNodePort")}(NodePort 类型不分配,LoadBalancer 才有)')
r = hit(CP, IP[WA], np2)[0]; print(f'  控制面 → worker(有后端):{r[0]}(用时 {r[1]} 秒)——后端看到的是真实的客户端 {IP[CP]}')
r = hit(CP, IP[WB], np2)[0]; print(f'  控制面 → worker2(没有本地后端):{r[0]}(用时 {r[1]} 秒)——Local 不会转发给别的节点的后端')
rc, o = nx(WB, 'iptables-save -t filter 2>/dev/null | grep -E "k68/s-local" | sed -e "s/-m comment --comment \\"[^\\"]*\\" //"'); print(f'  worker2 的 filter 表里这个 Service 的规则:{[x.strip()[:150] for x in o.strip().splitlines()]}')

print('== 三:LoadBalancer + Local——healthCheckNodePort 让负载均衡器知道哪些节点有后端')
k('apply', '-f', '-', input=svc('s-lb', 'Local', 'LoadBalancer')); time.sleep(3); sv = kj('get', 'svc', 's-lb', '-n', NS); hc = sv['spec'].get('healthCheckNodePort')
print(f'  Service s-lb(LoadBalancer + Local):healthCheckNodePort={hc}')
def hc_status(n):
    rc, o = nx(CP, f'curl -s -m 3 -w " HTTP=%{{http_code}}" http://{IP[n]}:{hc}/ 2>&1'); b = json.loads(o[:o.rindex('}') + 1]) if '}' in o else {}
    return f'localEndpoints={b.get("localEndpoints")} HTTP={o.rsplit("HTTP=", 1)[-1].strip()}'
for n in (WA, WB, CP):
    print(f'  curl {n.replace("kx-main-", "")}:{hc}/ → {hc_status(n)}')
k('delete', 'pod', 'web', '-n', NS, '--wait=true', timeout=60); time.sleep(4)
print(f'  删掉后端 Pod 之后 worker:{hc} → {hc_status(WA)}(没有本地后端:返回 503,负载均衡器据此把这个节点摘掉)')

print('== 四:Cluster 模式的代价——多一跳')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: web, namespace: {NS}, labels: {{app: web}}}}
spec:
  nodeName: {WA}
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: nginx:1.27-alpine
    imagePullPolicy: IfNotPresent
    volumeMounts: [{{name: cfg, mountPath: /etc/nginx/conf.d}}]
  volumes: [{{name: cfg, configMap: {{name: ngx}}}}]
'''); k('wait', '--for=condition=Ready', 'pod/web', '-n', NS, '--timeout=90s'); time.sleep(3)
rc, o = nx(WB, f'conntrack -L -p tcp --dport {np1} 2>/dev/null | head -3'); print(f'  Cluster 模式下经过 worker2(没有后端)的连接在 worker2 的 conntrack 里:')
hit(CP, IP[WB], np1)
rc, o = nx(WB, f'conntrack -L -p tcp 2>/dev/null | grep "dport={np1}" | head -2'); [print('    ' + re.sub(r'\s+', ' ', l)[:210]) for l in o.strip().splitlines()]
print(f'  含义:CP→worker2:{np1} 先在 worker2 被 DNAT 成 Pod IP:80,再 SNAT 成 worker2 的地址,跨节点送到 worker 上的 Pod;回包原路返回——请求在集群内绕了一圈')
k('delete', 'ns', NS, '--wait=false')
