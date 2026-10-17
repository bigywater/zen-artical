import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k43')
cn, _ = up('sched', cfg=config(workers=4)); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k43')
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def sts(name='web', replicas=3, policy='OrderedReady', probe='cat /tmp/ok', retention='', delay=3, grace=0):
    return f'''apiVersion: v1
kind: Service
metadata: {{name: {name}, namespace: {NS}}}
spec: {{clusterIP: None, selector: {{app: {name}}}, ports: [{{port: 80}}]}}
---
apiVersion: apps/v1
kind: StatefulSet
metadata: {{name: {name}, namespace: {NS}}}
spec:
  serviceName: {name}
  replicas: {replicas}
  podManagementPolicy: {policy}
  selector: {{matchLabels: {{app: {name}}}}}
{retention}  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: {grace}
      containers:
      - name: c
        image: busybox:1.36
        command: [sh, -c, "touch /tmp/ok; echo $(hostname) > /data/who; sleep 3600"]
        readinessProbe: {{exec: {{command: [sh, -c, "{probe}"]}}, initialDelaySeconds: {delay}, periodSeconds: 1}}
        volumeMounts: [{{name: data, mountPath: /data}}]
  volumeClaimTemplates:
  - metadata: {{name: data}}
    spec: {{accessModes: [ReadWriteOnce], resources: {{requests: {{storage: 10Mi}}}}}}
'''
def pods(app='web'): return {p['metadata']['name']: p for p in kj('get', 'pods', '-n', NS, '-l', f'app={app}')['items']}
def ready(p): return any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', []))
print(f'集群 {cn};StatefulSet = 有稳定身份的 Deployment:固定的名字(web-0、web-1…)、固定的网络标识、固定的存储(每个 Pod 一个 PVC)')

print('== 一:有序创建与有序终止(OrderedReady)——前一个 Ready 了才创建下一个')
t0 = time.time(); k('apply', '-f', '-', input=sts(grace=5))
until(lambda: len([p for p in pods().values() if ready(p)]) == 3, 90); time.sleep(1)
ps = pods(); base = min(ts(p['metadata']['creationTimestamp']) for p in ps.values())
for n in sorted(ps):
    p = ps[n]; rd = [c for c in p['status']['conditions'] if c['type'] == 'Ready'][0]
    print(f'  {n}:创建于 +{ts(p["metadata"]["creationTimestamp"]) - base:4.1f}s;Ready 于 +{ts(rd["lastTransitionTime"]) - base:4.1f}s;所在节点 {p["spec"]["nodeName"].replace("kx-sched-", "")}')
print('  (就绪探针 initialDelaySeconds=3,加上调度、绑定 PVC 和拉起容器,每个 Pod 要 6~7 秒才 Ready;下一个 Pod 在上一个 Ready 之后才创建)')
t0 = time.time(); k('scale', 'sts/web', '-n', NS, '--replicas=1'); seen = {}
while time.time() - t0 < 30:
    cur = pods()
    for n in ('web-1', 'web-2'):
        if n not in seen and (n not in cur or cur[n]['metadata'].get('deletionTimestamp')): seen[n] = time.time() - t0
    if len(seen) == 2 and len(cur) == 1: break
    time.sleep(0.1)
print(f'  缩到 1 个副本(Pod 的 terminationGracePeriodSeconds=5,sleep 不处理 SIGTERM,每个要 5 秒才结束):web-2 在 +{seen.get("web-2", 0):.1f}s 开始终止,web-1 在 +{seen.get("web-1", 0):.1f}s 才开始终止(web-2 完全结束之后才轮到 web-1:从大序号往小序号逐个删)')
k('scale', 'sts/web', '-n', NS, '--replicas=3'); until(lambda: len([p for p in pods().values() if ready(p)]) == 3, 60)

print('== 二:稳定的网络身份——名字不变,IP 会变')
k('run', 'client', '-n', NS, '--image=busybox:1.36', '--restart=Never', '--', 'sleep', '3600'); until(lambda: (kj('get', 'pod', 'client', '-n', NS) or {}).get('status', {}).get('phase') == 'Running', 60)
def dns(host):
    rc, o = k('exec', 'client', '-n', NS, '--', 'nslookup', host); L = o.splitlines(); i = next((j for j, l in enumerate(L) if l.startswith('Name:')), 0)
    return ' '.join(l.split()[-1] for l in L[i:] if l.startswith('Address'))
ps = pods(); h = f'web-0.web.{NS}.svc.cluster.local'
print(f'  web-0 的 Pod IP {ps["web-0"]["status"]["podIP"]};hostname={ko("exec", "web-0", "-n", NS, "--", "hostname")};DNS {h} → {dns(h)}')
uid0 = ps['web-0']['metadata']['uid']; k('delete', 'pod', 'web-0', '-n', NS, '--wait=true', timeout=60); until(lambda: ready(pods().get('web-0', {'status': {}})) if pods().get('web-0') else False, 60); time.sleep(2)
ps = pods(); print(f'  删掉 web-0 重建之后:名字仍是 web-0,uid {"变了" if ps["web-0"]["metadata"]["uid"] != uid0 else "没变"},Pod IP {ps["web-0"]["status"]["podIP"]};DNS {h} → {dns(h)}')
print(f'  headless Service 的 DNS 返回所有 Pod:web.{NS}.svc → {dns(f"web.{NS}.svc.cluster.local")}')

print('== 三:稳定的存储——每个 Pod 一个 PVC,Pod 重建后接上原来的')
rc, o = k('get', 'pvc', '-n', NS); print('  ' + o.strip().replace('\n', '\n  ').replace('standard   ', 'standard   '))
print(f'  web-1 写入的文件:{ko("exec", "web-1", "-n", NS, "--", "cat", "/data/who")};往 /data/note 写 hello-1')
k('exec', 'web-1', '-n', NS, '--', 'sh', '-c', 'echo hello-1 > /data/note')
pv_before = ko('get', 'pvc', 'data-web-1', '-n', NS, '-o', 'jsonpath={.spec.volumeName}')
k('delete', 'pod', 'web-1', '-n', NS, '--wait=true', timeout=60); until(lambda: pods().get('web-1') and ready(pods()['web-1']), 60); time.sleep(1)
print(f'  删掉 web-1 重建之后:/data/note={ko("exec", "web-1", "-n", NS, "--", "cat", "/data/note")};PVC 绑定的 PV 没变:{pv_before == ko("get", "pvc", "data-web-1", "-n", NS, "-o", "jsonpath={.spec.volumeName}")}({pv_before[:12]}…)')
k('scale', 'sts/web', '-n', NS, '--replicas=1'); time.sleep(5)
print(f'  缩到 1 个副本之后 PVC:{ko("get", "pvc", "-n", NS, "-o", "name").replace(chr(10), " ")}(data-web-1、data-web-2 没有随 Pod 删除)')
k('scale', 'sts/web', '-n', NS, '--replicas=3'); until(lambda: len([p for p in pods().values() if ready(p)]) == 3, 60)
print(f'  再扩回 3 个:web-1 的 /data/note={ko("exec", "web-1", "-n", NS, "--", "cat", "/data/note")}(旧数据还在)')
k('delete', 'sts', 'web', '-n', NS, '--wait=true', timeout=90); k('delete', 'pvc', '--all', '-n', NS)
k('apply', '-f', '-', input=sts('wd', 2, retention='  persistentVolumeClaimRetentionPolicy: {whenScaled: Delete, whenDeleted: Delete}\n').replace('app: wd', 'app: wd')); until(lambda: len([p for p in pods('wd').values() if ready(p)]) == 2, 90)
k('scale', 'sts/wd', '-n', NS, '--replicas=1'); time.sleep(6)
print(f'  persistentVolumeClaimRetentionPolicy whenScaled: Delete 的 StatefulSet wd 缩到 1 个副本之后 PVC:{ko("get", "pvc", "-n", NS, "-o", "name").replace(chr(10), " ")}(data-wd-1 随 Pod 一起被删了)')
k('delete', 'sts', 'wd', '-n', NS, '--wait=true', timeout=90); time.sleep(4); print(f'  删除 StatefulSet(whenDeleted: Delete)之后 PVC:{ko("get", "pvc", "-n", NS, "-o", "name") or "(没有)"}')

print('== 四:OrderedReady 会被一个不就绪的 Pod 卡住;Parallel 不会')
for nm, pol in (('ord', 'OrderedReady'), ('par', 'Parallel')):
    k('apply', '-f', '-', input=sts(nm, 3, pol, probe='test -f /data/ready'))
time.sleep(18)
for nm, pol in (('ord', 'OrderedReady'), ('par', 'Parallel')):
    ps = pods(nm); print(f'  {nm}(podManagementPolicy={pol}),就绪探针要求 /data/ready 存在(没人去创建):18 秒后已创建的 Pod {sorted(ps)};Ready 的 {sorted(n for n, p in ps.items() if ready(p))}')
k('exec', 'ord-0', '-n', NS, '--', 'touch', '/data/ready'); time.sleep(6); print(f'  只给 ord-0 创建 /data/ready 之后(ord-1 被创建,但它自己没有这个文件):ord 的 Pod {sorted(pods("ord"))}')
rmns(NS)
