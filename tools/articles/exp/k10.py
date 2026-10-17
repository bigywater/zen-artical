import sys, os, re, time, json, yaml, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k10')
cn, _ = up('main')
NS = ns('k10')
k('delete', 'crd', 'boxes.k10.example.com', '--ignore-not-found', '--wait=true', timeout=120)
def mkdep():
    k('delete', 'deploy', 'web', '-n', NS, '--ignore-not-found')
    y = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'web', 'namespace': NS, 'annotations': {'keep': 'yes', 'drop': 'me'}}, 'spec': {'replicas': 0, 'selector': {'matchLabels': {'app': 'web'}}, 'template': {'metadata': {'labels': {'app': 'web'}}, 'spec': {'tolerations': [{'key': 't1', 'operator': 'Exists'}, {'key': 't2', 'operator': 'Exists'}], 'containers': [{'name': 'a', 'image': 'busybox:1.36', 'command': ['sleep', '3600'], 'env': [{'name': 'X', 'value': '1'}]}, {'name': 'b', 'image': 'busybox:1.36', 'command': ['sleep', '3600']}]}}}}
    k('create', '-f', '-', input=yaml.dump(y))
def cs(): return json.loads(ko('get', 'deploy', 'web', '-n', NS, '-o', 'json'))['spec']['template']['spec']
def brief():
    s = cs(); cts = {c['name']: {'image': c['image'], 'command': c.get('command'), 'env': [e['name'] for e in c.get('env', [])]} for c in s['containers']}
    return f'containers={json.dumps(cts, ensure_ascii=False)} tolerations={[t["key"] for t in s.get("tolerations", [])]}'
def patch(typ, body):
    rc, o = k('patch', 'deploy', 'web', '-n', NS, f'--type={typ}', '-p', body); return rc, o.strip().replace('\n', ' ')
print(f'集群 {cn};Deployment web(replicas=0,容器 a 带 command 和 env X,容器 b,两条 tolerations)用来对比三种 patch')

print('== 一:同一个想法“把容器 a 的镜像改成 busybox:1.35”,三种 patch 的结果')
body = {'spec': {'template': {'spec': {'containers': [{'name': 'a', 'image': 'busybox:1.35'}]}}}}
mkdep(); print(f'  初始:{brief()}')
rc, o = patch('merge', json.dumps(body)); print(f'  --type=merge(JSON merge patch,RFC 7386):退出码 {rc};{o[:200]}'); print(f'    {brief()}')
mkdep(); rc, o = patch('strategic', json.dumps(body)); print(f'  --type=strategic(默认,按 name 合并列表):退出码 {rc};{o}'); print(f'    {brief()}')
mkdep(); rc, o = patch('json', json.dumps([{'op': 'replace', 'path': '/spec/template/spec/containers/0/image', 'value': 'busybox:1.35'}])); print(f'  --type=json(JSON patch,RFC 6902,按下标):退出码 {rc};{o}'); print(f'    {brief()}')
body2 = {'spec': {'template': {'spec': {'containers': [{'name': 'a', 'image': 'busybox:1.35', 'command': ['sleep', '3600']}]}}}}
mkdep(); rc, o = patch('merge', json.dumps(body2)); print(f'  merge patch 把 a 的 image 和 command 写全再试:退出码 {rc};{o}'); print(f'    {brief()}(容器 b 仍然被整个列表替换掉了)')

print('== 二:删除——null、$patch: delete、JSON patch 的 remove,以及按下标的风险')
mkdep()
rc, o = patch('merge', json.dumps({'metadata': {'annotations': {'drop': None}}})); print(f'  merge patch 把 annotation drop 设为 null:{o};annotations={ko("get", "deploy", "web", "-n", NS, "-o", "jsonpath={.metadata.annotations}")}')
rc, o = patch('strategic', json.dumps({'spec': {'template': {'spec': {'containers': [{'name': 'b', '$patch': 'delete'}]}}}})); print(f'  strategic 用 $patch: delete 删掉容器 b:{o};{brief()}')
mkdep()
rc, o = patch('strategic', json.dumps({'spec': {'template': {'spec': {'containers': [{'name': 'a', 'env': [{'name': 'X', '$patch': 'delete'}]}]}}}})); print(f'  strategic 删掉容器 a 的 env X:{o};{brief()}')
mkdep(); rc, o = patch('json', json.dumps([{'op': 'remove', 'path': '/spec/template/spec/containers/0'}])); print(f'  JSON patch remove containers/0(按下标):{o};{brief()}')
mkdep(); rc, o = patch('json', json.dumps([{'op': 'test', 'path': '/spec/template/spec/containers/0/name', 'value': 'b'}, {'op': 'remove', 'path': '/spec/template/spec/containers/0'}])); print(f'  JSON patch 先 test containers/0/name==b 再 remove(下标和预期不符):退出码 {rc};{o[:200]}')

print('== 三:哪些列表按 key 合并——schema 里的 x-kubernetes-patch-strategy / patch-merge-key')
rc, o = k('get', '--raw', '/openapi/v3/apis/apps/v1', raw=True); sch = json.loads(o)['components']['schemas']
ps = sch['io.k8s.api.core.v1.PodSpec']['properties']; ct = sch['io.k8s.api.core.v1.Container']['properties']
def ext(d, f): return {kk: v for kk, v in d[f].items() if kk.startswith('x-kubernetes-patch') or kk == 'x-kubernetes-list-type'}
for lbl, d, f in (('PodSpec.containers', ps, 'containers'), ('PodSpec.volumes', ps, 'volumes'), ('PodSpec.tolerations', ps, 'tolerations'), ('Container.env', ct, 'env'), ('Container.ports', ct, 'ports'), ('Container.command', ct, 'command'), ('Container.args', ct, 'args')):
    print(f'  {lbl}:{ext(d, f) or "(没有扩展:整个列表被替换)"}')
mkdep(); rc, o = patch('strategic', json.dumps({'spec': {'template': {'spec': {'tolerations': [{'key': 't3', 'operator': 'Exists'}]}}}})); print(f'  strategic 改 tolerations(没有 merge key)写一条 t3:{o};{brief()}')

print('== 四:自定义资源不支持 strategic merge patch')
crd = '''
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: boxes.k10.example.com}
spec:
  group: k10.example.com
  scope: Namespaced
  names: {kind: Box, plural: boxes}
  versions:
  - {name: v1, served: true, storage: true, schema: {openAPIV3Schema: {type: object, x-kubernetes-preserve-unknown-fields: true}}}
'''
apply(crd); time.sleep(3)
k('create', '-f', '-', input=f'apiVersion: k10.example.com/v1\nkind: Box\nmetadata: {{name: b1, namespace: {NS}}}\nspec: {{items: [{{name: first, v: 1}}, {{name: second, v: 2}}]}}\n')
def reset(): k('delete', 'box', 'b1', '-n', NS, '--ignore-not-found'); k('create', '-f', '-', input=f'apiVersion: k10.example.com/v1\nkind: Box\nmetadata: {{name: b1, namespace: {NS}}}\nspec: {{items: [{{name: first, v: 1}}, {{name: second, v: 2}}]}}\n')
for typ in ('strategic', 'merge', 'json'):
    reset()
    body = json.dumps([{'op': 'replace', 'path': '/spec/items/0/v', 'value': 9}]) if typ == 'json' else json.dumps({'spec': {'items': [{'name': 'first', 'v': 9}]}})
    rc, o = k('patch', 'box', 'b1', '-n', NS, f'--type={typ}', '-p', body); print(f'  对自定义资源 --type={typ}:退出码 {rc};{o.strip()[:230]};spec.items={ko("get", "box", "b1", "-n", NS, "-o", "jsonpath={.spec.items}")}')
k('delete', 'crd', 'boxes.k10.example.com', '--wait=true', timeout=120); rmns(NS)
