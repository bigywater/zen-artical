import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k51')
cn, _ = up('sched', cfg=config(workers=4)); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k51')
for pv in ('k51-pv-2g', 'k51-pv-5g', 'k51-pv-10g', 'k51-pv-rwx', 'k51-pv-reserved', 'k51-pv-labeled'): k('delete', 'pv', pv, '--ignore-not-found', '--wait=true', timeout=60)
def pv(name, size, cls='manual', modes='[ReadWriteOnce]', labels='', claimref='', reclaim='Retain'):
    return f'apiVersion: v1\nkind: PersistentVolume\nmetadata: {{name: {name}{(", labels: {" + labels + "}") if labels else ""}}}\nspec:\n  capacity: {{storage: {size}}}\n  accessModes: {modes}\n  storageClassName: "{cls}"\n  persistentVolumeReclaimPolicy: {reclaim}\n  hostPath: {{path: /tmp/{name}, type: DirectoryOrCreate}}\n{claimref}'
def pvc(name, size, cls='manual', modes='[ReadWriteOnce]', sel=''):
    return f'apiVersion: v1\nkind: PersistentVolumeClaim\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  accessModes: {modes}\n  storageClassName: "{cls}"\n  resources: {{requests: {{storage: {size}}}}}\n{sel}'
def st(kind, name, ns_=None):
    j = kj('get', kind, name, *(['-n', ns_] if ns_ else [])); return j
def pvsum():
    items = [p for p in kj('get', 'pv')['items'] if p['metadata']['name'].startswith('k51-')]
    return '; '.join(f'{p["metadata"]["name"][4:]}={p["spec"]["capacity"]["storage"]}/{p["status"]["phase"]}' + (f'→{p["spec"]["claimRef"]["name"]}' if p['spec'].get('claimRef') else '') for p in sorted(items, key=lambda p: p['metadata']['name']))
print(f'集群 {cn};PV(集群级)与 PVC(命名空间级)靠 PV 控制器配对:大小够、访问模式够、存储类相同、标签选择器匹配')

print('== 一:配对规则——PVC 挑选“最小的、够用的”PV')
for n, sz in (('k51-pv-2g', '2Gi'), ('k51-pv-5g', '5Gi'), ('k51-pv-10g', '10Gi')): k('apply', '-f', '-', input=pv(n, sz))
time.sleep(1); print(f'  三个 PV(存储类 manual,RWO):{pvsum()}')
k('apply', '-f', '-', input=pvc('c3g', '3Gi')); time.sleep(3)
c = st('pvc', 'c3g', NS); print(f'  PVC c3g 请求 3Gi:phase={c["status"]["phase"]};绑定到 {c["spec"].get("volumeName")}(容量 {c["status"].get("capacity", {}).get("storage")});{pvsum()}')
k('apply', '-f', '-', input=pvc('c20g', '20Gi')); time.sleep(3); c = st('pvc', 'c20g', NS)
print(f'  PVC c20g 请求 20Gi(没有这么大的 PV):phase={c["status"]["phase"]};事件:{[e["message"][:90] for e in kj("get", "events", "-n", NS, "--field-selector", "involvedObject.name=c20g")["items"]][-1:]}')
k('apply', '-f', '-', input=pvc('crwx', '1Gi', modes='[ReadWriteMany]')); time.sleep(3); c = st('pvc', 'crwx', NS); print(f'  PVC crwx 请求 RWX(现有 PV 都只有 RWO):phase={c["status"]["phase"]}')
k('apply', '-f', '-', input=pvc('cclass', '1Gi', cls='other')); time.sleep(3); c = st('pvc', 'cclass', NS); print(f'  PVC cclass 的 storageClassName 是 other(PV 都是 manual):phase={c["status"]["phase"]}')
t_ = time.time(); k('apply', '-f', '-', input=pv('k51-pv-rwx', '1Gi', modes='[ReadWriteMany]'))
v, dt = until(lambda: st('pvc', 'crwx', NS)['status']['phase'] == 'Bound', 60, 0.5); c = st('pvc', 'crwx', NS)
print(f'  现在加一个 RWX 的 PV 之后 {dt:.1f} 秒:crwx phase={c["status"]["phase"]} → {c["spec"].get("volumeName")}(Pending 的 PVC 在有匹配的 PV 出现后自动绑定,PV 控制器是周期性同步的,所以有延迟)')
k('delete', 'pvc', '--all', '-n', NS, '--wait=true', timeout=60)

print('== 二:标签选择器与预留(claimRef)')
k('delete', 'pv', 'k51-pv-2g', 'k51-pv-5g', 'k51-pv-10g', 'k51-pv-rwx', '--ignore-not-found', '--wait=true', timeout=60)
k('apply', '-f', '-', input=pv('k51-pv-2g', '2Gi'))
k('apply', '-f', '-', input=pv('k51-pv-labeled', '4Gi', labels='tier: gold')); k('apply', '-f', '-', input=pv('k51-pv-5g', '5Gi', labels='tier: silver'))
k('apply', '-f', '-', input=pvc('want-gold', '1Gi', sel='  selector: {matchLabels: {tier: gold}}\n')); k('apply', '-f', '-', input=pvc('plain-small', '1Gi')); time.sleep(4)
for n in ('want-gold', 'plain-small'): c = st('pvc', n, NS); print(f'  PVC {n}({"selector tier=gold" if n == "want-gold" else "没有 selector,请求 1Gi"}):绑定 {c["spec"].get("volumeName")}')
k('delete', 'pvc', '--all', '-n', NS, '--wait=true', timeout=60); time.sleep(2)
k('delete', 'pv', 'k51-pv-labeled', 'k51-pv-5g', 'k51-pv-2g', '--ignore-not-found', '--wait=true', timeout=60)
res = f'  claimRef: {{namespace: {NS}, name: reserved-for-me}}\n'
k('apply', '-f', '-', input=pv('k51-pv-reserved', '1Gi', claimref=res)); k('apply', '-f', '-', input=pvc('someone-else', '500Mi')); time.sleep(4)
c = st('pvc', 'someone-else', NS); print(f'  PV k51-pv-reserved 预先写了 claimRef(只给 {NS}/reserved-for-me),此时集群里没有别的可用 PV:另一个 PVC someone-else 请求 500Mi → phase={c["status"]["phase"]}(PV 被预留了,别人拿不走);{pvsum()}')
k('apply', '-f', '-', input=pvc('reserved-for-me', '500Mi')); time.sleep(4); c = st('pvc', 'reserved-for-me', NS); print(f'  PVC reserved-for-me 请求 500Mi → phase={c["status"]["phase"]} {c["spec"].get("volumeName")}')
k('delete', 'pvc', '--all', '-n', NS, '--wait=true', timeout=60); k('delete', 'pv', 'k51-pv-reserved', '--wait=true', timeout=60)

print('== 三:删除 PVC 之后 PV 去哪了——reclaimPolicy')
k('apply', '-f', '-', input=pv('k51-pv-2g', '2Gi', reclaim='Retain')); k('apply', '-f', '-', input=pvc('c1', '1Gi')); time.sleep(3)
k('delete', 'pvc', 'c1', '-n', NS, '--wait=true', timeout=60); time.sleep(3)
p = st('pv', 'k51-pv-2g'); print(f'  persistentVolumeReclaimPolicy=Retain 的静态 PV:删除 PVC 之后 phase={p["status"]["phase"]};spec.claimRef 还在:{p["spec"].get("claimRef", {}).get("name")}(数据和绑定记录都保留着)')
k('apply', '-f', '-', input=pvc('c2', '1Gi')); time.sleep(3); c = st('pvc', 'c2', NS); print(f'  新建 PVC c2(1Gi):phase={c["status"]["phase"]}(Released 的 PV 不会被别人拿去用)')
k('patch', 'pv', 'k51-pv-2g', '--type=json', '-p', '[{"op":"remove","path":"/spec/claimRef"}]')
v, dt = until(lambda: st('pvc', 'c2', NS)['status']['phase'] == 'Bound', 60, 0.5); c = st('pvc', 'c2', NS); p = st('pv', 'k51-pv-2g')
print(f'  手动去掉 PV 的 claimRef 之后 {dt:.1f} 秒:c2 phase={c["status"]["phase"]};PV phase={p["status"]["phase"]}(Released → Available → Bound)')
k('delete', 'pvc', 'c2', '-n', NS, '--wait=true', timeout=60); k('delete', 'pv', 'k51-pv-2g', '--wait=true', timeout=60)
print('== 四:动态供给与 WaitForFirstConsumer')
sc = kj('get', 'sc', 'standard'); print(f'  动态供给的 StorageClass standard:reclaimPolicy={sc["reclaimPolicy"]} volumeBindingMode={sc["volumeBindingMode"]} provisioner={sc["provisioner"]}')
k('apply', '-f', '-', input=pvc('dyn', '10Mi', cls='standard')); time.sleep(2); c = st('pvc', 'dyn', NS)
print(f'  动态 PVC dyn 创建后立刻 phase={c["status"]["phase"]}(WaitForFirstConsumer:没有 Pod 用它就不供给);事件:{[e["reason"] + ": " + e["message"][:70] for e in kj("get", "events", "-n", NS, "--field-selector", "involvedObject.name=dyn")["items"]][-1:]}')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: user, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"], volumeMounts: [{{name: d, mountPath: /d}}]}}]\n  volumes: [{{name: d, persistentVolumeClaim: {{claimName: dyn}}}}]\n')
until(lambda: st('pvc', 'dyn', NS)['status']['phase'] == 'Bound', 60); c = st('pvc', 'dyn', NS); pvn = c['spec']['volumeName']
print(f'  创建用它的 Pod 之后:dyn phase={c["status"]["phase"]},自动创建了 PV {pvn[:16]}…,所在节点 {kj("get", "pv", pvn)["spec"]["nodeAffinity"]["required"]["nodeSelectorTerms"][0]["matchExpressions"][0]["values"]}')
k('delete', 'pod', 'user', '-n', NS, '--wait=true', timeout=60); k('delete', 'pvc', 'dyn', '-n', NS, '--wait=true', timeout=60); time.sleep(5)
print(f'  删除 PVC dyn 之后:PV {pvn[:16]}… 还在吗:{bool(kj("get", "pv", pvn))}(reclaimPolicy=Delete:PV 随 PVC 一起被删除)')
rmns(NS)
