import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k98')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k98')
def short(o, n=2, w=360): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def cm(name, labels):
    lb = ', '.join(f'{a}: "{b}"' for a, b in labels.items())
    return f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: {name}, namespace: {NS}, labels: {{{lb}}}}}\n---\n'
DATA = {'a': {'env': 'prod', 'tier': 'web'}, 'b': {'env': 'prod', 'tier': 'db'}, 'c': {'env': 'staging', 'tier': 'web'}, 'd': {'env': 'dev'}, 'e': {'tier': 'web'}, 'f': {}}
k('apply', '-f', '-', input=''.join(cm(n, l) for n, l in DATA.items()))
def sel(expr):
    rc, o = k('get', 'cm', '-n', NS, '-l', expr, '-o', 'name', '--no-headers'); return sorted(x.split('/')[1] for x in o.split() if x.startswith('configmap/') and x.split('/')[1] in DATA)
print(f'集群 {cn};标签(label)是对象上的键值对,选择器(selector)按标签挑出一组对象。六个 ConfigMap 的标签:' + ';'.join(f'{n}={ ",".join(f"{a}={b}" for a, b in l.items()) or "(无)"}' for n, l in DATA.items()))

print('== 一:kubectl 的标签选择器语法——哪些对象被选中')
for expr, d in (('env=prod', '等值'), ('env!=prod', '不等于:包括没有 env 标签的'), ('env=prod,tier=web', '逗号 = 与(AND)'), ('env in (prod,staging)', '集合:在其中'), ('env notin (prod)', 'notin:同样包括没有 env 标签的'), ('env', '存在这个键'), ('!env', '不存在这个键'), ('env=dev,!tier', '组合:env=dev 且没有 tier')):
    print(f'  -l {expr:<26}→ {sel(expr)}  ({d})')
print('  注意:没有“或”的写法能跨键:env=prod OR tier=web 只能分两次查;同一个键内的“或”用 in (a,b)')

print('== 二:控制器里的选择器——matchLabels / matchExpressions,以及它的限制')
def dep(name, sel_, tl_='app: frontend', extra=''):
    return f'apiVersion: apps/v1\nkind: Deployment\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  replicas: 0\n  selector: {sel_}\n  template:\n    metadata: {{labels: {{{tl_}}}}}\n    spec:\n      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
rc, o = k('apply', '-f', '-', input=dep('d-expr', '{matchExpressions: [{key: app, operator: In, values: [frontend, backend]}, {key: tier, operator: DoesNotExist}]}')); print(f'  matchExpressions(app In [frontend,backend] 且 tier 不存在),模板标签 app: frontend:退出码 {rc};{short(o, 1)}')
rc, o = k('apply', '-f', '-', input=dep('d-mismatch', '{matchLabels: {app: backend}}')); print(f'  选择器 app=backend 但模板标签是 app: frontend:退出码 {rc};{short(o, 2, 420)}')
rc, o = k('apply', '-f', '-', input=dep('d-empty', '{}')); print(f'  选择器写成 {{}}(空):退出码 {rc};{short(o, 2, 420)}')
rc, o = k('apply', '-f', '-', input=dep('d-fix', '{matchLabels: {app: frontend}}')); rc2, o2 = k('patch', 'deploy', 'd-fix', '-n', NS, '--type=merge', '-p', '{"spec":{"selector":{"matchLabels":{"app":"backend"}},"template":{"metadata":{"labels":{"app":"backend"}}}}}'); print(f'  创建后把 spec.selector 从 app=frontend 改成 app=backend:退出码 {rc2};{short(o2, 2, 420)}')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Service\nmetadata: {{name: svc-empty, namespace: {NS}}}\nspec: {{ports: [{{port: 80}}]}}\n'); print(f'  Service 不写 selector(空):不会去选 Pod,endpoints 由人手工管理;读出的 spec.selector={kj("get", "svc", "svc-empty", "-n", NS)["spec"].get("selector")}')
k('apply', '-f', '-', input=f'apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata: {{name: np-all, namespace: {NS}}}\nspec:\n  podSelector: {{}}\n  policyTypes: [Ingress]\n'); print(f'  NetworkPolicy 的 podSelector: {{}} 则是“选中命名空间里的全部 Pod”(同样是空选择器,含义相反)')

print('== 三:标签键、值的语法限制')
tests = [('值 63 个字符', {'k': 'a' * 63}), ('值 64 个字符', {'k': 'a' * 64}), ('值带空格', {'k': 'a b'}), ('值以 - 开头', {'k': '-ab'}), ('值为空串', {'k': ''}), ('键带前缀 example.com/name', {'example.com/name': 'v'}), ('键名部分 64 个字符', {'a' * 64: 'v'}), ('键前缀带大写 Example.com/name', {'Example.com/name': 'v'})]
for d, l in tests:
    rc, o = k('apply', '-f', '-', input=cm('lab-test', l)); print(f'  {d:<28}→ 退出码 {rc}' + ('' if rc == 0 else f';{short(o, 2, 300)[-1] if len(short(o, 2, 300)) > 1 else short(o, 1, 300)[0]}'))

print('== 四:标签变了,选择器的结果实时变')
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
      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
---
apiVersion: v1
kind: Service
metadata: {{name: web, namespace: {NS}}}
spec: {{selector: {{app: web}}, ports: [{{port: 80}}]}}
''')
k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); time.sleep(3)
def eps(): return len(sum([x['endpoints'] for x in kj('get', 'endpointslices', '-n', NS, '-l', 'kubernetes.io/service-name=web')['items']], []))
pods = [p['metadata']['name'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']]
print(f'  Deployment web 3 个副本,Service web 的 endpoint 数 {eps()}')
rc, o = k('label', 'pod', pods[0], '-n', NS, 'app=web', 'env=debug'); print(f'  给一个 Pod 加新标签 env=debug:{short(o, 1)[0]}')
rc, o = k('label', 'pod', pods[0], '-n', NS, 'env=other'); print(f'  再改同一个键 env=other(不加 --overwrite):退出码 {rc};{short(o, 1)}')
rc, o = k('label', 'pod', pods[0], '-n', NS, 'env=other', '--overwrite'); print(f'  加 --overwrite:{short(o, 1)[0]}')
t0 = time.time(); k('label', 'pod', pods[0], '-n', NS, 'app=web-quarantine', '--overwrite')
v, dt = until(lambda: eps() == 2, 30, 0.2); print(f'  把 app 标签改成 web-quarantine:{dt:.1f} 秒后 Service 的 endpoint 从 3 变成 {eps()}(Pod 被踢出 Service)')
time.sleep(3); alive = kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']; allp = kj('get', 'pods', '-n', NS)['items']
print(f'  Deployment 补了一个新 Pod:app=web 的 Pod 数 {len(alive)};命名空间里总共 {len(allp)} 个 Pod;被改标签的那个还在运行({pods[0] in [p["metadata"]["name"] for p in allp]}),但已脱离 ReplicaSet 和 Service——这是“隔离故障 Pod 留着排查”的常用手法')
k('delete', 'ns', NS, '--wait=false')
