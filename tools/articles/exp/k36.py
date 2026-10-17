import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k36')
cn, _ = up('main')
NS = ns('k36')
for n in ('k36-low', 'k36-mid', 'k36-high', 'k36-high-never'): k('delete', 'priorityclass', n, '--ignore-not-found')
k('apply', '-f', '-', input='''apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: k36-low}
value: 100
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: k36-mid}
value: 500
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: k36-high}
value: 1000
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: k36-high-never}
value: 1000
preemptionPolicy: Never
''')
def pod(name, prio, cpu='4', node=None, grace=0):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n{("  priorityClassName: " + prio + chr(10)) if prio else ""}{("  nodeName: " + node + chr(10)) if node else ""}  terminationGracePeriodSeconds: {grace}\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n    resources: {{requests: {{cpu: "{cpu}"}}}}\n'
def pods():
    return {p['metadata']['name']: p for p in kj('get', 'pods', '-n', NS)['items']}
def wait_running(*names, t=60): until(lambda: all(pods().get(n, {}).get('status', {}).get('phase') == 'Running' for n in names), t)
W1, W2 = 'kx-main-worker', 'kx-main-worker2'
print(f'集群 {cn};两个 worker 各 10 核(allocatable cpu={ko("get", "node", W1, "-o", "jsonpath={.status.allocatable.cpu}")}),用 requests.cpu=4 的 busybox Pod(不真的耗 CPU)把它们占满')

print('== 一:优先级是个整数——PriorityClass 在准入时被解析成 pod.spec.priority')
rc, o = k('get', 'priorityclass', '-o', 'custom-columns=NAME:.metadata.name,VALUE:.value,GLOBAL-DEFAULT:.globalDefault,PREEMPTION:.preemptionPolicy')
for l in o.strip().splitlines(): print('  ' + l)
k('apply', '-f', '-', input=pod('p-none', None, '10m')); k('apply', '-f', '-', input=pod('p-high', 'k36-high', '10m'))
for n in ('p-none', 'p-high'):
    p = pods()[n]; print(f'  Pod {n}:priorityClassName={p["spec"].get("priorityClassName")} → spec.priority={p["spec"]["priority"]};preemptionPolicy={p["spec"].get("preemptionPolicy")}')
rc, o = k('apply', '-f', '-', input=pod('p-bad', 'no-such-class', '10m')); print(f'  priorityClassName 写了不存在的类:退出码 {rc};{re.sub(r"^.*Forbidden: ", "", o.strip())[:150]}')
k('delete', 'pod', 'p-none', 'p-high', '-n', NS, '--wait=true', timeout=60)

print('== 二:抢占的时间线——节点装满了低优先级 Pod,高优先级 Pod 来了')
for i, n in enumerate(('low1', 'low2', 'low3', 'low4')): k('apply', '-f', '-', input=pod(n, 'k36-low', grace=12))
wait_running('low1', 'low2', 'low3', 'low4')
ps = pods(); print('  4 个 low Pod(requests.cpu=4,优先级 100,terminationGracePeriodSeconds=12)分布:' + ', '.join(f'{n}→{p["spec"]["nodeName"].replace("kx-main-", "")}' for n, p in sorted(ps.items())))
k('apply', '-f', '-', input=pod('hi', 'k36-high'))
t0 = time.time(); seen = {}; log = []
while time.time() - t0 < 40:
    ps = pods()
    for n, p in ps.items():
        st = (p['status'].get('phase'), p['status'].get('nominatedNodeName'), bool(p['metadata'].get('deletionTimestamp')))
        if seen.get(n) != st: seen[n] = st; log.append((time.time() - t0, n, st))
    if ps.get('hi', {}).get('status', {}).get('phase') == 'Running': break
    time.sleep(0.3)
for t, n, (ph, nom, dele) in log:
    if n == 'hi' or dele or nom: print(f'    +{t:5.1f}s {n:<5} phase={ph}' + (f' nominatedNodeName={nom.replace("kx-main-", "")}' if nom else '') + (' 正在被删除(deletionTimestamp 已设置)' if dele else ''))
ev = [e for e in kj('get', 'events', '-n', NS)['items'] if e['reason'] in ('Preempted', 'FailedScheduling', 'Scheduled', 'Killing') and e['involvedObject']['name'] in ('hi', 'low1', 'low2', 'low3', 'low4')]
for e in sorted(ev, key=lambda e: e.get('lastTimestamp') or e.get('eventTime') or ''): print(f'    事件 {e["involvedObject"]["name"]:<5} {e["reason"]:<17} {e["message"][:140]}')
ps = pods(); victims = sorted({e['involvedObject']['name'] for e in ev if e['reason'] == 'Preempted'})
print(f'  最终:hi 在 {ps["hi"]["spec"]["nodeName"].replace("kx-main-", "")} 上 phase={ps["hi"]["status"]["phase"]};被抢占的 low Pod(取自 Preempted 事件):{victims};hi 用了 {log[-1][0]:.1f} 秒才 Running(受害者的宽限期是 12 秒)')
for v in victims:
    pv = ps.get(v)
    if pv: print(f'  受害者 {v} 的状态:phase={pv["status"]["phase"]};conditions={[ (c["type"], c["status"], c.get("reason")) for c in pv["status"].get("conditions", []) if c["type"] == "DisruptionTarget"]};message={[c.get("message") for c in pv["status"].get("conditions", []) if c["type"] == "DisruptionTarget"]}')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=90)

print('== 三:选谁当受害者——让 worker 上是 low,worker2 上是 mid')
for n, pr, nd in (('a-low1', 'k36-low', W1), ('a-low2', 'k36-low', W1), ('b-mid1', 'k36-mid', W2), ('b-mid2', 'k36-mid', W2)): k('apply', '-f', '-', input=pod(n, pr, node=nd))
wait_running('a-low1', 'a-low2', 'b-mid1', 'b-mid2')
k('apply', '-f', '-', input=pod('hi', 'k36-high'))
until(lambda: pods().get('hi', {}).get('status', {}).get('phase') == 'Running', 60)
ps = pods()
print(f'  worker 上:a-low1、a-low2(优先级 100);worker2 上:b-mid1、b-mid2(优先级 500);hi(优先级 1000,requests.cpu=4)要么抢占 worker 上的一个 100,要么抢占 worker2 上的一个 500')
print(f'  结果:hi 在 {ps["hi"]["spec"]["nodeName"].replace("kx-main-", "")};被抢占的(从 Pod 列表里消失或状态为 Failed):{[n for n in ("a-low1", "a-low2", "b-mid1", "b-mid2") if n not in ps or ps[n]["status"]["phase"] == "Failed"]};仍在 Running 的:{sorted(n for n in ps if n != "hi" and ps[n]["status"]["phase"] == "Running")}')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=90)

print('== 四:preemptionPolicy: Never——优先级高,但不抢别人')
for i, n in enumerate(('low1', 'low2', 'low3', 'low4')): k('apply', '-f', '-', input=pod(n, 'k36-low'))
wait_running('low1', 'low2', 'low3', 'low4')
k('apply', '-f', '-', input=pod('hi-never', 'k36-high-never')); time.sleep(8)
p = pods()['hi-never']; c = [x for x in p['status']['conditions'] if x['type'] == 'PodScheduled'][0]
print(f'  hi-never(priority={p["spec"]["priority"]},preemptionPolicy={p["spec"]["preemptionPolicy"]}):phase={p["status"]["phase"]};PodScheduled={c["status"]} reason={c.get("reason")};nominatedNodeName={p["status"].get("nominatedNodeName")}')
print(f'    message={c.get("message", "")[:200]}')
print(f'  4 个 low Pod 都还在:{sorted(n for n in pods() if n.startswith("low"))}')
k('delete', 'pod', 'low1', '-n', NS, '--wait=true', timeout=60); until(lambda: pods().get('hi-never', {}).get('status', {}).get('phase') == 'Running', 30)
print(f'  手动删掉 low1 之后:hi-never phase={pods()["hi-never"]["status"]["phase"]}(优先级让它先于别的 Pending Pod 被调度,但没有抢占)')
for n in ('k36-low', 'k36-mid', 'k36-high', 'k36-high-never'): k('delete', 'priorityclass', n)
rmns(NS)
