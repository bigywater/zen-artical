import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k52')
cn, _ = up('sched', cfg=config(workers=4)); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k52')
for sc in ('k52-imm', 'k52-wait', 'k52-keep', 'k52-default'): k('delete', 'sc', sc, '--ignore-not-found')
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def sc(name, mode='WaitForFirstConsumer', reclaim='Delete', extra='', default=False):
    ann = '  annotations: {storageclass.kubernetes.io/is-default-class: "true"}\n' if default else ''
    return f'apiVersion: storage.k8s.io/v1\nkind: StorageClass\nmetadata:\n  name: {name}\n{ann}provisioner: rancher.io/local-path\nvolumeBindingMode: {mode}\nreclaimPolicy: {reclaim}\n{extra}'
def pvc(name, cls=None, size='10Mi', ns_=NS):
    c = f'  storageClassName: {cls}\n' if cls else ''
    return f'apiVersion: v1\nkind: PersistentVolumeClaim\nmetadata: {{name: {name}, namespace: {ns_}}}\nspec:\n  accessModes: [ReadWriteOnce]\n{c}  resources: {{requests: {{storage: {size}}}}}\n'
def user(name, claim):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "echo hello > /d/f; sleep 3600"], volumeMounts: [{{name: d, mountPath: /d}}]}}]\n  volumes: [{{name: d, persistentVolumeClaim: {{claimName: {claim}}}}}]\n'
print(f'集群 {cn};StorageClass 描述“怎么造卷”:谁来造(provisioner)、什么时候造(volumeBindingMode)、造完怎么回收(reclaimPolicy)')
rc, o = k('get', 'sc'); print('  集群里原有的 StorageClass:'); [print('    ' + l) for l in o.strip().splitlines()]

print('== 一:Immediate 与 WaitForFirstConsumer——PVC 什么时候被供给')
k('apply', '-f', '-', input=sc('k52-imm', 'Immediate')); k('apply', '-f', '-', input=sc('k52-wait', 'WaitForFirstConsumer'))
k('apply', '-f', '-', input=pvc('p-imm', 'k52-imm')); k('apply', '-f', '-', input=pvc('p-wait', 'k52-wait')); time.sleep(6)
for n in ('p-imm', 'p-wait'):
    c = kj('get', 'pvc', n, '-n', NS); print(f'  PVC {n}(没有 Pod 使用):phase={c["status"]["phase"]};volumeName={c["spec"].get("volumeName", "(空)")[:20]}')
ev_imm = [e['reason'] + ': ' + e['message'][:150] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=p-imm')['items']]
print(f'    p-imm 的事件:{ev_imm[-2:]}')
t0 = time.time(); k('apply', '-f', '-', input=user('u-wait', 'p-wait')); v, dt = until(lambda: kj('get', 'pvc', 'p-wait', '-n', NS)['status']['phase'] == 'Bound', 60, 0.3)
until(lambda: kj('get', 'pod', 'u-wait', '-n', NS)['spec'].get('nodeName'), 30, 0.2); c = kj('get', 'pvc', 'p-wait', '-n', NS); pvn = c['spec']['volumeName']; pv = kj('get', 'pv', pvn)
print(f'  创建使用 p-wait 的 Pod 后 {dt:.1f} 秒 PVC Bound:PV {pvn[:20]}…;PV 的 nodeAffinity={pv["spec"]["nodeAffinity"]["required"]["nodeSelectorTerms"][0]["matchExpressions"][0]["values"]};Pod 调度到 {kj("get", "pod", "u-wait", "-n", NS)["spec"]["nodeName"]}(PV 在 Pod 被调度的那个节点上造出来)')
ann = c['metadata'].get('annotations', {}); print(f'  PVC 上的注解:{ {k_: v_ for k_, v_ in ann.items() if "volume" in k_} }')

print('== 二:供给的过程——PVC → provisioner → PV → 绑定(看事件和时间)')
k('delete', 'pod', 'u-wait', '-n', NS, '--wait=true', timeout=60); k('delete', 'pvc', 'p-wait', 'p-imm', '-n', NS, '--wait=true', timeout=60); time.sleep(3)
k('apply', '-f', '-', input=pvc('p2', 'k52-wait')); t0 = time.time(); k('apply', '-f', '-', input=user('u2', 'p2'))
until(lambda: kj('get', 'pvc', 'p2', '-n', NS)['status']['phase'] == 'Bound', 60, 0.2); t_bound = time.time() - t0
ev = sorted(kj('get', 'events', '-n', NS)['items'], key=lambda e: e.get('firstTimestamp') or e.get('eventTime') or '')
for e in ev:
    if e['involvedObject']['name'] in ('p2', 'u2'): print(f'    事件 {e["involvedObject"]["kind"]}/{e["involvedObject"]["name"]} {e["reason"]}: {e["message"][:130]}')
pv = kj('get', 'pv', kj('get', 'pvc', 'p2', '-n', NS)['spec']['volumeName']); print(f'  PV 的 spec:hostPath/local 路径={pv["spec"].get("hostPath", {}).get("path") or pv["spec"].get("local", {})};storageClassName={pv["spec"]["storageClassName"]};reclaim={pv["spec"]["persistentVolumeReclaimPolicy"]};annotations={ {k_: v_ for k_, v_ in pv["metadata"].get("annotations", {}).items()} }')
print(f'  从创建 Pod 到 PVC Bound 用了 {t_bound:.1f} 秒')
k('delete', 'pod', 'u2', '-n', NS, '--wait=true', timeout=60); k('delete', 'pvc', 'p2', '-n', NS, '--wait=true', timeout=60)

print('== 三:没写 storageClassName——默认存储类')
dflt = [s['metadata']['name'] for s in kj('get', 'sc')['items'] if s['metadata'].get('annotations', {}).get('storageclass.kubernetes.io/is-default-class') == 'true']
print(f'  现在的默认存储类:{dflt}')
k('apply', '-f', '-', input=pvc('nocls')); c = kj('get', 'pvc', 'nocls', '-n', NS); print(f'  不写 storageClassName 的 PVC nocls:spec.storageClassName={c["spec"].get("storageClassName")}(准入补成了默认类)')
k('apply', '-f', '-', input=pvc('emptycls', '""')); c = kj('get', 'pvc', 'emptycls', '-n', NS); print(f'  storageClassName: "" 的 PVC emptycls:spec.storageClassName={c["spec"].get("storageClassName")!r};phase={c["status"]["phase"]}(空字符串表示“不要动态供给,只绑静态 PV”,没有静态 PV 就一直 Pending)')
k('apply', '-f', '-', input=sc('k52-default', 'WaitForFirstConsumer', default=True)); time.sleep(1)
dflt2 = [s['metadata']['name'] for s in kj('get', 'sc')['items'] if s['metadata'].get('annotations', {}).get('storageclass.kubernetes.io/is-default-class') == 'true']
print(f'  再标一个默认类 k52-default 之后,集群里有 {len(dflt2)} 个默认存储类:{dflt2}')
k('apply', '-f', '-', input=pvc('two-defaults')); c = kj('get', 'pvc', 'two-defaults', '-n', NS); print(f'  不写 storageClassName 的 PVC two-defaults:spec.storageClassName={c["spec"].get("storageClassName")}(多个默认类时选“最新创建的”)')
k('delete', 'pvc', '--all', '-n', NS, '--wait=true', timeout=60); k('delete', 'sc', 'k52-default')

print('== 四:reclaimPolicy 写在存储类上,供给出来的 PV 继承它')
k('apply', '-f', '-', input=sc('k52-keep', 'WaitForFirstConsumer', 'Retain'))
k('apply', '-f', '-', input=pvc('keep-me', 'k52-keep')); k('apply', '-f', '-', input=user('u3', 'keep-me')); until(lambda: kj('get', 'pvc', 'keep-me', '-n', NS)['status']['phase'] == 'Bound', 60)
pvn = kj('get', 'pvc', 'keep-me', '-n', NS)['spec']['volumeName']; print(f'  存储类 k52-keep(reclaimPolicy: Retain)供给的 PV {pvn[:20]}…:persistentVolumeReclaimPolicy={kj("get", "pv", pvn)["spec"]["persistentVolumeReclaimPolicy"]}')
until(lambda: kj('get', 'pod', 'u3', '-n', NS)['spec'].get('nodeName'), 30, 0.2); time.sleep(3); node = kj('get', 'pod', 'u3', '-n', NS)['spec']['nodeName']; path = kj('get', 'pv', pvn)['spec'].get('hostPath', {}).get('path') or kj('get', 'pv', pvn)['spec'].get('local', {}).get('path')
k('delete', 'pod', 'u3', '-n', NS, '--wait=true', timeout=60); k('delete', 'pvc', 'keep-me', '-n', NS, '--wait=true', timeout=60); time.sleep(5)
p = kj('get', 'pv', pvn); print(f'  删掉 PVC 之后:PV {"仍在,phase=" + p["status"]["phase"] if p else "没有了"};节点 {node.replace("kx-sched-", "")} 上目录里的文件:{nx(node, f"cat {path}/f 2>&1 | head -1")[1]}(数据还在)')
k('delete', 'pv', pvn, '--wait=true', timeout=60); nx(node, f'rm -rf {path}')
for s_ in ('k52-imm', 'k52-wait', 'k52-keep'): k('delete', 'sc', s_)
rmns(NS)
