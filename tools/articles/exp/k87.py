import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k87')
cn, _ = up('main'); wait_nodes_ready()
NS = ns('k87')
def short(o, n=2, w=330): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def dep(name, replicas): return f'apiVersion: apps/v1\nkind: Deployment\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  replicas: {replicas}\n  selector: {{matchLabels: {{app: {name}}}}}\n  template:\n    metadata: {{labels: {{app: {name}}}}}\n    spec:\n      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
def clean():
    k('delete', 'validatingadmissionpolicybinding', 'k87-bind', 'k87-bind-param', '--ignore-not-found'); k('delete', 'validatingadmissionpolicy', 'k87-max-replicas', 'k87-param-limit', 'k87-bad', '--ignore-not-found')
clean()
POLICY = '''apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata: {name: k87-max-replicas}
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
    - {apiGroups: [apps], apiVersions: [v1], operations: [CREATE, UPDATE], resources: [deployments]}
  validations:
  - expression: "object.spec.replicas <= 3"
    messageExpression: "'副本数 ' + string(object.spec.replicas) + ' 超过上限 3'"
    reason: Invalid
'''
BIND = lambda actions, sel='': f'apiVersion: admissionregistration.k8s.io/v1\nkind: ValidatingAdmissionPolicyBinding\nmetadata: {{name: k87-bind}}\nspec:\n  policyName: k87-max-replicas\n  validationActions: {actions}\n  matchResources:\n    namespaceSelector: {{matchLabels: {{kubernetes.io/metadata.name: {NS}}}}}\n'
print(f'集群 {cn};ValidatingAdmissionPolicy(VAP)用 CEL 表达式直接在 API Server 里校验对象,不需要部署 webhook 服务。一个策略(policy)+ 一个绑定(binding)才生效')

print('== 一:策略 + 绑定')
k('apply', '-f', '-', input=POLICY); time.sleep(2)
rc, o = k('apply', '-f', '-', input=dep('d1', 10)); print(f'  只有策略、没有绑定,创建 replicas=10 的 Deployment:退出码 {rc};{short(o, 1)}(策略没有生效)')
k('delete', 'deploy', 'd1', '-n', NS)
k('apply', '-f', '-', input=BIND('[Deny]')); t0 = time.time()
def blocked(): return k('apply', '-f', '-', input=dep('probe', 10), args=None) if False else (k('apply', '-f', '-', '--dry-run=server', input=dep('probe', 10))[0] != 0)
v, dt = until(blocked, 30, 0.2); print(f'  创建绑定(validationActions: [Deny],只作用在命名空间 {NS})后 {dt:.1f} 秒开始生效')
rc, o = k('apply', '-f', '-', input=dep('d2', 10)); print(f'  replicas=10:退出码 {rc};{short(o, 1, 400)}')
rc, o = k('apply', '-f', '-', input=dep('d3', 3)); print(f'  replicas=3:退出码 {rc};{short(o, 1)}')
rc, o = k('patch', 'deploy', 'd3', '-n', NS, '--type=merge', '-p', '{"spec":{"replicas":8}}'); print(f'  patch 把 d3 改成 replicas=8(UPDATE 也被拦):退出码 {rc};{short(o, 1, 400)}')
rc, o = k('scale', 'deploy/d3', '-n', NS, '--replicas=8'); print(f'  kubectl scale deploy/d3 --replicas=8:退出码 {rc};{short(o, 1)}(scale 走的是 deployments/scale 子资源,策略里只写了 deployments,没有匹配上)')
k('scale', 'deploy/d3', '-n', NS, '--replicas=3')
rc, o = k('apply', '-f', '-', input=dep('d4', 10).replace(NS, 'default')); print(f'  同样的 Deployment 放到 default 命名空间(绑定的 namespaceSelector 没选中它):退出码 {rc};{short(o, 1)}')
k('delete', 'deploy', 'd4', '-n', 'default', '--ignore-not-found')

print('== 二:参数化——把阈值放进 ConfigMap')
k('delete', 'validatingadmissionpolicybinding', 'k87-bind'); k('delete', 'validatingadmissionpolicy', 'k87-max-replicas'); k('delete', 'ns', NS, '--wait=true', timeout=120); time.sleep(2)
NS = ns('k87p')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: limits, namespace: {NS}}}\ndata: {{maxReplicas: "5"}}\n')
k('apply', '-f', '-', input="""apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata: {name: k87-param-limit}
spec:
  failurePolicy: Fail
  paramKind: {apiVersion: v1, kind: ConfigMap}
  matchConstraints:
    resourceRules:
    - {apiGroups: [apps], apiVersions: [v1], operations: [CREATE, UPDATE], resources: [deployments]}
  validations:
  - expression: "object.spec.replicas <= int(params.data.maxReplicas)"
    messageExpression: "'副本数 ' + string(object.spec.replicas) + ' 超过参数 maxReplicas=' + params.data.maxReplicas"
""")
k('apply', '-f', '-', input=f'apiVersion: admissionregistration.k8s.io/v1\nkind: ValidatingAdmissionPolicyBinding\nmetadata: {{name: k87-bind-param}}\nspec:\n  policyName: k87-param-limit\n  validationActions: [Deny]\n  paramRef: {{name: limits, namespace: {NS}, parameterNotFoundAction: Deny}}\n  matchResources:\n    namespaceSelector: {{matchLabels: {{kubernetes.io/metadata.name: {NS}}}}}\n')
v, dt0 = until(lambda: k('apply', '-f', '-', '--dry-run=server', input=dep('probe2', 6))[0] != 0, 30, 0.2); print(f'  创建参数化策略和绑定之后 {dt0:.1f} 秒开始生效(阈值来自 ConfigMap limits)')
rc, o = k('apply', '-f', '-', input=dep('p1', 4)); print(f'  参数 maxReplicas=5,创建 replicas=4:退出码 {rc};{short(o, 1)}')
rc, o = k('apply', '-f', '-', input=dep('p2', 6)); print(f'  replicas=6:退出码 {rc};{short(o, 1, 400)}')
k('patch', 'cm', 'limits', '-n', NS, '--type=merge', '-p', '{"data":{"maxReplicas":"8"}}'); t0 = time.time()
v, dt = until(lambda: k('apply', '-f', '-', '--dry-run=server', input=dep('p3', 6))[0] == 0, 30, 0.2); print(f'  把参数改成 8:{dt:.1f} 秒后 replicas=6 通过了(改的是 ConfigMap,策略本身没动)')

print('== 三:validationActions 与类型检查')
k('delete', 'validatingadmissionpolicybinding', 'k87-bind-param'); NS = ns('k87w'); k('apply', '-f', '-', input=POLICY); k('apply', '-f', '-', input=BIND('[Warn]')); time.sleep(3)
rc, o = k('apply', '-f', '-', input=dep('w1', 10)); print(f'  validationActions: [Warn]:退出码 {rc};{short(o, 2, 360)}(创建成功,只返回 Warning)')
rc, o = k('apply', '-f', '-', input=BIND('[Warn, Deny]')); print(f'  把 validationActions 改成 [Warn, Deny]:退出码 {rc};{short(o, 1, 360)}')
k('apply', '-f', '-', input=BIND('[Deny]')); time.sleep(3)
rc, o = k('apply', '-f', '-', input=dep('w2', 10)); print(f'  改回 [Deny]:退出码 {rc};{short(o, 1, 360)}')
k('apply', '-f', '-', input='''apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata: {name: k87-bad}
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
    - {apiGroups: [apps], apiVersions: [v1], operations: [CREATE], resources: [deployments]}
  validations:
  - expression: "object.spec.replica <= 3"
''')
v, dt = until(lambda: (kj('get', 'validatingadmissionpolicy', 'k87-bad').get('status') or {}).get('typeChecking'), 30, 0.5)
tc = (kj('get', 'validatingadmissionpolicy', 'k87-bad').get('status') or {}).get('typeChecking') or {}
print(f'  表达式里写错字段名(object.spec.replica):{dt:.1f} 秒后策略的 status.typeChecking.expressionWarnings={[ (w["fieldRef"], re.sub(chr(10), " ", w["warning"])[:200]) for w in tc.get("expressionWarnings", [])]}')
k('delete', 'validatingadmissionpolicybinding', 'k87-bind'); k('delete', 'ns', NS, '--wait=false'); clean()
