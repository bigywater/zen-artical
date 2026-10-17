import sys, os, re, time, json, datetime, random, string; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k99')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k99')
def short(o, n=2, w=330): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def cm(name, ann=None, labels=None, data=None):
    d = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name, 'namespace': NS}}
    if ann: d['metadata']['annotations'] = ann
    if labels: d['metadata']['labels'] = labels
    if data: d['data'] = data
    return json.dumps(d)
print(f'集群 {cn};标签用来“选”(选择器、索引),注解用来“带信息”(给工具、人、控制器读)。两者都是 metadata 里的字符串键值对,区别在限制和用途')

print('== 一:大小限制——注解总量上限 256 KiB')
key = 'k'
for size in (262144 - len(key), 262144 - len(key) + 1):
    rc, o = k('create', '-f', '-', input=cm(f'ann-{size}', ann={key: 'x' * size})); print(f'  一个注解,键 1 字节 + 值 {size} 字节(合计 {len(key) + size}):退出码 {rc};{short(o, 1)}')
rc, o = k('create', '-f', '-', input=cm('ann-two', ann={'a': 'x' * 150000, 'b': 'y' * 150000})); print(f'  两个注解各 150000 字节(总计 300000,每个都没超):退出码 {rc};{short(o, 1)}(上限是所有注解加起来)')
rc, o = k('create', '-f', '-', input=cm('lab-big', labels={'big': 'z' * 100})); print(f'  对比标签:值 100 字节:退出码 {rc};{short(o, 1, 200)}(标签值上限 63)')

print('== 二:注解不能被选择器选中')
k('apply', '-f', '-', input=cm('has-ann', ann={'owner': 'team-a'}, labels={'owner': 'team-a'}) + '\n'); k('apply', '-f', '-', input=cm('only-ann', ann={'owner': 'team-b'}))
rc, o = k('get', 'cm', '-n', NS, '-l', 'owner=team-a', '-o', 'name'); print(f'  -l owner=team-a(标签):{[x for x in o.split() if "has-ann" in x or "only-ann" in x]}')
rc, o = k('get', 'cm', '-n', NS, '-l', 'owner=team-b', '-o', 'name'); print(f'  -l owner=team-b(only-ann 只有注解 owner=team-b):{[x for x in o.split() if "has-ann" in x or "only-ann" in x] or "选不到"}')
items = kj('get', 'cm', '-n', NS)['items']; print(f'  只能把全部对象读出来,在客户端按注解过滤:{[i["metadata"]["name"] for i in items if (i["metadata"].get("annotations") or {}).get("owner") == "team-b"]}')
rc, o = k('get', 'cm', '-n', NS, '--field-selector', 'metadata.annotations.owner=team-b'); print(f'  --field-selector metadata.annotations.owner=team-b:退出码 {rc};{short(o, 1, 250)}')

print('== 三:改注解会不会触发滚动更新')
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
      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s')
def rs(): return sorted([r['metadata']['name'][-5:] for r in kj('get', 'rs', '-n', NS)['items']])
a0 = rs(); k('annotate', 'deploy', 'web', '-n', NS, 'note=hello'); time.sleep(4); a1 = rs()
print(f'  给 Deployment 本身加注解 note=hello:ReplicaSet 数 {len(a0)} → {len(a1)}(没有新 ReplicaSet,不触发滚动)')
k('patch', 'deploy', 'web', '-n', NS, '--type=merge', '-p', '{"spec":{"template":{"metadata":{"annotations":{"restarted-at":"v1"}}}}}'); time.sleep(6); a2 = rs()
print(f'  改 spec.template.metadata.annotations(Pod 模板里的注解):ReplicaSet 数 {len(a1)} → {len(a2)}(模板变了,新建 ReplicaSet,触发滚动更新;kubectl rollout restart 就是这么做的)')
rc, o = k('get', 'deploy', 'web', '-n', NS, '-o', 'jsonpath={.spec.template.metadata.annotations}'); print(f'  rollout restart 写入的注解:', end='')
k('rollout', 'restart', 'deploy/web', '-n', NS); time.sleep(3); rc, o = k('get', 'deploy', 'web', '-n', NS, '-o', 'jsonpath={.spec.template.metadata.annotations}'); print(o.strip())
rc, o = k('rollout', 'history', 'deploy/web', '-n', NS); print(f'  rollout history 的行数:{len(o.strip().splitlines()) - 2}(每个 ReplicaSet 一个 revision)')

print('== 四:kubectl apply 会把整份配置抄进注解——大对象会撞上 256 KiB')
for n_ in (100_000, 300_000):
    data = {'blob': ''.join(random.choices(string.ascii_letters, k=n_))}
    y = json.dumps({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': f'big-{n_ // 1000}k', 'namespace': NS}, 'data': data})
    rc1, o1 = k('create', '-f', '-', input=y); rc2, o2 = k('apply', '-f', '-', input=y.replace(f'big-{n_ // 1000}k', f'big-apply-{n_ // 1000}k'))
    rc3, o3 = k('apply', '-f', '-', '--server-side', input=y.replace(f'big-{n_ // 1000}k', f'big-ssa-{n_ // 1000}k'))
    print(f'  ConfigMap data 约 {n_ // 1000} KB:create → 退出码 {rc1};client-side apply → 退出码 {rc2}' + (f'({short(o2, 1, 250)[0][:200]})' if rc2 else '') + f';server-side apply → 退出码 {rc3}')
rc, o = k('get', 'cm', 'big-apply-100k', '-n', NS, '-o', 'jsonpath={.metadata.annotations}'); print(f'  apply 创建的 100 KB 的 ConfigMap 上,kubectl.kubernetes.io/last-applied-configuration 注解大小 {len(o)} 字节(≈ 整份对象)')
k('delete', 'ns', NS, '--wait=false')
