import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k53')
cn, _ = up('sched', cfg=config(workers=4)); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k53')
for sc in ('k53-noexp', 'k53-exp'): k('delete', 'sc', sc, '--ignore-not-found')
def sc(name, expand):
    return f'apiVersion: storage.k8s.io/v1\nkind: StorageClass\nmetadata: {{name: {name}}}\nprovisioner: rancher.io/local-path\nvolumeBindingMode: WaitForFirstConsumer\nallowVolumeExpansion: {str(expand).lower()}\n'
def pvc(name, cls, size):
    return f'apiVersion: v1\nkind: PersistentVolumeClaim\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  accessModes: [ReadWriteOnce]\n  storageClassName: {cls}\n  resources: {{requests: {{storage: {size}}}}}\n'
def user(name, claim):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "sleep 3600"], volumeMounts: [{{name: d, mountPath: /d}}]}}]\n  volumes: [{{name: d, persistentVolumeClaim: {{claimName: {claim}}}}}]\n'
def grow(name, size):
    return k('patch', 'pvc', name, '-n', NS, '--type=merge', '-p', json.dumps({'spec': {'resources': {'requests': {'storage': size}}}}))
def show(name):
    c = kj('get', 'pvc', name, '-n', NS)
    return f'spec.requests={c["spec"]["resources"]["requests"]["storage"]};status.capacity={c["status"].get("capacity", {}).get("storage", "(无)")};conditions={[x["type"] for x in c["status"].get("conditions", [])] or "(无)"}'
def bind(name, claim):
    k('apply', '-f', '-', input=user(name, claim)); until(lambda: kj('get', 'pvc', claim, '-n', NS)['status']['phase'] == 'Bound', 60, 0.3)
    until(lambda: kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), 40, 0.3)
print(f'集群 {cn};PVC 扩容 = 把 spec.resources.requests.storage 改大;API Server 管“让不让改”,真正改文件系统要靠存储驱动')

print('== 一:存储类不允许扩容——API Server 直接拒绝')
k('apply', '-f', '-', input=sc('k53-noexp', False)); k('apply', '-f', '-', input=pvc('a', 'k53-noexp', '10Mi')); bind('ua', 'a')
print(f'  存储类 k53-noexp(allowVolumeExpansion: false)的 PVC a:{show("a")}')
rc, o = grow('a', '20Mi'); print(f'  把 a 改成 20Mi:退出码 {rc};{o.strip()[:230]}')
print(f'  被拒绝之后 a:{show("a")}')
k('patch', 'sc', 'k53-noexp', '-p', '{"allowVolumeExpansion": true}'); time.sleep(1)
rc, o = grow('a', '20Mi'); print(f'  把存储类的 allowVolumeExpansion 改成 true 之后再改 a 为 20Mi:退出码 {rc};{o.strip()[:100]}(字段是随时可改的,而且对已有 PVC 立即生效)')

print('== 二:被受理之后——spec 变了,status.capacity 和文件系统没变')
k('apply', '-f', '-', input=sc('k53-exp', True)); k('apply', '-f', '-', input=pvc('b', 'k53-exp', '10Mi')); bind('ub', 'b')
pvn = kj('get', 'pvc', 'b', '-n', NS)['spec']['volumeName']
def dfsize(pod): return nx_pod(pod)
def df(pod):
    rc, o = k('exec', pod, '-n', NS, '--', 'sh', '-c', 'df -k /d | tail -1'); return o.split()[1] + ' KiB' if rc == 0 else o.strip()[:60]
print(f'  扩容前 b:{show("b")};PV capacity={kj("get", "pv", pvn)["spec"]["capacity"]["storage"]};Pod 里 df /d 总大小 {df("ub")}(local-path 的卷是节点磁盘上的目录,df 看到的是整块节点磁盘)')
rc, o = grow('b', '20Mi'); print(f'  把 b 改成 20Mi:退出码 {rc};{o.strip()[:80]}')
time.sleep(40)
print(f'  40 秒之后 b:{show("b")};PV capacity={kj("get", "pv", pvn)["spec"]["capacity"]["storage"]};df 总大小 {df("ub")}')
ev = [e['reason'] + ': ' + e['message'][:90] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=b')['items'] if e['reason'] not in ('WaitForFirstConsumer', 'ExternalProvisioning', 'Provisioning', 'ProvisioningSucceeded')]
print(f'    b 上多出来的事件:{ev or "(没有)"}')

print('== 三:缩小——不能低于 status.capacity')
rc, o = grow('b', '5Mi'); print(f'  b 现在 spec 是 20Mi、容量 10Mi;改成 5Mi:退出码 {rc};{o.strip()[:230]}')
rc, o = grow('b', '15Mi'); print(f'  改成 15Mi(比 spec 的 20Mi 小,但比容量 10Mi 大):退出码 {rc};{o.strip()[:100]};现在 {show("b")}')
rc, o = grow('b', '10Mi'); print(f'  改回 10Mi(等于容量):退出码 {rc};{o.strip().splitlines()[0][:300]};现在 {show("b")}')

print('== 四:没绑定的 PVC——spec 整个不可变;绑定之后只有 requests 能改')
k('apply', '-f', '-', input=pvc('c', 'k53-exp', '10Mi')); time.sleep(2)
print(f'  PVC c(类 k53-exp 允许扩容,没有 Pod 使用,phase={kj("get", "pvc", "c", "-n", NS)["status"]["phase"]}):{show("c")}')
rc, o = grow('c', '30Mi'); print(f'  把还是 Pending 的 c 改大到 30Mi:退出码 {rc};{o.strip().splitlines()[0][:300]}')
bind('uc', 'c'); print(f'  创建 Pod 使 c 绑定之后:{show("c")};PV capacity={kj("get", "pv", kj("get", "pvc", "c", "-n", NS)["spec"]["volumeName"])["spec"]["capacity"]["storage"]}')
rc, o = k('patch', 'pvc', 'c', '-n', NS, '--type=merge', '-p', json.dumps({'spec': {'accessModes': ['ReadWriteMany']}})); print(f'  绑定之后改 accessModes:退出码 {rc};{o.strip().splitlines()[0][:300]}')
rc, o = grow('c', '30Mi'); print(f'  绑定之后改 requests.storage 为 30Mi:退出码 {rc};{o.strip()[:100]}')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60); k('delete', 'pvc', '--all', '-n', NS, '--wait=true', timeout=60); k('delete', 'sc', 'k53-noexp', 'k53-exp')
