import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
import kl
tee('k31')
down('evict')
cn, dt_up = up('evict', cfg=config(workers=1))
load('busybox:1.36', 'python:3.12-alpine')
W = 'kx-evict-worker'
NS = ns('k31')
def avail():
    rc, o = k('get', '--raw', f'/api/v1/nodes/{W}/proxy/stats/summary', raw=True); return json.loads(o)['node']['memory']['availableBytes'] / 2**20
def node_state():
    n = kj('get', 'node', W); c = {x['type']: x['status'] for x in n['status']['conditions']}
    return c.get('MemoryPressure'), [t['key'] + ':' + t['effect'] for t in n['spec'].get('taints', [])]
a0 = avail(); thr = int(a0 - 900)
print(f'集群 {cn}(1 控制面 + 1 工作节点 {W},Kubernetes v1.37.0);kubelet 看到的节点 memory.available = {a0:.0f} MiB')
rc, o = sh('docker', 'exec', W, 'cat', '/var/lib/kubelet/config.yaml', raw=True); cfg = yaml.safe_load(o)
print(f'  默认的 evictionHard:{cfg["evictionHard"]}(kind 把磁盘类阈值都关成了 0%,没有 memory.available);evictionPressureTransitionPeriod={cfg["evictionPressureTransitionPeriod"]}')
def pod(name, mem, res='', idle_wait=True, node=True):
    wait = 'while [ ! -f /tmp/go ]; do sleep 0.2; done; ' if idle_wait else ''
    shcmd = f"{wait}exec python -c 'import time; d = b\"x\" * ({mem} * 2**20); time.sleep(3600)'"
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
{"  nodeName: " + W + chr(10) if node else ""}  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: python:3.12-alpine
    imagePullPolicy: IfNotPresent
    command: [sh, -c, {json.dumps(shcmd)}]
{res}'''
PODS = [('a-besteffort', 400, '', 'BestEffort,将占 400 MiB,没有 requests'),
        ('b-burst-under', 400, '    resources: {requests: {memory: 500Mi}, limits: {memory: 800Mi}}\n', 'Burstable,将占 400 MiB,requests 500 MiB(用量低于 requests)'),
        ('c-burst-over', 300, '    resources: {requests: {memory: 50Mi}, limits: {memory: 800Mi}}\n', 'Burstable,将占 300 MiB,requests 50 MiB(用量超出 requests 250 MiB)'),
        ('d-guaranteed', 300, '    resources: {requests: {memory: 400Mi, cpu: 50m}, limits: {memory: 400Mi, cpu: 50m}}\n', 'Guaranteed,将占 300 MiB,requests = limits = 400 MiB')]

print('== 一:先设好阈值,再让四个已经就绪、统计齐全的 Pod 同时去占内存')
cfg['evictionHard']['memory.available'] = f'{thr}Mi'; cfg['evictionPressureTransitionPeriod'] = '20s'
sh('docker', 'exec', '-i', W, 'sh', '-c', 'cat > /var/lib/kubelet/config.yaml', input=yaml.dump(cfg))
nx(W, 'systemctl restart kubelet'); until(lambda: ko('get', 'node', W, '-o', 'jsonpath={.status.conditions[?(@.type=="Ready")].status}') == 'True', 60); time.sleep(8)
print(f'  把工作节点 kubelet 的 evictionHard.memory.available 设成 {thr}Mi(比当时的可用量少 900 MiB)、evictionPressureTransitionPeriod 设成 20s,重启 kubelet;重启后 MemoryPressure={node_state()[0]}')
for n, m, r, d in PODS: k('apply', '-f', '-', input=pod(n, m, r))
for n, m, r, d in PODS: print(f'  {n:<14} {d}')
until(lambda: all((kj('get', 'pod', n, '-n', NS) or {}).get('status', {}).get('phase') == 'Running' for n, _, _, _ in PODS), 90); time.sleep(20)
for n, m, r, d in PODS:
    rc_, o_ = k('exec', n, '-n', NS, '--', 'touch', '/tmp/go'); assert rc_ == 0, (n, o_)
t0 = time.time()
print(f'  四个 Pod 都在 Running、还没有分配内存时 memory.available = {avail():.0f} MiB(阈值 {thr});同时对四个 Pod 执行 touch /tmp/go,它们各自分配 400 / 400 / 300 / 300 MiB(合计 1400 MiB,会越过阈值)')
timeline = []; seen = {}; pressure_t = None; avail_log = []
while time.time() - t0 < 100:
    ps = {p['metadata']['name']: p for p in kj('get', 'pods', '-n', NS)['items']}
    for n, p in ps.items():
        st = (p['status'].get('phase'), p['status'].get('reason'))
        if seen.get(n) != st: seen[n] = st; timeline.append((time.time() - t0, n, st))
    mp, tn = node_state()
    if mp == 'True' and pressure_t is None and any('memory-pressure' in x for x in tn):
        pressure_t = time.time() - t0; pressure_taints = tn
    if not avail_log or time.time() - t0 - avail_log[-1][0] > 5: avail_log.append((time.time() - t0, avail()))
    if pressure_t and mp != 'True' and time.time() - t0 > pressure_t + 25: break
    time.sleep(1)
print('== 二:驱逐的先后——Pod 状态变化的时间线(T0 = 同时触发分配内存的时刻)')
for t, n, st in timeline:
    if n.startswith('new-'): continue
    if st == ('Running', None) and t < 3: continue
    print(f'  +{t:5.1f}s {n:<14} phase={st[0]} reason={st[1]}')
print('  节点 memory.available 每隔约 5 秒的采样(MiB):' + ', '.join(f'{v:.0f}' for t, v in avail_log) + f'(阈值 {thr})')
print('== 三:被驱逐的 Pod 留下了什么')
for n, m, r, d in PODS:
    p = kj('get', 'pod', n, '-n', NS)
    if p['status'].get('reason') == 'Evicted':
        print(f'  {n}:phase={p["status"]["phase"]} reason={p["status"]["reason"]};STATUS 列={k("get", "pod", n, "-n", NS)[1].strip().splitlines()[-1].split()[2]}')
        print(f'    message={p["status"]["message"][:300]}')
alive = [n for n, m, r, d in PODS if kj('get', 'pod', n, '-n', NS)['status']['phase'] == 'Running']
print(f'  没有被驱逐的(仍在 Running):{alive}')
print('== 四:节点状态——MemoryPressure 条件与污点的时间线')
print(f'  第 {pressure_t:.0f} 秒 MemoryPressure 变成 True,同时节点出现污点 {pressure_taints}' if pressure_t else '  MemoryPressure 一直没有变成 True')
t_clear = None; tt0 = time.time()
while time.time() - tt0 < 60:
    mp, tn = node_state()
    if mp != 'True': t_clear = time.time() - t0; break
    time.sleep(1)
print(f'  最后一次越过阈值大约在第 {timeline[-1][0]:.0f} 秒(最后一次驱逐);MemoryPressure 在第 {t_clear:.0f} 秒回到 False(evictionPressureTransitionPeriod=20s,压力消失后条件还要保持 20 秒);此时 taints={node_state()[1]}' if t_clear else '  60 秒内 MemoryPressure 没有回到 False')
down('evict')
