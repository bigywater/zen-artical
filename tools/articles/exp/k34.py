import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k34')
cn, _ = up('main')
NS = ns('k34')
LR = f'''apiVersion: v1
kind: LimitRange
metadata: {{name: lr, namespace: {NS}}}
spec:
  limits:
  - type: Container
    default: {{cpu: 500m, memory: 256Mi}}
    defaultRequest: {{cpu: 100m, memory: 128Mi}}
    min: {{cpu: 50m, memory: 64Mi}}
    max: {{cpu: "1", memory: 512Mi}}
    maxLimitRequestRatio: {{cpu: "4"}}
  - type: PersistentVolumeClaim
    max: {{storage: 1Gi}}
    min: {{storage: 10Mi}}
'''
LR_BAD = LR
rc, o = k('apply', '-f', '-', input=LR); assert rc == 0, o
def pod(name, res=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n{res}'
def res(name):
    p = kj('get', 'pod', name, '-n', NS)
    r = p['spec']['containers'][0].get('resources', {})
    return f'requests={r.get("requests")} limits={r.get("limits")} qos={p["status"]["qosClass"]}', p
print(f'集群 {cn};LimitRange 在命名空间 {NS} 里:容器默认 limit cpu 500m(随后会改)/ memory 256Mi,默认 request cpu 100m / memory 128Mi,min cpu 50m / memory 64Mi,max cpu 1 / memory 512Mi,cpu 的 limit/request 比最大 4;PVC 的 storage 在 10Mi~1Gi 之间')
print('== 一:什么都没写的 Pod——LimitRange 在准入时补上默认值(默认值自己也要满足 min / max / 比例)')
rc, o = k('apply', '-f', '-', input=pod('plain')); print(f'  默认 limit cpu 500m、默认 request cpu 100m(比例 5,而 maxLimitRequestRatio 是 4):创建 Pod plain 退出码 {rc};{re.sub(r"^.*Forbidden: ", "", o.strip())[:200]}')
LR = LR.replace('default: {cpu: 500m, memory: 256Mi}', 'default: {cpu: 400m, memory: 256Mi}'); k('apply', '-f', '-', input=LR)
print('  把默认 limit 改成 cpu 400m(比例 4)之后:')
k('apply', '-f', '-', input=pod('plain'))
r, p = res('plain'); print(f'  Pod plain(没写 resources):{r}')
print(f'  注解:{ {k_: v for k_, v in p["metadata"].get("annotations", {}).items() if "limit" in k_} }')
k('delete', 'pod', 'plain', '-n', NS, '--wait=false')

print('== 二:写了一部分——只补缺的那几项')
for n_, rs in (('only-limit-cpu', '    resources: {limits: {cpu: 200m}}\n'), ('only-req-mem', '    resources: {requests: {memory: 100Mi}}\n'), ('full', '    resources: {requests: {cpu: 100m, memory: 100Mi}, limits: {cpu: 300m, memory: 200Mi}}\n')):
    k('apply', '-f', '-', input=pod(n_, rs)); r, p = res(n_); print(f'  {n_:<15} 写了 {rs.strip().replace("resources: ", "")}  →  {r}')
    k('delete', 'pod', n_, '-n', NS, '--wait=false')

print('== 三:越界的 Pod 在准入时被拒绝')
for n_, rs, d in (('too-big', '    resources: {requests: {cpu: "2"}, limits: {cpu: "2"}}\n', 'cpu 请求 2 核(max 是 1)'), ('too-small', '    resources: {requests: {memory: 10Mi}, limits: {memory: 200Mi}}\n', 'memory 请求 10Mi(min 是 64Mi)'), ('big-ratio', '    resources: {requests: {cpu: 100m}, limits: {cpu: 900m}}\n', 'cpu limit/request = 9(最大 4)'), ('mem-over', '    resources: {requests: {memory: 100Mi}, limits: {memory: 1Gi}}\n', 'memory limit 1Gi(max 是 512Mi)')):
    rc, o = k('apply', '-f', '-', input=pod(n_, rs)); print(f'  {d}:退出码 {rc};{re.sub(r"^.*Forbidden: ", "", o.strip())[:210]}')

print('== 四:PVC 的范围,以及 LimitRange 改了之后不影响已经存在的 Pod')
for n_, st in (('pvc-ok', '500Mi'), ('pvc-big', '5Gi'), ('pvc-small', '1Mi')):
    rc, o = k('apply', '-f', '-', input=f'apiVersion: v1\nkind: PersistentVolumeClaim\nmetadata: {{name: {n_}, namespace: {NS}}}\nspec: {{accessModes: [ReadWriteOnce], resources: {{requests: {{storage: {st}}}}}}}\n')
    print(f'  PVC {n_}(storage {st}):退出码 {rc};{re.sub(r"^.*Forbidden: ", "", o.strip())[:230]}')
k('apply', '-f', '-', input=pod('old')); r_old, _ = res('old')
k('apply', '-f', '-', input=LR.replace('default: {cpu: 400m, memory: 256Mi}', 'default: {cpu: 800m, memory: 400Mi}').replace('defaultRequest: {cpu: 100m, memory: 128Mi}', 'defaultRequest: {cpu: 200m, memory: 128Mi}'))
k('apply', '-f', '-', input=pod('new')); r_new, _ = res('new'); r_old2, _ = res('old')
print(f'  把 LimitRange 的默认 limit 改成 cpu 800m / memory 400Mi(默认 request cpu 改成 200m)之后:已有的 Pod old 仍是 {r_old2.split(" qos")[0]}(没变:{r_old == r_old2});新建的 Pod new 是 {r_new.split(" qos")[0]}')
rmns(NS)
