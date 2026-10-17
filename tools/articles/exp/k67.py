import sys, os, re, time, json, datetime, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k67')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k67')
W = 'kx-main-worker'
k('apply', '-f', '-', input=f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: web, namespace: {NS}}}
spec:
  replicas: 3
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
metadata: {{name: plain, namespace: {NS}}}
spec: {{selector: {{app: web}}, ports: [{{port: 80}}]}}
---
apiVersion: v1
kind: Service
metadata: {{name: sticky, namespace: {NS}}}
spec: {{selector: {{app: web}}, sessionAffinity: ClientIP, ports: [{{port: 80}}]}}
---
apiVersion: v1
kind: Pod
metadata: {{name: cli1, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
---
apiVersion: v1
kind: Pod
metadata: {{name: cli2, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=120s'); until(lambda: all(kj('get', 'pod', c, '-n', NS)['status'].get('phase') == 'Running' for c in ('cli1', 'cli2')), 60, 0.3); time.sleep(3)
def get(pod, svc): return k('exec', pod, '-n', NS, '--', 'sh', '-c', f'wget -qO- -T 2 http://{svc}:80 2>&1')[1].strip()[-5:]
def many(pod, svc, n=30):
    rc, o = k('exec', pod, '-n', NS, '--', 'sh', '-c', f'for i in $(seq {n}); do wget -qO- -T 2 http://{svc}:80; done | sort | uniq -c')
    return sorted([int(l.split()[0]) for l in o.strip().splitlines()], reverse=True)
print(f'集群 {cn};sessionAffinity: ClientIP 让来自同一个客户端 IP 的连接固定到同一个后端,默认超时 10800 秒(3 小时)')
print(f'  Service 的字段:sticky.spec.sessionAffinity={kj("get", "svc", "sticky", "-n", NS)["spec"]["sessionAffinity"]};sessionAffinityConfig={kj("get", "svc", "sticky", "-n", NS)["spec"].get("sessionAffinityConfig")};plain.spec.sessionAffinity={kj("get", "svc", "plain", "-n", NS)["spec"]["sessionAffinity"]}')

print('== 一:有无会话保持——同一个客户端发 30 个新连接')
print(f'  plain(None):{many("cli1", "plain")}(各后端收到的数量,从多到少)')
print(f'  sticky(ClientIP):{many("cli1", "sticky")}(全部落在同一个后端)')
print(f'  另一个客户端 cli2 访问 sticky:{many("cli2", "sticky")};两个客户端分别固定到哪个后端:cli1→{get("cli1", "sticky")} cli2→{get("cli2", "sticky")}(各自独立,不一定相同)')

print('== 二:iptables 里是怎么实现的——recent 模块')
rc, o = nx(W, 'iptables-save -t nat 2>/dev/null', raw=True); txt = o
sc = re.search(rf'-A KUBE-SERVICES -d [\d.]+/32 -p tcp -m comment --comment "{NS}/sticky cluster IP" -m tcp --dport 80 -j (KUBE-SVC-\w+)', txt).group(1)
def short(l): return re.sub(r'-m comment --comment "[^"]*" ', '', l).replace('-A ', '')
rules = [short(l) for l in txt.splitlines() if l.startswith(f'-A {sc} ')]
print(f'  sticky 的 SVC 链 {sc}:'); [print('    ' + r[:250]) for r in rules]
sep = re.search(r'-j (KUBE-SEP-\w+)', [r for r in rules if 'recent' in r][0]).group(1)
seprules = [short(l) for l in txt.splitlines() if sep and l.startswith(f'-A {sep} ')]
print(f'  其中一个 SEP 链 {sep}:'); [print('    ' + r[:250]) for r in seprules]
rc, o = nx(W, 'ls /proc/net/xt_recent/ 2>&1 | head -4'); print(f'  内核 recent 表(每个后端一张,记录客户端 IP):{o.strip().split()}')
for f_ in nx(W, 'ls /proc/net/xt_recent/')[1].split():
    rc, o = nx(W, f'cat /proc/net/xt_recent/{f_}'); ln = [re.sub(r'\s+', ' ', x)[:110] for x in o.strip().splitlines()]
    if ln: print(f'  {f_} 里记录的客户端:{ln}')

print('== 三:超时——每次访问都会刷新计时器')
k('patch', 'svc', 'sticky', '-n', NS, '--type=merge', '-p', '{"spec":{"sessionAffinityConfig":{"clientIP":{"timeoutSeconds":3}}}}'); time.sleep(3)
print(f'  timeoutSeconds 改成 3:{kj("get", "svc", "sticky", "-n", NS)["spec"]["sessionAffinityConfig"]}')
rules = [short(l) for l in nx(W, 'iptables-save -t nat 2>/dev/null', raw=True)[1].splitlines() if l.startswith(f'-A {sc} ') and 'recent' in l]; print(f'  规则里的 --seconds:{re.findall(r"--seconds (\d+)", rules[0]) if rules else "(无)"}')
same_in = diff_out = 0; N = 12
for i in range(N):
    a = get('cli1', 'sticky'); time.sleep(1); b = get('cli1', 'sticky'); same_in += (a == b)
    time.sleep(4); c = get('cli1', 'sticky'); diff_out += (c != b)
print(f'  {N} 轮试验:间隔 1 秒(<3 秒)的两次访问落在同一个后端 {same_in}/{N};间隔 4 秒(>3 秒)的两次访问落在不同后端 {diff_out}/{N}(超时后重新抽签,3 个后端时换一个的概率约 2/3)')
seq = [get('cli1', 'sticky')]
for i in range(6): time.sleep(2); seq.append(get('cli1', 'sticky'))
print(f'  每 2 秒访问一次(每次都在 3 秒超时内)共 7 次:{len(set(seq))} 个不同后端(每次访问都刷新计时器,所以一直粘在同一个)')

print('== 四:后端消失之后')
t_pod = [p for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items'] if p['metadata']['name'].endswith(get('cli1', 'sticky'))]
cur = get('cli1', 'sticky'); victim = [p['metadata']['name'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items'] if p['metadata']['name'].endswith(cur)][0]
k('patch', 'svc', 'sticky', '-n', NS, '--type=merge', '-p', '{"spec":{"sessionAffinityConfig":{"clientIP":{"timeoutSeconds":10800}}}}')
k('delete', 'pod', victim, '-n', NS, '--wait=true', timeout=60); k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); time.sleep(4)
nxt = [get('cli1', 'sticky') for _ in range(5)]
print(f'  固定的后端 {cur}(超时 10800 秒)被删除后立即重新访问 5 次:{nxt}(客户端被重新分配到存活的后端;之后又固定下来:{len(set(nxt)) == 1})')
k('delete', 'ns', NS, '--wait=false')
