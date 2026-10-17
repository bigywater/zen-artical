import sys, os, re, time, json, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k5')
cn, _ = up('main')
NS = ns('k5')
k('delete', 'crd', 'things.k5.example.com', '--ignore-not-found', '--wait=true', timeout=120)
k('create', 'deploy', 'app', '-n', NS, '--image=busybox:1.36', '--replicas=0', '--', 'sleep', '3600')
hpa = f'''
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {{name: h1, namespace: {NS}}}
spec:
  scaleTargetRef: {{apiVersion: apps/v1, kind: Deployment, name: app}}
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource: {{name: cpu, target: {{type: Utilization, averageUtilization: 50}}}}
  - type: Resource
    resource: {{name: memory, target: {{type: Utilization, averageUtilization: 70}}}}
  behavior:
    scaleDown: {{stabilizationWindowSeconds: 60}}
'''
rc, o = k('create', '-f', '-', input=hpa); assert rc == 0, o
print(f'集群 {cn};用 autoscaling/v2 创建一个 HPA(CPU 50% + 内存 70% 两个指标,scaleDown 稳定窗口 60 秒)')
def raw(path):
    return json.loads(ko('get', '--raw', path))

print('== 一:同一个对象,用 autoscaling/v1 和 autoscaling/v2 分别读出来')
v2 = raw(f'/apis/autoscaling/v2/namespaces/{NS}/horizontalpodautoscalers/h1')
v1 = raw(f'/apis/autoscaling/v1/namespaces/{NS}/horizontalpodautoscalers/h1')
print(f'  v2:apiVersion={v2["apiVersion"]};spec 的键 {sorted(v2["spec"])};metrics 有 {len(v2["spec"]["metrics"])} 项:' + ', '.join(f'{m["resource"]["name"]}={m["resource"]["target"]["averageUtilization"]}%' for m in v2['spec']['metrics']))
print(f'  v1:apiVersion={v1["apiVersion"]};spec 的键 {sorted(v1["spec"])};targetCPUUtilizationPercentage={v1["spec"].get("targetCPUUtilizationPercentage")}')
ann = {a: v for a, v in v1['metadata'].get('annotations', {}).items() if a.startswith('autoscaling.alpha')}
print('  v1 多出来的注解:' + ', '.join(sorted(ann)))
print('    autoscaling.alpha.kubernetes.io/metrics = ' + ann.get('autoscaling.alpha.kubernetes.io/metrics', '(无)'))
print(f'  v2 的注解里有 autoscaling.alpha 开头的吗:{any(a.startswith("autoscaling.alpha") for a in v2["metadata"].get("annotations", {}))}')

print('== 二:etcd 里存的是哪个版本(用 v1 写和用 v2 写,存进去的都一样吗)')
v1y = f'apiVersion: autoscaling/v1\nkind: HorizontalPodAutoscaler\nmetadata: {{name: h2, namespace: {NS}}}\nspec: {{scaleTargetRef: {{apiVersion: apps/v1, kind: Deployment, name: app}}, minReplicas: 1, maxReplicas: 3, targetCPUUtilizationPercentage: 80}}\n'
rc, o = k('create', '-f', '-', input=v1y); print(f'  用 autoscaling/v1 创建 h2:{o.strip()}')
def etcd_bytes(key):
    rc, o = k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'get', key, '-w', 'json', raw=True)
    return base64.b64decode(json.loads(o)['kvs'][0]['value'])
def pb_head(b):
    """k8s protobuf 封装:'k8s\\0' + Unknown{typeMeta{apiVersion, kind}, raw...}"""
    assert b[:4] == b'k8s\x00'
    i = 4; assert b[i] == 0x0a; i += 1
    def varint(i):
        n = sh_ = 0
        while True:
            c = b[i]; i += 1; n |= (c & 0x7f) << sh_; sh_ += 7
            if not c & 0x80: return n, i
    ln, i = varint(i); end = i + ln
    assert b[i] == 0x0a; i += 1; l1, i = varint(i); av = b[i:i + l1].decode(); i += l1
    assert b[i] == 0x12; i += 1; l2, i = varint(i); kd = b[i:i + l2].decode()
    return av, kd
for name in ('h1', 'h2'):
    b = etcd_bytes(f'/registry/horizontalpodautoscalers/{NS}/{name}')
    av, kd = pb_head(b)
    print(f'  {name}:etcd 里的值 {len(b)} 字节,开头 {b[:4]!r}(k8s 的 protobuf 封装),解出的 apiVersion={av} kind={kd}')

print('== 三:弃用警告——内置的 v1 Endpoints 与自己 CRD 里标记 deprecated 的版本')
def dep_count(res):
    rc, o = k('get', '--raw', '/metrics', raw=True)
    return sum(int(float(l.rsplit(' ', 1)[1])) for l in o.splitlines() if l.startswith('apiserver_requested_deprecated_apis') and f'resource="{res}"' in l)
rc, o = k('get', 'endpoints', '-n', 'default')
print('  kubectl get endpoints -n default 的输出:')
for l in o.strip().splitlines(): print('    ' + l[:150])
rc, o = k('get', '--raw', '/metrics', raw=True)
ml = [l for l in o.splitlines() if l.startswith('apiserver_requested_deprecated_apis') or l.startswith('# TYPE apiserver_requested_deprecated_apis')]
print('  /metrics 里的弃用记录:')
for l in ml: print('    ' + l)
rc, o = k('get', 'endpoints', '-n', 'default', '-v=8', raw=True)
print('  响应头里的警告:' + next((l.split('Warning:')[-1].strip() for l in o.splitlines() if 'Warning:' in l and 'deprecated' in l and 'Response Headers' not in l), '(未找到)'))
crd = '''
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: things.k5.example.com}
spec:
  group: k5.example.com
  scope: Namespaced
  names: {kind: Thing, plural: things}
  versions:
  - {name: v1beta1, served: true, storage: false, deprecated: true, deprecationWarning: "k5.example.com/v1beta1 Thing 已弃用,请改用 k5.example.com/v1 Thing", schema: {openAPIV3Schema: {type: object, x-kubernetes-preserve-unknown-fields: true}}}
  - {name: v1, served: true, storage: true, schema: {openAPIV3Schema: {type: object, x-kubernetes-preserve-unknown-fields: true}}}
'''
apply(crd); time.sleep(3)
for ver in ('v1beta1', 'v1'):
    rc, o = k('get', f'things.{ver}.k5.example.com', '-n', NS); print(f'  kubectl get things.{ver}.k5.example.com:{o.strip().replace(chr(10), " | ")}')

print('== 四:发现接口——kubectl 默认用哪个版本')
print('  kubectl api-versions 里 autoscaling 的版本:' + ' '.join(l for l in ko('api-versions').splitlines() if l.startswith('autoscaling')))
g = raw('/apis/autoscaling')
print(f'  /apis/autoscaling:preferredVersion={g["preferredVersion"]["groupVersion"]};versions 的顺序 {[x["groupVersion"] for x in g["versions"]]}')
for desc, args in (('kubectl get hpa', ('get', 'hpa', '-n', NS)), ('kubectl get horizontalpodautoscalers.v1.autoscaling', ('get', 'horizontalpodautoscalers.v1.autoscaling', '-n', NS)), ('kubectl get horizontalpodautoscalers.v2.autoscaling', ('get', 'horizontalpodautoscalers.v2.autoscaling', '-n', NS)), ('kubectl get hpa.v1.autoscaling(短名带版本)', ('get', 'hpa.v1.autoscaling', '-n', NS))):
    rc, o = k(*args, '-v=6', raw=True)
    url = next((re.search(r'url="([^"]+)"', l).group(1) for l in o.splitlines() if 'verb="GET"' in l and 'horizontalpodautoscalers' in l), '(无)')
    print(f'  {desc} 实际请求的路径:{re.sub(r"https://[^/]+", "", url)}')
k('delete', 'crd', 'things.k5.example.com', '--wait=true', timeout=120); rmns(NS)
