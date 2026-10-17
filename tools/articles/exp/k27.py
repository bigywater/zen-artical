import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k27')
cn, _ = up('main')
NS = ns('k27')
UP = "$(cut -d' ' -f1 /proc/uptime)"
def stcol(n):
    l = k('get', 'pod', n, '-n', NS)[1].strip().splitlines(); return l[-1].split()[2] if len(l) > 1 else '?'
def tl(n, secs, stop=lambda p: False):
    seq = []; t0 = time.time()
    while time.time() - t0 < secs:
        p = kj('get', 'pod', n, '-n', NS)
        if not p: break
        s = stcol(n)
        if not seq or seq[-1][1] != s: seq.append((round(time.time() - t0, 1), s))
        if stop(p): break
        time.sleep(0.3)
    return seq
fmt = lambda seq: ' → '.join(f'{s}(+{t}s)' for t, s in seq)
print(f'集群 {cn};原生 sidecar = initContainers 里 restartPolicy: Always 的容器:先于应用容器启动,和应用容器一起运行,最后被终止')

print('== 一:启动顺序——sidecar 启动后后面的容器才继续,但它不需要“退出”')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: order, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 1
  volumes: [{{name: w, emptyDir: {{}}}}]
  initContainers:
  - {{name: setup, image: busybox:1.36, command: [sh, -c, "echo setup-start {UP} >> /w/log; sleep 2; echo setup-end {UP} >> /w/log"], volumeMounts: [{{name: w, mountPath: /w}}]}}
  - name: side
    image: busybox:1.36
    restartPolicy: Always
    command: [sh, -c, "echo side-start {UP} >> /w/log; sleep 3600"]
    startupProbe: {{exec: {{command: [sh, -c, "sleep 1; true"]}}, periodSeconds: 1, timeoutSeconds: 5}}
    volumeMounts: [{{name: w, mountPath: /w}}]
  containers:
  - {{name: app, image: busybox:1.36, command: [sh, -c, "echo app-start {UP} >> /w/log; sleep 3600"], volumeMounts: [{{name: w, mountPath: /w}}]}}
''')
seq = tl('order', 40, stop=lambda p: p['status']['phase'] == 'Running' and all(c.get('ready') for c in p['status'].get('containerStatuses', [])))
print(f'  STATUS 变化:{fmt(seq)}')
time.sleep(1.5)
log = [l.split() for l in ko('exec', 'order', '-n', NS, '-c', 'app', '--', 'cat', '/w/log').splitlines()]; t0_ = float(log[0][1])
for ev_, t in log: print(f'    {ev_:<12} +{float(t) - t0_:5.2f}s')
p = kj('get', 'pod', 'order', '-n', NS)
print(f'  initContainerStatuses:' + '; '.join(f'{c["name"]}={list(c["state"])[0]}' for c in p['status']['initContainerStatuses']) + f';containerStatuses:app={list(p["status"]["containerStatuses"][0]["state"])[0]};Initialized={[c["status"] for c in p["status"]["conditions"] if c["type"] == "Initialized"][0]}')
print(f'  sidecar 是 init 容器,但它在 Pod 运行期间一直 running(普通 init 容器必须 exit 0 才算完成)')

print('== 二:Job 里的 sidecar——应用容器结束后 Job 能不能完成')
for n_, spec in (('native', '''      initContainers:
      - {name: side, image: busybox:1.36, restartPolicy: Always, command: [sleep, "3600"]}
      containers:
      - {name: main, image: busybox:1.36, command: [sh, -c, "sleep 3; echo done"]}'''), ('classic', '''      containers:
      - {name: main, image: busybox:1.36, command: [sh, -c, "sleep 3; echo done"]}
      - {name: side, image: busybox:1.36, command: [sleep, "3600"]}''')):
    k('apply', '-f', '-', input=f'''apiVersion: batch/v1
kind: Job
metadata: {{name: {n_}, namespace: {NS}}}
spec:
  template:
    spec:
      restartPolicy: Never
      terminationGracePeriodSeconds: 1
{spec}
''')
time.sleep(25)
for n_, d in (('native', 'sidecar 写在 initContainers 里(restartPolicy: Always)'), ('classic', 'sidecar 写在 containers 里')):
    j = kj('get', 'job', n_, '-n', NS); p = kj('get', 'pods', '-n', NS, '-l', f'job-name={n_}')['items'][0]
    print(f'  Job {n_}({d}):25 秒后 Job 状态 {[c["type"] for c in j["status"].get("conditions", [])] or "(未完成)"};succeeded={j["status"].get("succeeded", 0)};Pod phase={p["status"]["phase"]};kubectl get STATUS={k("get", "pod", p["metadata"]["name"], "-n", NS)[1].strip().splitlines()[-1].split()[2]}')

print('== 三:终止顺序——Pod 删除时应用容器先收到 SIGTERM,等它退出后才轮到 sidecar')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: term, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 20
  volumes: [{{name: w, hostPath: {{path: /tmp/k27-term, type: DirectoryOrCreate}}}}]
  initContainers:
  - name: side
    image: busybox:1.36
    restartPolicy: Always
    command: [sh, -c, "trap 'read u _ < /proc/uptime; echo side-sigterm $u >> /w/log; sleep 1; read u _ < /proc/uptime; echo side-exit $u >> /w/log; exit 0' TERM; rm -f /w/log; read u _ < /proc/uptime; echo side-start $u >> /w/log; while true; do sleep 1; done"]
    volumeMounts: [{{name: w, mountPath: /w}}]
  containers:
  - name: app
    image: busybox:1.36
    command: [sh, -c, "trap 'read u _ < /proc/uptime; echo app-sigterm $u >> /w/log; sleep 3; read u _ < /proc/uptime; echo app-exit $u >> /w/log; exit 0' TERM; read u _ < /proc/uptime; echo app-start $u >> /w/log; while true; do sleep 1; done"]
    volumeMounts: [{{name: w, mountPath: /w}}]
''')
until(lambda: kj('get', 'pod', 'term', '-n', NS)['status']['phase'] == 'Running' and all(c.get('ready') for c in kj('get', 'pod', 'term', '-n', NS)['status'].get('containerStatuses', [])), 60); time.sleep(2)
node = ko('get', 'pod', 'term', '-n', NS, '-o', 'jsonpath={.spec.nodeName}')
k('delete', 'pod', 'term', '-n', NS, '--wait=true', timeout=60)
rc, o = nx(node, 'cat /tmp/k27-term/log'); nx(node, 'rm -rf /tmp/k27-term')
rows = [l.split() for l in o.splitlines() if l.strip()]; t0_ = float(rows[0][1])
print('  日志(hostPath 卷,Pod 删掉后从节点上读;时间相对第一行):')
for ev_, t in rows: print(f'    {ev_:<13} +{float(t) - t0_:6.2f}s')
tt = {ev_: float(t) for ev_, t in rows}
print(f'  app 收到 SIGTERM 与 sidecar 收到 SIGTERM 相差 {tt["side-sigterm"] - tt["app-sigterm"]:.2f} 秒;app 退出后 {tt["side-sigterm"] - tt["app-exit"]:.2f} 秒 sidecar 才收到 SIGTERM')

print('== 四:sidecar 的探针会影响 Pod 就绪;sidecar 崩溃只重启自己')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: probe, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 1
  initContainers:
  - name: side
    image: busybox:1.36
    restartPolicy: Always
    command: [sh, -c, "sleep 3600"]
    readinessProbe: {{exec: {{command: [cat, /tmp/ready]}}, periodSeconds: 1}}
  containers: [{{name: app, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
time.sleep(8); p = kj('get', 'pod', 'probe', '-n', NS)
cc = {c['type']: c['status'] for c in p['status']['conditions']}
print(f'  sidecar 的 readinessProbe 一直失败(/tmp/ready 不存在),应用容器本身没有探针:Initialized={cc["Initialized"]} ContainersReady={cc["ContainersReady"]} Ready={cc["Ready"]};app 容器 ready={p["status"]["containerStatuses"][0]["ready"]};sidecar ready={p["status"]["initContainerStatuses"][0].get("ready")}')
k('exec', 'probe', '-n', NS, '-c', 'side', '--', 'touch', '/tmp/ready'); v, dt = until(lambda: [c for c in kj('get', 'pod', 'probe', '-n', NS)['status']['conditions'] if c['type'] == 'Ready'][0]['status'] == 'True', 20, 0.3)
print(f'  在 sidecar 里创建 /tmp/ready 之后 {dt:.1f} 秒 Pod Ready=True')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: crashy, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 1
  initContainers:
  - {{name: side, image: busybox:1.36, restartPolicy: Always, command: [sh, -c, "sleep 3; exit 1"]}}
  containers: [{{name: app, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
time.sleep(25); p = kj('get', 'pod', 'crashy', '-n', NS)
print(f'  sidecar 每 3 秒崩溃一次:25 秒后 sidecar restartCount={p["status"]["initContainerStatuses"][0]["restartCount"]};app 容器 restartCount={p["status"]["containerStatuses"][0]["restartCount"]} state={list(p["status"]["containerStatuses"][0]["state"])[0]};Pod phase={p["status"]["phase"]}')
rmns(NS)
