import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k102')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('python:3.12-alpine')
install_metrics_server()
NS = ns('k102')
W = 'kx-main-worker'
def qty(q):
    m = re.match(r'(\d+)(n|u|m|Ki|Mi|Gi)?$', q); v = int(m.group(1)); return v * {'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'Ki': 1024, 'Mi': 1048576, 'Gi': 1073741824, None: 1}[m.group(2)]
def raw(path): rc, o = k('get', '--raw', path, raw=True); return json.loads(o)
print(f'集群 {cn};kubectl top 的数据来自 Metrics API(metrics.k8s.io),它由 metrics-server 实现,再往下是每个节点 kubelet 暴露的资源指标')

print('== 一:kubectl top 与 Metrics API')
rc, o = k('top', 'nodes'); print('  kubectl top nodes:'); [print('    ' + re.sub(r'\s+', ' ', l)) for l in o.strip().splitlines()]
aps = kj('get', 'apiservice', 'v1beta1.metrics.k8s.io'); sp = aps['spec']; print(f'  APIService v1beta1.metrics.k8s.io:service={sp["service"]["namespace"]}/{sp["service"]["name"]};Available={[ (c["type"], c["status"]) for c in aps["status"]["conditions"]]}(聚合 API:apiserver 把 /apis/metrics.k8s.io 的请求转发给 metrics-server)')
j = raw('/apis/metrics.k8s.io/v1beta1/nodes'); n0 = j['items'][0]
print(f'  GET /apis/metrics.k8s.io/v1beta1/nodes 的一项:name={n0["metadata"]["name"].replace("kx-main-", "")};timestamp={n0["timestamp"][11:19]};window={n0["window"]};usage={n0["usage"]}')
print(f'  对应 kubectl top 里的数字:CPU {n0["usage"]["cpu"]} = {qty(n0["usage"]["cpu"]) * 1000:.0f}m;内存 {n0["usage"]["memory"]} = {qty(n0["usage"]["memory"]) / 1048576:.0f}Mi')

print('== 二:数据源——kubelet 的 /metrics/resource,CPU 是累计计数器')
def kub(n=W):
    rc, o = k('get', '--raw', f'/api/v1/nodes/{n}/proxy/metrics/resource', raw=True); return o
o = kub(); names = sorted({l.split('{')[0].split()[0] for l in o.splitlines() if l and not l.startswith('#')}); print(f'  GET /api/v1/nodes/{W.replace("kx-main-", "")}/proxy/metrics/resource 里的指标名:{names}')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: burn, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sh, -c, "while :; do :; done"]\n    resources: {{limits: {{cpu: 300m}}}}\n')
k('wait', '--for=condition=Ready', 'pod/burn', '-n', NS, '--timeout=60s')
def cpu_sec():
    for l in kub().splitlines():
        if l.startswith('container_cpu_usage_seconds_total') and f'pod="burn"' in l: f = l.split(); return float(f[1]), int(f[2]) / 1000
tb = time.time(); v, dt1 = until(lambda: k('top', 'pod', 'burn', '-n', NS, '--no-headers')[0] == 0, 120, 2)
print(f'  burn 创建后 {time.time() - tb + 1:.0f} 秒(从 Ready 起算),kubectl top pod burn 才第一次有数据')
time.sleep(16); (a, ta) = cpu_sec(); time.sleep(20); (b, tb2) = cpu_sec(); dt = tb2 - ta
print(f'  burn 容器的 container_cpu_usage_seconds_total 两次读数:{a:.2f}(采样时刻 …{int(ta) % 1000}s)和 {b:.2f}(…{int(tb2) % 1000}s)——每个读数后面都带着 kubelet 采样的时间戳;累计秒数只增不减;用采样时间戳算间隔 {dt:.1f} 秒 → 平均 CPU = ({b:.2f}-{a:.2f})/{dt:.1f} = {(b - a) / dt * 1000:.0f}m(limit 是 300m)')
rc, o = k('top', 'pod', 'burn', '-n', NS, '--no-headers'); print(f'  同一时间 kubectl top pod burn:{re.sub(chr(32) + "+", " ", o.strip())}(与上面的速率相符)')
print('  metrics-server 做的事:每 15 秒向每个 kubelet 取一次这个累计值,相邻两次相减再除以时间,得到 CPU 用量')

print('== 三:新 Pod 多久能在 top 里看到')
rc, o = k('top', 'pod', 'nope', '-n', NS); print(f'  不存在的 Pod:{o.strip()[:100]}')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: fresh, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'); t0 = time.time()
k('wait', '--for=condition=Ready', 'pod/fresh', '-n', NS, '--timeout=60s'); tready = time.time() - t0
rc, o = k('top', 'pod', 'fresh', '-n', NS); print(f'  fresh 刚 Ready({tready:.1f} 秒)时 kubectl top:退出码 {rc};{o.strip().splitlines()[0][:100]}')
v, dt2 = until(lambda: k('top', 'pod', 'fresh', '-n', NS, '--no-headers')[0] == 0, 120, 1)
print(f'  fresh 从创建到 top 里第一次出现:{time.time() - t0:.0f} 秒(metrics-server 每 15 秒采集一次,新容器要有两次样本才能算出速率)')

print('== 四:内存是 working set,不是 RSS 也不是 cgroup 的 usage')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: mem, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: python:3.12-alpine\n    command: [python, -c, "import time; a = bytearray(80 * 2**20); [a.__setitem__(i, 1) for i in range(0, len(a), 4096)]; f = open(\'/data/f\', \'wb\'); f.write(b\'x\' * (150 * 2**20)); f.flush(); import os; os.fsync(f.fileno()); time.sleep(3600)"]\n    volumeMounts: [{{name: d, mountPath: /data}}]\n  volumes: [{{name: d, emptyDir: {{}}}}]\n')
k('wait', '--for=condition=Ready', 'pod/mem', '-n', NS, '--timeout=60s'); time.sleep(5)
p = kj('get', 'pod', 'mem', '-n', NS); node, cg, cid = container_cgroup(p, 'c')
cur = int(cgread(node, cg, 'memory.current')); st = {l.split()[0]: int(l.split()[1]) for l in cgread(node, cg, 'memory.stat').splitlines()}
ws = cur - st['inactive_file']
print(f'  mem 容器(进程 80 MiB 匿名内存 + 写了 150 MiB 文件的页缓存):cgroup memory.current={cur / 1048576:.0f} MiB;其中 anon={st["anon"] / 1048576:.0f} MiB,file(页缓存)={st["file"] / 1048576:.0f} MiB,inactive_file={st["inactive_file"] / 1048576:.0f} MiB')
print(f'  working set = memory.current − inactive_file = {ws / 1048576:.0f} MiB')
v, dt3 = until(lambda: k('top', 'pod', 'mem', '-n', NS, '--no-headers')[0] == 0, 120, 2); time.sleep(16)
rc, o = k('top', 'pod', 'mem', '-n', NS, '--no-headers'); print(f'  kubectl top pod mem:{re.sub(chr(32) + "+", " ", o.strip())}(与 working set 一致,而不是 memory.current;页缓存里不活跃的部分被扣掉了,kubelet 的节点内存压力驱逐也看 working set,见 k31)')
k('delete', 'ns', NS, '--wait=false')
