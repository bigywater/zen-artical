import sys, os, re, time, json, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k28')
cn, _ = up('main')
NS = ns('k28')
LOG = "read u _ < /proc/uptime; echo %s $u >> /w/log"
def L(ev): return LOG % ev
def podyaml(name, grace, prestop, extra_term='sleep 1'):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}, labels: {{app: {name}}}}}
spec:
  terminationGracePeriodSeconds: {grace}
  volumes: [{{name: w, hostPath: {{path: /tmp/k28-{name}, type: DirectoryOrCreate}}}}]
  containers:
  - name: app
    image: busybox:1.36
    command: [sh, -c, "trap '{L('sigterm')}; {extra_term}; {L('exit')}; exit 0' TERM; {L('start')}; while true; do sleep 1; done"]
    volumeMounts: [{{name: w, mountPath: /w}}]
    lifecycle:
      preStop:
        exec: {{command: [sh, -c, "{prestop}"]}}
---
apiVersion: v1
kind: Service
metadata: {{name: {name}, namespace: {NS}}}
spec: {{selector: {{app: {name}}}, ports: [{{port: 80}}]}}
'''
def uptime(node):
    rc, o = nx(node, "cut -d' ' -f1 /proc/uptime"); return float(o.split()[0])
def run_case(name, grace, prestop, extra_term='sleep 1', events=True):
    k('apply', '-f', '-', input=podyaml(name, grace, prestop, extra_term))
    until(lambda: (kj('get', 'pod', name, '-n', NS) or {}).get('status', {}).get('phase') == 'Running', 60); time.sleep(2)
    node = ko('get', 'pod', name, '-n', NS, '-o', 'jsonpath={.spec.nodeName}')
    eps = []; stop = threading.Event(); t0h = [None]
    def watch():
        last = None
        while not stop.is_set():
            j = kj('get', 'endpointslices', '-n', NS, '-l', f'kubernetes.io/service-name={name}')
            e = [(x['conditions'].get('ready'), x['conditions'].get('serving'), x['conditions'].get('terminating')) for it in (j or {}).get('items', []) for x in (it.get('endpoints') or [])]
            cur = tuple(e)
            if cur != last: eps.append((time.time(), cur)); last = cur
            time.sleep(0.05)
    th = threading.Thread(target=watch); th.start(); time.sleep(0.6)
    u0 = uptime(node); t_call = time.time()
    k('delete', 'pod', name, '-n', NS, '--wait=true', timeout=90); t_gone = time.time()
    stop.set(); th.join()
    rc, o = nx(node, f'cat /tmp/k28-{name}/log; rm -rf /tmp/k28-{name}')
    rows = [l.split() for l in o.splitlines() if l.strip()]
    ev = (kj('get', 'events', '-n', NS, '--field-selector', f'involvedObject.name={name}') or {}).get('items', []) if events else []
    return u0, t_call, t_gone, rows, eps, ev
def show(label, u0, t_call, t_gone, rows, eps, ev):
    print(f'  {label}:kubectl delete 从发出到 Pod 消失用了 {t_gone - t_call:.1f} 秒')
    for e_, t in rows: print(f'    容器日志 {e_:<9} T0{float(t) - u0:+6.2f}s')
    for t, cur in eps: print(f'    EndpointSlice 里端点的 (ready, serving, terminating) = {cur or "(没有端点)"}  T0{t - t_call:+6.2f}s')
    for e in ev:
        if e['reason'] in ('Killing', 'FailedPreStopHook', 'FailedKillPod'): print(f'    事件 {e["reason"]}:{e["message"].strip()[:130]}')
print(f'集群 {cn};删除 Pod 时 kubelet 的动作:设置 deletionTimestamp → 执行 preStop 钩子 → 发 SIGTERM → 等到宽限期结束 → SIGKILL;同时端点控制器把 Pod 从 Service 后端摘掉')
print('  时间轴的 T0 = 发出 kubectl delete 的时刻(容器日志用节点 /proc/uptime 对齐,端点变化用宿主机时钟,各有几十毫秒误差)')

print('== 一:preStop 睡 5 秒——SIGTERM 要等钩子结束')
r = run_case('pre5', 30, 'read u _ < /proc/uptime; echo prestop-start $u >> /w/log; sleep 5; read u _ < /proc/uptime; echo prestop-end $u >> /w/log'); show('preStop 睡 5 秒、应用收到 SIGTERM 后再睡 1 秒才退出', *r)

print('== 二:没有 preStop 的对照——SIGTERM 立刻到')
r = run_case('nopre', 30, 'true'); show('preStop 是个空命令(true)', *r)

print('== 三:preStop 比宽限期还长——钩子被截断,SIGKILL 准时到')
r = run_case('long', 6, 'read u _ < /proc/uptime; echo prestop-start $u >> /w/log; sleep 10; read u _ < /proc/uptime; echo prestop-end $u >> /w/log', extra_term='sleep 5'); show('terminationGracePeriodSeconds=6,preStop 睡 10 秒,应用收到 SIGTERM 后要 5 秒才肯退出', *r)

print('== 四:preStop 自己失败了——终止流程不受影响')
r = run_case('failhook', 30, 'read u _ < /proc/uptime; echo prestop-fail $u >> /w/log; exit 1'); show('preStop 执行 exit 1', *r)
rmns(NS)
