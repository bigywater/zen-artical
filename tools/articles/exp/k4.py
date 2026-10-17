import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
import kweb
tee('k4')
cn, _ = up('main')
NS = ns('k4')
for r in ('gadgets', 'gizmos'): k('delete', 'crd', f'{r}.k4.example.com', '--ignore-not-found', '--wait=true', timeout=120)
ca = kweb.deploy('conv', NS)
def crd(plural, kind, conv, storage='v1'):
    sch = lambda f: f'schema: {{openAPIV3Schema: {{type: object, properties: {{spec: {{type: object, properties: {{{f}: {{type: integer}}}}}}}}}}}}'
    c = '  conversion: {strategy: None}\n' if conv == 'None' else f'  conversion:\n    strategy: Webhook\n    webhook:\n      conversionReviewVersions: ["v1"]\n      clientConfig:\n        caBundle: {ca}\n        service: {{namespace: {NS}, name: conv, path: /convert}}\n'
    return f'''
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {{name: {plural}.k4.example.com}}
spec:
  group: k4.example.com
  scope: Namespaced
  names: {{kind: {kind}, plural: {plural}}}
{c}  versions:
  - {{name: v1beta1, served: true, storage: {str(storage == 'v1beta1').lower()}, {sch('replicas')}}}
  - {{name: v1, served: true, storage: {str(storage == 'v1').lower()}, {sch('size')}}}
'''
for plural, kind, conv in (('gadgets', 'Gadget', 'Webhook'), ('gizmos', 'Gizmo', 'None')):
    rc, o = apply(crd(plural, kind, conv)); assert rc == 0, o
time.sleep(3)
print(f'集群 {cn};两个 CRD:gadgets(conversion.strategy=Webhook)、gizmos(strategy=None);都有 v1beta1(spec.replicas)和 v1(spec.size,存储版本)两个版本;转换 webhook 是集群里自己写的 HTTPS 服务')
def etcd_get(key):
    rc, o = k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'get', key, '--print-value-only', raw=True)
    return json.loads(o.strip())
def obj(plural, kind, ver, name, field, val):
    return f'apiVersion: k4.example.com/{ver}\nkind: {kind}\nmetadata: {{name: {name}, namespace: {NS}}}\nspec: {{{field}: {val}}}\n'
def show(plural, ver, name):
    j = kj('get', f'{plural}.{ver}.k4.example.com', name, '-n', NS)
    return f'apiVersion={j["apiVersion"]} spec={json.dumps(j["spec"])}' if j else '(读取失败)'
def nlog(): return len(kweb.hook_logs('conv', NS))
def newlogs(n0): return kweb.hook_logs('conv', NS)[n0:]

print('== 一:用 v1beta1 写入(spec.replicas=3),分别用 v1beta1 和 v1 读,再看 etcd 里存了什么')
def calls(n0):
    time.sleep(0.7); L = newlogs(n0)
    return '没有调用 webhook' if not L else '调用 webhook ' + str(len(L)) + ' 次(' + ';'.join(f'{x["frm"][0].split("/")[1]}→{x["to"].split("/")[1]} 共 {x["n"]} 个对象' for x in L) + ')'
for plural, kind in (('gadgets', 'Gadget'), ('gizmos', 'Gizmo')):
    n0 = nlog()
    rc, o = k('create', '-f', '-', input=obj(plural, kind, 'v1beta1', 'a1', 'replicas', 3)); w = calls(n0) if plural == 'gadgets' else ''
    print(f'  [{plural}] 用 v1beta1 创建:{o.strip()}' + (f'  ← {w}' if w else ''))
    n0 = nlog(); r = show(plural, "v1beta1", "a1"); w = calls(n0) if plural == 'gadgets' else ''
    print(f'    用 v1beta1 读:{r}' + (f'  ← {w}' if w else ''))
    n0 = nlog(); r = show(plural, "v1", "a1"); w = calls(n0) if plural == 'gadgets' else ''
    print(f'    用 v1 读:      {r}' + (f'  ← {w}' if w else ''))
    e = etcd_get(f'/registry/k4.example.com/{plural}/{NS}/a1')
    print(f'    etcd 里存的:  apiVersion={e["apiVersion"]} spec={json.dumps(e["spec"])}')

print('== 二:webhook 什么时候被调用——写入、单个读、list 各一次')
def cnt():
    rc, o = k('get', '--raw', '/metrics', raw=True)
    return sum(int(float(l.rsplit(' ', 1)[1])) for l in o.splitlines() if l.startswith('apiserver_crd_conversion_webhook_duration_seconds_count') and 'gadgets' in l)
def act(label, fn):
    n0, c0 = nlog(), cnt(); fn(); time.sleep(0.8); L = newlogs(n0)
    d = ';'.join(sorted({f'{x["frm"][0].split("/")[1]}→{x["to"].split("/")[1]}' for x in L})) or '无'
    print(f'  {label}:webhook 被调用 {len(L)} 次({d});apiserver 的转换计数器增加 {cnt() - c0}')
act('用 v1(存储版本)创建 a2——没有任何读', lambda: k('create', '-f', '-', input=obj('gadgets', 'Gadget', 'v1', 'a2', 'size', 2)))
for i in range(3, 7): k('create', '-f', '-', input=obj('gadgets', 'Gadget', 'v1', f'a{i}', 'size', i))
time.sleep(1)
act('用 v1 读 a2(GET)', lambda: k('get', 'gadgets.v1.k4.example.com', 'a2', '-n', NS))
act('用 v1beta1 读 a2(GET)', lambda: k('get', 'gadgets.v1beta1.k4.example.com', 'a2', '-n', NS))
act('用 v1beta1 list 全部 6 个对象', lambda: k('get', 'gadgets.v1beta1.k4.example.com', '-n', NS))
rc, o = k('get', 'gadgets.v1beta1.k4.example.com', '-n', NS, '-o', 'custom-columns=NAME:.metadata.name,VERSION:.apiVersion,REPLICAS:.spec.replicas')
print('  那次 list 返回的内容:')
for l in o.splitlines(): print('    ' + l)

print('== 三:转换 webhook 挂了(存储版本是 v1)——哪些请求还能用')
kweb.scale('conv', NS, 0); time.sleep(1)
def tryit(label, *args, inp=None):
    t0 = time.time(); rc, o = k(*args, input=inp); dt = time.time() - t0
    print(f'  {label}:退出码 {rc};{dt:.2f} s;' + (' | '.join(l[:230] for l in o.strip().splitlines()[:2]) if rc else o.strip().splitlines()[0][:120]))
tryit('用 v1 读 a2', 'get', 'gadgets.v1.k4.example.com', 'a2', '-n', NS, '-o', 'name')
tryit('用 v1beta1 读 a2', 'get', 'gadgets.v1beta1.k4.example.com', 'a2', '-n', NS, '-o', 'name')
tryit('用 v1 创建 c2(存储版本,不需要转换)', 'create', '-f', '-', inp=obj('gadgets', 'Gadget', 'v1', 'c2', 'size', 2))
tryit('用 v1beta1 创建 c3(要先转成 v1)', 'create', '-f', '-', inp=obj('gadgets', 'Gadget', 'v1beta1', 'c3', 'replicas', 3))
tryit('用 v1 list', 'get', 'gadgets.v1.k4.example.com', '-n', NS, '-o', 'name')
tryit('用 v1beta1 list', 'get', 'gadgets.v1beta1.k4.example.com', '-n', NS, '-o', 'name')
kweb.scale('conv', NS, 1); time.sleep(4)
tryit('webhook 恢复后用 v1beta1 list', 'get', 'gadgets.v1beta1.k4.example.com', '-n', NS, '-o', 'name')

print('== 四:改存储版本:storedVersions 与旧对象')
sv = lambda p: ko('get', 'crd', f'{p}.k4.example.com', '-o', 'jsonpath={.status.storedVersions}')
print(f'  gadgets 当前 status.storedVersions={sv("gadgets")}')
rc, o = apply(crd('gadgets', 'Gadget', 'Webhook', storage='v1beta1')); time.sleep(2)
print(f'  把 storage 改到 v1beta1:storedVersions={sv("gadgets")}')
print(f'  旧对象 a2 在 etcd 里:apiVersion={etcd_get(f"/registry/k4.example.com/gadgets/{NS}/a2")["apiVersion"]}(还是旧版本,没人重写它)')
k('create', '-f', '-', input=obj('gadgets', 'Gadget', 'v1beta1', 'a7', 'replicas', 7))
e7 = etcd_get(f"/registry/k4.example.com/gadgets/{NS}/a7")
print(f'  新建 a7 在 etcd 里:apiVersion={e7["apiVersion"]} spec={json.dumps(e7["spec"])}')
k('replace', '-f', '-', input=ko('get', 'gadgets.v1beta1.k4.example.com', 'a2', '-n', NS, '-o', 'yaml'))
print(f'  kubectl replace a2 重写之后:apiVersion={etcd_get(f"/registry/k4.example.com/gadgets/{NS}/a2")["apiVersion"]}')
rc, o = k('patch', 'crd', 'gadgets.k4.example.com', '--type=json', '-p', '[{"op":"remove","path":"/spec/versions/1"}]')
print(f'  想从 CRD 里删掉 v1 版本:{re.sub(r"^.*is invalid: ", "", o.strip())[:260]}')
for r in ('gadgets', 'gizmos'): k('delete', 'crd', f'{r}.k4.example.com', '--wait=true', timeout=120)
rmns(NS)
