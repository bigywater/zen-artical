import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k61')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS = ns('k61')
def ex(name, cmd): return k('exec', name, '-n', NS, '--', 'sh', '-c', cmd)[1].strip()
def nodes(): return [n['metadata']['name'] for n in kj('get', 'nodes')['items']]
def nip(n): return next(a['address'] for a in kj('get', 'node', n)['status']['addresses'] if a['type'] == 'InternalIP')
k('apply', '-f', '-', input=f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: web, namespace: {NS}}}
spec:
  replicas: 1
  selector: {{matchLabels: {{app: web}}}}
  template:
    metadata: {{labels: {{app: web}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: web
        image: nginx:1.27-alpine
        imagePullPolicy: IfNotPresent
        ports: [{{containerPort: 80}}]
---
apiVersion: v1
kind: Pod
metadata: {{name: cli, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); until(lambda: kj('get', 'pod', 'cli', '-n', NS)['status'].get('phase') == 'Running', 60, 0.3)
webpod = kj('get', 'pods', '-n', NS, '-l', 'app=web')['items'][0]; wnode = webpod['spec']['nodeName']; wip = webpod['status']['podIP']
others = [n for n in nodes() if n != wnode]
def svc(name, typ, extra=''):
    return f'apiVersion: v1\nkind: Service\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  type: {typ}\n  selector: {{app: web}}\n  ports: [{{port: 8080, targetPort: 80{extra}}}]\n'
def get(cmd_from, url):
    if cmd_from == 'pod': return ex('cli', f'wget -qO- -T 3 {url} 2>&1 | grep -o "<title>[^<]*" | head -1 || true') or '(失败)'
    rc, o = nx(cmd_from, f'curl -s -m 3 http://{url} 2>&1 | head -c 400'); return ('<title>' in o and re.search(r'<title>[^<]*', o).group(0)) or ('(失败) ' + o.strip()[:80])
print(f'集群 {cn};Service 把一组 Pod 暴露成一个稳定的虚拟地址;后端 nginx 在节点 {wnode.replace("kx-main-", "")} 上,Pod IP {wip}')

print('== 一:ClusterIP——只在集群内部可达')
k('apply', '-f', '-', input=svc('s-cip', 'ClusterIP')); time.sleep(2)
s = kj('get', 'svc', 's-cip', '-n', NS); cip = s['spec']['clusterIP']
print(f'  Service s-cip:type={s["spec"]["type"]};clusterIP={cip}(来自 Service CIDR {kj("get", "cm", "kubeadm-config", "-n", "kube-system")["data"]["ClusterConfiguration"].split("serviceSubnet:")[1].split()[0]});port 8080 → targetPort 80')
print(f'  从 Pod cli 访问 {cip}:8080 → {get("pod", f"{cip}:8080")};用 Service DNS s-cip:8080 → {get("pod", "s-cip:8080")}')
print(f'  从节点 {wnode.replace("kx-main-", "")}(有后端的节点)访问 → {get(wnode, f"{cip}:8080")};从别的节点 {others[0].replace("kx-main-", "")} 访问 → {get(others[0], f"{cip}:8080")}(kube-proxy 在每个节点上都写了规则)')
rc, o = sh('curl', '-s', '-m', '3', f'http://{cip}:8080', raw=True); print(f'  从宿主机(Mac)直接访问 {cip}:8080:{"可达" if "<title>" in o else "不可达(超时)"}')
print(f'  直接访问 Pod IP {wip}:80 → {get("pod", f"{wip}:80")}(Pod IP 也通,但 Pod 重建后会变)')

print('== 二:NodePort——在每个节点上开一个端口')
k('apply', '-f', '-', input=svc('s-np', 'NodePort')); time.sleep(2)
s = kj('get', 'svc', 's-np', '-n', NS); np_ = s['spec']['ports'][0]['nodePort']
print(f'  Service s-np:type=NodePort;自动分配 nodePort={np_}(范围 30000-32767);同时也有 clusterIP={s["spec"]["clusterIP"]}(NodePort 是 ClusterIP 的超集)')
for n in nodes():
    print(f'  从 Pod cli 访问节点 {n.replace("kx-main-", "")}({nip(n)}):{np_} → {get("pod", f"{nip(n)}:{np_}")}' + ('(这个节点有后端 Pod)' if n == wnode else '(这个节点没有后端 Pod,也能通)'))
rc, o = sh('curl', '-s', '-m', '3', f'http://localhost:{np_}', raw=True); print(f'  宿主机访问 localhost:{np_}(kind 没有映射这个端口):{"可达" if "<title>" in o else "不可达"}')
rc, o = k('apply', '-f', '-', input=svc('s-bad', 'NodePort', ', nodePort: 80')); print(f'  指定 nodePort: 80:退出码 {rc};{o.strip().splitlines()[0][:200]}')
rc, o = k('apply', '-f', '-', input=svc('s-pin', 'NodePort', ', nodePort: 31234')); print(f'  指定 nodePort: 31234:退出码 {rc};实际 nodePort={kj("get", "svc", "s-pin", "-n", NS)["spec"]["ports"][0]["nodePort"]}')
rc, o = k('apply', '-f', '-', input=svc('s-pin2', 'NodePort', ', nodePort: 31234')); print(f'  另一个 Service 也要 31234:退出码 {rc};{o.strip().splitlines()[0][:200] if o.strip() else ""}')

print('== 三:LoadBalancer——没有云厂商时只会 pending')
k('apply', '-f', '-', input=svc('s-lb', 'LoadBalancer')); time.sleep(8)
s = kj('get', 'svc', 's-lb', '-n', NS); print(f'  Service s-lb:type=LoadBalancer;status.loadBalancer={s["status"].get("loadBalancer")};clusterIP={s["spec"]["clusterIP"]};nodePort={s["spec"]["ports"][0].get("nodePort")}')
rc, o = k('get', 'svc', 's-lb', '-n', NS); print('  kubectl get svc:' + o.strip().splitlines()[-1])
nps = s['spec']['ports'][0]['nodePort']; print(f'  LoadBalancer 创建时同时分配了 nodePort {nps};用它访问 {nip(wnode)}:{nps} → {get("pod", f"{nip(wnode)}:{nps}")}(云上的负载均衡器就是把流量转发到这些 NodePort)')
k('apply', '-f', '-', input=svc('s-lb2', 'LoadBalancer', '').replace('  type: LoadBalancer\n', '  type: LoadBalancer\n  allocateLoadBalancerNodePorts: false\n')); time.sleep(3)
print(f'  allocateLoadBalancerNodePorts: false 的 s-lb2:nodePort={kj("get", "svc", "s-lb2", "-n", NS)["spec"]["ports"][0].get("nodePort")}')
ev = [e['reason'] + ': ' + e['message'][:100] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=s-lb')['items']]; print(f'    s-lb 的事件:{ev or "(没有——没有云控制器来处理它)"}')

print('== 四:ExternalName——只是一条 DNS 别名')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Service\nmetadata: {{name: s-ext, namespace: {NS}}}\nspec:\n  type: ExternalName\n  externalName: example.com\n')
s = kj('get', 'svc', 's-ext', '-n', NS); print(f'  Service s-ext:clusterIP={s["spec"].get("clusterIP")!r};externalName={s["spec"]["externalName"]}')
o = ex('cli', 'nslookup s-ext.k61.svc.cluster.local 2>&1'); cname = [l.strip() for l in o.splitlines() if 'canonical name' in l][:1]; addrs = sorted({l.split()[-1] for l in o.splitlines() if l.startswith('Address') and '#' not in l})
print(f'  在 Pod 里 nslookup s-ext:{cname};最后解析到 {len(addrs)} 个外部地址(不是 Service 的 IP)')
rc, o = nx(wnode, 'iptables-save 2>/dev/null | grep -c "k61/s-ext"'); print(f'  iptables 里有 s-ext 的规则吗:{o.strip()} 条(没有 kube-proxy 规则,不经过 Service 转发)')
k('delete', 'ns', NS, '--wait=false')
