import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k101')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k101')
def short(o, n=2, w=300): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def timed(*a, timeout=120):
    t0 = time.time(); rc, o = k(*a, timeout=timeout); return rc, o, time.time() - t0
print(f'集群 {cn};“资源就绪了吗”有几种问法:kubectl wait(等某个条件/字段)、kubectl rollout status(等控制器说它完成了)。它们的“就绪”不是一回事')

print('== 一:kubectl wait 的几种写法')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: slow, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n    readinessProbe: {{exec: {{command: [cat, /tmp/ready]}}, periodSeconds: 1, initialDelaySeconds: 1}}\n')
time.sleep(3)
rc, o, dt = timed('wait', '--for=condition=Ready', 'pod/slow', '-n', NS, '--timeout=5s'); print(f'  --for=condition=Ready(探针一直失败):退出码 {rc};{short(o, 1)};等了 {dt:.1f} 秒')
rc, o, dt = timed('wait', '--for=jsonpath={.status.phase}=Running', 'pod/slow', '-n', NS, '--timeout=5s'); print(f'  --for=jsonpath={{.status.phase}}=Running:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒(phase 已经是 Running,而 Ready 条件还没好)')
k('exec', 'slow', '-n', NS, '--', 'touch', '/tmp/ready'); rc, o, dt = timed('wait', '--for=condition=Ready', 'pod/slow', '-n', NS, '--timeout=10s'); print(f'  让探针通过后再等 Ready:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒')
rc, o, dt = timed('wait', '--for=condition=Ready', 'pod/nothing', '-n', NS, '--timeout=5s'); print(f'  等一个不存在的 pod/nothing:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒(没有等,立刻报错)')
import threading
def late_create(): time.sleep(3); k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: later, namespace: {NS}}}\n')
th = threading.Thread(target=late_create); th.start(); rc, o, dt = timed('wait', '--for=create', 'cm/later', '-n', NS, '--timeout=15s'); th.join(); print(f'  --for=create 等一个 3 秒后才创建的 ConfigMap:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒')
def late_del(): time.sleep(3); k('delete', 'pod', 'slow', '-n', NS, '--wait=false')
th = threading.Thread(target=late_del); th.start(); rc, o, dt = timed('wait', '--for=delete', 'pod/slow', '-n', NS, '--timeout=30s'); th.join(); print(f'  --for=delete 等 pod/slow 被删掉:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒')

print('== 二:rollout status 与 Deployment 的 Available')
DEP = lambda image, v: f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: web, namespace: {NS}}}
spec:
  replicas: 3
  progressDeadlineSeconds: 20
  strategy: {{type: RollingUpdate, rollingUpdate: {{maxSurge: 1, maxUnavailable: 0}}}}
  selector: {{matchLabels: {{app: web}}}}
  template:
    metadata: {{labels: {{app: web}}, annotations: {{v: "{v}"}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: {image}
        command: [sleep, "3600"]
        readinessProbe: {{exec: {{command: [sh, -c, "sleep 0; test -f /tmp/r || (sleep 4; touch /tmp/r)"]}}, periodSeconds: 5, initialDelaySeconds: 1, timeoutSeconds: 10}}
'''
k('apply', '-f', '-', input=DEP('busybox:1.36', '1')); rc, o, dt = timed('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); print(f'  首次创建 3 副本:rollout status 退出码 {rc},用时 {dt:.0f} 秒;输出:'); [print('    ' + l[:130]) for l in o.strip().splitlines()]
k('apply', '-f', '-', input=DEP('busybox:1.36', '2'))
res = {}
def w_avail():
    t0 = time.time(); rc, o = k('wait', '--for=condition=Available', 'deploy/web', '-n', NS, '--timeout=60s'); res['avail'] = (rc, time.time() - t0)
th = threading.Thread(target=w_avail); th.start(); t0 = time.time()
rc, o, dt = timed('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s'); th.join()
print(f'  改模板触发滚动更新(maxSurge 1 / maxUnavailable 0,新 Pod 要约 5 秒才就绪):')
print(f'    kubectl wait --for=condition=Available 在 {res["avail"][1]:.1f} 秒就返回了(退出码 {res["avail"][0]}),因为更新过程中 Available 一直是 True(旧 Pod 还在服务)')
print(f'    kubectl rollout status 等到 {dt:.1f} 秒才结束(退出码 {rc}),输出:'); [print('      ' + l[:130]) for l in o.strip().splitlines()]
rc, o, dt = timed('wait', '--for=condition=Progressing', 'deploy/web', '-n', NS, '--timeout=5s'); dep = kj('get', 'deploy', 'web', '-n', NS); print(f'  Progressing 条件:{[(c["type"], c["status"], c["reason"]) for c in dep["status"]["conditions"]]}')

print('== 三:rollout 卡住时——progressDeadlineSeconds')
k('apply', '-f', '-', input=DEP('localhost:5999/nosuchimage:1.0', '3')); rc, o, dt = timed('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=90s')
print(f'  把镜像改成拉不到的(progressDeadlineSeconds: 20):rollout status 用时 {dt:.0f} 秒,退出码 {rc}')
for l in short(o, 6, 150): print('    ' + l)
dep = kj('get', 'deploy', 'web', '-n', NS); print(f'  Deployment 条件:{[(c["type"], c["status"], c["reason"]) for c in dep["status"]["conditions"]]};旧副本仍在服务(availableReplicas={dep["status"].get("availableReplicas")}、readyReplicas={dep["status"].get("readyReplicas")})')
rc, o, dt = timed('rollout', 'undo', 'deploy/web', '-n', NS); rc2, o2, dt2 = timed('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=60s'); print(f'  rollout undo 后再 status:{short(o2, 1)};退出码 {rc2}')

print('== 四:Job 的完成与失败')
k('apply', '-f', '-', input=f'apiVersion: batch/v1\nkind: Job\nmetadata: {{name: ok, namespace: {NS}}}\nspec:\n  template:\n    spec:\n      restartPolicy: Never\n      containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "sleep 2"]}}]\n---\napiVersion: batch/v1\nkind: Job\nmetadata: {{name: bad, namespace: {NS}}}\nspec:\n  backoffLimit: 0\n  template:\n    spec:\n      restartPolicy: Never\n      containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "exit 1"]}}]\n')
rc, o, dt = timed('wait', '--for=condition=complete', 'job/ok', '-n', NS, '--timeout=30s'); print(f'  --for=condition=complete job/ok:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒')
rc, o, dt = timed('wait', '--for=condition=complete', 'job/bad', '-n', NS, '--timeout=10s'); print(f'  --for=condition=complete job/bad(这个 Job 会失败):退出码 {rc};{short(o, 1)};等满 {dt:.1f} 秒才超时——失败的 Job 永远不会 Complete')
rc, o, dt = timed('wait', '--for=condition=failed', 'job/bad', '-n', NS, '--timeout=10s'); print(f'  --for=condition=failed job/bad:退出码 {rc};{short(o, 1)};用时 {dt:.1f} 秒')
k('delete', 'ns', NS, '--wait=false')
