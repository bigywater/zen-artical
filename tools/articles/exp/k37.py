import sys, os, re, time, json, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k37')
cn, _ = up('main')
NS = ns('k37')
W1, W2 = 'kx-main-worker', 'kx-main-worker2'
for n in (W1, W2): k('label', 'node', n, 'k37=yes', '--overwrite')
def dep(name, replicas, extra='', delay=0):
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
      nodeSelector: {{k37: "yes"}}
      containers:
      - name: c
        image: busybox:1.36
        command: [sh, -c, "touch /tmp/ok; sleep 3600"]
        readinessProbe: {{exec: {{command: [cat, /tmp/ok]}}, initialDelaySeconds: {delay}, periodSeconds: 1}}
{extra}'''
def pdb(name, app, spec, policy=''):
    return f'apiVersion: policy/v1\nkind: PodDisruptionBudget\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  selector: {{matchLabels: {{app: {app}}}}}\n  {spec}\n{policy}'
def pst(name):
    s = kj('get', 'pdb', name, '-n', NS)['status']; return f'currentHealthy={s.get("currentHealthy")} desiredHealthy={s.get("desiredHealthy")} disruptionsAllowed={s.get("disruptionsAllowed")} expectedPods={s.get("expectedPods")}'
def ready_pods(app): return [p for p in kj('get', 'pods', '-n', NS, '-l', f'app={app}')['items'] if any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])) and not p['metadata'].get('deletionTimestamp')]
def evict(pod):
    body = json.dumps({'apiVersion': 'policy/v1', 'kind': 'Eviction', 'metadata': {'name': pod, 'namespace': NS}})
    rc, o = k('create', '--raw', f'/api/v1/namespaces/{NS}/pods/{pod}/eviction', '-f', '-', input=body, raw=True)
    return rc, o.strip()
print(f'集群 {cn};PodDisruptionBudget 约束的是“自愿中断”(通过 Eviction API 驱逐,kubectl drain 用的就是它);直接 kubectl delete pod 不经过它')

print('== 一:同样 5 个 Pod,不同写法的 PDB 算出的允许中断数')
k('apply', '-f', '-', input=dep('w5', 5)); until(lambda: len(ready_pods('w5')) == 5, 90)
for n_, sp in (('minAvailable: 2', 'minAvailable: 2'), ('minAvailable: "50%"', 'minAvailable: "50%"'), ('maxUnavailable: 1', 'maxUnavailable: 1'), ('maxUnavailable: "50%"', 'maxUnavailable: "50%"'), ('minAvailable: "100%"', 'minAvailable: "100%"')):
    k('apply', '-f', '-', input=pdb('p', 'w5', sp)); time.sleep(2); print(f'  {n_:<22} → {pst("p")}')
    k('delete', 'pdb', 'p', '-n', NS)
k('delete', 'deploy', 'w5', '-n', NS, '--wait=true', timeout=60)

print('== 二:Eviction API——预算用完就返回 429,等替代的 Pod 就绪才能继续')
k('apply', '-f', '-', input=dep('web', 3, delay=5)); until(lambda: len(ready_pods('web')) == 3, 90)
k('apply', '-f', '-', input=pdb('web-pdb', 'web', 'minAvailable: 2')); time.sleep(2)
print(f'  3 个 Pod、minAvailable: 2:{pst("web-pdb")}')
names = sorted(p['metadata']['name'] for p in ready_pods('web'))
t0 = time.time(); rc, o = evict(names[0]); print(f'  驱逐第 1 个 Pod:退出码 {rc};{o[:100]}')
rc, o = evict(names[1]); st = json.loads(o) if o.startswith('{') else {}
print(f'  紧接着驱逐第 2 个 Pod:退出码 {rc};' + (f'code={st.get("code")} reason={st.get("reason")} message={st.get("message")}' if st else o[:200]))
print(f'    此时 PDB:{pst("web-pdb")}')
v, dt = until(lambda: len(ready_pods('web')) == 3, 60, 0.3); dt = time.time() - t0; time.sleep(1)
print(f'  从第 1 次驱逐算起,Deployment 补出新 Pod 并就绪用了 {dt:.1f} 秒(就绪探针 initialDelaySeconds=5);PDB:{pst("web-pdb")}')
alive = sorted(p['metadata']['name'] for p in ready_pods('web')); rc, o = evict(alive[0]); print(f'  现在再驱逐一个:退出码 {rc};{o[:90]}')

print('== 三:kubectl drain 遵守 PDB,kubectl delete pod 不遵守')
until(lambda: len(ready_pods('web')) == 3, 60)
loc = {}
for p in ready_pods('web'): loc.setdefault(p['spec']['nodeName'], []).append(p['metadata']['name'])
node = max(loc, key=lambda n: len(loc[n])); print(f'  3 个 web Pod 的分布:' + ', '.join(f'{n.replace("kx-main-", "")}:{len(v)}' for n, v in sorted(loc.items())) + f';要清空的节点:{node.replace("kx-main-", "")}({len(loc[node])} 个 Pod)')
t0 = time.time()
r = subprocess.run(['kubectl', '--kubeconfig', kcfg(), 'drain', node, '--ignore-daemonsets', '--delete-emptydir-data', '--force', '--timeout=90s'], capture_output=True, text=True)
out_ = [l for l in (r.stdout + r.stderr).splitlines() if 'evict' in l.lower() or 'drain' in l.lower() or 'cordon' in l.lower()]
print(f'  kubectl drain {node.replace("kx-main-", "")}(退出码 {r.returncode},用了 {time.time() - t0:.0f} 秒)输出里和驱逐有关的行:')
for l in out_[:12]: print('    ' + l[:200])
k('uncordon', node)
until(lambda: len(ready_pods('web')) == 3, 60); time.sleep(1)
pods_ = sorted(p['metadata']['name'] for p in ready_pods('web')); t0 = time.time()
k('delete', 'pod', *pods_[:2], '-n', NS, '--wait=false'); time.sleep(0.5)
print(f'  对比:kubectl delete pod 一次删掉 2 个(不经过 Eviction API,PDB 拦不住):0.5 秒后 ready 的 Pod 有 {len(ready_pods("web"))} 个;PDB:{pst("web-pdb")}')
until(lambda: len(ready_pods('web')) == 3, 60)
k('delete', 'deploy', 'web', '-n', NS, '--wait=true', timeout=60); k('delete', 'pdb', 'web-pdb', '-n', NS)

print('== 四:Pod 本身不健康时——unhealthyPodEvictionPolicy')
for pol in ('IfHealthyBudget', 'AlwaysAllow'):
    k('apply', '-f', '-', input=dep('un', 3)); until(lambda: len(ready_pods('un')) == 3, 90)
    k('apply', '-f', '-', input=pdb('un-pdb', 'un', 'minAvailable: 3', policy=f'  unhealthyPodEvictionPolicy: {pol}')); 
    bad = sorted(p['metadata']['name'] for p in ready_pods('un'))[0]
    k('exec', bad, '-n', NS, '--', 'rm', '/tmp/ok'); until(lambda: len(ready_pods('un')) == 2, 30, 0.3); time.sleep(2)
    print(f'  unhealthyPodEvictionPolicy={pol}:3 个 Pod 里 1 个就绪探针失败、minAvailable: 3:{pst("un-pdb")}')
    rc, o = evict(bad); st = json.loads(o) if o.startswith('{') else {}
    print(f'    驱逐那个不健康的 Pod:退出码 {rc};' + (f'code={st.get("code")} message={st.get("message")}' if st and st.get('code') else o[:120]))
    k('delete', 'deploy', 'un', '-n', NS, '--wait=true', timeout=60); k('delete', 'pdb', 'un-pdb', '-n', NS)
for n in (W1, W2): k('label', 'node', n, 'k37-')
rmns(NS)
