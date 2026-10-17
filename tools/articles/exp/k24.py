import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k24')
cn, _ = up('main')
NS = ns('k24')
def pod(name, spec_c, extra=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}, labels: {{app: {name}}}}}\nspec:\n  terminationGracePeriodSeconds: 0\n{extra}  containers:\n  - name: c\n    image: busybox:1.36\n{spec_c}'
def events(name, reasons=None):
    ev = (kj('get', 'events', '-n', NS, '--field-selector', f'involvedObject.name={name}') or {}).get('items', [])
    ev = sorted(ev, key=lambda e: e.get('lastTimestamp') or e.get('eventTime') or '')
    return [(e['reason'], e.get('count', 1), e['message'].strip()[:130]) for e in ev if not reasons or e['reason'] in reasons]
def cstat(name):
    p = kj('get', 'pod', name, '-n', NS) or {}
    cs = (p.get('status', {}).get('containerStatuses') or [{}])[0]
    return p, cs
def ready(p): return any(c['type'] == 'Ready' and c['status'] == 'True' for c in p.get('status', {}).get('conditions', []))
print(f'集群 {cn};三种探针:startup(启动完成之前挡住另外两个)、readiness(决定要不要接收流量)、liveness(决定要不要重启容器);每个探针都由 kubelet 定期执行')

print('== 一:readinessProbe 失败——Pod 变成 NotReady,从 Service 后端里摘掉,但容器不会被重启')
k('apply', '-f', '-', input=pod('rd', '''    command: [sh, -c, "touch /tmp/ok; sleep 3600"]
    readinessProbe: {exec: {command: [cat, /tmp/ok]}, periodSeconds: 2, failureThreshold: 2}
''') + f'---\napiVersion: v1\nkind: Service\nmetadata: {{name: rd, namespace: {NS}}}\nspec: {{selector: {{app: rd}}, ports: [{{port: 80}}]}}\n')
until(lambda: ready(cstat('rd')[0]), 60)
eps = lambda: ko('get', 'endpointslices', '-n', NS, '-l', 'kubernetes.io/service-name=rd', '-o', 'jsonpath={.items[0].endpoints[*].conditions.ready}') or '(无端点)'
print(f'  Pod rd 就绪:Ready={ready(cstat("rd")[0])};EndpointSlice 里端点的 ready 条件={eps()}')
k('exec', 'rd', '-n', NS, '--', 'rm', '/tmp/ok'); t0 = time.time()
v, dt = until(lambda: not ready(cstat('rd')[0]), 30, 0.2)
p, cs = cstat('rd')
print(f'  删掉 /tmp/ok 后 {dt:.1f} 秒 Pod 变成 NotReady(periodSeconds=2,failureThreshold=2);容器 restartCount={cs["restartCount"]}(没有重启);EndpointSlice 里端点 ready={eps()}')
print(f'  事件:{events("rd", ("Unhealthy",))}')
k('exec', 'rd', '-n', NS, '--', 'touch', '/tmp/ok'); v, dt = until(lambda: ready(cstat('rd')[0]), 30, 0.2)
print(f'  恢复 /tmp/ok 后 {dt:.1f} 秒 Pod 重新 Ready,EndpointSlice 里端点 ready={eps()}')

print('== 二:livenessProbe 失败——容器被杀掉并重启')
k('apply', '-f', '-', input=pod('lv', '''    command: [sh, -c, "touch /tmp/ok; sleep 3600"]
    livenessProbe: {exec: {command: [cat, /tmp/ok]}, periodSeconds: 2, failureThreshold: 3}
'''))
until(lambda: ready(cstat('lv')[0]), 60)
p, cs = cstat('lv'); cid0 = cs['containerID'][-12:]
k('exec', 'lv', '-n', NS, '--', 'rm', '/tmp/ok'); t0 = time.time()
v, dt = until(lambda: cstat('lv')[1]['restartCount'] > 0, 40, 0.2)
p, cs = cstat('lv')
print(f'  删掉 /tmp/ok 后 {dt:.1f} 秒容器被重启(periodSeconds=2,failureThreshold=3 → 约 3 次失败 ≈ 6 秒);restartCount={cs["restartCount"]};容器 ID {cid0}… → {cs["containerID"][-12:]}…(是新容器);lastState.terminated.reason={cs["lastState"]["terminated"]["reason"]} exitCode={cs["lastState"]["terminated"]["exitCode"]}')
print(f'  事件:{events("lv", ("Unhealthy", "Killing"))}')
time.sleep(4); print(f'  重启后的新容器里 /tmp/ok 又被命令重新创建,probe 通过:Ready={ready(cstat("lv")[0])}')

print('== 三:startupProbe 没过之前,另外两个探针不执行——给启动慢的程序留时间')
k('apply', '-f', '-', input=pod('slow-start', '''    command: [sh, -c, "sleep 20; touch /tmp/started; touch /tmp/ok; sleep 3600"]
    startupProbe: {exec: {command: [cat, /tmp/started]}, periodSeconds: 2, failureThreshold: 15}
    livenessProbe: {exec: {command: [cat, /tmp/ok]}, periodSeconds: 2, failureThreshold: 1}
'''))
t0 = time.time(); seq = []
while time.time() - t0 < 32:
    p, cs = cstat('slow-start')
    key = (cs.get('started'), cs.get('ready'), cs.get('restartCount'))
    if not seq or seq[-1][1] != key: seq.append((round(time.time() - t0, 1), key))
    time.sleep(0.3)
for t, (st, rd_, rc_) in seq: print(f'  +{t:>4.1f}s containerStatuses[0]:started={st} ready={rd_} restartCount={rc_}')
print(f'  容器启动后 20 秒才创建 /tmp/started(startupProbe 通过);liveness 的 failureThreshold 只有 1,如果它在启动阶段就执行,这个容器早被杀了:最终 restartCount={cstat("slow-start")[1]["restartCount"]}')
print(f'  对照 —— 没有 startupProbe、只有同样的 liveness 的容器:')
k('apply', '-f', '-', input=pod('no-startup', '''    command: [sh, -c, "sleep 20; touch /tmp/ok; sleep 3600"]
    livenessProbe: {exec: {command: [cat, /tmp/ok]}, periodSeconds: 2, failureThreshold: 1}
'''))
time.sleep(26); p, cs = cstat('no-startup'); print(f'    26 秒后 restartCount={cs["restartCount"]};lastState={cs.get("lastState", {}).get("terminated", {}).get("reason")}(liveness 一启动就开始检查,/tmp/ok 还不存在,被反复杀)')

print('== 四:探针的几种类型和判定——httpGet、tcpSocket、exec 的成功标准;initialDelaySeconds 与 timeoutSeconds')
k('apply', '-f', '-', input=pod('http', '''    command: [sh, -c, "mkdir -p /www && echo ok > /www/healthz && httpd -f -p 8080 -h /www"]
    ports: [{containerPort: 8080}]
    readinessProbe: {httpGet: {path: /healthz, port: 8080}, periodSeconds: 1}
    livenessProbe: {tcpSocket: {port: 8080}, periodSeconds: 2}
'''))
until(lambda: ready(cstat('http')[0]), 60); p, cs = cstat('http')
print(f'  httpGet(/healthz 返回 200)+ tcpSocket(8080 端口能连上):Ready={ready(p)} restartCount={cs["restartCount"]}')
k('exec', 'http', '-n', NS, '--', 'rm', '/www/healthz'); v, dt = until(lambda: not ready(cstat('http')[0]), 20, 0.2)
print(f'  删掉 /www/healthz(接口变 404,端口还通):{dt:.1f} 秒后 Ready={ready(cstat("http")[0])};restartCount={cstat("http")[1]["restartCount"]}(tcpSocket 仍通过);最后一个 Unhealthy 事件:{events("http", ("Unhealthy",))[-1:]}')
k('apply', '-f', '-', input=pod('timeout', '''    command: [sh, -c, "touch /tmp/ok; sleep 3600"]
    readinessProbe: {exec: {command: [sh, -c, "sleep 3; cat /tmp/ok"]}, periodSeconds: 2, timeoutSeconds: 1, failureThreshold: 1}
'''))
time.sleep(14); p, cs = cstat('timeout')
print(f'  exec 命令要 3 秒才结束而 timeoutSeconds=1:Ready={ready(p)};事件:{events("timeout", ("Unhealthy",))[:1]}')
rmns(NS)
