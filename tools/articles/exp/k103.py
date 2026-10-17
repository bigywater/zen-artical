import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k103')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k103')
W = 'kx-main-worker'
def short(o, n=2, w=320): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
k('apply', '-f', '-', input='''apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata: {name: runc-heavy}
handler: runc
overhead:
  podFixed: {cpu: 250m, memory: 120Mi}
---
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata: {name: no-such-handler}
handler: gvisor-not-installed
''')
def pod(name, rc=None, res='requests: {cpu: 100m, memory: 64Mi}, limits: {cpu: 100m, memory: 64Mi}', node=W, ns_=NS):
    r = f'  runtimeClassName: {rc}\n' if rc else ''
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {ns_}}}\nspec:\n  nodeName: {node}\n  terminationGracePeriodSeconds: 0\n{r}  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n    resources: {{{res}}}\n'
def alloc(n=W):
    rc, o = k('describe', 'node', n); sec = o[o.index('Allocated resources'):]; return {l.split()[0]: (l.split()[1], l.split()[3]) for l in sec.splitlines() if l.strip() and l.split()[0] in ('cpu', 'memory') and len(l.split()) >= 4}
print(f'集群 {cn};RuntimeClass 把 Pod 和一个运行时处理器(handler)绑定,还可以声明 overhead:运行这个 Pod 本身(沙箱、shim)要额外付出的固定开销。调度、配额和 cgroup 都会把它算进去')

print('== 一:overhead 被写进 Pod,并被调度器计入节点')
a0 = alloc(); k('apply', '-f', '-', input=pod('plain')); k('wait', '--for=condition=Ready', 'pod/plain', '-n', NS, '--timeout=60s'); a1 = alloc()
k('apply', '-f', '-', input=pod('heavy', rc='runc-heavy')); k('wait', '--for=condition=Ready', 'pod/heavy', '-n', NS, '--timeout=60s'); a2 = alloc()
ph = kj('get', 'pod', 'heavy', '-n', NS); pp = kj('get', 'pod', 'plain', '-n', NS)
print(f'  RuntimeClass runc-heavy:handler=runc;overhead.podFixed={{cpu: 250m, memory: 120Mi}}')
print(f'  Pod plain(没写 runtimeClassName):spec.overhead={pp["spec"].get("overhead")};Pod heavy(runtimeClassName: runc-heavy):spec.overhead={ph["spec"].get("overhead")}(RuntimeClass 准入控制器写进去的,容器 requests 都是 100m / 64Mi)')
print(f'  节点 worker 的 Allocated resources(requests):加 plain 前 {a0["cpu"][0]} / {a0["memory"][0]} → 加 plain 后 {a1["cpu"][0]} / {a1["memory"][0]} → 再加 heavy 后 {a2["cpu"][0]} / {a2["memory"][0]}')
print(f'  plain 增加 cpu {int(a1["cpu"][0].rstrip("m")) - int(a0["cpu"][0].rstrip("m"))}m、heavy 增加 cpu {int(a2["cpu"][0].rstrip("m")) - int(a1["cpu"][0].rstrip("m"))}m(= 100m + 250m overhead)')

print('== 二:overhead 进入 Pod 的 cgroup 限制')
def lim(p):
    node, pcg = pod_cgroup(p); node2, ccg, cid = container_cgroup(p, 'c')
    return {'pod.memory.max': int(cgread(node, pcg, 'memory.max')), 'pod.cpu.max': cgread(node, pcg, 'cpu.max'), 'ctr.memory.max': int(cgread(node, ccg, 'memory.max')), 'ctr.cpu.max': cgread(node, ccg, 'cpu.max')}
for nm in ('plain', 'heavy'):
    p = kj('get', 'pod', nm, '-n', NS); l = lim(p); print(f'  {nm}(qosClass={p["status"]["qosClass"]}):Pod 级 memory.max={l["pod.memory.max"] / 1048576:.0f} MiB cpu.max={l["pod.cpu.max"]};容器级 memory.max={l["ctr.memory.max"] / 1048576:.0f} MiB cpu.max={l["ctr.cpu.max"]}')
print('  Pod 级限制 = 容器 limits 之和 + overhead;容器自己的限制不变——overhead 是给沙箱/运行时组件留的空间')

print('== 三:overhead 参与配额和调度')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ResourceQuota\nmetadata: {{name: q, namespace: {NS}}}\nspec:\n  hard: {{requests.cpu: 500m, pods: "10"}}\n')
time.sleep(2); u = kj('get', 'resourcequota', 'q', '-n', NS)['status']['used']; print(f'  命名空间已有 plain + heavy,ResourceQuota requests.cpu 上限 500m,已用 {u.get("requests.cpu")}(plain 100m + heavy 100m + overhead 250m)')
rc, o = k('apply', '-f', '-', input=pod('third', rc='runc-heavy', node=W)); print(f'  再创建一个 heavy 类的 Pod(容器 100m + overhead 250m = 350m,合计会到 800m):退出码 {rc};{short(o, 1, 380)}')
rc, o = k('apply', '-f', '-', input=pod('small')); print(f'  再创建一个普通 Pod(100m,合计 550m 也超了):退出码 {rc};{short(o, 1, 380)}')
k('delete', 'resourcequota', 'q', '-n', NS)
huge = pod('huge', rc='runc-heavy').replace('runc-heavy', 'runc-huge'); k('apply', '-f', '-', input='apiVersion: node.k8s.io/v1\nkind: RuntimeClass\nmetadata: {name: runc-huge}\nhandler: runc\noverhead:\n  podFixed: {cpu: 100, memory: 1Gi}\n')
time.sleep(1); rc, o = k('apply', '-f', '-', input=huge.replace(f'  nodeName: {W}\n', '')); time.sleep(5)
ph2 = kj('get', 'pod', 'huge', '-n', NS); print(f'  overhead 是 100 个 CPU 的 RuntimeClass runc-huge:Pod huge 的 phase={ph2["status"]["phase"]};{[(c["type"], c.get("reason"), c.get("message", "")[:150]) for c in ph2["status"].get("conditions", []) if c["status"] == "False"]}')

print('== 四:RuntimeClass 不存在 / handler 没装')
rc, o = k('apply', '-f', '-', input=pod('missing-rc', rc='nope', node=W)); print(f'  runtimeClassName: nope(没有这个 RuntimeClass 对象):退出码 {rc};{short(o, 1, 300)}')
k('apply', '-f', '-', input=pod('nohandler', rc='no-such-handler')); time.sleep(8)
pn = kj('get', 'pod', 'nohandler', '-n', NS); cs = (pn['status'].get('containerStatuses') or [{}])[0]; print(f'  RuntimeClass 存在但 handler: gvisor-not-installed 节点上没配:phase={pn["status"]["phase"]};{pn["status"].get("reason")};容器状态 {list(cs.get("state", {}).keys())}')
rc, ev = k('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=nohandler'); print(f'  事件:{[re.sub(chr(32) + "+", " ", l)[:260] for l in ev.strip().splitlines()[1:3]]}')
k('delete', 'runtimeclass', 'runc-heavy', 'runc-huge', 'no-such-handler'); k('delete', 'ns', NS, '--wait=false')
