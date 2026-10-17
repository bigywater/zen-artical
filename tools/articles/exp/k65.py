import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k65')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k65')
NODE = 'kx-main-worker'
def ipt(table='nat'): return nx(NODE, f'iptables-save -t {table} 2>/dev/null', raw=True)[1]
def dep(n):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: web, namespace: {NS}}}
spec:
  replicas: {n}
  selector: {{matchLabels: {{app: web}}}}
  template:
    metadata: {{labels: {{app: web}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: busybox:1.36
        command: [sh, -c, "mkdir -p /www; echo $HOSTNAME > /www/index.html; exec httpd -f -p 80 -h /www"]
        readinessProbe: {{httpGet: {{path: /, port: 80}}, periodSeconds: 1}}
---
apiVersion: v1
kind: Service
metadata: {{name: web, namespace: {NS}}}
spec: {{type: NodePort, selector: {{app: web}}, ports: [{{port: 80}}]}}
'''
def svc_chain(text, cip):
    m = re.search(rf'-A KUBE-SERVICES -d {re.escape(cip)}/32 -p tcp -m comment --comment "{NS}/web cluster IP" -m tcp --dport 80 -j (KUBE-SVC-\w+)', text)
    return m.group(1) if m else None
def chain_rules(text, name): return [l for l in text.splitlines() if l.startswith(f'-A {name} ')]
def short(l): return re.sub(r'-m comment --comment "[^"]*" ', '', l).replace('-A ', '')
k('apply', '-f', '-', input=dep(3)); k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); time.sleep(3)
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: cli, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n')
until(lambda: kj('get', 'pod', 'cli', '-n', NS)['status'].get('phase') == 'Running', 60, 0.3)
s = kj('get', 'svc', 'web', '-n', NS); cip = s['spec']['clusterIP']; np_ = s['spec']['ports'][0]['nodePort']
pods = {p['status']['podIP']: p['metadata']['name'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']}
print(f'集群 {cn};kube-proxy 模式 iptables(用 nf_tables 后端的 iptables 命令),在节点 {NODE.replace("kx-main-", "")} 上读 nat 表;Service web 的 ClusterIP {cip}:80,NodePort {np_},3 个后端 {sorted(i.split(".", 2)[2] for i in pods)}(IP 末两段)')

print('== 一:一个 Service 在 nat 表里的三层链')
txt = ipt(); sc = svc_chain(txt, cip)
print(f'  入口:KUBE-SERVICES 里匹配 {cip}:80 的规则 → 跳到 {sc}')
print(f'  KUBE-SERVICES 里这条规则:{short([l for l in txt.splitlines() if cip in l and "KUBE-SERVICES" in l][0])}')
for l in chain_rules(txt, sc): print(f'  {short(l)}')
seps = re.findall(r'-j (KUBE-SEP-\w+)', '\n'.join(chain_rules(txt, sc)))
for sep in seps[:1]:
    for l in chain_rules(txt, sep): print(f'  {short(l)}')
for sep in seps[1:]:
    for l in chain_rules(txt, sep):
        if 'DNAT' in l: print(f'  {short(l)}')
print(f'  整个 nat 表有 {len(txt.splitlines())} 行,其中和 k65/web 有关的 {sum(1 for l in txt.splitlines() if "k65/web" in l)} 行')

print('== 二:随机负载均衡——statistic 概率怎么算')
for n in (2, 5):
    k('scale', 'deploy/web', '-n', NS, f'--replicas={n}'); k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s')
    time.sleep(4); txt = ipt(); sc = svc_chain(txt, cip)
    probs = []
    for l in [x for x in chain_rules(txt, sc) if '-j KUBE-SEP' in x]:
        m = re.search(r'--probability ([\d.]+)', l); probs.append(m.group(1) if m else '(无条件)')
    print(f'  {n} 个副本:{sc} 里依次的 probability = {probs}(从前到后依次是 1/{n}, 1/{n - 1}, …, 1/2,最后一条无条件)')
k('scale', 'deploy/web', '-n', NS, '--replicas=3'); k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); time.sleep(4)
pods = {p['status']['podIP']: p['metadata']['name'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']}
N = 300
rc, o = k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'for i in $(seq {N}); do wget -qO- -T 2 http://{cip}:80; done | sort | uniq -c')
print(f'  回到 3 个副本,从 cli 发 {N} 个新连接到 ClusterIP,按后端 Pod 统计:{[(l.split()[1][-5:], int(l.split()[0])) for l in o.strip().splitlines()]}(每个连接各自抽签,期望 {N // 3} 左右)')

print('== 三:更新延迟与没有后端时的行为')
k('scale', 'deploy/web', '-n', NS, '--replicas=4')
txt0 = ipt(); n0 = len(re.findall(r'-j (KUBE-SEP-\w+)', '\n'.join(chain_rules(txt0, svc_chain(txt0, cip)))))
t0 = time.time()
def has4():
    t = ipt(); return len(re.findall(r'-j (KUBE-SEP-\w+)', '\n'.join(chain_rules(t, svc_chain(t, cip))))) >= 4
v, dt = until(has4, 60, 0.3)
rdy = kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']
print(f'  scale 到 4 个副本:新 Pod 就绪后,iptables 里 {svc_chain(txt0, cip)} 的 SEP 数从 {n0} 变 4 用了 {dt:.1f} 秒(从 scale 算起,包含 Pod 启动和就绪)')
k('scale', 'deploy/web', '-n', NS, '--replicas=0'); until(lambda: not kj('get', 'pods', '-n', NS, '-l', 'app=web')['items'], 60, 0.5); time.sleep(4)
f = nx(NODE, 'iptables-save -t filter 2>/dev/null', raw=True)[1]; rej = [short(l) for l in f.splitlines() if f'{NS}/web' in l]
print(f'  副本数 0:nat 表里 {NS}/web 的 SEP 规则 {sum(1 for l in ipt().splitlines() if "k65/web" in l and "KUBE-SEP" in l)} 行;filter 表里出现 REJECT 规则:{rej}')
t0 = time.time(); rc, o = k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'wget -qO- -T 3 http://{cip}:80 2>&1; echo "exit=$?"'); print(f'  访问 ClusterIP:{o.strip().splitlines()[-2:]};几乎立刻被拒绝(用时 {time.time() - t0:.1f} 秒,含 kubectl exec 开销),而不是等超时')

print('== 四:NodePort 与 conntrack')
k('scale', 'deploy/web', '-n', NS, '--replicas=3'); k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); time.sleep(4); txt = ipt()
print('  NodePort 入口:' + '; '.join(short(l) for l in txt.splitlines() if 'KUBE-NODEPORTS' in l and 'k65/web' in l)[:300])
print(f'  KUBE-SERVICES 末尾:{short([l for l in txt.splitlines() if l.startswith("-A KUBE-SERVICES") and "NODEPORTS" in l][0])}')
k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'wget -qO- -T 2 http://{cip}:80 >/dev/null'); 
rc, o = nx(NODE, f'conntrack -L -d {cip} 2>&1 | head -3')
print(f'  conntrack 表里 ClusterIP 的连接(这个节点上):{o.strip().splitlines()[:2] if o.strip() else "(没有)"}')
rc, o = k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'wget -qO- -T 2 http://{cip}:80 >/dev/null; echo ok')
k('delete', 'ns', NS, '--wait=false')
