import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k15')
cn, _ = up('main')
NS = ns('k15')
k('delete', 'clusterrolebinding', 'k15-sched', 'k15-sched-volume', '--ignore-not-found'); k('delete', 'rolebinding', 'k15-sched-auth', '-n', 'kube-system', '--ignore-not-found')
y = f'''
apiVersion: v1
kind: ServiceAccount
metadata: {{name: sched, namespace: {NS}}}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {{name: k15-sched}}
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:kube-scheduler}}
subjects: [{{kind: ServiceAccount, name: sched, namespace: {NS}}}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {{name: k15-sched-volume}}
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:volume-scheduler}}
subjects: [{{kind: ServiceAccount, name: sched, namespace: {NS}}}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {{name: k15-sched-auth, namespace: kube-system}}
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: Role, name: extension-apiserver-authentication-reader}}
subjects: [{{kind: ServiceAccount, name: sched, namespace: {NS}}}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {{name: leases, namespace: {NS}}}
rules: [{{apiGroups: [coordination.k8s.io], resources: [leases], verbs: [create, get, list, watch, update]}}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {{name: leases, namespace: {NS}}}
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: Role, name: leases}}
subjects: [{{kind: ServiceAccount, name: sched, namespace: {NS}}}]
---
apiVersion: v1
kind: ConfigMap
metadata: {{name: cfg, namespace: {NS}}}
data:
  c.yaml: |
    apiVersion: kubescheduler.config.k8s.io/v1
    kind: KubeSchedulerConfiguration
    leaderElection: {{leaderElect: true, leaseDuration: 15s, renewDeadline: 10s, retryPeriod: 2s, resourceLock: leases, resourceNamespace: {NS}, resourceName: k15-sched}}
    profiles: [{{schedulerName: k15-scheduler}}]
'''
rc, o = apply(y); assert rc == 0, o
def pod(n): return f'''apiVersion: v1
kind: Pod
metadata: {{name: {n}, namespace: {NS}}}
spec:
  serviceAccountName: sched
  containers:
  - name: s
    image: registry.k8s.io/kube-scheduler:v1.37.0
    imagePullPolicy: Never
    command: [kube-scheduler, --config=/cfg/c.yaml, --v=2]
    volumeMounts: [{{name: cfg, mountPath: /cfg}}]
  volumes: [{{name: cfg, configMap: {{name: cfg}}}}]
'''

def lease(name='k15-sched', ns_=NS):
    return (kj('get', 'lease', name, '-n', ns_) or {}).get('spec', {})
def holder(): return (lease().get('holderIdentity') or '').split('_')[0]
def ts(s): return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def leader_logs(p):
    rc, o = k('logs', p, '-n', NS, raw=True)
    return [re.sub(r'^\S+\s+\d+\s+', '', l)[:150] for l in o.splitlines() if 'leaderelection.go' in l or 'Leaderelection lost' in l]
print(f'集群 {cn};Lease(coordination.k8s.io)是选主用的锁:holderIdentity 是当前持有者,renewTime 是它最后一次续约,别人要等 leaseDurationSeconds 过期才能抢')

print('== 一:集群自带组件的 Lease——kube-controller-manager 和 kube-scheduler 在 kube-system 里每隔几秒续约一次')
for n in ('kube-controller-manager', 'kube-scheduler'):
    s = lease(n, 'kube-system')
    seen = []; t0 = time.time()
    while time.time() - t0 < 9:
        rt = lease(n, 'kube-system').get('renewTime')
        if rt and (not seen or seen[-1] != rt): seen.append(rt)
        time.sleep(0.4)
    gaps = [round(ts(b) - ts(a), 1) for a, b in zip(seen, seen[1:])]
    print(f'  {n}:holderIdentity={s.get("holderIdentity")} leaseDurationSeconds={s.get("leaseDurationSeconds")} leaseTransitions={s.get("leaseTransitions")};9 秒内观察到 {len(seen)} 次续约,相邻两次 renewTime 间隔 {gaps} 秒')

print('== 二:三个候选者(我们自己跑的 kube-scheduler,只用 Lease k15/k15-sched 选主,调度器名是 k15-scheduler,不影响默认调度器)')
k('apply', '-f', '-', input=pod('sched-a')); until(lambda: holder() == 'sched-a', 60)
k('apply', '-f', '-', input=pod('sched-b')); k('apply', '-f', '-', input=pod('sched-c'))
until(lambda: all(ko('get', 'pod', p, '-n', NS, '-o', 'jsonpath={.status.phase}') == 'Running' for p in ('sched-b', 'sched-c')), 60); time.sleep(6)
s = lease()
print(f'  Lease:holderIdentity={s["holderIdentity"]};leaseDurationSeconds={s["leaseDurationSeconds"]};leaseTransitions={s["leaseTransitions"]};acquireTime={s["acquireTime"]}')
for p in ('sched-a', 'sched-b', 'sched-c'):
    for l in leader_logs(p)[:3]: print(f'    {p} 的日志:{l}')

print('== 三:故障转移——三种方式让 leader 消失,看新 leader 多久接手、Lease 经历了哪些状态')
def states(old, maxs=60):
    """每 50 毫秒读一次 Lease,返回 [(秒, holder, leaseDurationSeconds)](只记变化)和接手的耗时。"""
    t0 = time.time(); seq = []
    while time.time() - t0 < maxs:
        s_ = lease(); h = (s_.get('holderIdentity') or '').split('_')[0]; d_ = s_.get('leaseDurationSeconds')
        if not seq or seq[-1][1:] != (h, d_): seq.append((round(time.time() - t0, 1), h, d_))
        if h not in ('', old): return seq, time.time() - t0
        time.sleep(0.05)
    return seq, None
def show(seq): return ' → '.join(f'[+{t}s holder={h or "(空)"} leaseDuration={d_}]' for t, h, d_ in seq)
def node_pid(pod):
    node = ko('get', 'pod', pod, '-n', NS, '-o', 'jsonpath={.spec.nodeName}')
    rc, o = nx(node, f"pid=$(crictl inspect -o go-template --template '{{{{.info.pid}}}}' $(crictl ps -q --pod $(crictl pods --name {pod} -q | head -1)) ); echo $pid")
    return node, o.strip()
def case(label, action):
    old = holder(); s0 = lease(); age = time.time() - ts(s0['renewTime']); action(old); seq, dt = states(old); s1 = lease()
    print(f'  {label}:原 leader={old}(被动手时离上次续约约 {age:.1f} 秒)')
    print(f'    Lease 状态变化:{show(seq)}')
    print(f'    {"新 leader=" + holder() + ",接手用了 %.1f 秒" % dt if dt is not None else "60 秒内没有新 leader"};leaseTransitions {s0["leaseTransitions"]} → {s1["leaseTransitions"]}')
    return old
def sigkill(old):
    node, pid = node_pid(old); nx(node, f'kill -9 {pid}')
old = case('① 在节点上对 leader 进程 kill -9(没有机会释放租约)', sigkill)
until(lambda: ko('get', 'pod', old, '-n', NS, '-o', 'jsonpath={.status.containerStatuses[0].ready}') == 'true', 60); time.sleep(5)
def force(old): k('delete', 'pod', old, '-n', NS, '--grace-period=0', '--force', '--wait=false')
old = case('② kubectl delete pod --grace-period=0 --force(API 对象立刻删掉,kubelet 仍会终止进程)', force)
k('apply', '-f', '-', input=pod(old)); until(lambda: ko('get', 'pod', old, '-n', NS, '-o', 'jsonpath={.status.phase}') == 'Running', 60); time.sleep(6)
def soft(old): k('delete', 'pod', old, '-n', NS, '--wait=false')
old = case('③ kubectl delete pod(默认宽限期,进程收到 SIGTERM)', soft)

print('== 四:Lease 被别人改写——当前 leader 续约失败后的反应')
cur = holder(); k('apply', '-f', '-', input=pod(cur)) if False else None
rs0 = ko('get', 'pod', cur, '-n', NS, '-o', 'jsonpath={.status.containerStatuses[0].restartCount}')
t0 = time.time()
rc, o = k('patch', 'lease', 'k15-sched', '-n', NS, '--type=merge', '-p', '{"spec":{"holderIdentity":"intruder"}}'); print(f'  把 Lease 的 holderIdentity 改成 intruder(当前 leader 是 {cur}):{o.strip()}')
v, dt = until(lambda: int(ko('get', 'pod', cur, '-n', NS, '-o', 'jsonpath={.status.containerStatuses[0].restartCount}') or 0) > int(rs0 or 0), 60, 0.5)
print(f'  {cur} 的容器重启次数 {rs0} → {ko("get", "pod", cur, "-n", NS, "-o", "jsonpath={.status.containerStatuses[0].restartCount}")}({dt:.1f} 秒后重启:{v})')
rc, o = k('logs', cur, '-n', NS, '--previous', raw=True)
for l in [re.sub(r'^\S+\s+\d+\s+', '', l)[:170] for l in o.splitlines() if 'eader' in l][-4:]: print(f'    {cur} 重启前的日志:{l}')
h0 = lease()['holderIdentity']
v, dt = until(lambda: lease().get('holderIdentity') != h0, 90, 0.3)
print(f'  intruder 一直占着 Lease,直到 {dt:.1f} 秒后 holderIdentity 才变成 {holder() if v else "(90 秒内没变)"}(从我改写 Lease 起算 {time.time() - t0:.1f} 秒);leaseTransitions={lease()["leaseTransitions"]}')
k('delete', 'clusterrolebinding', 'k15-sched', 'k15-sched-volume', '--ignore-not-found'); k('delete', 'rolebinding', 'k15-sched-auth', '-n', 'kube-system', '--ignore-not-found')
rmns(NS)
