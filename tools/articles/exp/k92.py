import sys, os, re, time, json, base64, collections, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k92')
cn, _ = up('main'); wait_nodes_ready()
NS = ns('k92')
POD = f'etcd-{cn}-control-plane'
def etcdctl(*a, input=None, timeout=60):
    return k('exec', '-i', '-n', 'kube-system', POD, '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', *a, input=input, raw=True, timeout=timeout)
def getjson(key, *extra):
    rc, o = etcdctl('get', key, '-w', 'json', *extra); return json.loads(o[o.index('{'):])
k('create', 'configmap', 'cm1', '-n', NS, '--from-literal=hello=world')
k('apply', '-f', '-', input='''apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: widgets.k92.example.com}
spec:
  group: k92.example.com
  scope: Namespaced
  names: {plural: widgets, singular: widget, kind: Widget}
  versions:
  - name: v1
    served: true
    storage: true
    schema: {openAPIV3Schema: {type: object, x-kubernetes-preserve-unknown-fields: true}}
''')
until(lambda: k('get', 'widgets.k92.example.com', '-n', NS)[0] == 0, 30, 0.5)
k('apply', '-f', '-', input=f'apiVersion: k92.example.com/v1\nkind: Widget\nmetadata: {{name: w1, namespace: {NS}}}\nspec: {{size: 3}}\n')
print(f'集群 {cn};Kubernetes 把每个对象存成 etcd 里的一个 key,key 是对象的 REST 路径,value 是序列化后的对象')

print('== 一:key 的结构')
rc, o = etcdctl('get', '/registry/', '--prefix', '--keys-only'); keys = [l for l in o.splitlines() if l.startswith('/registry/')]
cnt = collections.Counter(re.match(r'/registry/([^/]+(?:/[^/]+)?)', kk).group(1).split('/')[0] for kk in keys)
print(f'  /registry/ 下共 {len(keys)} 个 key;按第一段(资源类型)统计的前 8 个:{cnt.most_common(8)}')
ex = [f'/registry/configmaps/{NS}/cm1', f'/registry/namespaces/{NS}', f'/registry/k92.example.com/widgets/{NS}/w1', '/registry/clusterroles/view', f'/registry/minions/{cn}-worker', f'/registry/leases/kube-node-lease/{cn}-worker', '/registry/deployments/kube-system/coredns']
for kk in ex:
    rc, o = etcdctl('get', kk, '--keys-only'); print(f'  {kk:<55}{"存在" if o.strip().startswith("/registry") else "不存在"}')
print('  规律:/registry/<资源>/<命名空间>/<名字>(集群级资源没有命名空间段);CRD 的资源前面多一段 API 组;节点的路径是历史遗留的 minions;Service 分成 services/specs 和 services/endpoints')
svc = [kk for kk in keys if kk.startswith('/registry/services/')][:3]; print(f'  services 下的前几个 key:{svc}')

print('== 二:value 的编码——内置资源是 protobuf,CRD 是 JSON')
v1 = base64.b64decode(getjson(f'/registry/configmaps/{NS}/cm1')['kvs'][0]['value']); v2 = base64.b64decode(getjson(f'/registry/k92.example.com/widgets/{NS}/w1')['kvs'][0]['value'])
print(f'  ConfigMap cm1:{len(v1)} 字节;开头 {v1[:4]!r}(魔数 k8s\\x00 = protobuf 存储格式);可读片段:{[m.decode() for m in re.findall(rb"[ -~]{5,}", v1)][:6]}')
print(f'  Widget w1(CRD 对象):{len(v2)} 字节;开头 {v2[:30]!r};是 JSON:{v2[:1] == b"{"};能 json.loads 吗:{bool(json.loads(v2))}')
rc, o = k('get', 'cm', 'cm1', '-n', NS, '-o', 'json'); cm = json.loads(o)
print(f'  同一个 ConfigMap 经 API Server 读出来是 JSON({len(o)} 字节),比 etcd 里的 protobuf({len(v1)} 字节)大——存储格式比 API 格式紧凑')

print('== 三:resourceVersion 就是 etcd 的 mod_revision')
kv = getjson(f'/registry/configmaps/{NS}/cm1')['kvs'][0]
print(f'  etcd 里 key 的 create_revision={kv["create_revision"]};mod_revision={kv["mod_revision"]};version={kv["version"]}')
print(f'  API 里 cm1 的 resourceVersion={cm["metadata"]["resourceVersion"]}(与 mod_revision 相同:{str(kv["mod_revision"]) == cm["metadata"]["resourceVersion"]})')
k('patch', 'cm', 'cm1', '-n', NS, '--type=merge', '-p', '{"data":{"hello":"again"}}'); kv2 = getjson(f'/registry/configmaps/{NS}/cm1')['kvs'][0]; rv2 = kj('get', 'cm', 'cm1', '-n', NS)['metadata']['resourceVersion']
print(f'  patch 一次之后:mod_revision={kv2["mod_revision"]}(create_revision 仍是 {kv2["create_revision"]});version={kv2["version"]};resourceVersion={rv2}')
k('create', 'configmap', 'cm2', '-n', NS, '--from-literal=a=b'); rc, o = k('get', 'cm', 'cm2', '-n', NS, '-o', 'jsonpath={.metadata.resourceVersion}'); print(f'  新建另一个 cm2:resourceVersion={o.strip()},比 cm1 的 {rv2} 大(全局 revision 只增不减,所有对象共用一条时间线)')

print('== 四:用 etcdctl watch 看 API 操作如何变成 etcd 事件')
p = subprocess.Popen(['kubectl', '--kubeconfig', kcfg(), 'exec', '-n', 'kube-system', POD, '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'watch', f'/registry/configmaps/{NS}/', '--prefix', '-w', 'json'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
time.sleep(2)
k('create', 'configmap', 'cm3', '-n', NS, '--from-literal=x=1'); time.sleep(0.5)
k('label', 'cm', 'cm3', '-n', NS, 'a=b'); time.sleep(0.5)
k('delete', 'cm', 'cm3', '-n', NS); time.sleep(2); p.terminate()
out = p.stdout.read(); evs = []
for l in out.splitlines():
    try: j = json.loads(l)
    except Exception: continue
    for e in j.get('Events', []): evs.append(('DELETE' if e.get('type') in (1, 'DELETE') else 'PUT', base64.b64decode(e['kv']['key']).decode().split('/')[-1], e['kv']['mod_revision'], e['kv'].get('version')))
print(f'  etcdctl watch /registry/configmaps/{NS}/ --prefix 收到的事件(类型, key 末段, mod_revision, version):')
for e in evs: print(f'    {e}')
print('  含义:create / label 都是 PUT(label 是一次新的写入,version 加 1);delete 是 DELETE 事件,这就是 API Server 的 watch 的数据来源')
k('delete', 'crd', 'widgets.k92.example.com', '--wait=false'); k('delete', 'ns', NS, '--wait=false')
