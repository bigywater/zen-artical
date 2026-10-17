import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k26')
cn, _ = up('main')
NS = ns('k26')
def status_col(n): 
    l = k('get', 'pod', n, '-n', NS)[1].strip().splitlines()
    return l[-1].split()[2] if len(l) > 1 else '?'
def timeline(n, secs, stop=lambda p: False):
    seq = []; t0 = time.time()
    while time.time() - t0 < secs:
        p = kj('get', 'pod', n, '-n', NS)
        if not p: break
        s = status_col(n)
        if not seq or seq[-1][1] != s: seq.append((round(time.time() - t0, 1), s))
        if stop(p): break
        time.sleep(0.3)
    return seq
def fmt(seq): return ' → '.join(f'{s}(+{t}s)' for t, s in seq)
print(f'集群 {cn};init 容器在应用容器之前按顺序运行,必须全部成功退出,Pod 才会进入 Initialized,应用容器才会启动')

print('== 一:顺序执行——三个 init 容器各睡 2 秒,应用容器要等它们全部结束')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: seq, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  volumes: [{{name: w, emptyDir: {{}}}}]
  initContainers:
  - {{name: i1, image: busybox:1.36, command: [sh, -c, "echo i1 start $(cut -d' ' -f1 /proc/uptime) >> /w/log; sleep 2; echo i1 end $(cut -d' ' -f1 /proc/uptime) >> /w/log"], volumeMounts: [{{name: w, mountPath: /w}}]}}
  - {{name: i2, image: busybox:1.36, command: [sh, -c, "echo i2 start $(cut -d' ' -f1 /proc/uptime) >> /w/log; sleep 2; echo i2 end $(cut -d' ' -f1 /proc/uptime) >> /w/log"], volumeMounts: [{{name: w, mountPath: /w}}]}}
  - {{name: i3, image: busybox:1.36, command: [sh, -c, "echo i3 start $(cut -d' ' -f1 /proc/uptime) >> /w/log; sleep 2; echo i3 end $(cut -d' ' -f1 /proc/uptime) >> /w/log"], volumeMounts: [{{name: w, mountPath: /w}}]}}
  containers:
  - {{name: app, image: busybox:1.36, command: [sh, -c, "echo app start $(cut -d' ' -f1 /proc/uptime) >> /w/log; sleep 3600"], volumeMounts: [{{name: w, mountPath: /w}}]}}
''')
seq = timeline('seq', 40, stop=lambda p: p['status']['phase'] == 'Running' and all(c.get('ready') for c in p['status'].get('containerStatuses', [])))
print(f'  kubectl get pod seq 的 STATUS 变化:{fmt(seq)}')
time.sleep(1)
log = [l.split() for l in ko('exec', 'seq', '-n', NS, '-c', 'app', '--', 'cat', '/w/log').splitlines()]
t0_ = float(log[0][2])
print('  共享卷里的日志(时间是相对第一行的秒数):')
for n_, ev_, t in log: print(f'    {n_:<4} {ev_:<5} +{float(t) - t0_:5.2f}s')
p = kj('get', 'pod', 'seq', '-n', NS)
print(f'  initContainerStatuses:' + '; '.join(f'{c["name"]}={list(c["state"])[0]}(exitCode={c["state"]["terminated"]["exitCode"]})' for c in p['status']['initContainerStatuses']) + f';Initialized={[c["status"] for c in p["status"]["conditions"] if c["type"] == "Initialized"][0]}')

print('== 二:init 容器失败——重试与 restartPolicy')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: retry, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  volumes: [{{name: w, emptyDir: {{}}}}]
  initContainers:
  - name: flaky
    image: busybox:1.36
    command: [sh, -c, "echo run >> /w/runs; n=$(wc -l < /w/runs); echo attempt $n; [ $n -ge 3 ]"]
    volumeMounts: [{{name: w, mountPath: /w}}]
  containers: [{{name: app, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
seq = timeline('retry', 70, stop=lambda p: p['status']['phase'] == 'Running')
p = kj('get', 'pod', 'retry', '-n', NS); ic = p['status']['initContainerStatuses'][0]
print(f'  init 容器前两次 exit 1、第三次成功(用 emptyDir 里的计数文件实现):STATUS 变化:{fmt(seq)}')
print(f'  initContainerStatuses.restartCount={ic["restartCount"]};最终 phase={p["status"]["phase"]};应用容器 app 状态={list(p["status"]["containerStatuses"][0]["state"])[0]}')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: never, namespace: {NS}}}
spec:
  restartPolicy: Never
  initContainers: [{{name: bad, image: busybox:1.36, command: [sh, -c, "exit 1"]}}]
  containers: [{{name: app, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
time.sleep(6); p = kj('get', 'pod', 'never', '-n', NS)
print(f'  restartPolicy=Never 的 Pod,init 容器 exit 1:phase={p["status"]["phase"]};STATUS 列={status_col("never")};应用容器 app 状态={list(p["status"]["containerStatuses"][0]["state"])[0]}(从未启动)')

print('== 三:init 容器的资源请求也算——调度看的是 max(各 init 容器, 全部应用容器之和)')
for n_, ic_, app_ in (('req-app', '10m', '100m'), ('req-init-big', '100', '100m')):
    k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: {n_}, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  initContainers: [{{name: i, image: busybox:1.36, command: [sh, -c, "true"], resources: {{requests: {{cpu: "{ic_}"}}}}}}]
  containers: [{{name: app, image: busybox:1.36, command: [sleep, "3600"], resources: {{requests: {{cpu: "{app_}"}}}}}}]
''')
time.sleep(8)
for n_, d in (('req-app', 'init 10m、应用 100m'), ('req-init-big', 'init 100 核、应用 100m')):
    p = kj('get', 'pod', n_, '-n', NS); c = [c for c in p['status']['conditions'] if c['type'] == 'PodScheduled'][0]
    print(f'  {n_}({d}):phase={p["status"]["phase"]};PodScheduled={c["status"]}' + (f' reason={c.get("reason")};{c.get("message", "")[:95]}' if c['status'] != 'True' else f';nodeName={p["spec"].get("nodeName")}'))
nodes_cpu = ko('get', 'nodes', '-o', 'jsonpath={.items[0].status.allocatable.cpu}'); print(f'  (每个节点 allocatable cpu={nodes_cpu} 核)')

print('== 四:init 容器只在 Pod 启动时运行一次——应用容器崩溃重启不会重新执行它们')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: once, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  volumes: [{{name: w, emptyDir: {{}}}}]
  initContainers: [{{name: setup, image: busybox:1.36, command: [sh, -c, "echo setup-ran >> /w/log"], volumeMounts: [{{name: w, mountPath: /w}}]}}]
  containers: [{{name: app, image: busybox:1.36, command: [sh, -c, "echo app-start >> /w/log; cat /w/log; sleep 2; exit 1"], volumeMounts: [{{name: w, mountPath: /w}}]}}]
''')
time.sleep(28)
p = kj('get', 'pod', 'once', '-n', NS)
rc, o = k('logs', 'once', '-n', NS, '-c', 'app', raw=True)
lines = [l for l in o.splitlines() if l in ('setup-ran', 'app-start')]
print(f'  应用容器 2 秒后 exit 1,28 秒内重启了 {p["status"]["containerStatuses"][0]["restartCount"]} 次;最近一次应用容器 cat 出的共享卷日志里 setup-ran 出现 {lines.count("setup-ran")} 次、app-start 出现 {lines.count("app-start")} 次(每次启动应用容器都追加一行);init 容器 setup 的 restartCount={p["status"]["initContainerStatuses"][0]["restartCount"]}')
rmns(NS)
