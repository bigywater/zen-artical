import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k83')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
def mk(name, labels):
    k('delete', 'ns', name, '--ignore-not-found', '--wait=true', timeout=90)
    lb = ''.join(f'    pod-security.kubernetes.io/{a}: {b}\n' for a, b in labels.items())
    k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {name}\n  labels:\n{lb}' if labels else f'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {name}\n')
def pod(name, ns_, spec_extra='', csc='', vols=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {ns_}}}\nspec:\n  terminationGracePeriodSeconds: 0\n{spec_extra}  containers:\n  - name: c\n    image: busybox:1.36\n    imagePullPolicy: IfNotPresent\n    command: [sleep, "3600"]\n{csc}{vols}'
def apply(y): rc, o = k('apply', '-f', '-', input=y); return rc, o.strip()
def lines(o, n=3, w=330): return [re.sub(r'\s+', ' ', l)[:w] for l in o.splitlines() if l.strip()][:n]
print(f'集群 {cn};Pod Security 准入控制器按命名空间标签 pod-security.kubernetes.io/<mode>=<level> 检查 Pod:level 是 privileged / baseline / restricted,mode 是 enforce(拒绝)/ audit(记审计)/ warn(警告)')

print('== 一:enforce=baseline')
mk('ps-base', {'enforce': 'baseline'})
rc, o = apply(pod('ok', 'ps-base')); print(f'  普通 Pod(什么都不设):退出码 {rc};{lines(o, 1)}')
rc, o = apply(pod('priv', 'ps-base', csc='    securityContext: {privileged: true}\n')); print(f'  privileged: true:退出码 {rc};{lines(o, 2)}')
rc, o = apply(pod('hostnet', 'ps-base', spec_extra='  hostNetwork: true\n')); print(f'  hostNetwork: true:退出码 {rc};{lines(o, 2)}')
rc, o = apply(pod('hostpath', 'ps-base', vols='  volumes: [{name: h, hostPath: {path: /etc}}]\n')); print(f'  hostPath 卷:退出码 {rc};{lines(o, 2)}')
rc, o = apply(pod('caps', 'ps-base', csc='    securityContext: {capabilities: {add: [NET_ADMIN]}}\n')); print(f'  add NET_ADMIN:退出码 {rc};{lines(o, 2)}')
rc, o = apply(pod('caps2', 'ps-base', csc='    securityContext: {capabilities: {add: [NET_BIND_SERVICE]}}\n')); print(f'  add NET_BIND_SERVICE(baseline 允许的少数能力之一):退出码 {rc};{lines(o, 1)}')

print('== 二:enforce=restricted')
mk('ps-restr', {'enforce': 'restricted'})
rc, o = apply(pod('plain', 'ps-restr')); print(f'  普通 Pod:退出码 {rc}')
for l in lines(o, 6, 760): print('    ' + l)
GOOD = '    securityContext:\n      allowPrivilegeEscalation: false\n      capabilities: {drop: [ALL]}\n      runAsNonRoot: true\n      runAsUser: 1000\n      seccompProfile: {type: RuntimeDefault}\n'
rc, o = apply(pod('good', 'ps-restr', csc=GOOD)); print(f'  补齐 allowPrivilegeEscalation=false / drop ALL / runAsNonRoot / seccomp RuntimeDefault:退出码 {rc};{lines(o, 1)}')
rc, o = apply(pod('almost', 'ps-restr', csc=GOOD.replace('      runAsUser: 1000\n', '').replace('runAsNonRoot: true', 'runAsNonRoot: true'))); k('delete', 'pod', 'almost', '-n', 'ps-restr', '--ignore-not-found'); print(f'  去掉 runAsUser(镜像是 root,但 runAsNonRoot=true 声明了):退出码 {rc}(准入只看字段,不看镜像;运行时 kubelet 才会拒绝)')

print('== 三:warn / audit 模式与控制器')
mk('ps-warn', {'warn': 'restricted', 'enforce': 'baseline'})
rc, o = apply(pod('w1', 'ps-warn')); print(f'  warn=restricted + enforce=baseline,创建普通 Pod:退出码 {rc};')
for l in lines(o, 3): print('    ' + l)
mk('ps-dep', {'enforce': 'restricted'})
rc, o = apply(f'apiVersion: apps/v1\nkind: Deployment\nmetadata: {{name: dep, namespace: ps-dep}}\nspec:\n  replicas: 1\n  selector: {{matchLabels: {{app: dep}}}}\n  template:\n    metadata: {{labels: {{app: dep}}}}\n    spec:\n      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n')
print(f'  enforce=restricted 的命名空间里创建不合规的 Deployment:退出码 {rc};{lines(o, 3)}')
time.sleep(5); d = kj('get', 'deploy', 'dep', '-n', 'ps-dep'); rs = kj('get', 'rs', '-n', 'ps-dep')['items'][0]
print(f'  Deployment 本身创建成功,但 readyReplicas={d["status"].get("readyReplicas", 0)};ReplicaSet 的 conditions:{[(c["type"], c.get("reason"), c.get("message", "")[:150]) for c in rs["status"].get("conditions", [])]}')
rc, ev = k('get', 'events', '-n', 'ps-dep', '--field-selector', 'reason=FailedCreate'); print(f'  事件:{lines(ev, 3)[-1:]}')

print('== 四:给已有 Pod 的命名空间加标签')
mk('ps-late', {})
apply(pod('old', 'ps-late', csc='    securityContext: {privileged: true}\n')); time.sleep(3)
rc, o = k('label', '--dry-run=server', 'ns', 'ps-late', 'pod-security.kubernetes.io/enforce=baseline'); print(f'  --dry-run=server 加 enforce=baseline:退出码 {rc};{lines(o, 3)}')
rc, o = k('label', 'ns', 'ps-late', 'pod-security.kubernetes.io/enforce=baseline'); print(f'  真正加上标签:退出码 {rc};{lines(o, 2)}')
print(f'  已经在运行的 privileged Pod 老 old:phase={kj("get", "pod", "old", "-n", "ps-late")["status"]["phase"]}(不受影响,只对之后创建/更新 Pod 的请求检查)')
rc, o = apply(pod('new', 'ps-late', csc='    securityContext: {privileged: true}\n')); print(f'  再创建一个 privileged 的 new:退出码 {rc};{lines(o, 1)}')
k('label', 'ns', 'ps-late', 'pod-security.kubernetes.io/enforce-version=v1.24', '--overwrite'); 
k('delete', 'ns', 'ps-base', 'ps-restr', 'ps-warn', 'ps-dep', 'ps-late', '--wait=false')
