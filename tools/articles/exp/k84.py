import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k84')
cn, _ = up('main'); wait_nodes_ready()
NS = ns('k84')
def rules_of(name): return kj('get', 'clusterrole', name)['rules'] or []
def has(name, group, res): return any(group in (r.get('apiGroups') or []) and res in (r.get('resources') or []) for r in rules_of(name))
def can(verb, res, user='alice', ns_=None): rc, o = k('auth', 'can-i', verb, res, f'--as={user}', *(['-n', ns_] if ns_ else [])); return o.strip()
print(f'集群 {cn};聚合 ClusterRole(aggregationRule)让一个 ClusterRole 的 rules 由带特定标签的其他 ClusterRole 自动汇总,CRD 作者可以把自己资源的权限“并入”内置的 view / edit / admin')

print('== 一:内置的 view / edit / admin 是聚合出来的')
for n in ('view', 'edit', 'admin'):
    cr_ = kj('get', 'clusterrole', n); sel = cr_['aggregationRule']['clusterRoleSelectors']
    print(f'  ClusterRole {n}:aggregationRule 选择 {[s["matchLabels"] for s in sel]};当前汇总出 {len(cr_["rules"])} 条 rule')
srcs = kj('get', 'clusterroles', '-l', 'rbac.authorization.k8s.io/aggregate-to-view=true')['items']; print(f'  带标签 rbac.authorization.k8s.io/aggregate-to-view=true 的 ClusterRole 有 {len(srcs)} 个:{sorted(s["metadata"]["name"] for s in srcs)}')
print(f'  view 里的一条汇总进来的 rule 例子:{ {k_: v for k_, v in next(r for r in rules_of("view") if "configmaps" in (r.get("resources") or [])).items()} }')
print(f'  edit 的标签链:admin 还聚合 edit 吗?admin 的 selector:{[s["matchLabels"] for s in kj("get", "clusterrole", "admin")["aggregationRule"]["clusterRoleSelectors"]]}')

print('== 二:CRD 作者把自己资源并入 view')
k('apply', '-f', '-', input='''apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: widgets.k84.example.com}
spec:
  group: k84.example.com
  scope: Namespaced
  names: {plural: widgets, singular: widget, kind: Widget}
  versions:
  - name: v1
    served: true
    storage: true
    schema: {openAPIV3Schema: {type: object, x-kubernetes-preserve-unknown-fields: true}}
''')
until(lambda: k('get', 'widgets.k84.example.com', '-n', NS)[0] == 0, 30, 0.5)
k('create', 'clusterrolebinding', 'k84-alice-view', '--clusterrole=view', '--user=alice')
time.sleep(2)
print(f'  创建 CRD widgets.k84.example.com 并把 alice 绑定到 view:alice list widgets → {can("list", "widgets.k84.example.com", ns_=NS)};list pods → {can("list", "pods", ns_=NS)}')
print(f'  view 的 rules 里已有 widgets:{has("view", "k84.example.com", "widgets")}')
k('apply', '-f', '-', input='''apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k84-widgets-view
  labels: {rbac.authorization.k8s.io/aggregate-to-view: "true"}
rules:
- {apiGroups: [k84.example.com], resources: [widgets], verbs: [get, list, watch]}
''')
t0 = time.time(); v, dt = until(lambda: has('view', 'k84.example.com', 'widgets'), 60, 0.05)
print(f'  创建带 aggregate-to-view 标签的 ClusterRole k84-widgets-view 之后 {dt:.1f} 秒,view 的 rules 里出现 widgets;alice list widgets → {can("list", "widgets.k84.example.com", ns_=NS)};alice delete widgets → {can("delete", "widgets.k84.example.com", ns_=NS)}(view 只有读权限)')
vl = kj('get', 'clusterrole', 'view')['metadata']['labels']
print(f'  edit 里有 widgets 吗:{has("edit", "k84.example.com", "widgets")};admin 里呢:{has("admin", "k84.example.com", "widgets")}——因为 view 这个 ClusterRole 自己带着标签 {[k_ for k_ in vl if "aggregate-to" in k_]},它的(聚合后的)rules 又会被 edit、admin 聚合进去:view → edit → admin 形成一条链')
n_before = len(rules_of('view'))
k('delete', 'clusterrole', 'k84-widgets-view'); t0 = time.time(); v, dt = until(lambda: not has('view', 'k84.example.com', 'widgets'), 60, 0.1)
print(f'  删除这个 ClusterRole 后 {dt:.1f} 秒,widgets 从 view 里消失;alice list widgets → {can("list", "widgets.k84.example.com", ns_=NS)}')

print('== 三:手动改聚合角色的 rules 会被覆盖')
n0 = len(rules_of('view'))
rc, o = k('patch', 'clusterrole', 'view', '--type=json', '-p', '[{"op":"add","path":"/rules/-","value":{"apiGroups":[""],"resources":["secrets"],"verbs":["get"]}}]', '-o', 'json'); n_ret = len(json.loads(o[o.index('{'):])['rules']) if rc == 0 else None
print(f'  给 view 手动追加一条 secrets get:退出码 {rc};patch 返回的对象有 {n_ret} 条 rule(原来 {n0} 条)')
t0 = time.time(); seen = []
while time.time() - t0 < 5:
    seen.append(len(rules_of('view'))); time.sleep(0.05)
    if seen[-1] == n0: break
print(f'    之后连续读 view 的 rule 数:{seen[:8]}…最终 {seen[-1]};控制器把额外那条还原了;alice get secrets → {can("get", "secrets", ns_=NS)}')

print('== 四:自己定义一个聚合角色')
k('apply', '-f', '-', input='''apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: k84-monitoring}
aggregationRule:
  clusterRoleSelectors:
  - matchLabels: {k84/aggregate-to-monitoring: "true"}
rules: []
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: k84-src-nodes, labels: {k84/aggregate-to-monitoring: "true"}}
rules:
- {apiGroups: [""], resources: [nodes, nodes/metrics], verbs: [get, list]}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: k84-src-pods, labels: {k84/aggregate-to-monitoring: "true"}}
rules:
- {apiGroups: [""], resources: [pods], verbs: [get, list, watch]}
- {apiGroups: [""], resources: [nodes], verbs: [get, list]}
''')
v, dt = until(lambda: len(rules_of('k84-monitoring')) >= 2, 30, 0.1)
print(f'  k84-monitoring 本身 rules 写的是空,{dt:.1f} 秒后汇总出 {len(rules_of("k84-monitoring"))} 条:{[(r["resources"], r["verbs"]) for r in rules_of("k84-monitoring")]}')
print(f'  两个来源里都有 nodes get/list:汇总时{"没有去重(重复保留)" if sum(1 for r in rules_of("k84-monitoring") if r["resources"][:1] == ["nodes"]) > 1 else "合并成一条"}')
k('delete', 'clusterrole', 'k84-src-pods'); time.sleep(2); print(f'  删掉 k84-src-pods 后:{[(r["resources"], r["verbs"]) for r in rules_of("k84-monitoring")]}')
k('delete', 'clusterrole', 'k84-monitoring', 'k84-src-nodes'); k('delete', 'clusterrolebinding', 'k84-alice-view'); k('delete', 'crd', 'widgets.k84.example.com', '--wait=false'); k('delete', 'ns', NS, '--wait=false')
