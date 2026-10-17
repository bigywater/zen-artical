import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k86')
cn, _ = up('main'); wait_nodes_ready()
NS = ns('k86')
def short(o, n=1, w=300): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
k('apply', '-f', '-', input=f'''apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {{name: pod-reader, namespace: {NS}}}
rules:
- {{apiGroups: [""], resources: [pods], verbs: [get, list]}}
- {{apiGroups: [""], resources: [pods/log], verbs: [get]}}
- {{apiGroups: [""], resources: [configmaps], resourceNames: [app-cfg], verbs: [get, update]}}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {{name: alice-reader, namespace: {NS}}}
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: Role, name: pod-reader}}
subjects: [{{kind: User, name: alice}}]
''')
time.sleep(1)
print(f'集群 {cn};kubectl auth can-i 只是对三个鉴权 API 的包装:SelfSubjectAccessReview(能不能)、SubjectAccessReview(别人能不能)、SelfSubjectRulesReview(--list)。alice 在命名空间 {NS} 有 Role pod-reader(pods get/list、pods/log get、configmap app-cfg get/update)')

print('== 一:can-i 与 yes/no、退出码')
for cmd in (['list', 'pods'], ['delete', 'pods'], ['get', 'pods/log'], ['get', 'configmaps/app-cfg'], ['get', 'configmaps/other'], ['update', 'configmaps/app-cfg']):
    rc, o = k('auth', 'can-i', *cmd, '-n', NS, '--as=alice'); print(f'  can-i {" ".join(cmd):<28}--as=alice -n {NS} → {short(o)[0] if short(o) else ""}(退出码 {rc})')
rc, o = k('auth', 'can-i', 'list', 'pods', '--as=alice', '-n', 'default'); print(f'  换成命名空间 default:{short(o)}(退出码 {rc})')
rc, o = k('auth', 'can-i', 'list', 'pods', '--as=alice', '--all-namespaces'); print(f'  --all-namespaces:{short(o)}(RoleBinding 只在 {NS} 里生效)')
rc, o = k('auth', 'can-i', 'list', 'nodes', '--as=alice'); print(f'  集群级资源 nodes:{short(o)}')
rc, o = k('auth', 'can-i', 'get', '/healthz', '--as=alice'); print(f'  非资源 URL /healthz(system:public-info-viewer 默认允许认证用户):{short(o)}')
rc, o = k('auth', 'can-i', 'get', '/metrics', '--as=alice'); print(f'  非资源 URL /metrics:{short(o)}')

print('== 二:背后的 API 调用')
rc, o = k('auth', 'can-i', 'list', 'pods', '-n', NS, '--as=alice', '-v=8', raw=True)
req = [l.strip() for l in o.splitlines() if ('"Request" verb="POST"' in l and 'selfsubjectaccessreviews' in l) or 'Impersonate-User' in l or ('"Response" status=' in l and '201' in l)]
for l in req[:4]: print('  ' + re.sub(r'\s+', ' ', l)[:200])
sy = f'apiVersion: authorization.k8s.io/v1\nkind: SelfSubjectAccessReview\nspec:\n  resourceAttributes: {{namespace: {NS}, verb: list, resource: pods}}\n'
rc, o = k('create', '-f', '-', '-o', 'json', '--as=alice', '--validate=false', input=sy); st = json.loads(o)['status']; print(f'  自己提交 SelfSubjectAccessReview(--as=alice,list pods):allowed={st["allowed"]};reason={st.get("reason")!r}')
y = f'apiVersion: authorization.k8s.io/v1\nkind: SubjectAccessReview\nspec:\n  user: alice\n  resourceAttributes: {{namespace: {NS}, verb: list, resource: pods}}\n'
rc, o = k('create', '-f', '-', '-o', 'json', input=y); st = json.loads(o)['status']; print(f'  直接提交 SubjectAccessReview(user: alice, list pods):allowed={st["allowed"]};reason={st.get("reason")!r}')
y2 = y.replace('verb: list', 'verb: delete'); rc, o = k('create', '-f', '-', '-o', 'json', input=y2); st = json.loads(o)['status']; print(f'  delete pods:allowed={st["allowed"]};reason={st.get("reason")!r}')
y3 = y.replace('user: alice', 'user: alice\n  groups: [system:masters]'); rc, o = k('create', '-f', '-', '-o', 'json', input=y3.replace('verb: list', 'verb: delete')); st = json.loads(o)['status']; print(f'  给 SubjectAccessReview 加上 groups: [system:masters],delete pods:allowed={st["allowed"]};reason={st.get("reason")!r}')

print('== 三:--list 与它的局限')
rc, o = k('auth', 'can-i', '--list', '-n', NS, '--as=alice'); ls = o.strip().splitlines()
print(f'  can-i --list -n {NS} --as=alice:共 {len(ls) - 1} 行;和 pod-reader 相关的:')
for l in ls: 
    if any(x in l for x in ('pods', 'configmaps')): print('    ' + re.sub(r'\s+', ' ', l)[:110])
y4 = f'apiVersion: authorization.k8s.io/v1\nkind: SelfSubjectRulesReview\nspec: {{namespace: {NS}}}\n'
rc, o = k('create', '-f', '-', '-o', 'json', '--as=alice', '--validate=false', input=y4); st = json.loads(o)['status']; print(f'  直接提交 SelfSubjectRulesReview:incomplete={st["incomplete"]};resourceRules {len(st["resourceRules"])} 条,nonResourceRules {len(st["nonResourceRules"])} 条;evaluationError={st.get("evaluationError")}')

print('== 四:常见的“陷阱”')
rc, o = k('auth', 'can-i', 'list', 'podz', '--as=alice', '-n', NS, raw=True); print(f'  资源名写错(podz):{short(o, 2)}(只给警告,结果仍是 no)')
rc, o = k('auth', 'can-i', 'get', 'pods', '--subresource=log', '--as=alice', '-n', NS); print(f'  --subresource=log:{short(o)}')
rc, o = k('auth', 'can-i', 'create', 'pods', '--as=alice', '-n', NS, '-q'); print(f'  -q 只返回退出码:{rc}(输出:{o.strip() or "空"})')
rc, o = k('auth', 'can-i', 'get', 'pods', '--as=alice', '--as-group=system:masters', '-n', NS, '-q'); rc2, o2 = k('auth', 'can-i', 'delete', 'pods', '--as=alice', '--as-group=system:masters', '-n', NS); print(f'  --as=alice --as-group=system:masters delete pods:{short(o2)}(管理员可以模拟任意组;组也参与鉴权)')
k('delete', 'ns', NS, '--wait=false')
