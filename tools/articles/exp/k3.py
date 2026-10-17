import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k3')
cn, _ = up('main')
NS = ns('k3')
k('delete', 'crd', 'widgets.k3.example.com', '--ignore-not-found')
crd = '''
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: widgets.k3.example.com}
spec:
  group: k3.example.com
  scope: Namespaced
  names: {kind: Widget, plural: widgets, singular: widget}
  versions:
  - name: v1
    served: true
    storage: true
    subresources: {status: {}}
    additionalPrinterColumns:
    - {name: Size, type: integer, jsonPath: .spec.size}
    - {name: Color, type: string, jsonPath: .spec.color}
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required: [size]
            properties:
              size: {type: integer, minimum: 1, maximum: 10}
              color: {type: string, enum: [red, green], default: red}
          status:
            type: object
            properties: {ready: {type: boolean}}
'''
rc, o = apply(crd); assert rc == 0, o
v, dt = until(lambda: 'Established' in ko('get', 'crd', 'widgets.k3.example.com', '-o', 'jsonpath={.status.conditions[*].type}'), 30)
print(f'集群 {cn};CRD widgets.k3.example.com(v1,spec.size 必填且 1..10,spec.color 枚举 red/green 默认 red,开了 status 子资源),{dt:.1f} 秒后 Established')
W = lambda name, spec, extra='': f'apiVersion: k3.example.com/v1\nkind: Widget\nmetadata: {{name: {name}, namespace: {NS}}}\nspec: {spec}\n{extra}'
def c1(y, *a): rc, o = k('apply', '-f', '-', *a, input=y); return rc, o.strip().replace('\n', ' ')

print('== 一:schema 校验——合法对象被接受并补上默认值,不合法的在提交时被拒绝')
print('  [size=3] ' + str(c1(W('w1', '{size: 3}'))))
print('  读回 w1 的 spec:' + ko('get', 'widget', 'w1', '-n', NS, '-o', 'jsonpath={.spec}'))
for label, spec in (('size=0', '{size: 0}'), ('缺少 size', '{color: red}'), ('color=blue', '{size: 2, color: blue}'), ('size="abc"', '{size: abc}')):
    rc, o = c1(W('bad', spec)); print(f'  [{label}] 退出码 {rc};{re.sub(r"^.*is invalid: ", "", o)[:200]}')
print('  kubectl get widgets(附加打印列来自 additionalPrinterColumns):')
for l in k('get', 'widgets', '-n', NS)[1].splitlines(): print('    ' + l)

print('== 二:schema 里没有的字段——kubectl 默认严格校验,绕过校验后服务端会把它剪掉(pruning)')
rc, o = c1(W('w2', '{size: 2, extra: hello}')); print(f'  默认(服务端严格字段校验):退出码 {rc};{o[:200]}')
rc, o = c1(W('w2', '{size: 2, extra: hello}'), '--validate=false'); print(f'  --validate=false:退出码 {rc};{o}')
print('  读回 w2 的 spec:' + ko('get', 'widget', 'w2', '-n', NS, '-o', 'jsonpath={.spec}') + '  ← extra 不见了')
rc, o = c1(W('w2', '{size: 2, extra: hello}'), '--validate=warn'); print(f'  --validate=warn:退出码 {rc};{o[:200]}')

print('== 三:etcd 里存的是什么——默认值写入时就固化了;CRD 之后新加的默认值是在读出来的时候补上的')
def etcd_get(key):
    rc, o = k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'get', key, '--print-value-only', raw=True)
    return o.strip()
key = f'/registry/k3.example.com/widgets/{NS}/w1'
j = json.loads(etcd_get(key))
print(f'  etcd key {key}')
print(f'  存进去的 JSON:apiVersion={j["apiVersion"]} kind={j["kind"]} spec={json.dumps(j["spec"])} metadata 字段:{sorted(j["metadata"])}')
crd2 = crd.replace("color: {type: string, enum: [red, green], default: red}", "color: {type: string, enum: [red, green], default: red}\n              shape: {type: string, default: circle}")
rc, o = apply(crd2); time.sleep(2)
print('  给 CRD 新增一个带默认值的字段 spec.shape(default: circle)之后:')
print('    读 w1 的 spec:' + ko('get', 'widget', 'w1', '-n', NS, '-o', 'jsonpath={.spec}'))
print('    etcd 里 w1 的 spec:' + json.dumps(json.loads(etcd_get(key))['spec']) + '  ← 没有 shape,默认值只在读的时候补')

print('== 四:status 子资源——主资源的写入忽略 status,status 的写入忽略 spec,generation 只跟着 spec 走')
g = lambda: ko('get', 'widget', 'w1', '-n', NS, '-o', 'jsonpath={.metadata.generation}')
print(f'  初始:generation={g()} status={ko("get", "widget", "w1", "-n", NS, "-o", "jsonpath={.status}") or "(空)"}')
rc, o = k('patch', 'widget', 'w1', '-n', NS, '--type=merge', '-p', '{"status":{"ready":true}}'); print(f'  patch 主资源写 status.ready=true:{o.strip()};读回 status={ko("get", "widget", "w1", "-n", NS, "-o", "jsonpath={.status}") or "(空)"}')
rc, o = k('patch', 'widget', 'w1', '-n', NS, '--subresource=status', '--type=merge', '-p', '{"status":{"ready":true}}'); print(f'  patch --subresource=status 写同样的内容:{o.strip()};读回 status={ko("get", "widget", "w1", "-n", NS, "-o", "jsonpath={.status}")};generation={g()}')
rc, o = k('patch', 'widget', 'w1', '-n', NS, '--subresource=status', '--type=merge', '-p', '{"spec":{"size":9}}'); print(f'  通过 status 子资源改 spec.size=9:{o.strip()};读回 spec.size={ko("get", "widget", "w1", "-n", NS, "-o", "jsonpath={.spec.size}")}')
rc, o = k('patch', 'widget', 'w1', '-n', NS, '--type=merge', '-p', '{"spec":{"size":5}}'); print(f'  通过主资源改 spec.size=5:{o.strip()};读回 spec.size={ko("get", "widget", "w1", "-n", NS, "-o", "jsonpath={.spec.size}")};generation={g()}')
k('delete', 'crd', 'widgets.k3.example.com', '--wait=true', timeout=120); rmns(NS)
