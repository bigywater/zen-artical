import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k50')
cn, _ = up('main')
dt_ms = install_metrics_server()
NS = ns('k50')
def dep(name, replicas, cpu_req='100m', cpu_lim='200m', res=True):
    r = f'        resources: {{requests: {{cpu: {cpu_req}}}, limits: {{cpu: {cpu_lim}}}}}\n' if res else ''
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: {replicas}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: busybox:1.36
        command: [sh, -c, "while :; do if [ -f /tmp/stop ]; then sleep 1; fi; done"]
{r}'''
def hpa(name, target=50, mn=1, mx=6, behavior=''):
    return f'''apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {{name: {name}, namespace: {NS}}}
spec:
  scaleTargetRef: {{apiVersion: apps/v1, kind: Deployment, name: {name}}}
  minReplicas: {mn}
  maxReplicas: {mx}
  metrics: [{{type: Resource, resource: {{name: cpu, target: {{type: Utilization, averageUtilization: {target}}}}}}}]
{behavior}'''
def hst(name):
    j = kj('get', 'hpa', name, '-n', NS); s = j['status']
    cm = s.get('currentMetrics') or []; u = (cm[0].get('resource', {}).get('current', {}).get('averageUtilization')) if cm else None
    return (s.get('currentReplicas'), s.get('desiredReplicas'), u)
def series(name, secs, stop=None, every=3):
    t0 = time.time(); out = []; last = None
    while time.time() - t0 < secs:
        cur = hst(name)
        if cur != last: out.append((round(time.time() - t0), cur)); last = cur
        if stop and stop(cur): break
        time.sleep(every)
    return out
def fmt(sr): return ' → '.join(f'(副本 {c[0]}→{c[1]}, 利用率 {c[2]}%)@{t}s' for t, c in sr)
def events(name):
    ev = [e for e in kj('get', 'events', '-n', NS, '--field-selector', f'involvedObject.name={name}')['items']]
    return sorted(ev, key=lambda e: e.get('firstTimestamp') or e.get('eventTime') or '')
print(f'集群 {cn};HPA(v2)每 15 秒从 metrics API 读一次 Pod 的 CPU 用量,按 desired = ceil(当前副本数 × 当前值 ÷ 目标值) 算期望副本数(metrics-server {MS_IMAGE.split(":")[1]},{dt_ms:.0f} 秒后有数据)')
print('  测试负载:busybox 里的死循环,limits.cpu=200m、requests.cpu=100m——每个 Pod 总是用满 limit,即 CPU 利用率(占 requests 的百分比)恒为 200% 左右')

print('== 一:扩容——利用率 200% 对目标 50%,一步步到最大副本数')
k('apply', '-f', '-', input=dep('app', 1)); until(lambda: kj('get', 'deploy', 'app', '-n', NS)['status'].get('readyReplicas') == 1, 60)
beh = '  behavior:\n    scaleDown: {stabilizationWindowSeconds: 30}\n'
t_hpa = time.time(); k('apply', '-f', '-', input=hpa('app', 50, 1, 6, beh))
sr = series('app', 110, stop=lambda c: c[0] == 6 and c[2] is not None and time.time() - t_hpa > 20)
print(f'  HPA app(目标利用率 50%,min 1、max 6)创建后,(当前副本→期望副本,利用率)的变化:{fmt(sr)}')
for e in events('app'):
    if e['reason'] == 'SuccessfulRescale': print(f'    事件 SuccessfulRescale:{e["message"]}')
u1 = next((c[2] for t, c in sr if c[2]), 200); first = next((c[1] for t, c in sr if c[1] and c[1] > 1), None)
import math
print(f'  算式:第一次决定:当前 1 个副本、利用率 {u1}%、目标 50% → ceil(1 × {u1} ÷ 50) = ceil({u1 / 50:.2f}) = {math.ceil(u1 / 50)}(实测期望副本 {first});第二次:当前 {first} 个、利用率仍是 {u1}% → ceil({first} × {u1} ÷ 50) = {math.ceil(first * u1 / 50)},超过 maxReplicas=6,所以只到 6')

print('== 二:缩容——负载没了以后,要等稳定窗口(这里设成 30 秒)才会缩')
pods = [p['metadata']['name'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=app')['items']]
t_stop = time.time()
for p in pods: k('exec', p, '-n', NS, '--', 'touch', '/tmp/stop')
sr = series('app', 150, stop=lambda c: c[0] == 1 and time.time() - t_stop > 20)
print(f'  给所有 Pod 创建 /tmp/stop(死循环改成 sleep,CPU 降到接近 0)之后,(当前副本→期望副本,利用率)的变化:{fmt(sr)}')
for e in events('app'):
    if e['reason'] == 'SuccessfulRescale' and 'below' in e['message']: print(f'    事件 SuccessfulRescale:{e["message"]}')
print(f'  从负载消失到缩到 1 个副本用了约 {sr[-1][0]} 秒(指标采集周期 15 秒 + HPA 同步周期 15 秒 + 稳定窗口 30 秒)')
k('delete', 'hpa', 'app', '-n', NS); k('delete', 'deploy', 'app', '-n', NS, '--wait=true', timeout=60)

print('== 三:容忍区——比目标高 4% 不动,高 40% 就扩(用 Python 占空比负载精确控制利用率)')
def duty(name, replicas, d):
    code = f'import time\nb = {d}\nwhile True:\n    t = time.perf_counter()\n    while time.perf_counter() - t < b * 0.1: pass\n    time.sleep(0.1 - b * 0.1)'
    cmd = json.dumps(['python', '-c', code])
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: {replicas}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: python:3.12-alpine
        imagePullPolicy: IfNotPresent
        command: {cmd}
        resources: {{requests: {{cpu: 100m}}}}
'''
for nm, d in (('tol-in', 0.052), ('tol-out', 0.07)):
    y = duty(nm, 2, d); k('apply', '-f', '-', input=y)
    until(lambda: kj('get', 'deploy', nm, '-n', NS)['status'].get('readyReplicas') == 2, 90)
    k('apply', '-f', '-', input=hpa(nm, 50, 1, 5))
time.sleep(100)
for nm, d_ in (('tol-in', '利用率约 52%,比目标 50% 高 4%(比值 1.04,在默认 ±10% 的容忍区内)'), ('tol-out', '利用率约 70%,比目标高 40%(比值 1.4)')):
    cur = hst(nm); print(f'  {nm}({d_}):100 秒后 当前副本 {cur[0]} 期望 {cur[1]} 利用率 {cur[2]}%;SuccessfulRescale 事件:{[e["message"][:90] for e in events(nm) if e["reason"] == "SuccessfulRescale"] or "(没有)"}')
k('delete', 'hpa', 'tol-in', 'tol-out', '-n', NS); k('delete', 'deploy', 'tol-in', 'tol-out', '-n', NS, '--wait=true', timeout=60)

print('== 四:没写 requests——“占 requests 的百分比”算不出来')
k('apply', '-f', '-', input=dep('noreq', 1, res=False)); until(lambda: kj('get', 'deploy', 'noreq', '-n', NS)['status'].get('readyReplicas') == 1, 60)
k('apply', '-f', '-', input=hpa('noreq', 50, 1, 4)); until(lambda: 'missing request' in json.dumps(kj('get', 'hpa', 'noreq', '-n', NS)['status'].get('conditions', [])), 90, 3)
j = kj('get', 'hpa', 'noreq', '-n', NS); conds = {c['type']: (c['status'], c.get('reason'), c.get('message', '')[:160]) for c in j['status'].get('conditions', [])}
print(f'  Deployment 没有 requests.cpu:HPA conditions:{json.dumps(conds, ensure_ascii=False)}')
print(f'  kubectl get hpa:{k("get", "hpa", "noreq", "-n", NS)[1].strip().splitlines()[-1]}')
rmns(NS)
