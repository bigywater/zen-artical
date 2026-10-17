import sys, os, re, time, json, tempfile, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k100')
cn, _ = up('main'); wait_nodes_ready()
def short(o, n=3, w=200): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
print(f'集群 {cn};API Server 会描述自己:有哪些资源(discovery)、每个字段是什么(OpenAPI 文档)。kubectl api-resources 和 kubectl explain 就是这两份描述的命令行视图')

print('== 一:api-resources 与发现机制')
rc, o = k('api-resources', '--no-headers'); rows = [l.split() for l in o.strip().splitlines()]
print(f'  kubectl api-resources:共 {len(rows)} 种资源;namespaced 的 {sum(1 for r in rows if r[-2] == "true")} 种,集群级的 {sum(1 for r in rows if r[-2] == "false")} 种')
rc, o = k('api-versions'); print(f'  kubectl api-versions:{len(o.split())} 个 group/version,例如 {o.split()[:4]}')
rc, o = k('api-resources', '--api-group=apps', '-o', 'wide'); print('  --api-group=apps -o wide:'); [print('    ' + re.sub(r'\s+', ' ', l)[:150]) for l in o.strip().splitlines()[:4]]
rc, o = k('api-resources', '--no-headers', '--verbs=create', '--namespaced=false'); print(f'  只看集群级且支持 create 的:{[r.split()[0] for r in o.strip().splitlines()][:8]}…共 {len(o.strip().splitlines())} 种')
d = tempfile.mkdtemp(); rc, o = k('api-resources', '-v=6', f'--cache-dir={d}', '--no-headers', raw=True)
gets = [l for l in o.splitlines() if 'GET https' in l or '"Request"' in l or 'Response Status' in l]
urls = sorted({re.search(r'(https://\S+)', l).group(1).split('6443')[-1].split('/', 1)[-1][:60] if re.search(r'(https://\S+)', l) else '' for l in o.splitlines() if 'GET' in l and 'https' in l})
print(f'  冷缓存(--cache-dir 是新目录)下 api-resources 发出的 GET 请求:{[re.sub(chr(34), "", u) for u in urls if u][:8]}(聚合发现:/api 和 /apis 两个请求就拿到全部资源)')
rc, o = k('get', '--raw', '/apis', raw=True); print(f'  GET /apis(普通 Accept)返回的 group 数 {len(json.loads(o)["groups"])}')

print('== 二:explain——字段文档来自 OpenAPI')
rc, o = k('explain', 'pod.spec.containers.imagePullPolicy'); print('  kubectl explain pod.spec.containers.imagePullPolicy:'); [print('    ' + l[:140]) for l in o.strip().splitlines()[:9]]
rc, o = k('explain', 'deployment.spec.strategy.rollingUpdate'); print('  kubectl explain deployment.spec.strategy.rollingUpdate:'); [print('    ' + l[:140]) for l in o.strip().splitlines()[:8]]
rc, o = k('explain', 'service.spec.type'); print(f'  kubectl explain service.spec.type 的 FIELD/VERSION/TYPE 头:{short(o, 4, 90)}')
rc, o = k('explain', 'deployment.spec', '--recursive'); fields = [l for l in o.splitlines() if re.match(r'\s+\w', l)]; print(f'  explain deployment.spec --recursive 展开了 {len(fields)} 行字段树(前几行:{[l.strip()[:50] for l in fields[:6]]})')
rc, o = k('explain', 'pod.spec.nonexistent'); print(f'  不存在的字段 pod.spec.nonexistent:退出码 {rc};{short(o, 6)[-1]}')
rc, o = k('explain', 'ingress', '--api-version=networking.k8s.io/v1'); print(f'  指定 API 版本:--api-version=networking.k8s.io/v1 → {short(o, 3, 80)}')

print('== 三:OpenAPI 文档本身')
rc, o = k('get', '--raw', '/openapi/v3', raw=True); paths = json.loads(o)['paths']; print(f'  GET /openapi/v3:{len(paths)} 个路径(每个 group/version 一份文档),例如 {sorted(paths)[:4]}')
rc, o = k('get', '--raw', '/openapi/v3/apis/apps/v1', raw=True); doc = json.loads(o); sch = doc['components']['schemas']; print(f'  GET /openapi/v3/apis/apps/v1:{len(o) // 1024} KiB;含 {len(sch)} 个 schema;其中 io.k8s.api.apps.v1.Deployment 的字段:{sorted(sch["io.k8s.api.apps.v1.Deployment"]["properties"])}')
imp = sch['io.k8s.api.core.v1.Container']['properties']['imagePullPolicy']; print(f'  Container.imagePullPolicy 在 OpenAPI 里:type={imp.get("type")};enum={imp.get("enum")};description 开头={imp["description"][:70]!r}…')
gvk = sch['io.k8s.api.apps.v1.Deployment'].get('x-kubernetes-group-version-kind'); print(f'  Deployment 的 x-kubernetes-group-version-kind={gvk}')

print('== 四:装一个 CRD 之后,发现信息和文档立刻跟着出现')
n0 = len(k('api-resources', '--no-headers')[1].strip().splitlines())
t0 = time.time(); k('apply', '-f', '-', input='''apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: gadgets.k100.example.com}
spec:
  group: k100.example.com
  scope: Namespaced
  names: {plural: gadgets, singular: gadget, kind: Gadget, shortNames: [gd]}
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            description: Gadget 的期望状态
            properties:
              size: {type: integer, description: 尺寸(单位毫米), minimum: 1}
              color: {type: string, enum: [red, green, blue], description: 颜色}
            required: [size]
''')
v, dt = until(lambda: any('gadgets' in l for l in k('api-resources', '--no-headers')[1].splitlines()), 30, 0.3)
print(f'  创建 CRD gadgets.k100.example.com 后 {dt:.1f} 秒,api-resources 里出现 gadgets(简称 gd),总数 {n0} → {len(k("api-resources", "--no-headers")[1].strip().splitlines())}')
v, dt2 = until(lambda: k('explain', 'gadget.spec.color')[0] == 0, 60, 0.5)
rc, o = k('explain', 'gadget.spec.color'); print(f'  kubectl explain gadget.spec.color({dt2:.1f} 秒后可用):'); [print('    ' + l[:120]) for l in o.strip().splitlines()[:8]]
rc, o = k('explain', 'gadget.spec'); print(f'  kubectl explain gadget.spec 的字段列表:{short(o, 12, 70)[3:8]}')
k('delete', 'crd', 'gadgets.k100.example.com', '--wait=false')
